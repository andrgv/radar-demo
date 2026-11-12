"""Multi-return CA-CFAR + reference-based RX2 azimuth. See docs/CFAR_MAP.md."""
from collections import deque
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import sys
import time
import uuid

import numpy as np

from radar_min.cfar import CfarConfig, ca_thresholds, json_array, peak_groups
from radar_min.cfar_range import refine_group
from radar_min.core import Config as RangeConfig, Continuity, range_spectrum
from radar_min.clock_sync import ClockSync
from .angle_lab import infer_azimuth_rx2, raw_model_phase
from .config import Config
from .protocol import Frame, HEADER
from .range_azimuth import check_acquisition, load_reference


class MultiObstacleMap:
    """One provisional direction per resolved range group, in sensor coordinates.

    Detection uses Amanda's uncorrected power and group refinement. Direction
    uses Andrea's gain-corrected complex RX2/RX1 phase at the SAME native bin.
    No empty-scene subtraction, world map, elevation estimate or held-last dots.
    """
    def __init__(self, config, reference_phase, reference_xyz, *, min_range,
                 max_range, settings=None, confirmation_frames=3, window=5,
                 target_z=None, limit_deg=25, association_deg=8):
        self.config = config.validate()
        self.reference_xyz = np.asarray(reference_xyz, float)
        if (self.reference_xyz.shape != (3,) or not np.isfinite(self.reference_xyz).all()
                or self.reference_xyz[1] <= 0 or not np.isfinite(reference_phase)):
            raise ValueError('Reference requires finite phase and XYZ with positive forward Y')
        self.reference_phase = float(reference_phase)
        self.z = float(self.reference_xyz[2] if target_z is None else target_z)
        if (not np.isfinite([min_range, max_range, self.z, limit_deg, association_deg]).all()
                or not 0 < min_range < max_range or not 0 < limit_deg <= 60
                or association_deg <= 0 or type(window) is not int or window < 1
                or type(confirmation_frames) is not int or confirmation_frames < 1):
            raise ValueError('Invalid range, height, angular bounds, window or confirmation count')
        # Preserve Amanda's uncalibrated physical range axis explicitly.
        if config.range_scale != 1 or config.range_offset_m != 0:
            raise ValueError('CFAR map requires range_scale=1 and range_offset_m=0')
        bins = np.flatnonzero((config.ranges >= min_range) & (config.ranges <= max_range)
                             & (np.arange(len(config.ranges)) >= 2)
                             & (np.arange(len(config.ranges)) < len(config.ranges)-1))
        if not len(bins):
            raise ValueError('Search interval contains no usable angle/range bins')
        self.range_config = RangeConfig(profile_id=config.profile_id, samples=config.samples,
            chirps=config.chirps, sample_rate_hz=config.sample_rate_hz,
            slope_hz_s=config.slope_hz_s, discard_chirps=config.discard_chirps,
            frame_interval_s=config.frame_interval_s, min_bin=int(bins[0]), max_bin=int(bins[-1]),
            confirmation_frames=confirmation_frames)
        self.settings = settings or CfarConfig()
        _, thresholds, _ = ca_thresholds(np.ones(len(config.ranges)), self.settings)
        if not np.isfinite(thresholds[bins]).any():
            raise ValueError('No searchable CFAR bins have enough training cells')
        # Refuse geometry with no horizontal phase sensitivity before acquisition.
        infer_azimuth_rx2(reference_phase, reference_phase, self.reference_xyz, config,
                          limit_deg=limit_deg)
        self.window = window
        self.limit_deg = limit_deg
        self.association_deg = association_deg
        self.guard = Continuity(self.range_config)
        self.tracks = {}
        self.next_id = 1
        self.metadata = dict(algorithm='multi-cfar-rx2-map-v1', cfar=asdict(self.settings),
            min_range_m=float(min_range), max_range_m=float(max_range),
            confirmation_frames=confirmation_frames, phase_window_frames=window,
            reference_xyz_m=self.reference_xyz.tolist(), reference_phase_rad=self.reference_phase,
            assumed_z_m=self.z, angle_limit_deg=limit_deg, association_deg=association_deg,
            frame_id='radar', calibrated=False, background_subtracted=False)

    def clear(self):
        self.tracks.clear()

    def invalid(self, reason, frame=None):
        self.clear()
        return dict(algorithm=self.metadata['algorithm'], frame_id='radar', calibrated=False,
            state='UNCERTAIN', reason=reason, sequence=int(frame.sequence) if frame else None,
            timestamp_us=int(frame.timestamp_us) if frame else None, assumed_z_m=self.z,
            observations=[], obstacles=[], power_db=[], threshold_db=[], training_cell_counts=[])

    def _direction(self, moments, distance):
        out = dict(azimuth_deg=None, coherence_rx2=None, phase_residual_deg=None,
                   reason='range_unresolved')
        if distance is None:
            return out
        values = np.sum(moments, axis=0)
        cross, p0, p1 = values
        coherence = float(np.clip(abs(cross)/np.sqrt(max(float(p0.real*p1.real), 1e-24)), 0, 1))
        out['coherence_rx2'] = coherence
        if coherence < .9:
            out['reason'] = 'rx2_coherence_below_0.90'
            return out
        if distance <= abs(self.z):
            out['reason'] = 'range_incompatible_with_assumed_height'
            return out
        horizontal = float(np.sqrt(distance**2-self.z**2))
        forward = horizontal
        for _ in range(3):
            az, residual = infer_azimuth_rx2(np.angle(cross), self.reference_phase,
                self.reference_xyz, self.config, forward_m=forward, z_m=self.z,
                limit_deg=self.limit_deg)
            forward = horizontal*np.cos(np.radians(az))
        out['phase_residual_deg'] = residual
        if abs(az) >= self.limit_deg-.05 or residual > 1:
            out['reason'] = 'phase_outside_azimuth_model'
            return out
        out.update(azimuth_deg=az, reason='usable_direction')
        return out

    def update(self, frame):
        reason = self.guard.check(frame)
        try:
            raw = range_spectrum(frame, self.range_config)
        except ValueError as error:
            return self.invalid(str(error), frame)
        if not frame.flags & 1:
            reason = 'invalid_adc_flag'
        # The initial frame may contain historic counters; changes are handled
        # by Continuity, just as in Amanda's detector.
        if reason:
            return self.invalid(reason, frame)
        p = np.mean(abs(raw)**2, axis=(0, 2))
        groups, _, _, thresholds, counts = peak_groups(p, self.range_config, self.settings)
        corrected = raw*self.config.gains
        observations = []
        for candidate in groups:
            k = candidate['range_bin']
            fine = refine_group(frame, self.range_config, candidate['bins'])
            channels = corrected[:, k, :2]
            moments = np.array([np.sum(channels[:, 1]*channels[:, 0].conj()),
                                np.sum(abs(channels[:, 0])**2), np.sum(abs(channels[:, 1])**2)])
            direction = self._direction([moments], fine['range_m'])
            observations.append(dict(**candidate, fine_range=fine, range_m=fine['range_m'],
                **direction, x_m=None, y_m=None, _moments=moments))

        # One-to-one greedy association. Only consecutive, overlapping range
        # groups with <=1-bin peak movement and compatible bearings may match.
        pairs = []
        for i, item in enumerate(observations):
            for track_id, old in self.tracks.items():
                if abs(item['range_bin']-old['range_bin']) > 1 or not set(item['bins']) & set(old['bins']):
                    continue
                az, previous = item['azimuth_deg'], old['azimuth_deg']
                delta = abs(az-previous) if az is not None and previous is not None else 0
                if delta <= self.association_deg:
                    pairs.append((abs(item['range_bin']-old['range_bin'])+delta/self.association_deg,
                                  i, track_id))
        matches, used = {}, set()
        for _, i, track_id in sorted(pairs):
            if i not in matches and track_id not in used:
                matches[i] = track_id
                used.add(track_id)
        next_tracks = {}
        for i, item in enumerate(observations):
            track_id = matches.get(i)
            if track_id is None:
                track_id = self.next_id
                self.next_id += 1
                old = dict(hits=0, history=deque(maxlen=self.window))
            else:
                old = self.tracks[track_id]
            history = old['history']
            history.append(item.pop('_moments'))
            item.update(self._direction(list(history), item['range_m']))
            hits = old['hits']+1
            confirmed = hits >= self.range_config.confirmation_frames
            item.update(track_id=track_id, confirmation_hits=hits, confirmed=confirmed,
                        averaged_frames=len(history), state='TENTATIVE')
            if confirmed:
                item['state'] = 'UNRESOLVED'
                if item['azimuth_deg'] is not None:
                    horizontal = float(np.sqrt(item['range_m']**2-self.z**2))
                    angle = np.radians(item['azimuth_deg'])
                    item.update(x_m=float(horizontal*np.sin(angle)), y_m=float(horizontal*np.cos(angle)),
                                state='LOCALIZED', reason='confirmed_cfar_and_rx2_direction')
            next_tracks[track_id] = dict(range_bin=item['range_bin'], bins=item['bins'],
                azimuth_deg=item['azimuth_deg'], hits=hits, history=history)
        self.tracks = next_tracks  # A miss removes that track; no stale dots.
        confirmed = [v for v in observations if v['confirmed']]
        return dict(algorithm=self.metadata['algorithm'], sequence=int(frame.sequence),
            timestamp_us=int(frame.timestamp_us), frame_id='radar', calibrated=False,
            state='OBSTACLES' if confirmed else 'TENTATIVE' if observations else 'NO_DETECTION',
            reason='current_frame', assumed_z_m=self.z, observations=observations,
            obstacles=confirmed, power_db=json_array(10*np.log10(np.maximum(p, 1e-12))),
            threshold_db=json_array(10*np.log10(np.maximum(thresholds, 1e-12))),
            training_cell_counts=counts.tolist())


def demo_frame(config, sequence, z=0):
    """Three simulated isolated reflectors; exercises real ADC -> FFT -> CFAR."""
    x = np.full((config.chirps, config.samples, 3), 32768., dtype=float)
    t = np.arange(config.samples)/config.samples
    spacing = config.ranges[1]-config.ranges[0]
    for bin_position, azimuth, amplitude in [(3.2, -12, 1600), (15.1, 8, 1100), (27.2, 18, 800)]:
        distance = float(bin_position*spacing)
        horizontal = np.sqrt(max(distance**2-z**2, 0))
        xyz = [horizontal*np.sin(np.radians(azimuth)), horizontal*np.cos(np.radians(azimuth)), z]
        direction = np.asarray(xyz)[[0, 2]]/distance
        raw = np.linalg.solve(config.angle_matrix, np.exp(2j*np.pi*(config.array_geometry@direction)))
        raw /= max(abs(raw))
        x += amplitude*np.real(np.exp(2j*np.pi*bin_position*t)[None, :, None]*raw[None, None, :])
    x += np.random.default_rng(sequence).normal(0, 2, x.shape)
    return Frame(sequence, sequence*round(config.frame_interval_s*1e6), config.profile_id,
                 np.clip(np.rint(x), 1, 65534).astype('uint16'))


def iter_results(estimator, *, port=None, recording=None, demo=False, output=None, seconds=None,
                 on_output_ready=None):
    """Live/replay share processing; raw recording precedes DSP, faults withdraw dots."""
    from .acquisition import Source
    from .storage import Recorder
    if sum([port is not None, recording is not None, bool(demo)]) != 1:
        raise ValueError('Select exactly one live port, replay or demo')
    if seconds is not None and (not np.isfinite(seconds) or seconds <= 0):
        raise ValueError('Seconds must be finite and positive')
    cfg = estimator.config
    if recording:
        check_acquisition(recording, cfg)
    with ExitStack() as stack:
        recorder = stack.enter_context(Recorder(output, cfg, estimator.metadata)) if output else None
        log = stack.enter_context((Path(output)/'obstacles2d.jsonl').open('x')) if output else None
        if recorder is not None and on_output_ready is not None:
            on_output_ready()
        source = None
        try:
            source = Source(cfg, port=port, recording=recording, synchronize=bool(port)) if not demo else None
            if source:
                source.transport_recorder = recorder
            started = last = time.monotonic()
            clock = ClockSync()
            counters = (0, 0, 0)
            sequence = 0
            received = 0
            packet_bytes = HEADER.size+cfg.chirps*cfg.samples*3*2+4
            while seconds is None or time.monotonic()-started < seconds:
                try:
                    sequence += 1
                    frame = demo_frame(cfg, sequence, estimator.z) if demo else source.read()
                except StopIteration:
                    if source.parser.buffer:
                        raise ValueError('Truncated recording: incomplete packet at EOF')
                    break
                now = time.monotonic()
                if frame is None:
                    if now-last > 1:
                        raise TimeoutError('No complete radar frame for one second')
                    yield None  # Let GUI process events even during missing data.
                    continue
                if recorder:
                    recorder.write(frame)
                received += 1
                last = now
                result = estimator.update(frame)
                if source:
                    parser = source.parser
                    current = (parser.bad_crc, parser.bad_headers, parser.discarded_bytes)
                    if current != counters:
                        result = estimator.invalid('transport_corruption', frame)
                    counters = current
                    if port:
                        backlog = len(source.pending) > 1 or source.serial.in_waiting > 2*packet_bytes
                        sync = clock.update(frame.timestamp_us, now,
                            eligible=result['state'] != 'UNCERTAIN' and not backlog,
                            restart=result['reason'] == 'restart_or_duplicate')
                        if backlog or sync['reason']:
                            result = estimator.invalid('serial_backlog' if backlog else sync['reason'], frame)
                        result['clock_sync'] = sync
                if log:
                    log.write(json.dumps(result, allow_nan=False)+'\n')
                    log.flush()
                yield result
            if not received:
                raise ValueError('No complete radar frames received')
        finally:
            try:
                if source:
                    source.close()
            finally:
                estimator.clear()
                if log:
                    log.write(json.dumps(estimator.invalid('stopped'), allow_nan=False)+'\n')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--port')
    source.add_argument('--replay')
    source.add_argument('--demo', action='store_true', help='Three simulated targets, no hardware/reference needed')
    p.add_argument('--config', default='configs/exploratory-roll90-phase.json')
    p.add_argument('--reference', help='Known-position raw recording; required except in demo')
    p.add_argument('--reference-xyz', type=float, nargs=3, metavar=('X', 'Y', 'Z'))
    p.add_argument('--target-z', type=float, help='Assumed common target height relative to radar')
    p.add_argument('--min-range', type=float, default=.7)
    p.add_argument('--max-range', type=float, default=10)
    p.add_argument('--cfar-guard', type=int, default=2)
    p.add_argument('--cfar-training', type=int, default=8)
    p.add_argument('--cfar-min-training', type=int, default=8)
    p.add_argument('--cfar-factor', type=float, default=6)
    p.add_argument('--confirmation-frames', type=int, default=3)
    p.add_argument('--window', type=int, default=5)
    p.add_argument('--angle-limit', type=float, default=25)
    p.add_argument('--seconds', type=float)
    p.add_argument('--output', help='New directory for raw frames, settings and obstacles2d.jsonl')
    p.add_argument('--plot', action='store_true')
    p.add_argument('--snapshot', help='Save final display to an image (also works with MPLBACKEND=Agg)')
    p.add_argument('--map-merge-radius', type=float, default=.35, help='Cluster/associate nearby return positions in meters')
    p.add_argument('--map-min-observations', type=int, default=3, help='Distinct localized frames before a region becomes mapped')
    p.add_argument('--map-remember-seconds', type=float, default=30, help='Age after which an unobserved region is marked stale')
    p.add_argument('--load-map', help='Resume map.json; radar must remain in exactly the same pose')
    a = p.parse_args(argv)
    if not a.demo and (not a.reference or a.reference_xyz is None):
        p.error('Live/replay requires --reference and --reference-xyz X Y Z')
    if a.demo and (a.reference or a.reference_xyz is not None):
        p.error('--demo supplies its own synthetic reference')
    plot = None
    scene = None
    archive = None
    last_display = None
    scene_time = None
    try:
        cfg = Config.load(a.config)
        xyz = [0, 2, a.target_z or 0] if a.demo else a.reference_xyz
        phase = float(raw_model_phase(cfg, xyz)[0]) if a.demo else load_reference(a.reference, xyz, cfg)
        detector = MultiObstacleMap(cfg, phase, xyz, min_range=a.min_range, max_range=a.max_range,
            settings=CfarConfig(a.cfar_guard, a.cfar_training, a.cfar_min_training, a.cfar_factor),
            confirmation_frames=a.confirmation_frames, window=a.window,
            target_z=a.target_z, limit_deg=a.angle_limit)
        detector.metadata.update(reference_recording=a.reference, source='synthetic' if a.demo else 'live' if a.port else 'replay')
        from .scene_map import FixedSceneMap, SceneMapSettings, MapArchive, reference_fingerprint
        scene = FixedSceneMap(reference_fingerprint(detector), SceneMapSettings(
            merge_radius_m=a.map_merge_radius, min_observations=a.map_min_observations,
            remember_seconds=a.map_remember_seconds), assumed_z=detector.z)
        if a.load_map:
            scene.restore(a.load_map)
        detector.metadata['scene_map'] = dict(settings=asdict(scene.settings), fingerprint=scene.fingerprint,
                                             fixed_radar_required=True, loaded_from=a.load_map)
        if (a.port or a.plot) and not a.output:
            a.output = str(Path('recordings')/f'fixed-map-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}')
        if a.output:
            print(f'Raw recording and persistent map: {Path(a.output).resolve()}', file=sys.stderr)
        archive = MapArchive(a.output)
        scene_time = scene.last_time if scene.last_time is not None else time.monotonic()
        scene.snapshot(now=scene_time)

        def save_map():
            snapshot = scene.snapshot(now=scene_time)
            if a.output and Path(a.output).is_dir():
                archive.write(snapshot, event='clear' if snapshot['reason'] == 'map_cleared' else 'save')
            return snapshot

        if a.plot or a.snapshot:
            from .cfar_map_gui import MapPlot
            plot = MapPlot(detector, interactive=a.plot, scene_map=scene, save_callback=save_map)
        results = iter_results(detector, port=a.port, recording=a.replay, demo=a.demo,
                               output=a.output, seconds=a.seconds, on_output_ready=archive.activate)
        previous_timestamp = None
        try:
            for result in results:
                if a.port:
                    scene_time = time.monotonic()
                elif result is not None and result.get('timestamp_us') is not None:
                    timestamp = result['timestamp_us']
                    if previous_timestamp is not None:
                        delta = (timestamp-previous_timestamp) & 0xffffffff
                        if 0 < delta < 0x80000000:
                            scene_time += delta/1e6
                    previous_timestamp = timestamp
                mapped = scene.update(result, now=scene_time)
                archive.write(mapped)
                if result is not None:
                    result['scene_map'] = mapped
                    last_display = result
                    if a.plot:
                        labels = [result['state']]
                        for item in mapped['objects']:
                            if item['confirmed']:
                                labels.append(f"Object #{item['object_id']} {item['range_m']:.3f} m, "
                                              f"{item['azimuth_deg']:+.2f}° ({item['state']})")
                        print(' | '.join(labels), flush=True)
                    else:
                        print(json.dumps(result, allow_nan=False), flush=True)
                if plot:
                    if last_display is not None:
                        plot.update(dict(last_display, scene_map=mapped))
                    else:
                        plot.update(None)
                    if not plot.is_open():
                        break
                if (a.demo or a.replay) and a.plot:
                    time.sleep(cfg.frame_interval_s)
        finally:
            results.close()
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, TimeoutError) as error:
        print(json.dumps(dict(state='UNCERTAIN', error=str(error))), flush=True)
        return 2
    finally:
        if scene is not None:
            stopped = scene.snapshot(now=scene_time, stopped=True)
            if archive is not None and a.output and Path(a.output).is_dir():
                archive.write(stopped, event='stopped')
            if plot and last_display is not None and plot.is_open():
                plot.update(dict(last_display, scene_map=stopped))
        if archive:
            archive.close()
        if plot:
            if a.snapshot:
                plot.save(a.snapshot)
            plot.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
