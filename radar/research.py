import csv
import json
from pathlib import Path
import numpy as np

FEATURES = ["reflection_db", "range_entropy", "angular_width_deg", "temporal_cv",
            "phase_consistency", "late_energy_ratio", "moving_energy_fraction"]


def session_rows(root):
    rows = []
    for metadata_path in sorted(Path(root).glob("*/metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("label") not in ("glass", "non_glass"):
            continue
        config_path = metadata_path.parent / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not config.get("verified", False):
            raise ValueError(f"Unverified hardware config: {config_path}")
        scene = metadata.get("scene_id", "unspecified")
        if scene == "unspecified" or not metadata.get("specimen_id"):
            raise ValueError(f"Set scene_id and specimen_id: {metadata_path}")
        values = []
        for line in (metadata_path.parent / "features.jsonl").read_text(encoding="utf-8").splitlines():
            feature = json.loads(line)
            if feature.get("temporal_frames", 0) >= 10 and feature.get("saturation_fraction", 1) < 0.001:
                values.append([feature[name] for name in FEATURES])
        if len(values) < 10:
            raise ValueError(f"Need at least ten quality-controlled feature frames: {metadata_path.parent}")
        rows.append({"session": metadata_path.parent.name, "scene": scene,
            "specimen": metadata["specimen_id"], "label": metadata["label"],
            "profile_id": config["profile_id"],
            **dict(zip(FEATURES, np.median(values, axis=0).tolist()))})
    return rows


def evaluate(root, output, heldout_scenes):
    rows = session_rows(root)
    if len(rows) < 8:
        raise ValueError("Collect at least eight labeled sessions, with both classes in each partition")
    if len({row["profile_id"] for row in rows}) != 1:
        raise ValueError("Compare sessions with the same acquisition profile")
    heldout = np.array([row["scene"] in heldout_scenes for row in rows])
    train_specimens = {row["specimen"] for row, test in zip(rows, heldout) if not test}
    test_specimens = {row["specimen"] for row, test in zip(rows, heldout) if test}
    if train_specimens & test_specimens:
        raise ValueError("Specimen overlap across train/test; hold out scenes and specimens together")
    features = np.array([[row[name] for name in FEATURES] for row in rows])
    labels = np.array([row["label"] == "glass" for row in rows], dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Nonfinite features")
    for partition in (heldout, ~heldout):
        if set(labels[partition]) != {0.0, 1.0}:
            raise ValueError("Both classes required in train and held-out test sessions")
    mean = features[~heldout].mean(axis=0)
    scale = np.maximum(features[~heldout].std(axis=0), 1e-6)
    design = np.column_stack([np.ones(len(rows)), (features - mean) / scale])
    weights = np.zeros(design.shape[1])
    regularization = np.ones_like(weights) * 0.05
    regularization[0] = 0
    for iteration in range(1500):
        scores = 1 / (1 + np.exp(-np.clip(design[~heldout] @ weights, -40, 40)))
        gradient = design[~heldout].T @ (scores - labels[~heldout]) / sum(~heldout) + regularization * weights
        weights -= 0.05 * gradient
    scores = 1 / (1 + np.exp(-np.clip(design[heldout] @ weights, -40, 40)))
    truth = labels[heldout].astype(bool)
    positive = scores[truth]
    negative = scores[~truth]
    auc = float(np.mean((positive[:, None] > negative) + 0.5 * (positive[:, None] == negative)))
    predicted = scores >= 0.5
    report = {"status": "exploratory session-level baseline; no claim of reliable glass detection",
        "features": FEATURES, "heldout_scenes": sorted(heldout_scenes),
        "train_sessions": int(sum(~heldout)), "test_sessions": int(sum(heldout)),
        "test_auc": auc, "test_accuracy": float(np.mean(predicted == truth)),
        "confusion": {"tp": int(sum(predicted & truth)), "fp": int(sum(predicted & ~truth)),
                      "tn": int(sum(~predicted & ~truth)), "fn": int(sum(~predicted & truth))},
        "model": {"mean": mean.tolist(), "scale": scale.tolist(), "weights": weights.tolist()},
        "test_predictions": [{"session": row["session"], "label": row["label"], "score": float(score)}
                             for row, score in zip([row for row, test in zip(rows, heldout) if test], scores)]}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (output / "sessions.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return report
