"""Experimental glass/drywall classification for the three-RX GRD3 stream.

Independently implements the flattened-signal/XGBoost approach described in
povilasDadelo/Material-classification. No upstream SDK, source or weights are
bundled. Whole recordings, rather than neighboring frames, define the split.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .config import Config
from .door_check import _validate_frame_config
from .protocol import Parser
from .storage import Recorder, replay

LABELS = ("drywall", "glass")  # XGBoost class 0 and class 1
UPSTREAM = "https://github.com/povilasDadelo/Material-classification"
UPSTREAM_COMMIT = "0455250483e5d4acee7d61347ca9af7d5c28e477"
LIMITATION = (
    "Experimental comparison of glass-facing and drywall-facing radar readings. "
    "Distance, angle, window frame/coating, background and sensor placement can "
    "explain a prediction. Scores are not calibrated probabilities. Other "
    "materials can receive either label. This is not a validated glass detector."
)
PARAMETERS = dict(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                  max_depth=2, eta=0.05, min_child_weight=2, reg_lambda=5,
                  subsample=1, colsample_bytree=1, seed=2026, nthread=1)
ROUNDS = 100


def _xgboost():
    try:
        import xgboost
    except Exception as error:  # XGBoostError also covers a missing native OpenMP library.
        raise ValueError("XGBoost is unavailable. Install the material extra with "
                         "`.venv/bin/python -m pip install -e '.[material]'`. "
                         "On macOS also run `brew install libomp`. "
                         f"Import error: {error}") from error
    return xgboost


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class FeatureSpec:
    kind: str = "spectrum"
    window_frames: int = 10
    skip_frames: int = 10
    bins: list | None = None

    def validate(self, config):
        if self.kind not in ("spectrum", "waveform"):
            raise ValueError("Features must be spectrum or waveform")
        if type(self.window_frames) is not int or not 1 <= self.window_frames <= 1000:
            raise ValueError("Window must contain 1 to 1000 frames")
        if type(self.skip_frames) is not int or not 0 <= self.skip_frames <= 10000:
            raise ValueError("Warm-up skip must be 0 to 10000 frames")
        if self.bins is not None:
            if (self.kind != "spectrum" or not self.bins or len(set(self.bins)) != len(self.bins)
                    or any(type(b) is not int or not 1 <= b < config.samples // 2 for b in self.bins)):
                raise ValueError("Supply distinct non-DC/non-Nyquist FFT bins for spectrum features")
        return self

    def names(self, config):
        indices = (self.bins if self.bins is not None else list(range(1, config.samples // 2)))
        if self.kind == "waveform":
            indices = range(config.samples)
        return [f"rx{rx + 1}_{self.kind}_{i}" for rx in range(3) for i in indices]

    def frame(self, frame, config):
        # Preserve stationary returns; do not subtract the scene or average RXs.
        x = frame.adc[config.discard_chirps:].astype(float)
        x -= x.mean(axis=1, keepdims=True)
        if self.kind == "waveform":
            # Upstream's three flattened first-chirp waveforms, centered and
            # scaled for this board's unsigned 16-bit transport containers.
            return (x[0].T / 32768).reshape(-1)
        window = np.hanning(config.samples)
        fft = np.fft.rfft(x * window[None, :, None], axis=1) * (2 / window.sum())
        power = np.mean(abs(fft)**2, axis=0)
        bins = self.bins if self.bins is not None else list(range(1, config.samples // 2))
        return (10 * np.log10(np.maximum(power[bins], 1e-12))).T.reshape(-1)


def _check_frame(frame, config, previous=None):
    _validate_frame_config(frame, config)
    if np.any((frame.adc == 0) | (frame.adc == 65535)):
        raise ValueError("ADC container rails encountered; inspect the raw recording")
    if previous is not None:
        dt = ((frame.timestamp_us - previous.timestamp_us) & 0xffffffff) / 1e6
        if (((frame.sequence - previous.sequence) & 0xffffffff) != 1
                or frame.dropped != previous.dropped or frame.errors != previous.errors
                or not 0 < dt <= max(1, 5 * config.frame_interval_s)):
            raise ValueError("Discontinuous radar frames or changed device loss/error counters")


class FeatureWindows:
    """The same nonoverlapping windows are used during replay and live capture."""

    def __init__(self, config, spec):
        self.config, self.spec = config, spec.validate(config)
        self.count = 0
        self.pending = []
        self.first_sequence = None

    def push(self, frame):
        self.count += 1
        if self.count <= self.spec.skip_frames:
            return None
        if not self.pending:
            self.first_sequence = frame.sequence
        self.pending.append(self.spec.frame(frame, self.config))
        if len(self.pending) < self.spec.window_frames:
            return None
        value = np.median(self.pending, axis=0)
        self.pending.clear()
        return value, dict(first_sequence=self.first_sequence, last_sequence=frame.sequence)


def recording_features(path, config, spec, allow_incomplete=False):
    path = Path(path)
    metadata = _json(path / "metadata.json")
    if metadata.get("material_experiment") and not allow_incomplete:
        completion = path / "material-capture.json"
        if not completion.exists() or _json(completion).get("complete") is not True:
            raise ValueError(f"{path}: material capture incomplete; partial raw data preserved")
    if Config.load(path / "config.json") != config:
        raise ValueError(f"{path}: configuration differs from the model/training recordings")
    parser = Parser()
    windows = FeatureWindows(config, spec)
    values, sequences, stamps, frame_hashes = [], [], [], []
    previous = None
    for frame in replay(path, parser):
        _check_frame(frame, config, previous)
        previous = frame
        stamps.append(frame.timestamp_us)
        frame_hashes.append(hashlib.sha256(frame.adc.tobytes()).hexdigest())
        result = windows.push(frame)
        if result is not None:
            value, sequence = result
            values.append(value)
            sequences.append(sequence)
    if (parser.bad_crc or parser.bad_headers or parser.gaps or parser.restarts
            or parser.discarded_bytes or parser.buffer):
        raise ValueError(f"{path}: corrupt, truncated or discontinuous raw recording")
    if not values:
        raise ValueError(f"{path}: need warm-up frames and at least one complete feature window")
    arrivals = [json.loads(line) for line in (path / "arrivals.jsonl").read_text().splitlines()]
    if len(arrivals) != len(stamps):
        raise ValueError(f"{path}: arrival count differs from the raw frame count")
    elapsed = np.cumsum([0] + [((b - a) & 0xffffffff) / 1e6 for a, b in zip(stamps, stamps[1:])])
    host = np.array([(a["host_unix_ns"] - arrivals[0]["host_unix_ns"]) / 1e9 for a in arrivals])
    if np.any(np.diff(host) < 0) or np.max(abs(host - elapsed)) > max(.5, .2 * elapsed[-1]):
        raise ValueError(f"{path}: sensor/host timing mismatch; stale data suspected")
    x = np.asarray(values, dtype=np.float32)
    if not np.isfinite(x).all():
        raise ValueError(f"{path}: nonfinite signal features")
    return dict(x=x, sequence_windows=sequences, frame_sha256=frame_hashes,
                raw_sha256=_hash(path / "frames.grd"), frames=len(stamps),
                discarded_tail_frames=len(windows.pending), sensor_span_s=float(elapsed[-1]))


def _manifest(path):
    path = Path(path)
    data = _json(path)
    mode = data.get("evaluation")
    if data.get("schema") != 1 or mode not in ("repeat_holdout", "surface_holdout"):
        raise ValueError("Use a schema 1 manifest with repeat_holdout or surface_holdout evaluation")
    rows = data.get("recordings", [])
    if not rows:
        raise ValueError("The material manifest has no recordings")
    rows = [dict(row, path=str((path.parent / row["path"]).resolve())) for row in rows]
    if len({row["path"] for row in rows}) != len(rows):
        raise ValueError("A recording cannot appear twice or in both train and test")
    specimens = {}
    for row in rows:
        if (row.get("label") not in LABELS or row.get("split") not in ("train", "test")
                or any(not isinstance(row.get(k), str) or not row[k].strip()
                       for k in ("specimen_id", "scene_id"))):
            raise ValueError("Each recording needs glass/drywall, train/test, specimen_id and scene_id")
        if row.get("distance_m") is not None and (
                not np.isfinite(row["distance_m"]) or row["distance_m"] <= 0):
            raise ValueError("Measured surface distances must be positive and finite")
        specimen = row["specimen_id"]
        if specimen in specimens and specimens[specimen] != row["label"]:
            raise ValueError("A physical specimen cannot have conflicting material labels")
        specimens[specimen] = row["label"]
    for split, minimum in (("train", 2), ("test", 1)):
        for label in LABELS:
            if sum(r["split"] == split and r["label"] == label for r in rows) < minimum:
                raise ValueError(f"Need at least {minimum} {label} recording(s) in {split}")
    if mode == "surface_holdout":
        for key in ("specimen_id", "scene_id"):
            train = {r[key] for r in rows if r["split"] == "train"}
            test = {r[key] for r in rows if r["split"] == "test"}
            if train & test:
                raise ValueError(f"surface_holdout requires disjoint train/test {key}; "
                                 "use repeat_holdout for repeated views of the same surfaces")
    return data, rows


def _decision(score):
    return "drywall" if score <= .35 else "glass" if score >= .65 else "uncertain"


def _prediction(scores):
    score = float(np.mean(scores))
    return dict(prediction=_decision(score), forced_choice=LABELS[int(score >= .5)],
                glass_score=score, windows=len(scores))


def _metrics(rows):
    confusion = [[sum(r["label"] == truth and r["forced_choice"] == predicted for r in rows)
                  for predicted in LABELS] for truth in LABELS]
    return dict(recordings=len(rows), correct=sum(r["label"] == r["forced_choice"] for r in rows),
                forced_choice_accuracy=float(np.mean([r["label"] == r["forced_choice"] for r in rows])),
                uncertain=sum(r["prediction"] == "uncertain" for r in rows),
                confusion_labels=list(LABELS), confusion_actual_rows_predicted_columns=confusion)


def train_material(manifest, output, spec=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Use a fresh model output directory: {output}")
    data, rows = _manifest(manifest)
    config = Config.load(Path(rows[0]["path"]) / "config.json")
    spec = (spec or FeatureSpec()).validate(config)
    captures, seen = [], set()
    for row in rows:
        capture = recording_features(row["path"], config, spec)
        hashes = set(capture["frame_sha256"])
        if seen & hashes:
            raise ValueError("Recordings share identical raw ADC frames; use independent captures")
        seen.update(hashes)
        captures.append(capture)
    training = [c for c, r in zip(captures, rows) if r["split"] == "train"]
    x = np.vstack([c["x"] for c in training])
    y = np.concatenate([np.full(len(c["x"]), LABELS.index(r["label"]))
                        for c, r in zip(captures, rows) if r["split"] == "train"])
    # Every recording contributes equal total weight, irrespective of duration.
    weights = np.concatenate([np.full(len(c["x"]), len(x) / (len(training) * len(c["x"])))
                              for c in training])
    xgb = _xgboost()
    names = spec.names(config)
    matrix = xgb.DMatrix(x, label=y, weight=weights, feature_names=names, nthread=1)
    booster = xgb.train(PARAMETERS, matrix, num_boost_round=ROUNDS)
    # No evaluation examples are used for fitting, early stopping or thresholds.
    predictions = []
    for row, capture in zip(rows, captures):
        if row["split"] != "test":
            continue
        scores = booster.predict(xgb.DMatrix(capture["x"], feature_names=names, nthread=1))
        predictions.append(dict(row, **_prediction(scores)))
    repeat = data["evaluation"] == "repeat_holdout"
    warnings = [LIMITATION]
    if repeat:
        warnings.insert(0, "Same-surface repeat test only. No evidence of recognizing a new window or wall.")
    if any(row.get("distance_m") is None for row in rows):
        warnings.append("Some surface distances were not recorded; distance can explain the class difference.")
    status = "experimental_repeat_comparison" if repeat else "experimental_unseen_surface_comparison"
    provenance = [dict(r, raw_sha256=c["raw_sha256"], frames=c["frames"],
                       feature_windows=len(c["x"]), discarded_tail_frames=c["discarded_tail_frames"])
                  for r, c in zip(rows, captures)]
    report = dict(schema=1, status=status, evaluation=data["evaluation"], limitations=warnings,
                  notes=data.get("notes", ""), features=asdict(spec),
                  training_recordings=len(training), heldout_recording_metrics=_metrics(predictions),
                  heldout_predictions=predictions, recordings=provenance,
                  parameters=PARAMETERS, boosting_rounds=ROUNDS,
                  uncalibrated_score_margins=dict(drywall_max=.35, glass_min=.65),
                  upstream=dict(url=UPSTREAM, inspected_commit=UPSTREAM_COMMIT))
    output.mkdir(parents=True, exist_ok=False)
    booster.save_model(output / "booster.ubj")
    model = dict(schema=1, method="three_rx_material_xgboost_v1", config=asdict(config),
                 features=asdict(spec), feature_names=names, classes=list(LABELS),
                 booster_sha256=_hash(output / "booster.ubj"), xgboost_version=xgb.__version__,
                 status=status, limitations=warnings,
                 training_frame_sha256=sorted({h for c in training for h in c["frame_sha256"]}),
                 training_recordings=[r for r in provenance if r["split"] == "train"],
                 upstream=report["upstream"])
    _save(output / "model.json", model)
    _save(output / "report.json", report)
    _save(output / "manifest.json", dict(data, recordings=rows))
    return report


def load_material(path):
    path = Path(path)
    path = path / "model.json" if path.is_dir() else path
    model = _json(path)
    if (model.get("schema") != 1 or model.get("method") != "three_rx_material_xgboost_v1"
            or model.get("classes") != list(LABELS)):
        raise ValueError("Unsupported material model")
    config = Config(**model["config"]).validate()
    spec = FeatureSpec(**model["features"]).validate(config)
    if model.get("feature_names") != spec.names(config):
        raise ValueError("Material model feature definition mismatch")
    if _hash(path.parent / "booster.ubj") != model.get("booster_sha256"):
        raise ValueError("Material booster checksum mismatch")
    booster = _xgboost().Booster(model_file=path.parent / "booster.ubj")
    if booster.num_features() != len(model["feature_names"]):
        raise ValueError("Material booster feature count mismatch")
    return model, config, spec, booster


def predict_material(recording, model_path, output=None):
    model, config, spec, booster = load_material(model_path)
    capture = recording_features(recording, config, spec)
    xgb = _xgboost()
    scores = booster.predict(xgb.DMatrix(capture["x"], feature_names=spec.names(config), nthread=1))
    overlap = bool(set(capture["frame_sha256"]) & set(model["training_frame_sha256"]))
    result = dict(schema=1, recording=str(Path(recording).resolve()),
                  model_status=model["status"], **_prediction(scores),
                  overlaps_training_frames=overlap, limitations=model["limitations"],
                  raw_sha256=capture["raw_sha256"], frames=capture["frames"],
                  discarded_tail_frames=capture["discarded_tail_frames"],
                  window_predictions=[dict(seq, prediction=_decision(float(score)), glass_score=float(score))
                                      for seq, score in zip(capture["sequence_windows"], scores)])
    if output:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        _save(output / "predictions.json", result)
    return result


def capture_material(output, config, port, seconds=30, settle=5, metadata=None, model_path=None):
    """Record labeled data, or raw data plus experimental live model predictions."""
    from .acquisition import Source

    config.validate()
    if not np.isfinite(seconds) or seconds < 3 or not np.isfinite(settle) or settle < 3:
        raise ValueError("Use at least three seconds of capture and three seconds to step clear")
    metadata = dict(metadata or {})
    if model_path is None:
        if (metadata.get("label") not in LABELS
                or any(not isinstance(metadata.get(k), str) or not metadata[k].strip()
                       for k in ("specimen_id", "scene_id"))
                or not np.isfinite(metadata.get("distance_m", float("nan")))
                or metadata["distance_m"] <= 0):
            raise ValueError("Labeled capture requires material, physical surface ID, scene and measured distance")
        spec = FeatureSpec()
        loaded = None
    else:
        model, expected, spec, booster = load_material(model_path)
        if config != expected:
            raise ValueError("Live configuration differs from the material model")
        loaded = model, booster
        metadata.update(label="unknown", material_model=str(Path(model_path).resolve()),
                        material_model_booster_sha256=model["booster_sha256"])
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Use a fresh recording directory: {output}")
    windows = FeatureWindows(config, spec)
    predictions, previous = [], None
    source = Source(config, port=port)
    try:
        print(f"Step clear and keep the radar still. Recording starts in {settle:g} seconds.", flush=True)
        start = last = time.monotonic()
        counters = None
        while time.monotonic() - start < settle:
            frame = source.read()  # Drain serial throughout setup; do not retain queued setup frames.
            if frame is not None:
                _check_frame(frame, config, previous)
                previous, last = frame, time.monotonic()
        if previous is None or time.monotonic() - last > 1:
            raise ValueError("No recent radar frames; check the port and board")
        counters = [getattr(source.parser, k) for k in
                    ("gaps", "bad_crc", "bad_headers", "restarts", "discarded_bytes")]
        with Recorder(output, config, dict(metadata, material_experiment=True)) as recorder:
            source.transport_recorder = recorder
            prediction_file = (output / "predictions.jsonl").open("x", encoding="utf-8")
            try:
                started = time.monotonic()
                while time.monotonic() - started < seconds:
                    frame = source.read()
                    if frame is None:
                        if time.monotonic() - last > max(1, 5 * config.frame_interval_s):
                            raise ValueError("Radar timeout; partial raw data preserved")
                        continue
                    _check_frame(frame, config, previous)
                    current = [getattr(source.parser, k) for k in
                               ("gaps", "bad_crc", "bad_headers", "restarts", "discarded_bytes")]
                    if current != counters:
                        raise ValueError("Transport errors; partial raw data preserved")
                    previous, last = frame, time.monotonic()
                    recorder.write(frame)
                    if loaded is None:
                        continue
                    result = windows.push(frame)
                    if result is None:
                        continue
                    value, sequence = result
                    score = float(booster.inplace_predict(value[None, :])[0])
                    prediction = dict(sequence, prediction=_decision(score), glass_score=score)
                    predictions.append(prediction)
                    prediction_file.write(json.dumps(prediction) + "\n")
                    prediction_file.flush()
                    label = prediction['prediction']
                    display = 'uncertain' if label == 'uncertain' else f'{label}-like'
                    print(f"{display} | experimental glass score {score:.3f}", flush=True)
            finally:
                source.transport_recorder = None
                prediction_file.close()
    finally:
        source.close()
    checked = recording_features(output, config, spec, allow_incomplete=True)
    result = dict(recording=str(output), frames=checked["frames"], complete=True,
                  label=metadata["label"], sensor_span_s=checked["sensor_span_s"])
    if loaded is not None:
        result.update(_prediction([r["glass_score"] for r in predictions]), limitations=model["limitations"])
    _save(output / "material-capture.json", result)
    return result
