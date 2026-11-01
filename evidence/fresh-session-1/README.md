# Fresh physical session after USB reconnection

Session: recordings/gui-20261101-153737-539230. Labels follow the requested
sequence and user's Done: live-002 empty, live-003 30 cm, live-004 40 cm,
live-005 50 cm, live-006 empty. If that order differed, these distance labels
must be corrected. No synchronized external ground truth. Earlier session
153614 contains another live recording without a confirmed scene label; it is
preserved and excluded from this comparison.

## Acquisition recovered

101 complete empty-training capture frames, then 1,080 complete frames across
five live runs. Zero gaps, CRC/header errors, restarts, timing/validity rejects.
Each latest capture retains one incomplete trailing byte. First 30 empty frames
fit the baseline; unused 71 have zero detections (same-recording holdout only).
The two separate empty recordings have 0/426 detections under every frozen method.
No firmware flash or new capture performed by the evaluator.

## Frozen-method validation

Methods were unchanged before reading these captures: associated v3, one-pass
far-component fit, alternating joint fit and three-component fit (32 iterations).
Source revision, raw hashes, metrics and convergence counts are in report.json.
Raw replay of associated v3 agrees with the saved live GUI decisions/distances
to 1e-8 m. No parameters were adjusted based on these new results.

| Scene | Associated v3 readings | Median | MAE among readings |
|---|---:|---:|---:|
| Empty before | 0/209 | — | — |
| 30 cm | 0/214 | — | unavailable |
| 40 cm | 78/226 | 37.66 cm | 2.84 cm |
| 50 cm | 0/214 | — | unavailable |
| Empty after | 0/217 | — | — |

At 40 cm: 30/226 total frames are reported within 2 cm; 95th-percentile reported
error 5.96 cm, zero reported errors >10 cm and zero adjacent jumps >20 cm.
One-pass and joint models give MAE 2.24/2.35 cm on 78 frames; three-component model
gives 3.62 cm on 77 frames. None recovers the 30/50 cm runs because all preserve
the frozen presence gate. Missing outputs are failures of availability, not
zero-error measurements and not evidence that no box was present.

## Detector evidence

Fresh baseline threshold dB by native bins 1–4:
3.74475, 12.67062, 16.36770, 7.58074.
The baseline's variability-derived thresholds are elevated in bins 2/3. This is
not a transport failure, nor a proof of why the empty scene was variable.

30 cm: all 214 frames have no_candidate_above_noise. Median candidate excess
2.59 dB; maximum candidate excess 7.64 dB. Candidate thresholds differ by bin.
50 cm: 204 below-noise, 6 checking-persistence, 4 ambiguous-separate-peak frames;
median candidate excess 4.53 dB, median candidate threshold 12.67 dB. These
medians are descriptive, not a replacement for per-bin qualification checks.

Changing estimators behind the same gate cannot fix these missed detections.
Do not lower thresholds after inspecting target outcomes and label the resulting
same-data performance fresh validation. Next work should separately diagnose the
empty-reference variability and target/empty separation, preserving this frozen
result and checking any proposed gate change on the earlier empty/target corpus.
No additional recordings needed for that diagnosis.

```sh
MPLCONFIGDIR=/tmp/wavvy-mpl OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.evaluate_fresh_session
```
