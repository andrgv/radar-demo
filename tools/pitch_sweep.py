#!/usr/bin/env python3
"""Measured-geometry pitch sweep for three-receiver GRD3 radar.

Standalone repo-root entrypoint, using existing radar acquisition/FFT/storage.
Raw recordings are immutable; analysis does not write/verify a calibration config.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
import time
import numpy as np
import serial

# Works when invoked as `python tools/pitch_sweep.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radar.config import Config
from radar.acquisition import Source
from radar.background import SpectralBackground
from radar.processing import noise_threshold, range_fft
from radar.storage import Recorder, replay

DEFAULT_PITCHES = [-15.0, -10.0, 0.0, 10.0, 15.0]
TRAIN_PITCHES = {-15.0, 0.0, 15.0}
MIN_FRAMES = 20


def wrap_rad(a):
    return np.angle(np.exp(1j * a))


def rounded_list(a, ndigits=4):
    return np.round(np.asarray(a, dtype=float), ndigits).tolist()


def planned_direction(target_xyz, sensor_xyz, pitch_deg):
    """World right/forward/up => sensor right/forward/up, positive pitch looks up."""
    target = np.asarray(target_xyz, dtype=float)
    sensor = np.asarray(sensor_xyz, dtype=float)
    if target.shape != (3,) or sensor.shape != (3,) or not np.isfinite(target).all() or not np.isfinite(sensor).all():
        raise ValueError('Target and antenna XYZ must be three finite world coordinates')
    v = target - sensor
    distance = float(np.linalg.norm(v))
    if distance <= 0:
        raise ValueError('Target is coincident with antenna')
    x, y, z = v / distance
    theta = np.radians(float(pitch_deg))
    forward = y * np.cos(theta) + z * np.sin(theta)
    up = -y * np.sin(theta) + z * np.cos(theta)
    if forward <= 0:
        raise ValueError('Target behind the pitched antenna')
    return np.array([x, up], dtype=float), distance, float(np.degrees(np.arctan2(up, forward)))


def signature(config, direction, domain='mixed'):
    """Predict 3 complex RX signatures in raw or vendor-matrix-mixed domain."""
    steering = np.exp(2j * np.pi * (config.array_geometry @ np.asarray(direction, dtype=float)))
    if domain == 'mixed':
        return steering
    if domain == 'raw':
        return np.linalg.solve(config.angle_matrix, steering)
    raise ValueError('domain must be mixed or raw')


def predicted_relative_phase(config, direction, domain='mixed'):
    s = signature(config, direction, domain)
    return np.angle(s[1:] * s[0].conjugate())


def validate_plan(plan, config):
    if plan.get('schema') != 1 or plan.get('kind') != 'pitch-rotation-static-target':
        raise ValueError('Unrecognized pitch-sweep plan')
    if not plan.get('target_and_support_fixed_for_target_pass'):
        raise ValueError('Target and support must remain fixed throughout target pass')
    if not plan.get('antenna_position_measured_or_assumed_fixed_center'):
        raise ValueError('Declare antenna motion assumptions in plan')
    poses = plan.get('poses', [])
    if len(poses) < 5 or len({p.get('name') for p in poses}) != len(poses):
        raise ValueError('Need at least five uniquely named poses')
    roles = [p.get('role') for p in poses]
    if roles.count('train') < 3 or roles.count('holdout') < 2:
        raise ValueError('Need >=3 training and >=2 held-out pitch angles')
    train_angles = [float(p['pitch_deg']) for p in poses if p['role'] == 'train']
    if len(set(train_angles)) < 3:
        raise ValueError('Training pitch angles must be distinct')
    if not np.isfinite(float(plan['mount_roll_deg'])):
        raise ValueError('Roll must be finite')
    target = plan['target_xyz_m']
    for p in poses:
        if p.get('role') not in ('train', 'holdout') or not isinstance(p.get('name'), str):
            raise ValueError(f"Bad pose role/name: {p}")
        if not np.isfinite(float(p['pitch_deg'])):
            raise ValueError('Nonfinite pitch angle')
        direction, distance, _ = planned_direction(target, p['antenna_xyz_m'], p['pitch_deg'])
        expected_bin = int(np.argmin(abs(config.ranges-distance)))
        if expected_bin < 2 or expected_bin >= len(config.ranges)-1:
            raise ValueError(f"{p['name']}: expected target range {distance:.3f} m outside usable range bins")
        p['expected_range_bin'] = expected_bin
        p['expected_range_m'] = distance
        p['expected_direction_right_up'] = direction.tolist()
    return plan


def new_plan(config_path, forward, antenna_height, target_height, right, roll):
    if not all(np.isfinite(x) for x in (forward, antenna_height, target_height, right, roll)):
        raise ValueError('All dimensions must be finite')
    if forward <= 0 or antenna_height <= 0 or target_height <= 0:
        raise ValueError('Heights and forward distance must be positive')
    pitches = DEFAULT_PITCHES + [0.0]
    poses = []
    for i, pitch in enumerate(pitches):
        poses.append(dict(name='zero_repeat' if i==len(pitches)-1 else f"pitch_{pitch:+.0f}".replace('+','plus').replace('-','minus'),
                          role='holdout' if pitch not in TRAIN_PITCHES or i==len(pitches)-1 else 'train',
                          pitch_deg=pitch,
                          antenna_xyz_m=[0.0, 0.0, antenna_height],
                          position_note='ASSUMED: antenna center stays fixed while pitched; edit XYZ if not true'))
    plan = dict(schema=1, kind='pitch-rotation-static-target',
                coordinate_frame='world right/forward/up, z above floor; radar yaw 0, positive pitch points upward',
                config_path=str(config_path), mount_roll_deg=roll,
                target_xyz_m=[right, forward, target_height],
                antenna_position_measured_or_assumed_fixed_center=True,
                target_and_support_fixed_for_target_pass=True,
                IMPORTANT='Edit per-pose antenna_xyz_m if mounting translates. Set pitch_deg to MEASURED angle, not intended angle. Never change box/support/target during target pass.',
                poses=poses)
    return plan



def bottle_midpoint_height(support_base_height_m, box_height_m=0.055, bottle_height_m=0.235):
    """World Z of geometric bottle midpoint: base surface + box + half bottle."""
    values=np.asarray([support_base_height_m,box_height_m,bottle_height_m],dtype=float)
    if not np.isfinite(values).all() or np.any(values<0) or bottle_height_m<=0:
        raise ValueError('Support surface, box height and bottle height must be finite and nonnegative')
    return float(values[0]+values[1]+values[2]/2)


def apply_fixed_pivot(plan, pivot_forward_m, pivot_up_m, target_center_height_m,
                      antenna_zero_height_m=None):
    """Derive antenna XYZ from a stationary horizontal bottom-edge pitch pivot.

    World axes: X right, Y forward toward the bottle, Z up. Positive pitch
    lifts the radar boresight (+Y toward +Z). At 0 deg, the measured antenna
    displacement FROM the pivot is (0, pivot_forward_m, pivot_up_m).

    R_x(pitch) sends (Y,Z) -> (Y*cos - Z*sin, Y*sin + Z*cos).
    This changes the antenna position; target stays at constant world XYZ.
    """
    if plan.get('schema') != 1 or plan.get('kind') != 'pitch-rotation-static-target':
        raise ValueError('Expected pitch-sweep plan')
    forward, up, height = map(float, (pivot_forward_m, pivot_up_m, target_center_height_m))
    if not np.isfinite([forward, up, height]).all() or up <= 0 or height <= 0:
        raise ValueError('Pivot offsets must be finite; pivot-up and target height must be positive')
    if antenna_zero_height_m is not None:
        zero_height=float(antenna_zero_height_m)
    else:
        zeros=[p for p in plan['poses'] if p['name']=='pitch_plus0']
        if len(zeros)!=1 or abs(float(zeros[0]['pitch_deg']))>1e-8:
            raise ValueError('Need a 0-degree reference pose or --antenna-zero-height')
        zero_height=float(zeros[0]['antenna_xyz_m'][2])
    if not np.isfinite(zero_height) or zero_height <= 0:
        raise ValueError('Zero-pitch antenna height must be finite and positive')
    out=json.loads(json.dumps(plan))  # do not modify input object
    out['target_xyz_m'][2]=height
    out['pivot_model']={
        'kind':'fixed_world_X_axis_bottom_edge',
        'antenna_minus_pivot_at_zero_pitch_m':[0.0,forward,up],
        'antenna_zero_pitch_xyz_m':[0.0,0.0,zero_height],
        'explanation':'Both coordinates measured at level (zero) pitch; pivot axis stays fixed while antenna rotates; pitch positive boresight up.'
    }
    out['antenna_position_measured_or_assumed_fixed_center']=True
    out['IMPORTANT']='Antenna XYZ computed from a stationary bottom-edge pivot; verify pitch-axis, offsets, absolute zero-pitch height, and absence of pivot slip. The target/box remains stationary.'
    for p in out['poses']:
        angle=np.deg2rad(float(p['pitch_deg']))
        c,si=float(np.cos(angle)),float(np.sin(angle))
        delta_y=forward*(c-1)-up*si
        delta_z=forward*si+up*(c-1)
        p['antenna_xyz_m']=[0.0,float(delta_y),float(zero_height+delta_z)]
        p['position_note']='Computed from measured fixed-pivot offset and this pitch; verify pivot stationary, yaw/roll unchanged'
        for stale in ('expected_range_bin','expected_range_m','expected_direction_right_up'):
            p.pop(stale,None)
    return out


class TransportIntegrityError(RuntimeError):
    """A capture that must not be used for phase calibration."""


TRANSPORT_COUNTERS = ('bad_crc', 'bad_headers', 'gaps', 'restarts', 'discarded_bytes')


def transport_counters(parser):
    return {name: int(getattr(parser, name)) for name in TRANSPORT_COUNTERS}


def start_synchronized_source(config, port, warmup_seconds=1.0):
    """Start like the successful 30-second serial test, not Source(port=...).

    Stop the old stream before resetting input; warm up and discard decoded
    *frames*, not arbitrary bytes of a running packet. Retain the parser's
    partial packet buffer and use counter deltas to exclude warmup errors.
    """
    source = Source(config)
    try:
        source.serial = serial.Serial(port, 2_000_000, timeout=0.1, write_timeout=1)
        source.serial.write(b'c')
        source.serial.flush()
        time.sleep(0.5)
        source.serial.reset_input_buffer()
        source.serial.write(b'B')
        source.serial.flush()

        warmup_valid = 0
        deadline = time.monotonic() + warmup_seconds
        while time.monotonic() < deadline:
            frame = source.read()
            if frame is not None:
                warmup_valid += 1
                if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
                    raise ValueError('Firmware/profile mismatch during startup')
        source.pending.clear()  # never use frames decoded while settling
        startup = transport_counters(source.parser)
        startup['valid_frames'] = warmup_valid
        if warmup_valid < 2:
            raise TransportIntegrityError(f'Radar did not start cleanly: {startup}')
        return source, startup
    except BaseException:
        source.close()
        raise


def _capture_once(path, config, port, seconds, metadata):
    """Read serial continuously in RAM; write files only after stream is stopped.

    A GRD3 capture at 10 Hz for six seconds occupies well below a megabyte.
    This avoids synchronous per-read transport JSON and disk writes that can
    starve a serial receiver on a loaded desktop. Every received byte remains
    available for inspecting rejected captures.
    """
    source = None
    try:
        with Recorder(path, config, metadata) as recorder:
            source, startup = start_synchronized_source(config, port)
            start = transport_counters(source.parser)
            frames = []
            wire = bytearray()
            invalid_frame = None
            deadline = time.monotonic() + seconds
            try:
                # Deliberately match the standalone 30-second test's read path.
                # No Recorder.write or write_transport while serial is live.
                while time.monotonic() < deadline:
                    data = source.serial.read(max(1, min(source.serial.in_waiting, 65536)))
                    if not data:
                        continue
                    wire.extend(data)
                    for frame in source.parser.feed(data):
                        if (frame.profile_id != config.profile_id or
                            frame.adc.shape != (config.chirps, config.samples, 3) or
                            not frame.flags & 1):
                            invalid_frame = 'Wrong radar firmware/profile/ADC shape'
                        if frame.errors or frame.dropped:
                            invalid_frame = 'Device reported dropped frames or errors'
                        frames.append(frame)
                counters = transport_counters(source.parser)
                stats = {name: counters[name] - start[name] for name in TRANSPORT_COUNTERS}
                stats.update(valid_frames=len(frames), startup=startup,
                             wire_bytes=len(wire), capture_strategy='in_memory_buffered')
                parser_for_audit = source.parser
            finally:
                # Stop incoming USB traffic *before* writing to disk.
                source.close()
                source = None

            recorder.write_transport(bytes(wire), parser_for_audit)
            for frame in frames:
                recorder.write(frame)
            (recorder.path/'transport_summary.json').write_text(json.dumps(stats, indent=2))
            if invalid_frame is not None:
                raise TransportIntegrityError(invalid_frame)
            if any(stats[k] for k in ('bad_crc', 'bad_headers', 'gaps', 'restarts')):
                raise TransportIntegrityError(f'Bad serial transport during capture: {stats}')
            if len(frames) < MIN_FRAMES:
                raise TransportIntegrityError(f'Only {len(frames)} valid frames; need >= {MIN_FRAMES}')
            print(f'  Saved {len(frames)} clean frames to {path}')
    finally:
        if source is not None:
            source.close()


def verify_existing_capture(path, config, stage, pose):
    """Safety gate for --resume: never treat corrupt or mismatched files as clean."""
    from radar.protocol import Parser
    path = Path(path)
    try:
        metadata = json.loads((path/'metadata.json').read_text())
        stats = json.loads((path/'transport_summary.json').read_text())
        if metadata.get('stage') != stage or metadata.get('pose') != pose:
            raise ValueError('stage/pose metadata does not match')
        if Config.load(path/'config.json') != config:
            raise ValueError('firmware/config does not match')
        if any(int(stats.get(field, -1)) != 0 for field in
               ('bad_crc', 'bad_headers', 'gaps', 'restarts')):
            raise ValueError('transport errors in capture summary')
        if int(stats.get('valid_frames', 0)) < MIN_FRAMES:
            raise ValueError('insufficient recorded frames')
        parser = Parser()
        count = 0
        for frame in replay(path, parser):
            if (frame.profile_id != config.profile_id or
                frame.adc.shape != (config.chirps, config.samples, 3) or
                not frame.flags & 1 or frame.dropped or frame.errors):
                raise ValueError('invalid frame in stored recording')
            count += 1
        if (count != stats['valid_frames'] or parser.bad_crc or parser.bad_headers or
            parser.gaps or parser.restarts or parser.buffer):
            raise ValueError('recorded file truncated, corrupted, or inconsistent')
        return count
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f'Cannot resume: {path} is not a verified clean capture ({exc}). '
                           'Do not overwrite it; recover or move it aside first.') from exc


def capture(path, config, port, seconds, metadata, retries=2):
    """Retake a bad pose automatically, preserving failed raw attempts."""
    if seconds < 3 or not np.isfinite(seconds):
        raise ValueError('Capture at least 3 seconds per position')
    path = Path(path)
    if retries < 0:
        raise ValueError('retries must be nonnegative')
    if path.exists():
        raise FileExistsError(f'{path} already exists; refusing to overwrite')
    for attempt in range(retries + 1):
        try:
            _capture_once(path, config, port, seconds, metadata)
            return
        except TransportIntegrityError as exc:
            # Do not silently accept any corrupted/partial capture. Preserve it.
            if path.exists():
                failure_number = 1
                failed = path.with_name(f'{path.name}__FAILED_attempt{failure_number}')
                while failed.exists():
                    failure_number += 1
                    failed = path.with_name(f'{path.name}__FAILED_attempt{failure_number}')
                path.rename(failed)
                print(f'  Rejected capture; raw audit preserved: {failed}')
            print(f'  Integrity failure: {exc}')
            if attempt >= retries:
                raise RuntimeError(f'All {retries + 1} captures failed at {path}. '
                                   'Inspect cable/USB stability; previous attempts preserved.') from exc
            print(f'  Retrying the SAME pose, same bottle/support state ({attempt + 2}/{retries + 1})...')
            time.sleep(2)


def do_record(args):
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    config = Config.load(plan['config_path'])
    config = replace(config,mount_roll_deg=float(plan['mount_roll_deg']),
                     verified=False, calibration_id='pitch-experiment-UNVERIFIED').validate()
    validate_plan(plan, config)
    root = Path(args.output)
    resume = getattr(args, 'resume', False)
    if resume:
        if not root.is_dir():
            raise FileNotFoundError(f'Cannot resume missing directory: {root}')
        saved_plan = json.loads((root/'pitch_plan.json').read_text())
        if saved_plan != plan or Config.load(root/'config.json') != config:
            raise ValueError('Cannot resume: existing plan/config differs from supplied plan/config')
        print(f'Resuming existing sweep: {root} (no clean captures overwritten)')
    else:
        if root.exists():
            raise FileExistsError(f'{root} exists; use --resume to continue clean captures')
        root.mkdir(parents=True)
        (root/'pitch_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        config.save(root/'config.json')
    print('\nTWO-PASS PROTOCOL: support and bottle are NOT moved during target pass.')
    print('Pass 1: empty room/support, record all pitch angles with bottle ABSENT.')
    print('Place the bottle ONCE at the marked target location after all backgrounds.')
    print('Pass 2: record the same angles with bottle fixed. Reproduce antenna pose for each pair.')
    print('Positive pitch points UP. Roll fixed at '+str(plan['mount_roll_deg'])+' degrees.')
    print('This method assumes the saved antenna_xyz_m values describe each actual pose.')

    for stage in ('background','target'):
        missing = []
        for pose in plan['poses']:
            capture_path = root/f'{stage}_{pose["name"]}'
            if capture_path.exists():
                n = verify_existing_capture(capture_path, config, stage, pose)
                print(f'  Already clean: {capture_path} ({n} frames)')
            else:
                missing.append(pose)
        if not missing:
            print(f'  {stage.upper()} pass already complete; skipping.')
            continue
        print(f'  {len(missing)} {stage} capture(s) still needed.')
        input('\nPress Enter to START '+stage.upper()+' pass (type Ctrl-C to stop): ')
        for pose in missing:
            xyz = pose['antenna_xyz_m']
            print(f"\n{stage.upper()}: {pose['name']} ({pose['role']}), pitch {pose['pitch_deg']:+.2f} deg")
            print(f"  Antenna WORLD XYZ = {xyz} m; target remains at {plan['target_xyz_m']} m")
            print('  Confirm measured pitch and antenna position match the plan.')
            if stage == 'background':
                prompt='  Bottle ABSENT; support and room ready. Enter, then step away: '
            else:
                prompt='  Bottle FIXED on support; do not move it. Enter, then step away: '
            input(prompt)
            print('  Recording begins in 3 seconds.')
            time.sleep(3)
            capture(root/f'{stage}_{pose["name"]}', config, args.port, args.seconds,
                    dict(label=f'pitch_{stage}',role=pose['role'],pose=pose,
                         stage=stage,scene_id=root.name), retries=args.retries)
    print('\nRaw captures complete. Analyze offline with:')
    print(f'  python tools/pitch_sweep.py analyze {root} --output artifacts/pitch-audit-01')


def pose_measurement(root, p, config, domain):
    folder = root/f'target_{p["name"]}'
    empty_folder = root/f'background_{p["name"]}'
    row = dict(name=p['name'], role=p['role'],pitch_deg=p['pitch_deg'],
               antenna_xyz_m=p['antenna_xyz_m'],expected_range_m=p['expected_range_m'],
               expected_range_bin=p['expected_range_bin'])
    if not (folder/'frames.grd').exists() or not (empty_folder/'frames.grd').exists():
        return {**row, 'accepted':False,'reason':'missing target/background capture'}
    if Config.load(folder/'config.json') != config or Config.load(empty_folder/'config.json') != config:
        raise ValueError('Captured configuration differs from plan at '+p['name'])
    bg = SpectralBackground.from_path(empty_folder, config)
    spec_all = []
    rails = 0
    n_adc = 0
    for frame in replay(folder):
        if frame.profile_id!=config.profile_id or frame.adc.shape!=(config.chirps,config.samples,3) or not frame.flags&1:
            raise ValueError('Invalid raw recording at '+p['name'])
        if frame.errors or frame.dropped:
            raise ValueError('Device errors/drops at '+p['name'])
        rails += int(np.count_nonzero((frame.adc==0)|(frame.adc==65535)))
        n_adc += frame.adc.size
        spec_all.append(bg.subtract(range_fft(frame.adc, config),config))
    if len(spec_all) < MIN_FRAMES:
        return {**row,'accepted':False,'frames':len(spec_all),'reason':'too few frames'}
    raw = np.asarray(spec_all)   # frames, chirps, range, receiver
    bins_power = np.mean(abs(raw)**2,axis=(0,1,3))
    k=p['expected_range_bin']
    contrast = 10*np.log10(max(bins_power[k],1e-12)/max(noise_threshold(bins_power,1)[k],1e-12))
    peak = bool(bins_power[k]>=max(bins_power[k-1],bins_power[k+1]))
    channels = raw[:,:,k,:]
    if domain == 'mixed':
        channels = channels @ config.angle_matrix.T
    cross = np.mean(channels[:,:,1:] * channels[:,:,:1].conj(),axis=(0,1))
    channel_power=np.mean(abs(channels)**2,axis=(0,1))
    coh = abs(cross)/np.sqrt(np.maximum(channel_power[1:]*channel_power[0],1e-20))
    phases = np.angle(cross)
    per_frame = np.mean(channels[:,:,1:]*channels[:,:,:1].conj(),axis=1)
    dev = wrap_rad(np.angle(per_frame)-phases[None,:])
    spread = np.degrees(np.sqrt(np.mean(dev**2,axis=0)))
    raw_bg_power = np.mean(abs(bg.reference[k])**2)
    residual_power = bins_power[k]
    residual_bg_db = 10*np.log10(max(residual_power,1e-12)/max(raw_bg_power,1e-12))
    accepted = bool(min(coh)>=0.90 and contrast>=config.snr_db and peak and rails==0)
    row.update(frames=len(spec_all),phase_deg=rounded_list(np.degrees(phases),3),
               phase_spread_deg=rounded_list(spread,2),
               min_coherence=float(np.min(coh)),
               contrast_db=float(contrast),
               local_peak=peak, clipped_samples=rails,
               residual_over_background_db=float(residual_bg_db),
               accepted=accepted,
               reason='passes fixed quality gate' if accepted else 'weak/incoherent/clipped/not range peak')
    return row


def fit_phase_offsets(rows, config, domain='mixed'):
    accepted_train = [r for r in rows if r['role']=='train' and r.get('accepted')]
    if len(accepted_train)<3:
        raise ValueError(f'Only {len(accepted_train)} accepted training poses; need >=3. No calibration or inference.')
    deltas=[]
    for r in accepted_train:
        pred=predicted_relative_phase(config,r['expected_direction_right_up'],domain)
        meas=np.radians(r['phase_deg'])
        deltas.append(wrap_rad(meas-pred))
    offsets=np.angle(np.mean(np.exp(1j*np.asarray(deltas)),axis=0))
    return offsets


def geometry_model_phases(config, plan, p, trial_z, domain):
    xyz=list(plan['target_xyz_m'])
    xyz[2]=float(trial_z)
    direction,_,_=planned_direction(xyz,p['antenna_xyz_m'],p['pitch_deg'])
    return predicted_relative_phase(config,direction,domain)


def invert_height(config,plan,p,observed_phase,offsets,domain,z_min,z_max):
    heights=np.linspace(z_min,z_max,801)
    phis=np.array([geometry_model_phases(config,plan,p,z,domain) for z in heights])
    errors=np.degrees(wrap_rad(phis+offsets-np.asarray(observed_phase)[None,:]))
    rms=np.sqrt(np.mean(errors**2,axis=1))
    best=int(np.argmin(rms))
    separated=np.flatnonzero(abs(heights-heights[best])>=0.10)
    competitor=int(separated[np.argmin(rms[separated])]) if len(separated) else best
    best_resid=float(rms[best]);second=float(rms[competitor])
    ambiguous=bool(second-best_resid<3.0 or best_resid>10.0 or
                   heights[best]-z_min<0.03 or z_max-heights[best]<0.03)
    return dict(estimated_z_m=float(heights[best]),fit_rms_phase_deg=best_resid,
                competitor_z_m=float(heights[competitor]),
                competitor_rms_phase_deg=second,
                fit_gap_deg=float(second-best_resid),
                ambiguous=ambiguous)


def evaluate_model(rows,plan,config,domain,z_min,z_max):
    pose_map={p['name']:p for p in plan['poses']}
    for r in rows:
        p=pose_map[r['name']]
        dr,dist,elev=planned_direction(plan['target_xyz_m'],p['antenna_xyz_m'],p['pitch_deg'])
        r['expected_direction_right_up']=dr.tolist()
        r['true_sensor_elevation_deg']=elev
    result=dict(domain=domain,offsets_deg=None,train_accepted=0,heldout_accepted=0,
                heldout_phase_mae_deg=None,heldout_height_mae_m=None,reason=None,poses=rows)
    try:
        offsets=fit_phase_offsets(rows,config,domain)
    except ValueError as ex:
        result['reason']=str(ex)
        return result
    result['offsets_deg']=rounded_list(np.degrees(offsets),3)
    result['train_accepted']=sum(r['accepted'] for r in rows if r['role']=='train')
    holdout_errors=[];height_errors=[]
    for r in rows:
        if not r.get('accepted'):
            continue
        p=pose_map[r['name']]
        observed=np.radians(r['phase_deg'])
        pred=predicted_relative_phase(config,r['expected_direction_right_up'],domain)
        residual_deg=rounded_list(np.degrees(wrap_rad(observed-(pred+offsets))),3)
        r['phase_residual_deg']=residual_deg
        if p['role'] == 'holdout':
            inv=invert_height(config,plan,p,observed,offsets,domain,z_min,z_max)
            r.update(inv)
            r['height_error_m']=float(inv['estimated_z_m']-plan['target_xyz_m'][2])
            holdout_errors.append(residual_deg)
            if not inv['ambiguous']:
                height_errors.append(abs(r['height_error_m']))
    result['heldout_accepted']=len(holdout_errors)
    if holdout_errors:
        result['heldout_phase_mae_deg']=rounded_list(np.mean(np.abs(holdout_errors),axis=0),3)
    if height_errors:
        result['heldout_height_mae_m']=float(np.mean(height_errors))
    return result



def export_unverified_pilot(config, model, path):
    """Opt-in experimental row-phase adjustment; never marks geometry verified."""
    if model['domain'] != 'mixed' or model['reason'] is not None:
        raise ValueError('Pilot export requires a successful mixed-domain physical fit')
    holds=[r for r in model['poses'] if r['role']=='holdout']
    if (len(holds)<2 or not all(r.get('accepted') and 'estimated_z_m' in r and not r['ambiguous'] for r in holds)):
        raise ValueError('Pilot export blocked: not all held-out pitch captures are valid and unambiguous')
    if any(max(abs(float(v)) for v in r['phase_residual_deg'])>5.0 or
           abs(r['height_error_m'])>.05 for r in holds):
        raise ValueError('Pilot export blocked: held-out phase >5 deg or height error >5 cm')
    path=Path(path)
    if path.exists():
        raise FileExistsError(f'{path} exists; refusing to overwrite pilot configuration')
    offsets=np.radians(model['offsets_deg'])
    correction=np.diag([1.0,np.exp(-1j*offsets[0]),np.exp(-1j*offsets[1])])
    new_matrix=correction@config.angle_matrix
    pilot=replace(config,angle_matrix_real=new_matrix.real.tolist(),
                  angle_matrix_imag=new_matrix.imag.tolist(),verified=False,
                  calibration_id='pitch-model-phase-pilot-UNVERIFIED')
    pilot.validate()
    path.parent.mkdir(parents=True,exist_ok=True)
    pilot.save(path)
    return path

def make_plots(report,output):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib unavailable; JSON summary still written')
        return
    model=report['model']
    rows=model['poses']
    fig,ax=plt.subplots(2,1,figsize=(9,8),sharex=True,layout='constrained')
    for ch in range(2):
        for role,mark in [('train','o'),('holdout','s')]:
            subset=[r for r in rows if r['role']==role and r.get('accepted')]
            ax[ch].scatter([r['pitch_deg'] for r in subset],[r['phase_residual_deg'][ch] for r in subset],
                           marker=mark,label=role)
        for r in rows:
            if not r.get('accepted'):
                ax[ch].scatter(r['pitch_deg'],0,marker='x',color='gray')
        ax[ch].axhline(0,linewidth=1,color='gray')
        ax[ch].set_ylabel(f'RX{ch+2} phase residual (deg)')
        ax[ch].grid(alpha=.25)
        ax[ch].legend()
    ax[-1].set_xlabel('Measured antenna pitch (deg), positive = nose up')
    fig.suptitle('Physical phase model vs measured pose; rejected poses marked x at zero for location only')
    fig.savefig(output/'phase_vs_pitch.png',dpi=150)
    plt.close(fig)
    held=[r for r in rows if r['role']=='holdout' and r.get('accepted')]
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    for idx,r in enumerate(held):
        c='tab:red' if r['ambiguous'] else 'tab:blue'
        ax.scatter(idx,r['estimated_z_m'],color=c,marker='o')
        ax.text(idx,r['estimated_z_m']+0.02, f"{r['fit_rms_phase_deg']:.1f}° {'ambiguous' if r['ambiguous'] else ''}",ha='center',fontsize=9)
    ax.axhline(report['plan']['target_xyz_m'][2],color='black',linestyle='--',label='Measured bottle-center height')
    ax.set_xticks(range(len(held)),[r['name'] for r in held],rotation=20)
    ax.set_ylabel('World target height (m)')
    ax.grid(alpha=.25);ax.legend()
    fig.savefig(output/'height_inversion.png',dpi=150)
    plt.close(fig)


def do_analyze(args):
    root=Path(args.recording)
    plan=json.loads((root/'pitch_plan.json').read_text())
    config=Config.load(root/'config.json')
    validate_plan(plan,config)
    if not args.z_min < args.z_max:
        raise ValueError('z-min must be below z-max')
    rows=[pose_measurement(root,p,config,args.domain) for p in plan['poses']]
    model=evaluate_model(rows,plan,config,args.domain,args.z_min,args.z_max)
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    result=dict(schema=1,kind='pitch-physical-model-audit',synthetic=False,
                model=model,plan=plan,calibration_exported=False,
                notes='Only training pitches fit static RX phase offsets. Held-out angles test same known-height target. This does NOT certify independent unknown-height generalization, multipath rejection, or robot use. No calibration config written.')
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    for r in model['poses']:
        if r.get('accepted'):
            msg=(f"{r['name']:15s} {r['role']:7s} PASS  contrast={r['contrast_db']:5.1f} dB  "
                 f"coh={r['min_coherence']:.2f}")
            if 'phase_residual_deg' in r:
                msg+=f"   phase error RX2/RX3={r['phase_residual_deg']} deg"
            if 'estimated_z_m' in r:
                msg+=f"   inferred z={r['estimated_z_m']:+.3f} m {'AMBIGUOUS' if r['ambiguous'] else 'candidate'}"
        else:
            msg=f"{r['name']:15s} {r['role']:7s} FAIL  {r['reason']}"
        print(msg)
    if model['reason']:
        print('NO FIT:',model['reason'])
    else:
        print(f"TRAIN-only receiver phase offsets: {model['offsets_deg']} deg")
        print(f"Accepted held-out poses: {model['heldout_accepted']}")
        print(f"Held-out RX2/RX3 phase MAE: {model['heldout_phase_mae_deg']} deg")
        print(f"Unambiguous held-out height MAE (if any): {model['heldout_height_mae_m']}")
        make_plots(result,output)
        if args.export_pilot:
            path=export_unverified_pilot(config,model,args.export_pilot)
            print('Saved UNVERIFIED pilot only:',path)
    print('Saved:',output/'summary.json')
    print('Experimental phase audit only; original recordings/configs unchanged; physical 3D accuracy NOT certified')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('init',help='Make an editable plan BEFORE recording')
    i.add_argument('--output',required=True)
    i.add_argument('--config',default='configs/qualification-hpf350.json')
    i.add_argument('--forward',type=float,required=True,help='Target forward coordinate (m), antenna nominal y=0')
    i.add_argument('--antenna-height',type=float,required=True)
    i.add_argument('--target-center-height',type=float,required=True)
    i.add_argument('--target-right',type=float,default=0)
    i.add_argument('--mount-roll',type=float,default=90)
    pivot=sub.add_parser('pivot',help='Correct plan for bottom-edge hinge translation and real box height')
    pivot.add_argument('--plan',required=True,help='Existing init plan (left unchanged)')
    pivot.add_argument('--output',required=True,help='New corrected plan, refuses overwrite')
    target_group=pivot.add_mutually_exclusive_group(required=True)
    target_group.add_argument('--target-center-height',type=float,
                              help='Measured absolute bottle-center height above floor in meters')
    target_group.add_argument('--support-base-height',type=float,
                              help='Height of surface the flat box RESTS ON, above floor (m); 0 if floor, tabletop height if on table')
    pivot.add_argument('--box-height',type=float,default=0.055,
                       help='Actual vertical thickness of box lying flat, meters (default 0.055)')
    pivot.add_argument('--bottle-height',type=float,default=0.235,
                       help='Actual bottle height in meters (default 0.235)')
    pivot.add_argument('--pivot-up-cm',type=float,required=True,
                       help='At zero pitch, vertical distance from stationary bottom hinge to antenna package center, centimeters')
    pivot.add_argument('--pivot-forward-cm',type=float,required=True,
                       help='At zero pitch, antenna position FORWARD of hinge (toward bottle), signed centimeters')
    pivot.add_argument('--antenna-zero-height',type=float,
                       help='Antenna-package center height above floor at 0 degree pitch, in meters; default original plan value')
    r=sub.add_parser('record',help='Capture empty pass, then fixed-target pass')
    r.add_argument('--plan',required=True)
    r.add_argument('--output',required=True)
    r.add_argument('--port',required=True)
    r.add_argument('--seconds',type=float,default=6)
    r.add_argument('--retries',type=int,default=2,help='Extra attempts for a corrupt/missing-frame pose (default 2); failed raw attempts retained')
    r.add_argument('--resume',action='store_true',help='Continue an existing sweep and verify/skip clean captures; never overwrites data')
    d=sub.add_parser('check',help='Print target geometry and bins; no hardware')
    d.add_argument('--plan',required=True)
    a=sub.add_parser('analyze',help='Analyze saved raw data; never writes calibration')
    a.add_argument('recording');a.add_argument('--output',required=True)
    a.add_argument('--domain',choices=['mixed','raw'],default='mixed')
    a.add_argument('--z-min',type=float,default=0.0)
    a.add_argument('--z-max',type=float,default=1.5)
    a.add_argument('--export-pilot',help='OPTIONAL: save separate UNVERIFIED phase pilot only if all heldout tests pass')
    args=p.parse_args(argv)
    if args.command == 'init':
        path=Path(args.output)
        if path.exists():
            raise FileExistsError(f'{path} exists; refusing to overwrite')
        config=Config.load(args.config)
        plan=new_plan(args.config,args.forward,args.antenna_height,
                      args.target_center_height,args.target_right,args.mount_roll)
        cfg=replace(config,mount_roll_deg=plan['mount_roll_deg']).validate()
        validate_plan(plan,cfg)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(plan,indent=2)+'\n')
        print('Saved plan:',path)
        print('IMPORTANT: edit actual antenna_xyz_m at every pitch if pivot shifts; adjust measured pitch_deg.')
        print(f'Check first: python tools/pitch_sweep.py check --plan {path}')
    elif args.command=='pivot':
        original=json.loads(Path(args.plan).read_text(encoding='utf-8'))
        output=Path(args.output)
        if output.exists():
            raise FileExistsError(f'{output} exists; original/previous plan must not be overwritten')
        target_z=(args.target_center_height if args.target_center_height is not None else
                  bottle_midpoint_height(args.support_base_height,args.box_height,args.bottle_height))
        corrected=apply_fixed_pivot(original,args.pivot_forward_cm/100.,args.pivot_up_cm/100.,
                                    target_z,args.antenna_zero_height)
        cfg=replace(Config.load(corrected['config_path']),mount_roll_deg=corrected['mount_roll_deg']).validate()
        validate_plan(corrected,cfg)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(corrected,indent=2)+'\n',encoding='utf-8')
        print(f'Saved bottom-edge-pivot-corrected plan: {output} (original unchanged)')
        print('Reference zero-pitch antenna height:',corrected['pivot_model']['antenna_zero_pitch_xyz_m'][2],'m')
        print('Target bottle midpoint above floor:',corrected['target_xyz_m'][2],'m')
        print('IMPORTANT: pitch angles, hinge offsets, and zero-pitch antenna height MUST be physically measured.')
        print(f'Check: python tools/pitch_sweep.py check --plan {output}')
    elif args.command=='check':
        plan=json.loads(Path(args.plan).read_text())
        cfg=replace(Config.load(plan['config_path']),mount_roll_deg=plan['mount_roll_deg']).validate()
        validate_plan(plan,cfg)
        print('Target WORLD XYZ:',plan['target_xyz_m'],'roll=',plan['mount_roll_deg'])
        for pose in plan['poses']:
            direction,distance,elev=planned_direction(plan['target_xyz_m'],pose['antenna_xyz_m'],pose['pitch_deg'])
            print(f"{pose['name']:15s} {pose['role']:7s} pitch={pose['pitch_deg']:+5.1f}° "
                  f"target sensor elev={elev:+6.2f}° range={distance:.3f} m "
                  f"bin={pose['expected_range_bin']} antenna XYZ={pose['antenna_xyz_m']}")
    elif args.command=='record':
        do_record(args)
    else:
        do_analyze(args)


if __name__=='__main__':
    main()
