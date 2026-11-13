"""Reference-free stationary-return audit; labels used only after detection.

python -m tools.audit_direct_obstacles recordings artifacts/direct-obstacle-01
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from radar.config import Config
from radar.door_check import _session
from radar.storage import replay


def candidates(power, threshold_db):
    """Fixed local-peak + noise-reference test; no scene or distance input.

    power: range-bin by RX. Guard +/-1, references offsets 2..5 on both
    sides. Median-reference threshold is an engineering contrast, not a
    calibrated CFAR false-alarm probability. Require support on >=2 RX.
    """
    count = len(power)
    selected = []
    contrast = np.full_like(power, np.nan, dtype=float)
    mean = power.mean(axis=1)
    for b in range(1, count-1):
        refs = [j for j in range(max(1, b-5), min(count-1, b+6)) if abs(j-b) >= 2]
        if len(refs) < 3:
            continue
        floor = np.maximum(np.median(power[refs], axis=0), 1e-12)
        contrast[b] = 10*np.log10(np.maximum(power[b], 1e-12)/floor)
        if mean[b] >= mean[b-1] and mean[b] > mean[b+1] and np.sum(contrast[b] >= threshold_db) >= 2:
            selected.append(b)
    return selected, contrast


def audit(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    sessions, skipped, rows = {}, {}, []
    thresholds = (3., 6., 10.)  # sensitivity analysis, not tuned per door
    plot_data = {}
    for manifest_path in sorted(root.glob('*/door-check.json')):
        experiment = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not manifest.get('complete'):
            skipped[experiment.name] = 'incomplete'
            continue
        config = Config.load(experiment/'config.json')
        spacing = 299792458.*config.sample_rate_hz/(2*config.slope_hz_s*config.samples)
        # Coordinates are nominal source-derived, not empirical fitted offsets.
        expected_bin = manifest['measured_glass_distance_m']/spacing
        roi = [b for b in range(1,config.samples//2) if abs(b-expected_bin) <= 1]
        for i in range(1, manifest['repeats']+1):
            for state in ('open','closed'):
                path = experiment/f'{state}-{i:02d}'
                health = _session(path, config)
                raw = np.array([f.adc for f in replay(path)], dtype=float)[:, config.discard_chirps:]
                raw -= raw.mean(axis=2, keepdims=True)
                window = np.hanning(config.samples)
                spectra = np.fft.rfft(raw*window[None,None,:,None], axis=2)*(2/window.sum())
                frame_power = np.mean(abs(spectra)**2, axis=1)
                chirp_coherence = np.abs(np.mean(spectra,axis=1))**2/np.maximum(frame_power,1e-12)
                # Cross-RX phase consistency across chirps. High coherence can
                # belong to a wall/clutter too, so it is diagnostic, not identity.
                cross = []
                for rx in (1,2):
                    cross.append(abs(np.mean(spectra[:,:,:,rx]*np.conj(spectra[:,:,:,0]),axis=1)) /
                                 np.sqrt(np.maximum(frame_power[:,:,rx]*frame_power[:,:,0],1e-24)))
                cross = np.stack(cross,axis=-1)
                # Oversampling only locates spectral maxima more finely; it
                # does not add independent range resolution or isolate paths.
                fine = np.fft.rfft(raw*window[None,None,:,None], n=config.samples*8, axis=2)*(2/window.sum())
                fine_power = np.median(np.mean(abs(fine)**2, axis=1), axis=0)
                fine_axis = np.arange(len(fine_power))/8
                fine_peaks = []
                for rx in range(3):
                    peaks = [b for b in range(8,len(fine_power)-8)
                             if fine_power[b,rx] >= fine_power[b-1,rx]
                             and fine_power[b,rx] > fine_power[b+1,rx]]
                    fine_peaks.append([dict(native_bin=float(fine_axis[b]),
                        nominal_m=float(fine_axis[b]*spacing), power_db=float(10*np.log10(max(fine_power[b,rx],1e-12))))
                        for b in peaks if abs(fine_axis[b]-expected_bin) <= 1])
                del fine
                n = max(1, int(np.ceil(1/config.frame_interval_s)))
                med_power = np.median(frame_power,axis=0)
                stats = {}
                for threshold in thresholds:
                    decisions = []
                    for start in range(0,len(frame_power)-n+1,n):
                        p = np.median(frame_power[start:start+n],axis=0)
                        bins, contrasts = candidates(p,threshold)
                        matches = [b for b in bins if b in roi]
                        decisions.append(dict(start_frame=start, bins=bins, near_pane_bins=matches))
                        rows.append(dict(experiment=experiment.name, session=path.name, state_label=state,
                                         threshold_db=threshold, start_frame=start,
                                         candidate_bins=';'.join(map(str,bins)),
                                         near_measured_pane=bool(matches)))
                    stats[str(threshold)] = dict(windows=len(decisions),
                        near_pane_windows=sum(bool(d['near_pane_bins']) for d in decisions), decisions=decisions)
                session_key = f'{experiment.name}/{path.name}'
                sessions[session_key] = dict(raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                    frames=health['frames'], state_label=state,
                    measured_distance_m=manifest['measured_glass_distance_m'], nominal_bin_spacing_m=spacing,
                    expected_fractional_bin=expected_bin, scoring_bins=roi,
                    median_power_db_per_rx=(10*np.log10(np.maximum(med_power,1e-12))).tolist(),
                    median_chirp_coherence_per_rx=np.median(chirp_coherence,axis=0).tolist(),
                    median_cross_rx_coherence=np.median(cross,axis=0).tolist(), detection=stats)
                sessions[session_key]['interpolated_local_maxima_near_pane_per_rx'] = fine_peaks
                plot_data[session_key] = (10*np.log10(np.maximum(med_power.mean(axis=1),1e-12)),expected_bin)
    summary = {}
    for experiment in sorted({k.split('/')[0] for k in sessions}):
        summary[experiment] = {}
        for state in ('open','closed'):
            summary[experiment][state] = {}
            for threshold in thresholds:
                values = [s['detection'][str(threshold)] for k,s in sessions.items()
                          if k.startswith(experiment+'/') and s['state_label']==state]
                summary[experiment][state][str(threshold)] = dict(
                    near_pane_windows=sum(v['near_pane_windows'] for v in values),
                    windows=sum(v['windows'] for v in values))
    report = dict(schema=1, detector='Reference-free fixed local contrast; >=2 RX; native-bin local peak',
                  thresholds_db=thresholds, summary=summary, sessions=sessions, skipped=skipped,
                  interpretation='Measured positions used ONLY for scoring/diagnostics, never for candidate selection. '
                  'Open scenes contain other real obstacles. Pane-neighborhood hits in open controls demonstrate '
                  'association ambiguity, not that all such detections are false objects. '
                  'Range scale/phase calibration unverified; failure of this audit does not prove impossibility '
                  'of all radar algorithms. All results are retrospective development evidence.')
    (output/'audit.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    with (output/'windows.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig=Figure(figsize=(11,3.4*len(summary)),tight_layout=True); FigureCanvasAgg(fig)
    for axis,experiment in zip(np.atleast_1d(fig.subplots(len(summary),1)),summary):
        for state,color in [('open','tab:blue'),('closed','tab:orange')]:
            for i in range(1,4):
                power,expected=plot_data[f'{experiment}/{state}-{i:02d}']
                axis.plot(power,color=color,alpha=.65,label=state if i==1 else None)
        axis.axvline(expected,color='black',linestyle='--',label='Measured pane / nominal scale')
        axis.set(title=experiment,xlabel='Native range FFT bin',ylabel='Median power (dB ADC²)')
        axis.legend()
    fig.savefig(output/'profiles.png',dpi=150)
    print(json.dumps(summary,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('root'); p.add_argument('output')
    args=p.parse_args(); audit(args.root,args.output)
