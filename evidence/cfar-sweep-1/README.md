# CA-CFAR parameter sweep

Retrospective replay of labeled recordings; no hardware changes or baseline subtraction.

Swept 81 settings on tuning recordings only. Selected: guard **1**, training **4** per side, minimum total **4**, factor **2**.

Selection maximizes mean target expected-bin coverage subject to mean empty detection rate ≤ 1.0% and longest empty episode ≤ 0.5 s. Each recording has equal weight. Ties favor fewer empty detections, more target detections, then a larger factor and smaller windows.

A feasible candidate existed: **True**. If none is feasible, selection falls back to balanced expected-bin/empty-specificity score; inspect limitations before using it.

| Split | Settings | Target any detection | Target expected-bin coverage | Empty detection | Empty episodes | Longest empty episode |
|---|---|---:|---:|---:|---:|---:|
| tune | default | 0.0% | 0.0% | 0.0% | 0 | 0.00 s |
| tune | selected | 88.1% | 85.1% | 0.0% | 0 | 0.00 s |
| validation | default | 0.0% | 0.0% | 0.0% | 0 | 0.00 s |
| validation | selected | 94.8% | 94.8% | 1.5% | 2 | 0.20 s |
| stress | default | 37.0% | 37.0% | 0.0% | 0 | 0.00 s |
| stress | selected | 88.4% | 84.5% | 29.2% | 11 | 5.70 s |

The selected settings **fail** the tuning empty-scene limits on validation, and **fail** them on stress data. Do not interpret tuning feasibility as validation success.

## Selected settings by capture group

| Group | Target any detection | Expected-bin coverage | Empty detection | Longest empty episode |
|---|---:|---:|---:|---:|
| distance-sweep-1 | 91.8% | 87.6% | 0.0% | 0.00 s |
| distance-sweep-2 | 77.0% | 69.3% | 1.0% | 0.10 s |
| hpf100-a | 96.5% | 96.5% | 86.6% | 5.70 s |
| hpf350-a | 94.8% | 94.8% | 1.5% | 0.20 s |
| hpf350-b | 88.1% | 85.1% | 0.0% | 0.00 s |

## Use the selected settings

```sh
./range-v1 gui --detector cfar \
  --config artifacts/hpf-pair-2/hpf350/range-config.json \
  --port /dev/cu.usbmodemACTUAL \
  --cfar-guard 1 --cfar-training 4 \
  --cfar-min-training 4 --cfar-factor 2
```

Defaults are unchanged. These are an experimental preset, not a deployment qualification.

## Per-recording results

| Recording | Split | Target | Default detection | Selected detection | Selected expected bin | Selected bin coverage | Longest miss |
|---|---|---:|---:|---:|---:|---:|---:|
| recordings/hpf350-b-empty-before | tune | empty | 0.0% | 0.0% | None | n/a | 10.10 s |
| recordings/hpf350-b-30cm | tune | 30 cm | 0.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf350-b-40cm | tune | 40 cm | 0.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf350-b-40cm-repeat | tune | 40 cm | 0.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf350-b-50cm | tune | 50 cm | 0.0% | 58.4% | 1 | 46.5% | 0.70 s |
| recordings/hpf350-b-empty-after | tune | empty | 0.0% | 0.0% | None | n/a | 10.10 s |
| recordings/hpf350-a-empty-before | validation | empty | 0.0% | 3.0% | None | n/a | 4.50 s |
| recordings/hpf350-a-30cm | validation | 30 cm | 0.0% | 94.1% | 1 | 94.1% | 0.40 s |
| recordings/hpf350-a-40cm | validation | 40 cm | 0.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf350-a-40cm-repeat | validation | 40 cm | 0.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf350-a-50cm | validation | 50 cm | 0.0% | 89.1% | 1 | 89.1% | 0.30 s |
| recordings/hpf350-a-empty-after | validation | empty | 0.0% | 0.0% | None | n/a | 10.10 s |
| recordings/hpf100-a-empty-before | stress | empty | 0.0% | 83.2% | None | n/a | 0.30 s |
| recordings/hpf100-a-30cm | stress | 30 cm | 98.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf100-a-40cm | stress | 40 cm | 98.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf100-a-40cm-repeat | stress | 40 cm | 98.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/hpf100-a-50cm | stress | 50 cm | 92.1% | 92.1% | 1 | 92.1% | 0.30 s |
| recordings/hpf100-a-empty-after | stress | empty | 0.0% | 90.1% | None | n/a | 0.50 s |
| recordings/distance-sweep-1-empty-before | stress | empty | 0.0% | 0.0% | None | n/a | 10.10 s |
| recordings/distance-sweep-1-30cm | stress | 30 cm | 0.0% | 92.1% | 1 | 92.1% | 0.30 s |
| recordings/distance-sweep-1-40cm | stress | 40 cm | 58.4% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/distance-sweep-1-40cm-repeat | stress | 40 cm | 0.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/distance-sweep-1-50cm | stress | 50 cm | 0.0% | 79.2% | 1 | 62.4% | 0.50 s |
| recordings/distance-sweep-1-empty-after | stress | empty | 0.0% | 0.0% | None | n/a | 10.10 s |
| recordings/distance-sweep-2-empty-before | stress | empty | 0.0% | 1.0% | None | n/a | 5.40 s |
| recordings/distance-sweep-2-30cm | stress | 30 cm | 0.0% | 82.2% | 1 | 82.2% | 0.60 s |
| recordings/distance-sweep-2-40cm | stress | 40 cm | 0.0% | 94.1% | 1 | 94.1% | 0.40 s |
| recordings/distance-sweep-2-40cm-repeat | stress | 40 cm | 0.0% | 98.0% | 1 | 98.0% | 0.20 s |
| recordings/distance-sweep-2-50cm | stress | 50 cm | 0.0% | 33.7% | 1 | 3.0% | 0.90 s |
| recordings/distance-sweep-2-empty-after | stress | empty | 0.0% | 1.0% | None | n/a | 6.30 s |

## Interpretation and limits

- For this study, 30/40/50 cm all map to nearest nominal bin 1. This score does not establish that the detector distinguishes those distances.
- Default means the original CA-CFAR settings (2 guard, 8 training, factor 6), not the empty-reference detector.
- The 1% empty-rate and 0.5 s episode constraints are explicit exploratory engineering targets, not measured reliability guarantees.
- Expected-bin agreement means rounding the user-reported distance to the nearest nominal FFT bin. It is a coarse diagnostic, not proof of box identity or physical accuracy; the grid is about 35 cm.
- Any detection counts can include the wrong reflector. Empty captures contain real clutter; their detections are unwanted outputs for this box experiment, not necessarily thermal-noise false alarms.
- Target misses include confirmation startup and every invalid frame. No failed recording or rejected target frame is dropped. Conditional range errors in JSON describe accepted outputs only and must be read with coverage.
- The tuning run was already explored before this sweep. Validation is another existing run, not a prospective blind experiment. Stress tests mix other sessions/profiles and are reported separately. No setting is selected using validation/stress results.
- All repeats from a run stay in the same split. Raw hashes detect exact duplicate files but cannot establish that distinct files have no overlapping samples. Correlated frames are not independent trials.
- Empty episodes and frame rates are empirical observations over short captures; they are not calibrated Pfa or confidence bounds. Frozen settings need longer fresh empty/target captures in new scenes.
- No fine range fit, smoothing, target-dependent threshold, search-mask change or firmware change was made. The existing three-frame persistence is unchanged.

## Artifacts

- [Tuning tradeoff](tradeoff.png)
- [Per-recording detection coverage](recording-coverage.png)
- [Selected-setting frame timeline](selected-timeline.png)
- [Full report and provenance](report.json)
- [Selected experimental settings](selected-settings.json)
- [Tuning grid CSV](grid.csv)
- [Default/selected per-frame decisions](timelines.jsonl)

## Reproduce

```sh
.venv/bin/python -m tools.sweep_cfar --manifest configs/cfar-study.json --output evidence/cfar-sweep-1-rerun --guards 1 2 3 --training 4 8 12 --factors 1.5 2 2.5 3 3.5 4 4.5 5 6 --max-empty-rate 0.01 --max-empty-episode-s 0.5 --root .
```
