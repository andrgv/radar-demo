"""Offline fitted-signal confidence experiment. Never imported by live GUI.

Twenty empty frames fit the reference; ten different frames calibrate projected
energy. Entire acquisition sessions are excluded from threshold selection.
Distance labels only score/select engineering thresholds, never fit frequency.
"""
import argparse
from collections import deque
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline, Detector, Continuity, power
from radar_min.associated_fit import AssociatedFit
from tools.fit_range_signal import traces
from tools.evaluate_association import measure


def datasets():
    for run in ('350-a', '100-a', '350-b'):
        group = 'hpf'+run
        root = Path('recordings')
        yield group, root/(group+'-empty-before'), [
            (root/(group+'-'+name), label, skip)
            for name, label, skip in [('empty-before', None, 30),
                ('30cm', .3, 0), ('40cm', .4, 0), ('40cm-repeat', .4, 0),
                ('50cm', .5, 0), ('empty-after', None, 0)]]
    for session, cases in [
        ('144515-340260', [('live-003', None), ('live-004', .3), ('live-005', .5)]),
        ('153737-539230', [('live-002', None), ('live-003', .3), ('live-004', .4), ('live-005', .5), ('live-006', None)]),
        ('155623-972019', [('live-002', .2), ('live-003', None), ('live-004', .4), ('live-005', .5)])]:
        root = Path('recordings')/('gui-20261101-'+session)
        yield session, root/'empty-001', [(root/'empty-001', None, 30)]+[(root/n, d, 0) for n,d in cases]


class FitEvidence:
    def __init__(self, config, empty):
        if len(empty) < 30:
            raise ValueError('Need 20 reference and 10 separate calibration frames')
        self.c = config
        self.fit = AssociatedFit(config)
        self.reference = np.mean([traces(f, config) for f in empty[:20]], axis=0)
        # Worst projected energy anywhere on the search grid, not only at a
        # favorable frequency. Calibration frames do not fit the reference.
        self.noise = max(max(self.spectrum(f)[0]) for f in empty[20:30])
        self.noise = max(float(self.noise), 1e-12)

    def spectrum(self, frame):
        power(frame, self.c)
        x = traces(frame, self.c)-self.reference
        x -= x.mean(axis=1, keepdims=True)
        projection = np.einsum('ts,gsb->gtb', x, self.fit.q, optimize=True)
        per_rx = np.sum(projection.reshape(len(self.fit.grid), -1, 3, 2)**2, axis=(1,3))
        return per_rx.sum(axis=1), per_rx, float(np.sum(x*x)), x

    def features(self, frame, candidate_bin, qualified_bins):
        scores, rx, energy, x = self.spectrum(frame)
        result = self.fit.fit_associated(x, candidate_bin, qualified_bins)
        value = result['range_m']
        if value is None:
            return dict(candidate=None, gain=0., purity=0., rx_spread=999.)
        k = int(np.argmin(abs(self.fit.grid-value)))
        rx_peaks = self.fit.grid[np.argmax(rx, axis=0)]
        return dict(candidate=value, gain=float(scores[k]/self.noise),
                    purity=float(scores[k]/max(energy,1e-12)),
                    rx_spread=float(np.max(abs(rx_peaks-value))))


def gate(features, thresholds, median_window=1):
    """Causal, current-frame acceptance; rejection clears all range history."""
    gain, purity, spread = thresholds[:3]
    stability = thresholds[3] if len(thresholds)>3 else None
    candidates = deque(maxlen=5)
    history = deque(maxlen=median_window)
    hits = 0
    values = []
    for f in features:
        if f.get('valid', True) and f['candidate'] is not None:
            candidates.append(f['candidate'])
        else:
            candidates.clear()
        stable = stability is None or (len(candidates)==5 and max(candidates)-min(candidates)<=stability)
        ok = (f.get('valid', True) and f['candidate'] is not None
              and f['gain'] >= gain and f['purity'] >= purity
              and f['rx_spread'] <= spread and stable)
        if not ok:
            hits = 0
            history.clear()
            values.append(None)
            continue
        hits += 1
        history.append(f['candidate'])
        values.append(float(np.median(history)) if hits >= 3 else None)
    return values


def metrics(record, thresholds, median_window=1):
    values = gate(record['features'], thresholds, median_window)
    m = measure(values, record['label'])
    m['errors_over_5cm'] = sum(v is not None and abs(v-record['label']) > .05
                              for v in values) if record['label'] is not None else 0
    return m


def select(records, candidates):
    """Conservative per-record empty constraint, not an aggregate hiding drift."""
    best = None
    for thresholds in candidates:
        scores = [metrics(r, thresholds) for r in records]
        if any(m['reported']/m['frames'] > .01 for r,m in zip(records,scores) if r['label'] is None):
            continue
        targets = [m for r,m in zip(records,scores) if r['label'] is not None]
        count = sum(m['reported'] for m in targets)
        if not count or sum(m['errors_over_5cm'] for m in targets)/count > .05:
            continue
        utility = np.mean([m['within_2cm']/m['frames'] for m in targets])
        if best is None or utility > best[0]:
            best = (float(utility), thresholds)
    return best


def latest_tradeoff(records):
    """Explicitly overfit one session to quantify, not hide, transfer failures."""
    latest=[r for r in records if r['group']=='155623-972019']
    options=[]
    for t in itertools.product([.25,.5,1.,2.,4.],[0.,.25,.5],[.1,.3,999.],[None,.02,.05,.1]):
        scores=[metrics(r,t) for r in latest]
        if any(m['reported'] for r,m in zip(latest,scores) if r['label'] is None):
            continue
        targets=[m for r,m in zip(latest,scores) if r['label'] in (.4,.5)]
        coverage=min(m['reported']/m['frames'] for m in targets)
        options.append((coverage,sum(m['within_2cm'] for m in targets),t))
    best=max(options,key=lambda x:x[:2])
    return dict(warning='Optimized on latest-session labels; not independent validation or a deployment choice',
        thresholds=best[2],minimum_latest_40_50_coverage=best[0],
        records=[dict(path=r['path'],label=r['label'],raw=metrics(r,best[2]),
                      median5=metrics(r,best[2],5)) for r in records])


def extract():
    records = []
    for group, reference, cases in datasets():
        c, empty, _ = read_recording(reference)
        model = FitEvidence(c, empty[:30])
        baseline = Baseline.fit(empty[:30], c)
        original_fit = AssociatedFit(c)
        original_reference = np.mean([traces(f,c) for f in empty[:30]],axis=0)
        for path,label,skip in cases:
            _,frames,_ = read_recording(path,c)
            detector = Detector(baseline)
            guard = Continuity(c)
            invalidated = False
            features = []
            existing = []
            for frame in frames[skip:]:
                reason = guard.check(frame)
                invalidated |= reason == 'restart_or_duplicate'
                r = detector.update(frame)
                valid = not reason and not invalidated and r['candidate_bin'] is not None
                f = model.features(frame,r['candidate_bin'],r.get('qualified_bins')) if valid else dict(candidate=None,gain=0.,purity=0.,rx_spread=999.)
                f.update(valid=valid,sequence=frame.sequence)
                features.append(f)
                fitted = original_fit.fit_associated(traces(frame,c)-original_reference,r['candidate_bin'],r.get('qualified_bins')) if valid and r['target_detected'] else {'range_m':None}
                existing.append(fitted['range_m'])
            records.append(dict(group=group,path=str(path),label=label,skip=skip,
                reference=str(reference), reference_sha256=hashlib.sha256((reference/'frames.grd').read_bytes()).hexdigest(),
                raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                config_fingerprint=c.fingerprint, noise=model.noise, features=features,
                existing=measure(existing,label)))
            print(path.name, label, len(features), flush=True)
    return records


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reuse-features',action='store_true')
    args=ap.parse_args()
    out=Path('evidence/fit-gate-1');out.mkdir(exist_ok=True)
    cache=out/'features.json'
    records=json.loads(cache.read_text()) if args.reuse_features else extract()
    if not args.reuse_features:cache.write_text(json.dumps(records)+'\n')
    candidates=list(itertools.product([1.,2.,4.,8.,16.,32.,64.,128.], [0.,.25,.5,.75,.9], [.03,.1,.3,999.], [None,.02,.05,.1]))
    report=dict(protocol=__doc__,constraints={'max_false_fraction_each_empty':.01,'max_fraction_reported_target_errors_over_5cm':.05},folds=[])
    for group in sorted({r['group'] for r in records}):
        selection=select([r for r in records if r['group']!=group],candidates)
        thresholds=selection[1] if selection else None
        fold=dict(excluded_group=group,thresholds=thresholds,training_utility=selection[0] if selection else None,records=[])
        for r in records:
            if r['group']!=group:continue
            row=dict(path=r['path'],label=r['label'],existing=r['existing'])
            for window in [1,5]:
                row['median'+str(window)]=metrics(r,thresholds,window) if thresholds else measure([None]*len(r['features']),r['label'])
            fold['records'].append(row)
        report['folds'].append(fold)
        print('FOLD',group,'selected',thresholds,flush=True)
    full=select(records,candidates)
    report['all_data_development_selection']=full
    report['deployment']='Not deployed; session-held-out results must be reviewed, all recordings are development data.'
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'balanced-latest-tradeoff.json').write_text(json.dumps(latest_tradeoff(records),indent=2)+'\n')


if __name__=='__main__':main()
