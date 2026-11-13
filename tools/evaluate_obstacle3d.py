"""Evaluate frozen 3D obstacle settings across complete raw recordings.

No fitting or per-recording threshold/receiver selection. Range labels only score
already selected candidates. Empty/reference scenes contain background objects;
counts there are not certified false-obstacle rates. No surveyed angular labels
are supplied by these captures, so real-data XYZ accuracy is unmeasured.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from radar.obstacle3d import Settings, iter_results, load_config


def evaluate(roots, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    settings = Settings()
    rows, skipped = [], []
    corrected_path = Path('experiments/materials/window-drywall-repeat.json')
    corrected = json.loads(corrected_path.read_text())['recordings']
    later_path = Path('evidence/material-transfer-check/report.json')
    later_labels = {Path(row['recording']).name: row['user_reported_target']
                    for row in json.loads(later_path.read_text())['sessions']}
    for root_index, root in enumerate(map(Path, roots)):
        for manifest_path in sorted(root.rglob('door-check.json')):
            if not json.loads(manifest_path.read_text()).get('complete'):
                skipped.append(dict(recording=str(manifest_path.parent), reason='incomplete_door_experiment'))
        for raw in sorted(root.rglob('frames.grd')):
            path = raw.parent
            relative = path.relative_to(root)
            door_manifest = next((p / 'door-check.json' for p in [path, *path.parents]
                                  if (p / 'door-check.json').exists() and p.is_relative_to(root)), None)
            manifest = json.loads(door_manifest.read_text()) if door_manifest else None
            if manifest and not manifest.get('complete'):
                skipped.append(dict(recording=str(path), reason='incomplete_door_experiment'))
                continue
            config_path = path / 'config.json'
            if not config_path.exists():
                skipped.append(dict(recording=str(path), reason='missing_configuration'))
                continue
            case = output / f'root-{root_index}' / relative
            metadata = json.loads((path / 'metadata.json').read_text()) if (path / 'metadata.json').exists() else {}
            measured_range = None
            label_source = None
            state = metadata.get('door_state')
            material_label = metadata.get('label') if metadata.get('label') in ('glass', 'drywall') else None
            if manifest and path.name.startswith(('open-', 'closed-')):
                measured_range = manifest['measured_glass_distance_m']
                label_source = str(door_manifest)
            # The original archive's OPEN/CLOSED notes were explicitly corrected:
            # the sensor faced drywall vs window, with unknown drywall distance.
            # Do not reuse that manifest's pane distance as wall ground truth.
            if path.parent.name == 'glass-pane-100cm-01':
                match = next((row for row in corrected if Path(row['path']).name == path.name), None)
                if match:
                    state, material_label = None, match['label']
                    measured_range = match['distance_m']
                    label_source = str(corrected_path)
            if path.name in later_labels:
                material_label = later_labels[path.name]
                label_source = str(later_path)
            # These named placements are explicitly documented by the user-
            # confirmed distance sweep and HPF experiment reports. Empty cases
            # deliberately receive no target distance.
            if path.name.startswith(('distance-sweep-1-', 'distance-sweep-2-', 'hpf100-a-', 'hpf350-a-', 'hpf350-b-')):
                for fragment, distance in (('-30cm', .3), ('-40cm', .4), ('-50cm', .5)):
                    if fragment in path.name:
                        measured_range = distance
                        label_source = 'DISTANCE_SWEEP_1.md / DISTANCE_SWEEP_2.md / HPF_COMPARISON_RESULTS.md'
            completion = path / 'material-capture.json'
            if metadata.get('material_experiment') and (not completion.exists() or
                    not json.loads(completion.read_text()).get('complete')):
                skipped.append(dict(recording=str(path), reason='incomplete_material_capture'))
                continue
            try:
                config = load_config(config_path)
                windows = []
                for result in iter_results(config, recording=path, output=case, settings=settings):
                    if result['complete_window']:
                        windows.append(result)
                report = json.loads((case / 'report.json').read_text())
            except (ValueError, OSError, TypeError, KeyError) as error:
                rows.append(dict(recording=str(path), evaluation_error=str(error), complete=False))
                continue
            persistent = [[r for r in w['returns'] if r['persistent']] for w in windows]
            row = dict(recording=str(path), raw_sha256=report['raw_sha256'], profile_id=config.profile_id,
                       complete=report['complete'], terminal_reason=report['terminal_reason'],
                       frames=report['frames'], windows=len(windows),
                       windows_with_persistent_candidates=sum(bool(r) for r in persistent),
                       provisional_3d=report['provisional_3d'], unresolved=report['unresolved'],
                       processing_ms_p50_p95=report['processing_ms_p50_p95'],
                       door_state=state, measured_range_m=measured_range, label_source=label_source,
                       material_label=material_label,
                       angular_ground_truth_available=False)
            if measured_range is not None:
                expected = (measured_range - config.range_offset_m) / (
                    (config.ranges[1] - config.ranges[0]))
                for tolerance in (.25, 1.):
                    row['within_' + str(tolerance) + '_native_bins'] = dict(
                        persistent_windows=sum(any(abs(r['native_bin'] - expected) <= tolerance for r in rs) for rs in persistent),
                        provisional_3d_windows=sum(any(abs(r['native_bin'] - expected) <= tolerance and r['xyz'] is not None
                                                       for r in rs) for rs in persistent))
            rows.append(row)
            print(str(path), row['frames'], row['provisional_3d'], row['unresolved'], row['terminal_reason'], flush=True)
    summary = dict(schema=1, settings=asdict(settings), roots=list(map(str, roots)),
                   protocol=__doc__, recordings=rows, skipped=skipped,
                   total_frames=sum(r.get('frames', 0) for r in rows),
                   complete_recordings=sum(r['complete'] for r in rows),
                   incomplete_or_rejected_recordings=sum(not r['complete'] for r in rows),
                   angular_accuracy_verified=False)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    evaluate(args.roots, args.output)
