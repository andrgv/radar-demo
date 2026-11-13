# Component-associated fit: partial improvement, not qualified ranging

Developed on saved recordings; this is a development comparison, not independent
validation. No distance labels enter the estimator, but examination of these
labeled failures informed method changes. All 2,349 complete evaluation frames
from 14 target captures and seven empty segments were replayed. First 30 empty
frames per session train references and are excluded from evaluation.

## Implemented method

Retain existing native-bin presence detector and waveform background subtraction.
Evaluate the same single-tone objective over nominal .15–1.50 m at 5 mm intervals.
Identify interior local maxima. Starting at the detected bin, include contiguous
qualified adjacent bins; accept local maxima within one native FFT spacing of
that connected group's outer bin centers. Select the largest supported maximum,
then refine its objective locally with a three-point quadratic. Reject if the
unrestricted grid winner is at a search endpoint, or there is no supported local
maximum. Never clip a result to the allowed interval or select by known distance.

This association interval is an engineering hypothesis, not a calibrated confidence
bound. It connects the fine fit to evidence that triggered presence and permits
adjacent qualified bins from one broad return. It cannot identify the box or
separate every reflection. FFT spacing remains provisional ~.348 m; 5 mm sampling
and sub-grid refinement do not imply 5 mm physical resolution or accuracy.

## Before / after

Baseline is the current GUI including the previous endpoint-rejection fix.
Errors below are among displayed readings; misses are listed separately.

| Recent capture | Current | Associated v3 |
|---|---:|---:|
| 50 cm mean absolute error | 16.94 cm | 1.83 cm |
| 50 cm 95th-percentile absolute error | 78.27 cm | 4.32 cm |
| 50 cm readings / total | 141/206 | 141/206 |
| 50 cm adjacent jumps >20 cm | 31/124 pairs | 1/124 pairs |
| 50 cm displayed readings within 2 cm | 91/206 total | 111/206 total |
| 50 cm displayed errors >10 cm | 36 | 4 |
| 30 cm mean absolute error | 9.86 cm | 8.88 cm |
| 30 cm readings / total | 75/207 | 70/207 |
| 30 cm displayed readings within 2 cm | 2/207 total | 2/207 total |
| Independent recent empty false detections | 1/208 | 1/208 |

The earlier twelve target captures keep their report counts; raw associated
MAEs remain essentially unchanged (differences below .02 cm). Earlier empty
segments remain 0/516; total empty false detections remain 1/724. The recent
50 cm improvement is real on these data, but 30 cm still fails, 65/206 50 cm
frames still lack a reading, and four reported 50 cm errors still exceed 10 cm.

Five-frame causal median, reset immediately on a missing reading, was evaluated
separately. At recent 50 cm it gives MAE 1.45 cm and zero adjacent >20 cm jumps,
but three >10 cm errors remain. It slightly worsens some earlier captures and
the recent 30 cm result. It is not enabled in the GUI; the improvement there
comes from component selection, not smoothing.

## Failed iterations retained

Variant 1 used only the winning bin's support. It improved recent 50 cm but
worsened initial 350-a 40 cm captures: good lower-frequency maxima were just
outside that interval while another qualified adjacent bin supported them.
Variant 2 includes connected qualified bins, but could promote secondary peaks
when the dominant fit was stuck at a search limit, worsening recent 30 cm.
Variant 3 additionally rejects those endpoint cases. Earlier outputs remain in
../associated-fit-1 and ../associated-fit-2. All variants are reproducible:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_association --variant 1
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_association --variant 2
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_association --variant 3
./range-v1 test
```

## GUI integration and verification

Optional `--estimator associated` enables v3; default remains `fixed`. Raw frames,
presence decisions and unrestricted candidate are retained. `associated_fit`
records local maxima and rejection reasons. Existing `fit_residual_fraction`,
`fit_boundary`, and `fit_near_optimal_width_m` describe the unrestricted fit;
associated_fit.residual_fraction describes the selected grid peak. Neither
residual nor width is a calibrated confidence measure. Live uses no smoothing.

GUI output was checked against the benchmark on all 621 recent raw frames;
accepted ranges match to 1e-8 m. Offscreen replay was rendered and inspected.
35 tests pass, including known tones, connected-bin support, endpoint rejection,
invalid input, raw recording preservation and timeout clearing.

Replay without board access, then click Start replay:

```sh
./range-v1 gui --config artifacts/hpf-pair-2/hpf350/range-config.json --baseline recordings/gui-20261101-144515-340260/empty-001/baseline.json --replay recordings/gui-20261101-144515-340260/live-005 --estimator associated
```

Use live-004 for the still-failing 30 cm capture and live-003 for empty. No new
hardware capture or flash was performed. Next offline work should target the
30 cm objective/baseline mismatch and false detection, retaining this complete
regression corpus. Fresh physical qualification remains necessary before claiming
reliable accuracy, but is not requested to continue this diagnosis.
