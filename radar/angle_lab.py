"""Offline range/azimuth evaluation and elevation identifiability audit.

Run from radar-demo:
    python -m radar.angle_lab recordings/box-angle-01 \
        --config configs/exploratory-roll90-phase.json \
        --output artifacts/angle-lab-01

Does not edit source recordings/configurations or claim verified elevation.
Uses the original quality gates, raw ADC and paired complex backgrounds.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def wrap(rad):
    return np.angle(np.exp(1j * np.asarray(rad, dtype=float)))


def raw_model_phase(config, xyz):
    """Expected relative phase in the actual raw-channel domain.

    The vendor angle matrix is non-diagonal: predicting phases from RX
    geometry alone is inconsistent with this repository's beamformer.
    Gain corrections multiply the raw signal AFTER angle-matrix inversion.
    """
    pos = np.asarray(xyz, dtype=float)
    if pos.shape != (3,) or pos[1] <= 0 or not np.isfinite(pos).all():
        raise ValueError('Invalid target coordinate')
    direction = pos[[0, 2]] / np.linalg.norm(pos)
    steering = np.exp(2j * np.pi * (config.array_geometry @ direction))
    received = np.linalg.solve(config.angle_matrix, steering) * config.gains
    if abs(received[0]) < 1e-12:
        raise ValueError('Singular reference receiver')
    return np.angle(received[1:] * np.conj(received[0]))


def infer_azimuth_rx2(phase_rad, anchor_phase_rad, anchor_xyz, config,
                       *, forward_m=None, z_m=None, limit_deg=25.0, step_deg=0.05):
    """Invert only RX2-RX1 horizontal phase difference about a known anchor.

    No measured target azimuth is supplied to the inversion. The known height
    of the fixed SUPPORT (not a measured radar elevation) is used for this
    controlled horizontal sweep. Limit to local unambiguous field of view.
    """
    anchor = np.asarray(anchor_xyz, float)
    forward = float(anchor[1] if forward_m is None else forward_m)
    z = float(anchor[2] if z_m is None else z_m)
    if forward <= 0 or limit_deg <= 0 or step_deg <= 0:
        raise ValueError('Invalid inversion bounds')
    angles = np.linspace(-limit_deg, limit_deg, round(2 * limit_deg / step_deg) + 1)
    target_x = forward * np.tan(np.radians(angles))
    actual_delta = wrap(float(phase_rad) - float(anchor_phase_rad))
    reference_model = raw_model_phase(config, anchor)[0]
    distances = np.sqrt(target_x**2 + forward**2 + z**2)
    directions = np.vstack([target_x / distances, np.full_like(target_x, z) / distances])
    virtual = np.exp(2j * np.pi * (config.array_geometry @ directions))
    raw = np.linalg.solve(config.angle_matrix, virtual) * config.gains[:, None]
    predicted = wrap(np.angle(raw[1] * np.conj(raw[0])) - reference_model)
    residual = np.abs(wrap(actual_delta - predicted))
    index = int(np.argmin(residual))
    # Guard against ambiguous / flat response rather than selecting a random angle.
    end_to_end = abs(float(wrap(predicted[-1] - predicted[0])))
    if end_to_end < np.radians(3):
        raise ValueError('RX2 response is nearly insensitive to horizontal angle')
    return float(angles[index]), float(np.degrees(residual[index]))


def infer_elevation_rx3(phase_rad, anchor_phase_rad, anchor_xyz, config,
                        *, forward_m=None, max_abs_elevation_deg=15., step_deg=.05):
    """Candidate vertical estimate from RX3-RX1, assuming target azimuth zero.

    Experimental only: anchor known, no multipath/height centroid modeling.
    A low numerical phase residual is NOT independent accuracy validation.
    """
    anchor = np.asarray(anchor_xyz, float)
    forward = float(anchor[1] if forward_m is None else forward_m)
    if forward <= 0 or max_abs_elevation_deg <= 0:
        raise ValueError('Invalid elevation model bounds')
    angles=np.linspace(-max_abs_elevation_deg,max_abs_elevation_deg,
                       round(2*max_abs_elevation_deg/step_deg)+1)
    vertical=forward*np.tan(np.radians(angles))
    distance=np.sqrt(forward*forward+vertical*vertical)
    direction=np.vstack([np.zeros_like(vertical),vertical/distance])
    virtual=np.exp(2j*np.pi*(config.array_geometry@direction))
    raw=np.linalg.solve(config.angle_matrix,virtual)*config.gains[:,None]
    model_ref=raw_model_phase(config,anchor)[1]
    prediction=wrap(np.angle(raw[2]*np.conj(raw[0]))-model_ref)
    observed=wrap(float(phase_rad)-float(anchor_phase_rad))
    err=np.abs(wrap(observed-prediction))
    index=int(np.argmin(err))
    return {'elevation_deg':float(angles[index]),
            'height_z_m':float(vertical[index]),
            'phase_fit_residual_deg':float(np.degrees(err[index])),
            'search_boundary_hit':bool(index==0 or index==len(angles)-1)}


def circular_spread_rad(phases):
    phases = np.asarray(phases)
    if not len(phases):
        return float('nan')
    r = np.abs(np.mean(np.exp(1j * phases)))
    return float(np.sqrt(max(0., -2 * np.log(max(r, 1e-12)))))


def _frame_spectra(folder, config):
    from .background import SpectralBackground
    from .processing import range_fft
    from .storage import replay
    folder = Path(folder)
    snapshot = folder / 'spectral-background.npz'
    if not snapshot.is_file():
        raise FileNotFoundError(f'Missing per-pose background: {snapshot}')
    bg = SpectralBackground.from_path(snapshot, config)
    arrays = []
    for frame in replay(folder):
        if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
            raise ValueError(f'Firmware mismatch in {folder}')
        arrays.append(bg.subtract(range_fft(frame.adc, config), config))
    if len(arrays) < 10:
        raise ValueError(f'Too few frames in {folder}')
    return np.asarray(arrays)


def _stats_at_bin(spectra, k):
    """Phase/covariance from raw per-frame complex samples (no angle mixing)."""
    samples = spectra[:, :, k, :]
    frame_cross = np.mean(samples[:, :, 1:] * samples[:, :, :1].conj(), axis=1)
    cross = frame_cross.mean(axis=0)
    powers = np.mean(abs(samples)**2, axis=(0, 1))
    coherence = np.abs(cross) / np.sqrt(np.maximum(powers[1:] * powers[0], 1e-24))
    return {
        'phase_rad': np.angle(cross),
        'coherence': coherence,
        'phase_spread_deg': np.degrees([circular_spread_rad(np.angle(frame_cross[:, k]))
                                        for k in range(2)]),
        'frame_cross': frame_cross,
    }


def _bootstrap_azimuth(s, anchor_s, anchor_xyz, config, y, z, *, reps=100):
    """Frame resampling quantifies only repeat noise, not calibration biases."""
    rng = np.random.default_rng(20261112)
    estimates = []
    for _ in range(reps):
        x = s['frame_cross'][rng.integers(0, len(s['frame_cross']), len(s['frame_cross'])), 0].mean()
        ref = anchor_s['frame_cross'][rng.integers(0, len(anchor_s['frame_cross']), len(anchor_s['frame_cross'])), 0].mean()
        az, _ = infer_azimuth_rx2(np.angle(x), np.angle(ref), anchor_xyz, config,
                                  forward_m=y, z_m=z, step_deg=0.2)
        estimates.append(az)
    return [float(x) for x in np.percentile(estimates, [2.5, 97.5])]


def _elevation_diagnostic(rows, stats, config, bins, ref_name='center_repeat'):
    """Compare vertical phase changes to a known physical model at each bin.

    A different support for every vertical height prevents separation of
    elevation sensitivity from support-dependent target coupling. Report this
    as a structural confound even if a pair of points happens to fit.
    """
    center_names = [n for n, row in rows.items() if abs(float(row['xyz_m'][0])) < 1e-7]
    center_names.sort(key=lambda n: rows[n]['xyz_m'][2])
    ref = rows[ref_name]
    ref_support = ref['support']
    diagnostic = []
    for k in bins:
        ref_phase = stats[ref_name][k]['phase_rad']
        ref_model = raw_model_phase(config, ref['xyz_m'])
        for name in center_names:
            pose = rows[name]
            actual_phase_delta = np.degrees(wrap(stats[name][k]['phase_rad'] - ref_phase))
            modeled_delta = np.degrees(wrap(raw_model_phase(config, pose['xyz_m']) - ref_model))
            error = np.degrees(wrap(np.radians(actual_phase_delta - modeled_delta)))
            vert = infer_elevation_rx3(stats[name][k]['phase_rad'][1],
                stats[ref_name][k]['phase_rad'][1], ref['xyz_m'], config,
                forward_m=float(pose['xyz_m'][1]))
            diagnostic.append({
                'name': name, 'bin': k,
                'candidate_rx3_elevation':vert,
                'candidate_z_error_m':vert['height_z_m']-float(pose['xyz_m'][2]),
                'range_m': float(config.ranges[k]),
                'height_m': float(pose['xyz_m'][2]),
                'support': pose['support'],
                'accepted_original_gate': bool(pose['accepted']),
                'observed_delta_deg_rx2_rx3': actual_phase_delta.tolist(),
                'predicted_delta_deg_rx2_rx3': modeled_delta.tolist(),
                'phase_model_error_deg_rx2_rx3': error.tolist(),
                'coherence_rx2_rx3': stats[name][k]['coherence'].tolist(),
                'frame_phase_spread_deg_rx2_rx3': stats[name][k]['phase_spread_deg'].tolist(),
            })
    independent_pairs = [(a, b) for i, a in enumerate(center_names) for b in center_names[i+1:]
                         if rows[a]['support'] == rows[b]['support']
                         and abs(rows[a]['xyz_m'][2] - rows[b]['xyz_m'][2]) > 0.01]
    # Fit two accepted raised positions, then *predict* center without changing
    # its measured phase. This directly tests the seductive two-point fit.
    checks = []
    for k in bins:
        lo, hi = stats['check_up'][k], stats['up'][k]
        u_lo = float(rows['check_up']['direction_right_up'][1])
        u_hi = float(rows['up']['direction_right_up'][1])
        if abs(u_hi - u_lo) < 1e-8:
            continue
        for channel in (0, 1):
            slope = float(wrap(hi['phase_rad'][channel] - lo['phase_rad'][channel]) / (u_hi-u_lo))
            u_ref = float(rows[ref_name]['direction_right_up'][1])
            predicted_at_ref = lo['phase_rad'][channel] + slope * (u_ref-u_lo)
            error = float(np.degrees(wrap(stats[ref_name][k]['phase_rad'][channel] - predicted_at_ref)))
            checks.append({'bin': k, 'rx': channel+2,
                           'empirical_slope_deg_per_direction_cosine': float(np.degrees(slope)),
                           'heldout_center_phase_error_deg': error})
    return {
        'structurally_identifiable': len(independent_pairs) > 0,
        'same_support_different_height_pairs': independent_pairs,
        'reason': ('No measurements have two different heights on the same support; '
                   'pose-dependent support/bottle interactions cannot be separated from elevation.'),
        'range_bin_checks': diagnostic,
        'two_raised_pose_extrapolation': checks,
        'recommendation': 'Do not claim calibrated physical Z from this sweep.',
    }


def analyze(root, config, output, *, anchor='center_repeat', max_az_deg=25):
    from .config import Config
    from .processing import interpolated_range, noise_threshold
    root, output = Path(root), Path(output)
    manifest = json.loads((root / 'sweep.json').read_text(encoding='utf-8'))
    report = json.loads((root / 'sweep-report.json').read_text(encoding='utf-8'))
    if manifest.get('kind') != 'measured-height-paired-background':
        raise ValueError('Expected box-angle sweep with per-pose backgrounds')
    cfg = Config.load(config)
    original = Config.load(root / 'config.json')
    for key in ('profile_id','samples','chirps','sample_rate_hz','slope_hz_s','carrier_hz','discard_chirps'):
        if getattr(original,key) != getattr(cfg,key):
            raise ValueError(f'Pilot config changed acquisition parameter {key}')
    if cfg.verified:
        raise ValueError('Refusing to treat this experimental pilot as verified')
    rows = {r['name']:r for r in report['poses']}
    poses = {p['name']:p for p in manifest['poses']}
    if set(rows) != set(poses) or anchor not in rows or not rows[anchor]['accepted']:
        raise ValueError('Missing/invalid sweep report or reference pose')
    for name in rows:
        if not np.allclose(rows[name]['xyz_m'], poses[name]['xyz_m']):
            raise ValueError(f'Survey positions disagree in {name}')
    reference = rows[anchor]
    support = reference['support']
    if not any(n in rows for n in ('check_left','check_right')):
        raise ValueError('No horizontal holdouts')
    k0 = int(reference['range_bin'])
    bins = [k for k in (k0-1,k0,k0+1) if 2 <= k < len(cfg.ranges)-1]
    spectra_by_name = {name: _frame_spectra(root/name, cfg) for name in rows}
    stats = {name:{k:_stats_at_bin(spectra,k) for k in bins} for name,spectra in spectra_by_name.items()}
    anchor_phase = float(stats[anchor][k0]['phase_rad'][0])
    horizontal=[]
    for name, row in rows.items():
        if row['support'] != support:
            continue
        spectra = spectra_by_name[name]
        signal = stats[name][k0]
        power = np.mean(abs(spectra)**2, axis=(0,1,3))
        observed_contrast = float(10*np.log10(max(power[k0],1e-12) / max(noise_threshold(power,1)[k0],1e-12)))
        az, phase_fit = infer_azimuth_rx2(signal['phase_rad'][0], anchor_phase,
                                         reference['xyz_m'], cfg, forward_m=float(row['xyz_m'][1]),
                                         z_m=float(reference['xyz_m'][2]), limit_deg=max_az_deg)
        measured_range = float(interpolated_range(power,k0,cfg))
        tanaz = np.tan(np.radians(az))
        z_per_y = float(reference['xyz_m'][2] / reference['xyz_m'][1])
        forward = measured_range / np.sqrt(1+tanaz*tanaz+z_per_y*z_per_y)
        estimated_x = float(forward * tanaz)
        true_x,true_y,_ = row['xyz_m']
        holdout = (name in ('check_left','check_right'))
        horizontal.append({
            'name':name,'accepted_original_gate':bool(row['accepted']),
            'validation_holdout':holdout, 'reference_pose':name==anchor,
            'expected_xyz_m':row['xyz_m'],
            'estimated_range_azimuth_only':{'x_m':estimated_x,'y_m':float(forward),
                                              'range_m':measured_range,'azimuth_deg':az},
            'reference_z_m_assumed_not_estimated':float(reference['xyz_m'][2]),
            'x_error_m':float(estimated_x-true_x),
            'azimuth_error_deg':float(az-np.degrees(np.arctan2(true_x,true_y))),
            'phase_residual_deg':phase_fit,
            'measured_coherence_rx2':float(signal['coherence'][0]),
            'measured_contrast_db':observed_contrast,
            'within_capture_bootstrap_azimuth_interval_95_deg':_bootstrap_azimuth(
                signal,stats[anchor][k0],reference['xyz_m'],cfg,float(row['xyz_m'][1]),
                float(reference['xyz_m'][2])) if name != anchor and row['accepted'] else None,
        })
    elev = _elevation_diagnostic(rows,stats,cfg,bins,anchor)
    accepted_heldouts = [r for r in horizontal if r['validation_holdout'] and r['accepted_original_gate']]
    summary = {
        'kind':'experimental-offline-range-azimuth-and-elevation-audit',
        'verified':False, 'method':'RX2-RX1 raw-domain physical steering LUT anchored to accepted center_repeat',
        'reference':anchor, 'range_bin':k0, 'config':str(config),
        'horizontal':horizontal,
        'accepted_horizontal_holdouts':len(accepted_heldouts),
        'heldout_abs_azimuth_error_deg':[abs(p['azimuth_error_deg']) for p in accepted_heldouts],
        'elevation':elev,
        'limitations':['Azimuth errors from same-scene validation, not independent scenes or calibrated metrology.',
                       'Anchor has a known position; uncalibrated global phase is removed by relative phase.',
                       'Horizontal estimator uses known support height, not estimated elevation.',
                       'Limited 2m range and 0.05-degree inversion grid; bottle is an extended scatterer.',
                       'Per-frame bootstrap intervals omit systematic geometry, support and scene errors.',
                       'Low-contrast original failures are displayed as diagnostics, not successful detections.',
                       'Vertical support changes confound geometry; no verified 3D calibration.'],
    }
    output.mkdir(parents=True,exist_ok=False)
    (output/'range_azimuth.json').write_text(json.dumps(summary,indent=2)+'\n', encoding='utf-8')
    _plot_results(summary, output)
    return summary


def _plot_results(summary, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = summary['horizontal']
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    ax=axes[0]
    for row in rows:
        truth=np.asarray(row['expected_xyz_m'])
        est=row['estimated_range_azimuth_only']
        color='tab:green' if row['accepted_original_gate'] else 'tab:orange'
        marker='o' if row['accepted_original_gate'] else 'x'
        ax.scatter(truth[0],truth[1],marker='+',s=90,color='black')
        ax.scatter(est['x_m'],est['y_m'],marker=marker,s=60,color=color)
        ax.plot([truth[0],est['x_m']],[truth[1],est['y_m']],color=color,alpha=.45)
        ax.annotate(row['name'],(est['x_m'],est['y_m']),fontsize=8,xytext=(3,4),textcoords='offset points')
    ax.set(xlabel='Right X (m)',ylabel='Forward Y (m)',title='2D target locations (black + = survey; green = accepted)')
    ax.grid(alpha=.25);ax.set_aspect('equal',adjustable='datalim')
    ax=axes[1]
    names=[r['name'] for r in rows]
    errs=[r['azimuth_error_deg'] for r in rows]
    ax.bar(range(len(rows)),errs,color=['tab:green' if r['accepted_original_gate'] else 'tab:orange' for r in rows])
    ax.set_xticks(range(len(rows)),names,rotation=35,ha='right')
    ax.axhline(0,color='black',lw=.6)
    ax.set(ylabel='Azimuth error (deg)',title='Reference-referenced RX2 azimuth (not 3D)')
    ax.grid(axis='y',alpha=.25)
    fig.suptitle('Experimental only | red/orange = below original quality gate | Z NOT estimated')
    fig.savefig(out/'range_azimuth.png',dpi=150)
    plt.close(fig)
    fig, axes=plt.subplots(1,3,figsize=(15,4.5),layout='constrained',sharey=True)
    for ax,k in zip(axes,sorted(set(r['bin'] for r in summary['elevation']['range_bin_checks']))):
        subset=[r for r in summary['elevation']['range_bin_checks'] if r['bin']==k]
        for row in subset:
            actual = row['predicted_delta_deg_rx2_rx3'][1]
            measured=row['observed_delta_deg_rx2_rx3'][1]
            color='tab:green' if row['accepted_original_gate'] else 'tab:orange'
            ax.scatter(row['height_m']*100,actual,marker='+',color='black',s=60)
            ax.scatter(row['height_m']*100,measured,color=color,s=50)
            ax.plot([row['height_m']*100]*2,[actual,measured],color=color,alpha=.45)
            ax.annotate(row['name'],(row['height_m']*100,measured),fontsize=7,xytext=(3,3),textcoords='offset points')
        ax.set(xlabel='Bottle center Z relative to radar (cm)',title=f'RX3 bin {k} ({subset[0]["range_m"]:.2f} m)')
        ax.axhline(0,color='black',lw=.6);ax.grid(alpha=.3)
    axes[0].set_ylabel('Phase difference vs center-repeat (deg)')
    fig.suptitle('Vertical phase: measured colors vs physical-model black + | different supports confounded')
    fig.savefig(out/'elevation_audit.png',dpi=150)
    plt.close(fig)

    fig, ax=plt.subplots(figsize=(7,5),layout='constrained')
    center_bin=summary['range_bin']
    diagnostic=[r for r in summary['elevation']['range_bin_checks'] if r['bin']==center_bin]
    for p in diagnostic:
        truth=p['height_m']*100
        candidate=p['candidate_rx3_elevation']['height_z_m']*100
        color='tab:green' if p['accepted_original_gate'] else 'tab:orange'
        ax.scatter(truth,candidate,color=color,s=55,marker='o' if p['accepted_original_gate'] else 'x')
        ax.annotate(p['name'],(truth,candidate),fontsize=9,xytext=(4,4),textcoords='offset points')
    bounds=[-65,65]
    ax.plot(bounds,bounds,color='black',ls='--',lw=1,label='Perfect estimate')
    ax.set(xlim=bounds,ylim=bounds,xlabel='Measured bottle center Z (cm)',
           ylabel='Experimental RX3-inferred Z (cm)',
           title='Elevation inversion attempt — bin 6, +90° model')
    ax.grid(alpha=.3);ax.legend()
    fig.savefig(out/'elevation_candidate.png',dpi=150)
    plt.close(fig)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('sweep')
    p.add_argument('--config',default='configs/exploratory-roll90-phase.json')
    p.add_argument('--output',default='artifacts/angle-lab-01')
    a=p.parse_args(argv)
    report=analyze(a.sweep,a.config,a.output)
    print('RX2 horizontal estimator (quality-gated results):')
    for row in report['horizontal']:
        status='PASS' if row['accepted_original_gate'] else 'WEAK'
        r=row['estimated_range_azimuth_only']
        print(f"{row['name']:15} {status:4} az {r['azimuth_deg']:+7.2f}° "
              f"X={r['x_m']:+.3f} m | az err {row['azimuth_error_deg']:+.2f}°")
    errs=report['heldout_abs_azimuth_error_deg']
    if errs:
        print(f'Accepted horizontal held-out mean absolute azimuth error: {np.mean(errs):.2f}° ({len(errs)} poses)')
    print('Elevation independent same-support height comparisons:',
          len(report['elevation']['same_support_different_height_pairs']))
    print('Elevation extrapolation check (raised pair -> center):')
    for r in report['elevation']['two_raised_pose_extrapolation']:
        if r['rx']==3:
            print(f"  RX3 bin {r['bin']}: held-out center phase error {r['heldout_center_phase_error_deg']:+.1f}°")
    print('RX3 experimental elevation inversion at target range bin:')
    for r in report['elevation']['range_bin_checks']:
        if r['bin']==report['range_bin']:
            z=r['candidate_rx3_elevation']['height_z_m']
            print(f"  {r['name']:14} true Z={r['height_m']:+.3f} m, estimated Z={z:+.3f} m, "
                  f"error={r['candidate_z_error_m']:+.3f} m")
    print(f'Wrote {a.output}/range_azimuth.json, range_azimuth.png, elevation_audit.png, elevation_candidate.png')
    print('NOT VERIFIED: elevation support confounding remains; no calibration config overwritten.')


if __name__=='__main__':
    main()
