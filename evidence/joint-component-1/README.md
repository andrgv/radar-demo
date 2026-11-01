# Joint target/interference refinement — not promoted

Implemented the promised alternating fit using saved raw data only. It does not
improve the recent 30/50 cm tradeoff enough to replace either baseline.

| Recent target | Associated v3 | One-pass interference fit | Joint refinement |
|---|---:|---:|---:|
| 30 cm MAE among reported readings | 8.88 cm | 5.35 cm | 5.86 cm |
| 30 cm reported / total | 70/207 | 129/207 | 107/207 |
| 30 cm reported within 2 cm / all frames | 2/207 | 33/207 | 21/207 |
| 30 cm errors >10 cm | 27 | 17 | 19 |
| 50 cm MAE among reported readings | 1.83 cm | 3.58 cm | 3.61 cm |
| 50 cm reported / total | 141/206 | 141/206 | 141/206 |
| 50 cm jumps >20 cm / adjacent reported pairs | 1/124 | 4/124 | 4/124 |
| 50 cm errors >10 cm | 4 | 10 | 10 |

Joint recent 30 cm median is 25.5 cm, 95th-percentile absolute error 13.5 cm.
Recent 50 cm median is 49 cm, 95th-percentile absolute error 19.5 cm. Medians do
not establish reliability. All 14 target recordings and seven empty segments
(2,349 total evaluation frames) are in report.json and comparison.json. The
independent recent empty run still gives 1/208 false detections; earlier unused
empty data give 0/516. No extra gating or temporal smoothing added.

## Method

Same first 30 empty-before training frames per session, same fixed waveform
subtraction, same nominal range conversion, same native presence detector and
associated-bin support. No target labels enter fitting. On presence-accepted
frames, start each RX's far nuisance frequency with its strongest single-tone
fit over 1.5–5 m (1 cm grid). Alternate:

1. Hold the three far frequencies fixed. Residualize near sine/cosine bases
   against each far basis; combine receiver scores for one shared near frequency.
   Select a supported local maximum on the .15–1.5 m, 5 mm near grid.
2. Hold that near frequency fixed. Residualize every candidate far basis against
   the near basis and choose each RX's best far frequency independently.
3. Stop when grid indices stop changing, or after eight sweeps.

Per-trace DC, sine and cosine coefficients are solved through orthogonal
projection. SVD discards singular directions below 1e-6. The recorded objective
is explained centered energy from the union of near and far bases. A near update
cannot reduce its conditional score. Search-boundary and unsupported-peak cases
remain unresolved; no clipping, history carry-forward or distance-label mapping.
The grids are numerical search steps, not physical resolution claims. The far
component is a mathematical nuisance, not an identified physical object.

This is coordinate optimization with one initialization and finite grids, not
proof of a global optimum. Nevertheless all 107 returned recent 30 cm fits and
141 returned recent 50 cm fits converged; they are not merely stopped early by
the iteration limit. Every nontrivial logged objective history was nondecreasing
to tolerance (714 histories, zero decreases below -1e-8).

The recent 30 cm model now rejects 25 frames for a near search boundary, one for
no associated peak, plus 74 existing presence misses. Optimizing the two-tone
model more thoroughly does not establish correct object distance. This supports
model/data mismatch as an issue; it does not prove which physical mechanism is
responsible or that all two-component methods must fail.

## Validation and preservation

39 tests pass. New synthetic tests cover differing receiver far frequencies,
random independent chirp/RX phases, stronger far interference, known near ranges,
monotonic objective, constant input and invalid data. These check the optimizer,
not hardware accuracy. Real recordings remain necessary evidence and fail the
promotion criterion. This repeatedly analyzed corpus is development/regression
data, not untouched final qualification.

Only new offline scripts, tests and evidence added. GUI and firmware unchanged.
Raw recordings and prior results preserved. comparison.json contains raw hashes,
per-recording before/after metrics and convergence checks. frames.jsonl contains
all results, rejection reasons, iterations, nuisance coordinates and objective
histories. No fresh capture requested for this experiment.

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_joint_components
python3 -m tools.summarize_joint_components
./range-v1 test
```

Decision: retain associated v3 as the existing optional GUI estimator; do not
switch automatically to joint refinement. Further refinement needs a changed,
testable signal model or independent signal/configuration evidence, not simply
more coordinate iterations or a smoother display.
