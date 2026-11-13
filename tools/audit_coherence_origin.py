"""Decompose observed coherence into stationary scene mean and fluctuations.

Follow-up to audit_glass_signature; not a glass classifier. Run from checkout:
python -m tools.audit_coherence_origin INITIAL_REPORT NEW_OUTPUT_DIRECTORY
"""

import argparse
import csv
from itertools import combinations
import json
from pathlib import Path

import numpy as np

from radar.config import Config
from radar.material import FeatureSpec, recording_features
from radar.storage import replay
from tools.audit_glass_signature import SKIP_FRAMES, WINDOW_FRAMES, paired_statistics


def coherence_components(spectra, bins):
    """Power-weighted coherence and exact stationary-mean decomposition."""
    x = np.asarray(spectra)[:, :, bins, :]
    if not len(bins) or not np.isfinite(x).all():
        raise ValueError('Need a nonempty range region and finite spectra')
    power = np.mean(abs(x)**2, axis=(0, 1))
    mean = np.mean(x, axis=(0, 1))
    result = {}
    for a, b in combinations(range(3), 2):
        cov = np.mean(x[:, :, :, a] * x[:, :, :, b].conj(), axis=(0, 1))
        static = mean[:, a] * mean[:, b].conj()
        denominator = max(float(np.sqrt(power[:, a] * power[:, b]).sum()), 1e-12)
        observed = float(abs(cov).sum() / denominator)
        surrogate = float(abs(static).sum() / denominator)
        result[f'rx{a + 1}{b + 1}'] = dict(observed=observed, stationary_mean=surrogate,
            observed_minus_stationary_mean=observed - surrogate,
            residual_cross_magnitude=float(abs(cov - static).sum() / denominator))
    return result


def audit(initial_report, output):
    initial_report, output = Path(initial_report), Path(output)
    if output.exists():
        raise FileExistsError('Use a fresh output directory')
    initial = json.loads(initial_report.read_text())
    if initial.get('experiment') != 'paired_scene_signal_audit_not_glass_identity':
        raise ValueError('Supply the initial glass-signature audit report')
    sessions, rows = [], []
    for source in initial['sessions']:
        path = Path(source['path'])
        config = Config.load(path / 'config.json')
        quality = recording_features(path, config, FeatureSpec())
        if quality['raw_sha256'] != source['raw_sha256']:
            raise ValueError(f'{path}: input changed since the initial audit')
        setup = initial['setups'][source['setup']]
        original = setup['regions']
        used = set(original['roi'] + original['references'])
        regions = dict(pane_roi=original['roi'], local_references=original['references'],
                       remaining_usable_bins=[b for b in range(1, config.samples // 2) if b not in used])
        taper = np.hanning(config.samples)
        windows, pending = [], []
        for i, frame in enumerate(replay(path)):
            if i < SKIP_FRAMES:
                continue
            raw = frame.adc[config.discard_chirps:].astype(float)
            raw -= raw.mean(axis=1, keepdims=True)
            pending.append(np.fft.rfft(raw * taper[None, :, None], axis=1) * (2 / taper.sum()))
            if len(pending) == WINDOW_FRAMES:
                values = {}
                for region, bins in regions.items():
                    for pair, components in coherence_components(pending, bins).items():
                        values.update({f'{region}_{pair}_{k}':v for k,v in components.items()})
                windows.append(values)
                rows.append(dict(setup=source['setup'], state=source['state'], pair=source['pair'],
                                 last_sequence=frame.sequence, **values))
                pending.clear()
        if len(windows) != source['windows']:
            raise ValueError(f'{path}: window count differs from initial audit')
        medians = {k:float(np.median([w[k] for w in windows])) for k in windows[0]}
        maximum_differences = {f'{region}_{pair}':max(
            abs(w[f'{region}_{pair}_observed_minus_stationary_mean']) for w in windows)
            for region in regions for pair in ('rx12', 'rx13', 'rx23')}
        sessions.append(dict(setup=source['setup'], state=source['state'], pair=source['pair'],
                             path=str(path), raw_sha256=quality['raw_sha256'],
                             medians=medians, max_abs_window_observed_minus_surrogate=maximum_differences))
    effects = {}
    for key in sessions[0]['medians']:
        effects[key] = {setup:paired_statistics(*[
            [s['medians'][key] for s in sessions if s['setup'] == setup and s['state'] == state]
            for state in ('open', 'closed')]) for setup in initial['setups']}
    report = dict(schema=1, experiment='exploratory_coherence_origin_followup',
                  initial_report=str(initial_report), sessions=sessions, effects=effects,
                  interpretation='The stationary-mean surrogate preserves deterministic scene spectra '
                      'and power, removing correlated temporal fluctuations. It has no material identity.',
                  limitations=['Post hoc follow-up, same development data, not independent validation.',
                               'Spectral regions are not independently attributed physical objects.',
                               'A surrogate match does not identify the noise distribution or physical path.'])
    output.mkdir(parents=True)
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (output / 'windows.csv').open('x', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for region in regions:
        print(region, flush=True)
        for setup in initial['setups']:
            print(setup, {component:report['effects'][f'{region}_rx12_{component}'][setup]['median_effect']
                          for component in ('observed', 'stationary_mean', 'observed_minus_stationary_mean')}, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('initial_report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    audit(args.initial_report, args.output)


if __name__ == '__main__':
    main()
