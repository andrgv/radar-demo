# Fitted-signal acceptance and median experiment

Decision: **do not replace the live acceptance rule**. A rule tuned to the
latest 40/50 cm placements improves those recordings substantially but fails
the 20 cm target and earlier independent empty scenes. The broader session-held-out
evaluation is worse than the existing rule. This is an unsuccessful experiment,
not a calibrated operating range or a claim that all software alternatives fail.

## Method and selection

The same local sinusoid association/search interval is retained. Twenty empty
frames fit a reference waveform. Ten subsequent empty frames set a projected
energy reference (maximum over all search frequencies and calibration frames).
No target frame fits this reference. Evaluation starts after those 30 frames.
Native candidate-bin association still comes from the existing detector, so this
is not wholly independent of native bins; its old power acceptance is replaced.

The tested features are fitted energy / empty reference energy, explained energy
fraction, maximum receiver peak disagreement, and optional five-frame candidate
range span. These are engineering diagnostics, not statistical confidence
intervals or probabilities. The shared single-tone and phase-aligned background
assumptions remain unverified on real hardware.

640 threshold combinations are scored. For each of six acquisition groups, the
thresholds are selected without any evaluated recording from that group. Selection
maximizes the mean per-target-record fraction within 2 cm, subject to at most 1%
false reports in **each** training empty recording and at most 5% of reported
training target readings having error over 5 cm. These are explicit development
criteria, not user-approved performance specifications. Selection therefore uses
training labels; frequency estimation never uses true distance. Neighboring
frames are not randomly split into train/test sets.

Three consecutive accepted frames are required. The optional stability test needs
five candidates, adding startup delay. A causal median uses up to five accepted
candidate values; it has a shorter window during startup. Rejection or invalid
continuity immediately clears output/history. No last-good value is held across
misses. Neither temporal median nor stable candidates prove target presence.

All sessions have already been inspected during development. Excluding a session
from threshold selection is stronger than tuning on it, but does not make this
an untouched prospective validation. Moving/unlabeled sessions are excluded;
the evaluated corpus contains the paired HPF captures and three labeled GUI
sessions. This is not every historical recording in the original project.

## Across acquisition groups

| Method | Target reports / 2,940 | Within 2 cm / 2,940 | Empty false reports / 1,569 |
|---|---:|---:|---:|
| Existing associated rule | 822 | 437 | 1 |
| Fit-based acceptance, session-held-out selection | 680 | 232 | 2 |
| Same acceptance plus median of up to five | 680 | 226 | 2 |

The held-out constraints sometimes fail despite being satisfied on the selection
groups. Median smoothing does not improve the overall within-2-cm count here.
This prevents a defensible default replacement.

## What tuning only the latest setup can achieve

A separate, explicitly optimistic search maximizes the minimum availability at
40 and 50 cm in gui-20261101-155623-972019, subject to zero reports in that session's
empty segments. It selects fitted-energy ratio >=2, no purity or RX-agreement
restriction, and five-frame span <=10 cm. This result is fitted to those captures,
not independent validation. It must also be evaluated on the 20 cm and other scenes.

| Latest target | Existing reports | Trial reports | Raw-fit MAE | Median MAE |
|---|---:|---:|---:|---:|
| 40 cm | 90/213 | 207/213 | 0.76 cm | 0.66 cm |
| 50 cm | 0/216 | 197/216 | 1.13 cm | 0.96 cm |
| 20 cm | 0/232 | 22/232 | **51.17 cm** | **51.03 cm** |

MAE is conditional on reported frames, not on all frames. The same trial admits
8/101 reports in hpf350-a-empty-after, 4/208 in the older GUI independent empty,
and 3/217 in the next GUI final empty. The latest independent empty remains clean.
Those failures are retained, not removed by narrowing the displayed distance axis.

This explains the user's observation: the 40/50 cm frequency candidates can be
accurate while the existing native-bin gate rejects them. Replacing the gate with
median stability can accept real targets, but also coherent clutter or a wrong
component. It does not establish a hard 38 cm minimum; a real 20 cm object can be
reported much farther away by the relaxed rule.

## Reproduce and next action

From wavvy-range-v1, with the existing NumPy environment:

```sh
./range-v1 test
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_fit_gate
```

Use --reuse-features only to reuse the preserved feature cache without re-reading
raw files. features.json records input hashes, baseline hashes, config fingerprints,
per-frame features and existing results. report.json contains all excluded-group
selections and outcomes. balanced-latest-tradeoff.json contains the deliberately
local optimization and its transfer failures. latest-only-tradeoff.json preserves
an earlier, three-feature local search; it is exploratory and not selected for use.

51 software tests pass. New tests cover calibration separation, causality, immediate
clearing, confirmation and the counterexample of a stable false target. No live
DSP, GUI, firmware or raw recordings changed.

Next hardware-dependent step remains the supported acquisition/timing request in
docs/INFINEON_CONFIGURATION_REQUEST.txt. No repeated unchanged capture is required.
Any proposed replacement must be frozen before new independent validation, include
close targets that it might misreport as distant, and score false reports and
availability alongside conditional distance error. A stable 40/50 cm demonstration
alone is insufficient to claim a reliable ranging system.
