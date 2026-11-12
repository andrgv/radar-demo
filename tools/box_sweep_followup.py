"""Investigate an existing paired-background box sweep; optionally recapture failed poses.

Run from the radar-demo repository root:
    .venv/bin/python tools/box_sweep_followup.py diagnose recordings/box-angle-01
    .venv/bin/python tools/box_sweep_followup.py recapture recordings/box-angle-01 \
      recordings/box-angle-01-retry --port /dev/ttyACM0

No original recording or calibration config is overwritten.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np

# When invoked as a script under tools/, include the repository's radar package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


COMPARE_PAIRS = (
    ('check_left', 'check_right'), ('left', 'right'),
    ('center', 'center_repeat'), ('center', 'up'),
    ('center', 'down'), ('up', 'check_up'),
    ('center', 'check_left'), ('center', 'check_right'),
)


def wrap_deg(angle):
    """Signed phase difference in degrees, in [-180, 180)."""
    return ((np.asarray(angle, dtype=float) + 180) % 360) - 180


def compare_phases(rows, baselines):
    """Compare 2-RX phase changes with the actual surveyed direction vectors."""
    results = []
    baselines = np.asarray(baselines, float)
    for start, end in COMPARE_PAIRS:
        if start not in rows or end not in rows:
            continue
        a, b = rows[start], rows[end]
        du = np.asarray(b['direction_right_up']) - np.asarray(a['direction_right_up'])
        predicted = wrap_deg(360 * (baselines @ du))
        observed = wrap_deg(np.asarray(b['relative_phase_deg']) - np.asarray(a['relative_phase_deg']))
        results.append({
            'from': start, 'to': end,
            'same_support': a['support'] == b['support'],
            'observed_deg_rx2_rx3': observed.tolist(),
            'predicted_deg_rx2_rx3': predicted.tolist(),
            'residual_deg_rx2_rx3': wrap_deg(observed - predicted).tolist(),
        })
    return results


def circular_spread_deg(phase_deg):
    """Circular standard deviation (degrees) of temporal phase samples."""
    phasor = np.mean(np.exp(1j * np.radians(np.asarray(phase_deg, float))), axis=0)
    r = np.clip(np.abs(phasor), 1e-15, 1.0)
    return np.degrees(np.sqrt(-2 * np.log(r)))


def _fft_recording(directory, cfg, neutral):
    from radar.processing import range_fft
    from radar.storage import replay
    spectra = []
    for frame in replay(directory):
        if frame.profile_id != cfg.profile_id or frame.adc.shape != (cfg.chirps, cfg.samples, 3) or not frame.flags & 1:
            raise ValueError(f'Frame/config mismatch: {directory}')
        spectra.append(range_fft(frame.adc, neutral))
    if len(spectra) < 10:
        raise ValueError(f'Fewer than ten frames: {directory}')
    return np.asarray(spectra)  # frame, chirp, range-bin, RX


def _cross_phase(spectrum, bin_idx):
    # spectrum: frames x chirps x bins x 3
    channels = spectrum[:, :, bin_idx, :]
    cross_frame = np.mean(channels * channels[:, :, :1].conj(), axis=1)
    cross = np.mean(cross_frame, axis=0)
    channels_power = np.mean(abs(channels) ** 2, axis=(0, 1))
    coherence = abs(cross) / np.sqrt(np.maximum(channels_power * channels_power[0], 1e-20))
    phases = np.degrees(np.angle(cross[1:] * cross[0].conj()))
    temporal_phases = np.degrees(np.angle(cross_frame[:, 1:] * cross_frame[:, :1].conj()))
    return {
        'relative_phase_deg': phases.tolist(),
        'min_coherence': float(np.min(coherence)),
        'per_rx_coherence': coherence.tolist(),
        'temporal_phase_spread_deg_rx2_rx3': circular_spread_deg(temporal_phases).tolist(),
    }


def diagnose(root, output=None, *, make_plots=True):
    from dataclasses import replace
    from radar.config import Config
    from radar.processing import noise_threshold

    root = Path(root)
    manifest = json.loads((root / 'sweep.json').read_text(encoding='utf-8'))
    if manifest.get('kind') != 'measured-height-paired-background':
        raise ValueError('Expected a measured-height paired-background sweep')
    cfg = Config.load(root / 'config.json')
    neutral = replace(cfg, gains_real=[1., 1., 1.], gains_imag=[0., 0., 0.])
    report_path = root / 'sweep-report.json'
    original_report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    accepted = {p['name']: p.get('accepted', False) for p in original_report.get('poses', [])}
    rows = {}
    power_curves = {}
    for pose in manifest['poses']:
        name = pose['name']
        bg_path = root / ('background_' + name)
        target_path = root / name
        background = _fft_recording(bg_path, cfg, neutral)
        target = _fft_recording(target_path, cfg, neutral)
        bg_reference = background.mean(axis=(0, 1))
        # Identical complex-spectrum subtraction to radar.box_sweep.analyze().
        residual = target - bg_reference[None, None, :, :]
        rng = float(np.linalg.norm(pose['xyz_m']))
        bin_idx = int(np.argmin(np.abs(cfg.ranges - rng)))
        d_power = np.mean(abs(residual) ** 2, axis=(0, 1, 3))
        b_power = np.mean(abs(background) ** 2, axis=(0, 1, 3))
        t_power = np.mean(abs(target) ** 2, axis=(0, 1, 3))
        delta_angle = _cross_phase(residual, bin_idx)
        raw_angle = _cross_phase(target, bin_idx)
        neighborhood = [int(i) for i in range(max(2, bin_idx - 1),
                                                   min(len(cfg.ranges) - 2, bin_idx + 2))]
        local_highest = max(neighborhood, key=lambda i: d_power[i])
        u = np.asarray(pose['xyz_m'])[[0, 2]] / rng
        rows[name] = {
            'name': name, 'fit': pose['fit'], 'support': pose['support'],
            'accepted_previous': accepted.get(name),
            'expected_range_m': rng, 'direction_right_up': u.tolist(),
            'range_bin': bin_idx, 'range_bin_m': float(cfg.ranges[bin_idx]),
            'nearby_highest_bin': local_highest,
            'nearby_highest_range_m': float(cfg.ranges[local_highest]),
            'frames_background': len(background), 'frames_target': len(target),
            'local_contrast_db': float(10 * np.log10(max(d_power[bin_idx], 1e-12) /
                                                    max(noise_threshold(d_power, 1)[bin_idx], 1e-12))),
            # This ratio describes total complex-residual power vs background power,
            # not a physical target SNR or clean target-only return.
            'residual_vs_background_power_db': float(10 * np.log10(max(d_power[bin_idx], 1e-12) /
                                                                   max(b_power[bin_idx], 1e-12))),
            'raw_target_vs_background_power_db': float(10 * np.log10(max(t_power[bin_idx], 1e-12) /
                                                                     max(b_power[bin_idx], 1e-12))),
            **delta_angle,
            'raw_target_phase_deg_rx2_rx3': raw_angle['relative_phase_deg'],
            'raw_target_min_coherence': raw_angle['min_coherence'],
            'raw_target_phase_spread_deg_rx2_rx3': raw_angle['temporal_phase_spread_deg_rx2_rx3'],
        }
        power_curves[name] = (d_power, b_power, t_power, bin_idx)
    baselines = cfg.array_geometry[1:] - cfg.array_geometry[0]
    comparisons = compare_phases(rows, baselines)
    raw_rows = {name: {**v, 'relative_phase_deg': v['raw_target_phase_deg_rx2_rx3']}
                for name, v in rows.items()}
    raw_comparisons = compare_phases(raw_rows, baselines)
    result = {
        'schema': 1, 'source_sweep': str(root), 'profile_id': hex(cfg.profile_id),
        'range_bin_spacing_m': float(cfg.ranges[1] - cfg.ranges[0]),
        'nominal_baselines_wavelengths_rx2_rx3': baselines.tolist(),
        'note': 'Differences in complex background-subtracted spectra can reflect multipath, '
                'phase coherence, and subtraction artifacts. Raw-target comparisons help '
                'isolate whether subtraction changes phase trends. Calibration remains blocked.',
        'poses': list(rows.values()), 'subtracted_phase_comparisons': comparisons,
        'raw_target_phase_comparisons': raw_comparisons,
    }
    output = Path(output) if output else root / 'box-sweep-diagnostics.json'
    if output.resolve() == (root / 'sweep-report.json').resolve():
        raise ValueError('Cannot overwrite original sweep report')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')

    print('Pose             Gate  Contrast  Residual/BG  RawTarget/BG  Coh   RX2/RX3 phase spread')
    for row in rows.values():
        a, b = row['temporal_phase_spread_deg_rx2_rx3']
        gate = 'PASS' if row['accepted_previous'] else 'FAIL'
        print(f"{row['name']:<16} {gate:<4} {row['local_contrast_db']:>7.1f} dB "
              f"{row['residual_vs_background_power_db']:>8.1f} dB "
              f"{row['raw_target_vs_background_power_db']:>11.1f} dB "
              f"{row['min_coherence']:>5.2f}   {a:>5.1f}/{b:>5.1f} deg")
    print('\nPairwise phase deltas: measured vs predicted (RX2, RX3), degrees')
    for comparison in comparisons:
        obs = comparison['observed_deg_rx2_rx3']
        pred = comparison['predicted_deg_rx2_rx3']
        print(f"{comparison['from']} -> {comparison['to']} "
              f"{'SAME SUPPORT' if comparison['same_support'] else 'different supports'}: "
              f"observed ({obs[0]:+.1f}, {obs[1]:+.1f}), "
              f"expected ({pred[0]:+.1f}, {pred[1]:+.1f})")
    if make_plots:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            print('matplotlib unavailable; JSON saved without plot')
        else:
            poses = list(rows)
            fig, axes = plt.subplots(5, 2, figsize=(13, 15), constrained_layout=True)
            for ax, name in zip(axes.flat, poses):
                power, bg, raw, bin_idx = power_curves[name]
                ax.plot(cfg.ranges, 10 * np.log10(np.maximum(power, 1e-12)), label='target minus paired BG')
                ax.plot(cfg.ranges, 10 * np.log10(np.maximum(bg, 1e-12)), label='empty support')
                ax.plot(cfg.ranges, 10 * np.log10(np.maximum(raw, 1e-12)), label='raw target', alpha=.65)
                ax.axvline(cfg.ranges[bin_idx], linestyle=':', color='black', label='predicted bin')
                ax.set(xlabel='Range (m)', ylabel='FFT power (dB, arbitrary ref)',
                       title=f"{name} — {rows[name]['local_contrast_db']:.1f} dB local contrast")
                ax.set_xlim(max(0, cfg.ranges[bin_idx] - 1.5), cfg.ranges[bin_idx] + 1.5)
                ax.grid(alpha=.25)
            axes.flat[0].legend(fontsize=8)
            figure_path = output.with_suffix('.png')
            fig.savefig(figure_path, dpi=130)
            plt.close(fig)
            print(f'Plot: {figure_path}')
    print(f'Full report: {output}')
    return result


def recapture(source, destination, port, *, names=None, seconds=5):
    from radar.box_sweep import _capture, analyze
    from radar.config import Config
    from radar.background import SpectralBackground
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Refusing to overwrite original recording')
    if destination.exists():
        raise ValueError(f'Output already exists: {destination}')
    manifest = json.loads((source / 'sweep.json').read_text(encoding='utf-8'))
    if manifest.get('kind') != 'measured-height-paired-background':
        raise ValueError('Expected a measured-height paired-background sweep')
    report = json.loads((source / 'sweep-report.json').read_text(encoding='utf-8'))
    poses = {p['name']: p for p in manifest['poses']}
    chosen = names if names else [r['name'] for r in report['poses'] if not r.get('accepted', False)]
    if not chosen:
        raise ValueError('No failed positions to recapture; choose explicit --names to retest')
    unknown = set(chosen) - set(poses)
    if unknown:
        raise ValueError('Unknown position(s): ' + ', '.join(sorted(unknown)))
    if len(chosen) != len(set(chosen)):
        raise ValueError('Duplicate position names')
    config = Config.load(source / 'config.json')
    if not np.isfinite(seconds) or seconds < 2:
        raise ValueError('Capture duration must be at least two seconds')
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source / 'config.json', destination / 'config.json')
    updated_manifest = {**manifest, 'recapture_of': str(source), 'recaptured_poses': chosen}
    (destination / 'sweep.json').write_text(json.dumps(updated_manifest, indent=2), encoding='utf-8')
    for name in poses:
        if name not in chosen:
            shutil.copytree(source / name, destination / name)
            shutil.copytree(source / ('background_' + name), destination / ('background_' + name))
    print('Original dataset remains unchanged:', source)
    print('Recapturing only:', ', '.join(chosen))
    print('Keep sensor FIXED and each support motionless within its empty/target pair.')
    for i, name in enumerate(chosen, 1):
        pose = poses[name]
        xyz = pose['xyz_m']
        print(f"\n[{i}/{len(chosen)}] {name}: {pose['support_description']}")
        print(f"  Measured bottle center: right {xyz[0]*100:+.1f} cm, "
              f"forward {xyz[1]:.2f} m, elevation offset {xyz[2]*100:+.2f} cm")
        input('  Remove bottle, leave support in place; Enter for empty background: ')
        bg_dir = destination / ('background_' + name)
        _capture(bg_dir, config, port, seconds,
                 {'label': 'calibration_background', 'sweep_pose': pose, 'scene_id': destination.name})
        background = SpectralBackground.from_path(bg_dir, config)
        input('  Add upright bottle WITHOUT moving support; step away; Enter for target: ')
        _capture(destination / name, config, port, seconds,
                 {'label': 'calibration', 'sweep_pose': pose, 'scene_id': destination.name,
                  'background_method': 'matched_per_pose_spectrum',
                  'background_source': '../background_' + name}, background=background)
    result = analyze(destination)
    print(f"Retake quality: {result['accepted_count']}/{result['total_poses']} passed")
    print('Compare diagnostics before trying any calibration.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmds = parser.add_subparsers(dest='command', required=True)
    d = cmds.add_parser('diagnose', help='Analyze existing raw paired recordings; no recapture')
    d.add_argument('sweep')
    d.add_argument('--output')
    d.add_argument('--no-plots', action='store_true')
    r = cmds.add_parser('recapture', help='Create a new dataset, retaking only failed poses')
    r.add_argument('sweep')
    r.add_argument('output')
    r.add_argument('--port', required=True)
    r.add_argument('--names', nargs='+', help='Explicit pose names; default: previously failed poses')
    r.add_argument('--seconds', type=float, default=5.)
    args = parser.parse_args()
    try:
        if args.command == 'diagnose':
            diagnose(args.sweep, args.output, make_plots=not args.no_plots)
        else:
            recapture(args.sweep, args.output, args.port, names=args.names, seconds=args.seconds)
    except (OSError, ValueError) as error:
        parser.exit(2, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
