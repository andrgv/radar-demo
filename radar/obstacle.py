"""Fixed-scene obstacle templates. Scores are similarity coordinates, not probabilities."""

from collections import Counter, deque
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .config import Config
from .door_check import _profile, _session, _validate_frame_config
from .storage import Recorder, replay


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def fit_profiles(opened, closed, open_mad):
    """Each row is one independent recording; no held-out rows allowed."""
    opened, closed, open_mad = [np.asarray(a, dtype=float) for a in (opened, closed, open_mad)]
    if (opened.ndim != 2 or opened.shape != closed.shape or opened.shape != open_mad.shape
            or len(opened) < 2 or opened.shape[1] < 3
            or not all(np.isfinite(a).all() for a in (opened, closed, open_mad))
            or np.any(open_mad < 0)):
        raise ValueError('Need matching finite profiles from at least two open/obstacle pairs')
    baseline = np.median(opened, axis=0)
    changes = closed - opened
    delta = np.median(changes, axis=0)
    threshold = np.maximum(3., np.maximum(2*np.ptp(opened, axis=0), 6*np.max(open_mad, axis=0)))
    mask = np.all(changes*np.sign(delta) >= threshold, axis=0)
    mask[0] = mask[-1] = False
    if np.sum(mask) < 2:
        raise ValueError('Insufficient repeatable multi-bin evidence; no obstacle model fitted')
    weights = np.where(mask, delta, 0.)
    scores = (np.vstack([opened, closed])-baseline) @ weights / (weights @ weights)
    if np.any(scores[:len(opened)] > .25) or np.any(scores[len(opened):] < .75):
        raise ValueError('Calibration examples do not separate with the fixed decision margins')
    return dict(baseline_db=baseline.tolist(), signature_db=weights.tolist(),
                selected_bins=np.flatnonzero(mask).tolist(), thresholds_db=threshold.tolist())


def classify_profile(profile, model):
    profile = np.asarray(profile, dtype=float)
    baseline = np.asarray(model['baseline_db'])
    weights = np.asarray(model['signature_db'])
    if profile.shape != baseline.shape or not np.isfinite(profile).all():
        raise ValueError('Invalid range-power profile')
    score = float((profile-baseline) @ weights / (weights @ weights))
    state = 'clear' if score <= .25 else 'obstacle' if score >= .75 else 'uncertain'
    mask = weights != 0
    residual = float(np.sqrt(np.mean((profile[mask]-baseline[mask]-score*weights[mask])**2)))
    return dict(state=state, similarity_score=score, pattern_residual_db=residual,
                range_m=None, material='unknown')


def load_model(path):
    model = json.loads(Path(path).read_text(encoding='utf-8'))
    if model.get('schema') != 1 or model.get('method') != 'fixed_scene_signed_template_v1':
        raise ValueError('Unsupported obstacle model')
    config = Config(**model['config']).validate()
    a, w = [np.asarray(model[k], dtype=float) for k in ('baseline_db', 'signature_db')]
    if (a.shape != (config.samples//2+1,) or w.shape != a.shape
            or not np.isfinite(a).all() or not np.isfinite(w).all()
            or np.count_nonzero(w) < 2 or w[0] != 0 or w[-1] != 0):
        raise ValueError('Invalid obstacle template')
    if (type(model.get('window_frames')) is not int or not 1 <= model['window_frames'] <= 10000
            or not isinstance(model.get('training_raw_sha256'), list)):
        raise ValueError('Invalid obstacle window/provenance')
    return model, config


def fit_experiment(root, output):
    root = Path(root)
    manifest = json.loads((root/'door-check.json').read_text(encoding='utf-8'))
    if not manifest.get('complete') or manifest.get('repeats', 0) < 3:
        raise ValueError('Need a complete experiment with at least three pairs')
    config = Config.load(root/'config.json')
    # Always reserve the last pair; no selection using evaluation data.
    names = [(f'open-{i:02d}', f'closed-{i:02d}') for i in range(1, manifest['repeats'])]
    summaries = {n: _session(root/n, config) for pair in names for n in pair}
    seconds = manifest.get('seconds_per_state')
    if (seconds is None or not np.isfinite(seconds) or seconds < 3
            or any(abs(s['sensor_span_s']-seconds) > max(1., .2*seconds) for s in summaries.values())):
        raise ValueError('Calibration recordings must cover the requested capture window')
    model = fit_profiles([summaries[o]['median_db'] for o, c in names],
                         [summaries[c]['median_db'] for o, c in names],
                         [summaries[o]['within_recording_mad_db'] for o, c in names])
    hashes = [_hash(root/n/'frames.grd') for pair in names for n in pair]
    if len(set(hashes)) != len(hashes):
        raise ValueError('Duplicate calibration recordings')
    model.update(schema=1, method='fixed_scene_signed_template_v1', config=asdict(config),
                 training_raw_sha256=hashes, experiment=str(root.resolve()),
                 training_sessions=[n for pair in names for n in pair],
                 reserved_pair=manifest['repeats'], window_frames=max(1, int(np.ceil(1/config.frame_interval_s))),
                 assumptions='Fixed radar and background; clear/obstacle examples from this setup only. '
                             'No material identity, calibrated range, confidence probability, or scene-transfer guarantee.')
    _write_new(output, model)
    return model


class ObstacleDetector:
    """Nonoverlapping one-second windows; discontinuities discard partial windows."""
    def __init__(self, model):
        self.model = model
        self.config = Config(**model['config']).validate()
        self.window = deque(maxlen=model['window_frames'])
        self.previous = None
        self.invalidated = False

    def reset_window(self):
        self.window.clear()

    def update(self, frame):
        _validate_frame_config(frame, self.config)
        reason = None
        old = self.previous
        self.previous = frame
        if old is not None:
            sequence_step = (frame.sequence-old.sequence) & 0xffffffff
            elapsed = ((frame.timestamp_us-old.timestamp_us) & 0xffffffff)/1e6
            if sequence_step == 0 or sequence_step >= 0x80000000:
                self.invalidated = True
            elif sequence_step != 1:
                reason = 'sequence_gap'
            if frame.dropped != old.dropped or frame.errors != old.errors:
                reason = 'device_counter_changed'
            if not 0 < elapsed <= max(1., 5*self.config.frame_interval_s):
                reason = 'timestamp_gap'
        if self.invalidated:
            reason = 'device_restart_requires_new_calibration'
        if np.any((frame.adc == 0) | (frame.adc == 65535)):
            reason = 'adc_container_rails'
        if reason:
            self.reset_window()
            return dict(state='uncertain', reason=reason, similarity_score=None, range_m=None, material='unknown')
        self.window.append(_profile(frame.adc, self.config))
        if len(self.window) < self.window.maxlen:
            return None
        result = classify_profile(np.median(self.window, axis=0), self.model)
        self.reset_window()
        return result


def replay_obstacle(recording, model_path, output):
    recording = Path(recording)
    model, config = load_model(model_path)
    if _hash(recording/'frames.grd') in model['training_raw_sha256']:
        raise ValueError('Calibration/evaluation overlap: this raw recording was used for fitting')
    # Audit the entire saved raw file and arrival timing before reporting decisions.
    session = _session(recording, config)
    detector = ObstacleDetector(model)
    decisions = []
    for frame in replay(recording):
        result = detector.update(frame)
        if result is not None:
            decisions.append(dict(sequence=frame.sequence, timestamp_us=frame.timestamp_us, **result))
    report = dict(schema=1, recording=str(recording.resolve()), model=str(Path(model_path).resolve()),
                  frames=session['frames'], discarded_tail_frames=len(detector.window),
                  window_frames=model['window_frames'], counts=dict(Counter(x['state'] for x in decisions)),
                  decisions=decisions, limitations=model['assumptions'],
                  evaluation_note='Retrospective development data; windows are not independent trials.')
    _write_new(output, report)
    return report


def live_obstacle(port, model_path, output, seconds=60):
    from .acquisition import Source
    if not np.isfinite(seconds) or seconds <= 0:
        raise ValueError('Duration must be finite and positive')
    model, config = load_model(model_path)
    detector = ObstacleDetector(model)
    # Reserve the directory before opening the serial port; no overwrite.
    with Recorder(output, config, {'label': 'unknown', 'obstacle_model': str(Path(model_path).resolve()),
                                  'fixed_scene_required': True}) as recorder:
        _write_new(Path(output)/'obstacle-model.json', model)
        source = Source(config, port=port)
        try:
            source.transport_recorder = recorder
            start = last = time.monotonic()
            first_host = None
            sensor_elapsed = 0.
            prior_stamp = None
            counters = [0]*5
            with (Path(output)/'obstacle-decisions.jsonl').open('x', encoding='utf-8') as log:
                while time.monotonic()-start < seconds:
                    frame = source.read()
                    now = time.monotonic()
                    if frame is None:
                        if now-last > max(1., 5*config.frame_interval_s):
                            raise ValueError('Radar timeout; current obstacle state is uncertain')
                        continue
                    last = now
                    recorder.write(frame)  # Preserve even frames rejected below.
                    new = [getattr(source.parser, k) for k in ('gaps','bad_crc','bad_headers','restarts','discarded_bytes')]
                    if new != counters:
                        raise ValueError('Transport discontinuity; obstacle state is uncertain')
                    if first_host is None:
                        first_host = now
                    if prior_stamp is not None:
                        sensor_elapsed += ((frame.timestamp_us-prior_stamp) & 0xffffffff)/1e6
                    prior_stamp = frame.timestamp_us
                    if abs(sensor_elapsed-(now-first_host)) > .5:
                        raise ValueError('Sensor/host timing mismatch; obstacle state is uncertain')
                    result = detector.update(frame)
                    if result is not None:
                        result.update(sequence=frame.sequence, timestamp_us=frame.timestamp_us)
                        line = json.dumps(result, allow_nan=False)
                        log.write(line+'\n')
                        log.flush()
                        print(line, flush=True)
        except (Exception, KeyboardInterrupt):
            print(json.dumps(dict(state='uncertain', reason='acquisition_stopped')), flush=True)
            raise
        finally:
            source.close()
    return dict(recorded_frames=recorder.count, output=str(output))
