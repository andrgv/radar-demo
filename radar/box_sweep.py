"""Measured-height, paired-background angular calibration of a 3-RX radar.

Run: python -m radar.box_sweep record OUTPUT --port /dev/ttyACM0 \
         --config configs/qualification-hpf350.json --distance 2.0
     python -m radar.box_sweep calibrate OUTPUT --output configs/box-angle.json

This intentionally DOES NOT use radar.sweep's equal/zero-centered vertical offsets.
Every support arrangement receives an empty background with the support in place.
The antenna and bottle must remain upright and fixed during each recording.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import time
import uuid

import numpy as np

# All heights measured vertically from the floor, in metres.
DEFAULT_ANTENNA_HEIGHT_M = 0.34
DEFAULT_BOTTLE_HEIGHT_M = 0.235
DEFAULT_BOX_LONG_M = 0.275
DEFAULT_BOX_THIN_M = 0.055


class CalibrationRejected(ValueError):
    pass


def _direction(xyz):
    xyz = np.asarray(xyz, float)
    distance = np.linalg.norm(xyz)
    if not np.isfinite(distance) or distance <= 0 or xyz[1] <= 0:
        raise ValueError('Invalid bottle center position')
    return (xyz[[0, 2]] / distance).tolist()


def _coords(right, forward, support_h, antenna_h, bottle_h):
    return [float(right), float(forward), float(support_h + bottle_h / 2 - antenna_h)]


def make_poses(*, distance=2.0, horizontal_offset=0.30,
               antenna_height=DEFAULT_ANTENNA_HEIGHT_M,
               bottle_height=DEFAULT_BOTTLE_HEIGHT_M,
               box_long=DEFAULT_BOX_LONG_M, box_thin=DEFAULT_BOX_THIN_M):
    """10 independent stationary captures: five training and five holdout.

    Training reference is TWO FLAT BOXES, not an impossible zero-height center.
    'Up/down' are names relative to the training reference, not necessarily
    relative to the radar boresight. Actual coordinates take precedence.
    """
    values = (distance, horizontal_offset, antenna_height, bottle_height, box_long, box_thin)
    if not np.all(np.isfinite(values)) or any(v <= 0 for v in values):
        raise ValueError('Distance, horizontal offset and dimensions must be positive and finite')
    if horizontal_offset >= distance:
        raise ValueError('Horizontal offset must be smaller than forward distance')
    supports = {
        'none': (0.0, 'no boxes'),
        'one_flat': (box_thin, 'one box flat (5.5 cm high)'),
        'two_flat': (2 * box_thin, 'two boxes stacked flat (11 cm high)'),
        'one_upright': (box_long, 'one box upright (27.5 cm high)'),
        'upright_plus_flat': (box_long + box_thin, 'one upright + one flat (33 cm high)'),
    }
    # Trial scenes are all independently background-subtracted. Support can be
    # shifted horizontally between poses, as long as it is identical within pair.
    plan = [
        ('center', 0.0, 'two_flat', True),
        ('left', -horizontal_offset, 'two_flat', True),
        ('right', horizontal_offset, 'two_flat', True),
        ('up', 0.0, 'upright_plus_flat', True),
        ('down', 0.0, 'none', True),
        ('check_right', horizontal_offset / 2, 'two_flat', False),
        ('check_left', -horizontal_offset / 2, 'two_flat', False),
        ('check_up', 0.0, 'one_upright', False),
        ('check_down', 0.0, 'one_flat', False),
        ('center_repeat', 0.0, 'two_flat', False),
    ]
    poses = []
    for name, right, support, fit in plan:
        height, description = supports[support]
        xyz = _coords(right, distance, height, antenna_height, bottle_height)
        poses.append({
            'name': name, 'fit': fit, 'support': support,
            'support_description': description,
            'support_height_m': height,
            'bottle_center_height_m': height + bottle_height / 2,
            'xyz_m': xyz,
        })
    return poses


def _capture(path, config, port, seconds, metadata, background=None):
    from .acquisition import Source
    from .storage import Recorder
    from .processing import Processor
    if background is not None:
        processor = Processor(config, background=background)
    else:
        processor = None
    # The source starts only after the operator has cleared the scene.
    print('Recording begins in 3 seconds; step away.')
    time.sleep(3)
    source = Source(config, port=port)
    try:
        with Recorder(path, config, metadata) as recorder:
            source.transport_recorder = recorder
            if background is not None:
                background.save(recorder.path / 'spectral-background.npz')
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                frame = source.read()
                if frame is None:
                    continue
                if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
                    raise ValueError(f'Firmware/frame mismatch in {path}: '
                                     f'profile={frame.profile_id:#x}, adc={frame.adc.shape}')
                if not frame.flags & 1:
                    raise ValueError(f'Frame lacks raw ADC flag in {path}')
                recorder.write(frame, processor.process(frame) if processor else None)
            count = recorder.count
    finally:
        source.close()
    if count < 10:
        raise ValueError(f'Only {count} frames in {path}; keep partial recording and retry with a new directory')
    print(f'  Saved {count} frames in {path}')


def record(root, config, port, *, distance=2.0, horizontal_offset=0.30,
           antenna_height=DEFAULT_ANTENNA_HEIGHT_M,
           bottle_height=DEFAULT_BOTTLE_HEIGHT_M,
           box_long=DEFAULT_BOX_LONG_M, box_thin=DEFAULT_BOX_THIN_M, seconds=5):
    from .background import SpectralBackground
    if not np.isfinite(seconds) or seconds < 2:
        raise ValueError('Record at least 2 seconds per scene')
    poses = make_poses(distance=distance, horizontal_offset=horizontal_offset,
                       antenna_height=antenna_height, bottle_height=bottle_height,
                       box_long=box_long, box_thin=box_thin)
    for pose in poses:
        rng = np.linalg.norm(pose['xyz_m'])
        if not config.ranges[2] <= rng <= config.ranges[-2]:
            raise ValueError(f"{pose['name']}: expected range {rng:.2f} m outside valid FFT bins")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    manifest = {
        'schema': 2, 'kind': 'measured-height-paired-background',
        'profile_id': config.profile_id, 'synthetic': False, 'handheld': False,
        'coordinate_frame': '+x right, +y forward, +z up (from behind radar)',
        'dimensions_m': {'antenna_above_floor': antenna_height, 'bottle_height': bottle_height,
                         'box_long': box_long, 'box_thin': box_thin},
        'distance_convention': 'antenna to bottle center projected forward along radar boresight',
        'center_model': 'geometric bottle midpoint; scattering center may differ',
        'horizontal_offset_m': horizontal_offset, 'seconds_per_capture': seconds,
        'paired_background': True, 'poses': poses,
    }
    (root / 'sweep.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    config.save(root / 'config.json')
    print('\nFixed antenna height: {:.1f} cm. Bottle is ALWAYS upright.'.format(antenna_height * 100))
    print('Keep the radar position/pointing unchanged. Measure {:.2f} m FORWARD to bottle center.'.format(distance))
    print('Right/left from BEHIND the radar. Keep boxes absolutely still within each empty/target pair.')
    print('Move the supports between positions if necessary; each pose has its OWN empty background.')
    print('IMPORTANT: No hands/body near bottle during capture. Only use stable box arrangements.')
    for i, pose in enumerate(poses, 1):
        x, y, z = pose['xyz_m']
        print(f"\n[{i}/{len(poses)}] {pose['name']} ({'TRAIN' if pose['fit'] else 'HOLDOUT'})")
        print(f"  Support: {pose['support_description']}; bottle center {pose['bottle_center_height_m']*100:.2f} cm above floor")
        print(f'  Bottle center: right={x*100:+.1f} cm, forward={y:.2f} m, height offset={z*100:+.2f} cm')
        input('  REMOVE BOTTLE, leave boxes in exact final position. Enter to record empty background: ')
        bg_dir = root / f"background_{pose['name']}"
        _capture(bg_dir, config, port, seconds,
                 {'label': 'calibration_background', 'sweep_pose': pose, 'scene_id': root.name})
        background = SpectralBackground.from_path(bg_dir, config)
        input('  Now PLACE BOTTLE upright at measured center. Step away, then Enter to record target: ')
        _capture(root / pose['name'], config, port, seconds,
                 {'label': 'calibration', 'sweep_pose': pose, 'scene_id': root.name,
                  'background_method': 'matched_per_pose_spectrum',
                  'background_source': f'../background_{pose["name"]}'}, background=background)
    report = analyze(root)
    print('\nSaved raw recordings and analysis in:', root)
    return report


def _wrap(rad):
    return np.angle(np.exp(1j * np.asarray(rad)))


def analyze(root):
    from .config import Config
    from .background import SpectralBackground
    from .storage import replay
    from .processing import range_fft, noise_threshold
    root = Path(root)
    manifest = json.loads((root / 'sweep.json').read_text(encoding='utf-8'))
    if manifest.get('kind') != 'measured-height-paired-background':
        raise ValueError('This is not a measured-height paired-background sweep')
    config = Config.load(root / 'config.json')
    neutral = replace(config, gains_real=[1, 1, 1], gains_imag=[0, 0, 0])
    rows = []
    for pose in manifest['poses']:
        bg_dir, target_dir = root / f"background_{pose['name']}", root / pose['name']
        if not (bg_dir / 'frames.grd').exists() or not (target_dir / 'frames.grd').exists():
            rows.append({**pose, 'accepted': False, 'reason': 'recording missing'})
            continue
        if Config.load(bg_dir / 'config.json') != config or Config.load(target_dir / 'config.json') != config:
            raise ValueError(f"Configuration mismatch at {pose['name']}")
        background = SpectralBackground.from_path(bg_dir, neutral)
        xyz = np.asarray(pose['xyz_m'], float)
        rng = float(np.linalg.norm(xyz))
        bin_idx = int(np.argmin(abs(config.ranges - rng)))
        if not 2 <= bin_idx < len(config.ranges) - 1:
            raise ValueError(f"{pose['name']}: expected range bin invalid")
        spectra = []
        for frame in replay(target_dir):
            if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
                raise ValueError(f"Frame/config mismatch at {pose['name']}")
            spectra.append(background.subtract(range_fft(frame.adc, neutral), neutral))
        if len(spectra) < 10:
            rows.append({**pose, 'accepted': False, 'reason': 'fewer than ten frames'})
            continue
        spectra = np.asarray(spectra)
        power = np.mean(abs(spectra) ** 2, axis=(0, 1, 3))
        channels = spectra[:, :, bin_idx].reshape(-1, 3)
        channel_power = np.mean(abs(channels) ** 2, axis=0)
        cross = np.mean(channels * channels[:, :1].conj(), axis=0)
        coherence = abs(cross) / np.sqrt(np.maximum(channel_power * channel_power[0], 1e-20))
        contrast = float(10 * np.log10(max(power[bin_idx], 1e-12) /
                                      max(noise_threshold(power, 1)[bin_idx], 1e-12)))
        local_peak = bool(power[bin_idx] >= max(power[bin_idx - 1], power[bin_idx + 1]))
        accepted = bool(np.min(coherence) >= .90 and contrast >= config.snr_db and local_peak)
        u = np.asarray(_direction(xyz))
        rows.append({**pose,
            'frames': len(spectra), 'expected_range_m': rng, 'range_bin': bin_idx,
            'expected_azimuth_deg': float(np.degrees(np.arctan2(xyz[0], xyz[1]))),
            'expected_elevation_deg': float(np.degrees(np.arcsin(xyz[2] / rng))),
            'direction_right_up': u.tolist(),
            'relative_phase_deg': np.degrees(np.angle(cross[1:] * cross[0].conj())).tolist(),
            'min_coherence': float(np.clip(np.min(coherence), 0, 1)),
            'local_contrast_db': contrast, 'local_peak': local_peak,
            'accepted': accepted,
            'reason': 'passes reference checks' if accepted else 'weak, incoherent or not a local peak'})
    report = {'schema': 2, 'kind': 'measured-height-paired-background',
              'synthetic': False, 'handheld': False, 'poses': rows,
              'accepted_count': sum(bool(p.get('accepted')) for p in rows),
              'total_poses': len(rows), 'calibration_saved': False,
              'limitations': 'Geometric bottle midpoint approximates RF scattering center. '
                             'Paired background does not remove multipath or floor effects.'}
    (root / 'sweep-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for row in rows:
        note = 'PASS' if row['accepted'] else 'FAIL'
        detail = f"coh={row['min_coherence']:.2f}, contrast={row['local_contrast_db']:.1f} dB" if 'min_coherence' in row else row['reason']
        print(f"  {note:4} {row['name']:14} {detail}")
    print(f"Accepted {report['accepted_count']}/{len(rows)}. Report: {root / 'sweep-report.json'}")
    return report


def _angle_error_degrees(estimated_u, actual_u):
    a = np.asarray(estimated_u, float)
    b = np.asarray(actual_u, float)
    if np.any(~np.isfinite(a)) or float(a @ a) >= 1:
        return None
    aa = np.array([a[0], np.sqrt(1 - a @ a), a[1]])
    bb = np.array([b[0], np.sqrt(1 - b @ b), b[1]])
    return float(np.degrees(np.arccos(np.clip(aa @ bb, -1, 1))))


def fit(report, config, *, mode='physical', max_heldout_error_deg=7.0,
        max_return_error_deg=5.0, max_baseline_delta=0.12):
    """Return (calibrated config, diagnostics), refusing unsupported evidence."""
    if mode not in ('physical', 'empirical'):
        raise ValueError('mode must be physical or empirical')
    if report.get('synthetic') or report.get('handheld'):
        raise CalibrationRejected('Synthetic or handheld captures cannot certify calibration')
    rows = {p['name']: p for p in report['poses']}
    fit_names = ('center', 'left', 'right', 'up', 'down')
    holdout_names = ('check_right', 'check_left', 'check_up', 'check_down', 'center_repeat')
    missing = [n for n in fit_names + holdout_names if n not in rows]
    if missing:
        raise CalibrationRejected('Missing poses: ' + ', '.join(missing))
    bad = [n for n in fit_names + holdout_names if not rows[n].get('accepted')]
    if bad:
        raise CalibrationRejected('Failed target-quality gates: ' + ', '.join(bad))
    ref = rows['center']
    u_ref = np.asarray(ref['direction_right_up'], float)
    phase_ref = np.radians(np.asarray(ref['relative_phase_deg'], float))
    training = [rows[n] for n in fit_names if n != 'center']
    delta_u = np.vstack([np.asarray(p['direction_right_up'], float) - u_ref for p in training])
    delta_phase = np.vstack([_wrap(np.radians(p['relative_phase_deg']) - phase_ref)
                             for p in training])
    if np.linalg.matrix_rank(delta_u) != 2:
        raise CalibrationRejected('Insufficient independent horizontal and vertical offsets')
    fitted = np.linalg.lstsq(delta_u, delta_phase / (2 * np.pi), rcond=None)[0].T
    train_residual = _wrap(delta_phase - 2 * np.pi * (delta_u @ fitted.T))
    train_max_deg = float(np.max(abs(np.degrees(train_residual))))
    if train_max_deg > 10:
        raise CalibrationRejected(f'Nonlinear/unstable training phase response ({train_max_deg:.1f} deg residual)')
    nominal = config.array_geometry[1:] - config.array_geometry[0]
    delta = float(np.max(abs(fitted - nominal)))
    if mode == 'physical':
        if delta > max_baseline_delta:
            raise CalibrationRejected(f'Observed baselines differ from nominal geometry by {delta:.3f} wavelengths '
                                      f'(limit {max_baseline_delta:.3f}). Check mounting, RX sign/order, multipath.')
        active = nominal
    else:
        lengths = np.linalg.norm(fitted, axis=1)
        if np.any((lengths < .3) | (lengths > .7)) or abs(np.linalg.det(fitted)) < .08:
            raise CalibrationRejected('Empirical baselines physically implausible or rank-deficient')
        active = fitted
    # Reference pose is BELOW antenna centerline: subtract the expected phase at
    # this actual direction, rather than blindly zeroing its raw channel phase.
    intercept = _wrap(phase_ref - 2 * np.pi * (active @ u_ref))
    measurements = []
    for n in fit_names + holdout_names:
        p = rows[n]
        observed = np.radians(np.asarray(p['relative_phase_deg'], float))
        u_est = np.linalg.solve(active, _wrap(observed - intercept) / (2 * np.pi))
        err = _angle_error_degrees(u_est, p['direction_right_up'])
        measurements.append({'pose': n, 'role': 'fit' if n in fit_names else 'holdout',
                             'expected_azimuth_deg': p['expected_azimuth_deg'],
                             'expected_elevation_deg': p['expected_elevation_deg'],
                             'direction_error_deg': err})
    heldout = [m for m in measurements if m['role'] == 'holdout' and m['pose'] != 'center_repeat']
    heldout_errors = [m['direction_error_deg'] for m in heldout]
    repeat_error = next(m['direction_error_deg'] for m in measurements if m['pose'] == 'center_repeat')
    if any(v is None for v in [*heldout_errors, repeat_error]):
        raise CalibrationRejected('At least one direction estimate outside forward hemisphere')
    maximum = float(max(heldout_errors))
    rms = float(np.sqrt(np.mean(np.square(heldout_errors))))
    if maximum > max_heldout_error_deg or repeat_error > max_return_error_deg:
        raise CalibrationRejected(f'Holdout failed: max error={maximum:.2f} deg '
                                  f'(limit {max_heldout_error_deg}), repeat={repeat_error:.2f} deg '
                                  f'(limit {max_return_error_deg})')
    gains = np.r_[1. + 0.j, np.exp(-1j * intercept)]
    if mode == 'physical':
        calibrated = replace(config, angle_matrix_real=None, angle_matrix_imag=None,
                             gains_real=gains.real.tolist(), gains_imag=gains.imag.tolist(),
                             verified=False, calibration_id=f'box-angular-{uuid.uuid4().hex[:12]}')
    else:
        calibrated = replace(config, geometry_mm=None,
                             geometry_wavelengths=np.vstack([np.zeros(2), fitted]).tolist(),
                             mount_roll_deg=0., angle_matrix_real=None, angle_matrix_imag=None,
                             geometry_label='Empirical phase baselines from box sweep; physical geometry UNVERIFIED',
                             gains_real=gains.real.tolist(), gains_imag=gains.imag.tolist(),
                             verified=False, calibration_id=f'box-angular-empirical-{uuid.uuid4().hex[:12]}')
    calibrated.validate()
    result = {
        'status': 'heldout_passed', 'mode': mode, 'fit_pose_names': fit_names,
        'heldout_pose_names': holdout_names,
        'fitted_baselines_wavelengths': fitted.tolist(), 'nominal_baselines_wavelengths': nominal.tolist(),
        'max_baseline_difference_wavelengths': delta, 'max_training_residual_deg': train_max_deg,
        'heldout_max_error_deg': maximum, 'heldout_rms_error_deg': rms,
        'center_repeat_error_deg': repeat_error,
        'reference_center_direction': u_ref.tolist(),
        'phase_correction_deg': np.degrees(np.angle(gains)).tolist(),
        'measurements': measurements,
        'limitations': 'Valid only for measured survey positions/range; not certified 3D reconstruction or accurate object scattering centers.',
        'geometry_verified': False, 'calibration_id': calibrated.calibration_id,
    }
    return calibrated, result


def calibrate(root, output, *, mode='physical', report_path=None):
    from .config import Config
    root = Path(root)
    source = Config.load(root / 'config.json')
    report = analyze(root)
    destination = Path(output)
    report_destination = Path(report_path) if report_path else destination.with_suffix('.validation.json')
    if destination.resolve() == (root / 'config.json').resolve():
        raise CalibrationRejected('Cannot overwrite the original sweep config')
    if destination.exists():
        raise CalibrationRejected(f'Will not overwrite existing config: {destination}')
    if destination.resolve() == report_destination.resolve():
        raise CalibrationRejected('Validation JSON path cannot equal config path')
    try:
        calibrated, diagnostics = fit(report, source, mode=mode)
    except CalibrationRejected as exc:
        report_destination.parent.mkdir(parents=True, exist_ok=True)
        report_destination.write_text(json.dumps({'status': 'rejected', 'reason': str(exc),
                                                  'source_sweep': str(root), 'no_config_written': True}, indent=2))
        raise
    destination.parent.mkdir(parents=True, exist_ok=True)
    report_destination.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.update(source_sweep=str(root), output_config=str(destination))
    report_destination.write_text(json.dumps(diagnostics, indent=2), encoding='utf-8')
    calibrated.save(destination)
    return diagnostics


def main(argv=None):
    p = argparse.ArgumentParser(description='Angular sweep with surveyed support heights and paired per-pose backgrounds')
    cmd = p.add_subparsers(dest='cmd', required=True)
    take = cmd.add_parser('record', help='Capture 10 measured-height poses, each with a matched empty background')
    take.add_argument('output')
    take.add_argument('--port', required=True)
    take.add_argument('--config', required=True)
    take.add_argument('--distance', type=float, default=2.0,
                      help='forward antenna-to-bottle-center distance in meters (default 2.0)')
    take.add_argument('--horizontal-offset', type=float, default=.30,
                      help='lateral left/right training offset in meters (default 0.30)')
    take.add_argument('--antenna-height', type=float, default=.34)
    take.add_argument('--bottle-height', type=float, default=.235)
    take.add_argument('--box-long', type=float, default=.275)
    take.add_argument('--box-thin', type=float, default=.055)
    take.add_argument('--seconds', type=float, default=5)
    read = cmd.add_parser('analyze', help='Report raw frame/quality checks without writing a calibration')
    read.add_argument('sweep')
    cal = cmd.add_parser('calibrate', help='Require independent held-out angles before writing calibration JSON')
    cal.add_argument('sweep')
    cal.add_argument('--output', required=True)
    cal.add_argument('--report')
    cal.add_argument('--mode', choices=('physical', 'empirical'), default='physical')
    a = p.parse_args(argv)
    try:
        if a.cmd == 'record':
            from .config import Config
            record(a.output, Config.load(a.config), a.port, distance=a.distance,
                   horizontal_offset=a.horizontal_offset, antenna_height=a.antenna_height,
                   bottle_height=a.bottle_height, box_long=a.box_long,
                   box_thin=a.box_thin, seconds=a.seconds)
        elif a.cmd == 'analyze':
            analyze(a.sweep)
        else:
            result = calibrate(a.sweep, a.output, mode=a.mode, report_path=a.report)
            print(json.dumps({k: result[k] for k in ('status', 'mode', 'heldout_rms_error_deg',
                                                   'heldout_max_error_deg', 'center_repeat_error_deg',
                                                   'output_config')}, indent=2))
    except (ValueError, OSError) as exc:
        p.exit(2, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
