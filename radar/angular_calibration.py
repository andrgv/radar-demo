"""Fit and independently validate a 2-axis receive-phase model from a guided sweep.

No single-direction calibration can validate the angular baselines. This module
requires independent off-axis holdouts on both axes, and never certifies a room
map or a dense point cloud.
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import uuid

import numpy as np

from .config import Config


class AngularCalibrationError(ValueError):
    """The data do not support a validated angular configuration."""


def _wrapped(rad):
    return np.angle(np.exp(1j * np.asarray(rad)))


def _vector_from_u(u):
    x, z = np.asarray(u, float)
    radius2 = x*x + z*z
    if not np.isfinite(radius2) or radius2 >= 1:
        return None
    return np.array([x, np.sqrt(1.0 - radius2), z])


def _angles_from_u(u):
    xyz = _vector_from_u(u)
    if xyz is None:
        return None
    return [float(np.degrees(np.arctan2(xyz[0], xyz[1]))),
            float(np.degrees(np.arcsin(xyz[2])))]


def _direction_error_deg(predicted, truth):
    x = _vector_from_u(predicted)
    y = _vector_from_u(truth)
    if x is None or y is None:
        return float('inf')
    return float(np.degrees(np.arccos(np.clip(x @ y, -1, 1))))


def _row_phase(row):
    return np.radians(np.asarray(row['relative_phase_deg'], float))


def _row_u(row):
    return np.asarray(row['direction_right_up'], float)


def fit_angular_report(report, config, *, mode='physical',
                       max_heldout_error_deg=7.0,
                       max_center_drift_deg=5.0,
                       max_physical_baseline_delta=0.12):
    """Compute a candidate and a numerical validation report; do not write files.

    'physical' changes only per-channel phase gains and uses the physical array.
    'empirical' opts into apparent phase baselines identified by the sweep.
    Both require independent validation, not just phase fit on training points.
    """
    if mode not in ('physical', 'empirical'):
        raise ValueError('mode must be physical or empirical')
    if report.get('synthetic') or report.get('handheld'):
        raise AngularCalibrationError('Synthetic or handheld sweeps cannot certify angular calibration')
    rows = {row['name']: row for row in report['poses']}
    required_fit = ('center', 'left', 'right', 'up')
    required_holdout = ('check_right', 'check_left', 'check_up', 'check_down', 'center_repeat')
    required = required_fit + required_holdout
    missing = [name for name in required if name not in rows]
    if missing:
        raise AngularCalibrationError('Missing sweep poses: ' + ', '.join(missing) +
            '. Old sweeps need an independent vertical holdout; do not reuse training poses.')
    rejected = [name for name in required if not rows[name].get('accepted')]
    if rejected:
        raise AngularCalibrationError('Reference quality checks failed: ' + ', '.join(rejected))
    center_phase = _row_phase(rows['center'])
    train = [rows[name] for name in ('left', 'right', 'up')]
    train_u = np.vstack([_row_u(row) for row in train])
    train_phase = np.vstack([_wrapped(_row_phase(row) - center_phase) for row in train])
    if np.linalg.matrix_rank(train_u) != 2:
        raise AngularCalibrationError('Training positions do not span both angular axes')
    # Phase values are on the principal branch, reasonable for ~lambda/2
    # baselines and the guided small-angle placement. Do not unwrap by guessing
    # arbitrary integer cycles or fit unobserved remote directions.
    fitted = np.linalg.lstsq(train_u, train_phase / (2*np.pi), rcond=None)[0].T
    baseline_residual = _wrapped(train_phase - 2*np.pi*train_u @ fitted.T)
    training_max_phase_residual_deg = float(np.max(np.abs(np.degrees(baseline_residual))))
    if training_max_phase_residual_deg > 10.:
        raise AngularCalibrationError(
            f'Training phase response inconsistent ({training_max_phase_residual_deg:.1f} deg maximum).')
    nominal = config.array_geometry[1:] - config.array_geometry[0]
    nominal_delta = float(np.max(np.abs(fitted - nominal)))

    if mode == 'physical':
        active_baselines = nominal
        if nominal_delta > max_physical_baseline_delta:
            raise AngularCalibrationError(
                f'Observed phase slopes do not match nominal RX geometry: max delta '
                f'{nominal_delta:.3f} wavelengths > {max_physical_baseline_delta:.3f}. '
                'Verify receiver order, board orientation and multipath; '
                'do not hide this with a center-only phase correction.')
    else:
        lengths = np.linalg.norm(fitted, axis=1)
        # Only allow a plausible nondegenerate two-axis L array.
        if np.any((lengths < .3) | (lengths > .7)) or abs(np.linalg.det(fitted)) < .08:
            raise AngularCalibrationError('Measured effective baselines are physically implausible/degenerate')
        active_baselines = fitted

    # RX1 phase is an arbitrary reference. The background-subtracted complex
    # spectra in sweep.analyze_sweep used unit gains; this correction returns
    # the phase at boresight to zero for the raw receive channels.
    gains = np.r_[1.+0j, np.exp(-1j*center_phase)]
    measurements = []
    for name in required:
        row = rows[name]
        phase = _wrapped(_row_phase(row) - center_phase)
        estimated_u = np.linalg.lstsq(2*np.pi*active_baselines, phase, rcond=None)[0]
        reference_u = _row_u(row)
        error = _direction_error_deg(estimated_u, reference_u)
        measurements.append({
            'pose': name, 'role': 'train' if name in required_fit else 'heldout',
            'reference_az_el_deg': [row['expected_azimuth_deg'], row['expected_elevation_deg']],
            'estimated_az_el_deg': _angles_from_u(estimated_u),
            'direction_error_deg': error if np.isfinite(error) else None,
            'min_coherence': row['min_coherence'],
            'local_contrast_db': row['local_contrast_db'],
        })
    holdouts = [m for m in measurements if m['role'] == 'heldout' and m['pose'] != 'center_repeat']
    holdout_errors = [m['direction_error_deg'] for m in holdouts]
    center_repeat = next(m for m in measurements if m['pose'] == 'center_repeat')
    all_errors = holdout_errors + [center_repeat['direction_error_deg']]
    if any(e is None for e in all_errors):
        raise AngularCalibrationError('Angular fit predicts an invalid (out-of-field) direction')
    max_heldout = max(holdout_errors)
    heldout_rms = float(np.sqrt(np.mean(np.square(holdout_errors))))
    center_drift = center_repeat['direction_error_deg']
    if max_heldout > max_heldout_error_deg or center_drift > max_center_drift_deg:
        raise AngularCalibrationError(
            f'Held-out angular validation failed: maximum off-center error '
            f'{max_heldout:.2f} deg (limit {max_heldout_error_deg:.2f}), '
            f'return-to-center error {center_drift:.2f} deg '
            f'(limit {max_center_drift_deg:.2f}).')

    if mode == 'empirical':
        # Empirical geometry overrides physical coordinates only with explicit
        # user selection, and stays marked unverified as physical phase centers.
        new_geometry = np.vstack([np.zeros(2), fitted])
        calibrated = replace(config, geometry_mm=None,
                             geometry_wavelengths=new_geometry.tolist(), mount_roll_deg=0.,
                             geometry_label='Empirical phase response from held-out angular sweep; NOT physical antenna positions',
                             angle_matrix_real=None, angle_matrix_imag=None,
                             gains_real=gains.real.tolist(), gains_imag=gains.imag.tolist(),
                             verified=False, calibration_id=f'angular-empirical-{uuid.uuid4().hex[:12]}')
    else:
        calibrated = replace(config, angle_matrix_real=None, angle_matrix_imag=None,
                             gains_real=gains.real.tolist(), gains_imag=gains.imag.tolist(),
                             verified=False, calibration_id=f'angular-physical-{uuid.uuid4().hex[:12]}')
    calibrated.validate()
    results = {
        'schema': 1, 'status': 'heldout_passed', 'mode': mode,
        'calibration_id': calibrated.calibration_id,
        'fit_pose_names': list(required_fit),
        'heldout_pose_names': list(required_holdout),
        'fitted_effective_baselines_wavelengths_rx2_rx3': fitted.tolist(),
        'nominal_baselines_wavelengths_rx2_rx3': nominal.tolist(),
        'max_physical_baseline_delta_wavelengths': nominal_delta,
        'training_max_phase_residual_deg': training_max_phase_residual_deg,
        'heldout_max_error_deg': float(max_heldout),
        'heldout_rms_error_deg': heldout_rms,
        'center_repeat_error_deg': float(center_drift),
        'measurements': measurements,
        'gains_phase_correction_deg': [0., *np.degrees(np.angle(gains[1:])).tolist()],
        'qualification': 'Validated only at surveyed sweep poses/ranges; not room or surface reconstruction',
        'geometry_verified': False,
    }
    return calibrated, results


def calibrate_sweep(root, output, *, mode='physical', report_path=None):
    """Recompute sweep measurements from raw ADC, then save only on pass."""
    from .sweep import analyze_sweep
    root = Path(root)
    config = Config.load(root / 'config.json')
    report = analyze_sweep(root)
    destination = Path(output)
    report_destination = Path(report_path) if report_path else destination.with_suffix('.validation.json')
    try:
        calibrated, validation = fit_angular_report(report, config, mode=mode)
    except AngularCalibrationError as exc:
        failure = {
            'schema': 1, 'status': 'rejected', 'reason': str(exc),
            'sweep': str(root), 'mode': mode,
            'no_config_written': True,
        }
        report_destination.parent.mkdir(parents=True, exist_ok=True)
        report_destination.write_text(json.dumps(failure, indent=2), encoding='utf-8')
        raise
    if destination.resolve() == (root / 'config.json').resolve():
        raise AngularCalibrationError('Refusing to overwrite sweep acquisition config')
    if destination.exists():
        raise AngularCalibrationError(f'Refusing to overwrite existing config: {destination}')
    if destination.resolve() == report_destination.resolve():
        raise AngularCalibrationError('Validation report and output config must have different paths')
    destination.parent.mkdir(parents=True, exist_ok=True)
    report_destination.parent.mkdir(parents=True, exist_ok=True)
    validation['sweep'] = str(root)
    validation['output_config'] = str(destination)
    report_destination.write_text(json.dumps(validation, indent=2), encoding='utf-8')
    calibrated.save(destination)
    return validation


def main(argv=None):
    p = argparse.ArgumentParser(description='Calibrate RX angular response using independently held-out horizontal and vertical sweep positions')
    p.add_argument('sweep', help='Guided sweep directory created by python -m radar sweep')
    p.add_argument('--output', required=True, help='New validated config JSON destination')
    p.add_argument('--report', help='Validation report JSON destination (default: next to config)')
    p.add_argument('--mode', choices=['physical', 'empirical'], default='physical',
                   help='physical=phase-only against nominal array; empirical=explicit fitted effective baselines')
    args = p.parse_args(argv)
    try:
        result = calibrate_sweep(args.sweep, args.output, mode=args.mode, report_path=args.report)
    except AngularCalibrationError as e:
        p.exit(2, f'Calibration REJECTED: {e}\n')
    print(json.dumps({key: result[key] for key in ('status','mode','heldout_rms_error_deg',
          'heldout_max_error_deg','center_repeat_error_deg','output_config')}, indent=2))


if __name__ == '__main__':
    main()
