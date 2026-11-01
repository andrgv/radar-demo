# Further estimator attempts, November 1

No new estimator passed. All 14 target captures and seven empty evaluation
segments were processed, from the three HPF series plus the recent GUI session.
Training is first 30 empty-before frames per session; these frames are excluded
from evaluation. Range labels score errors only. Existing presence decisions
are unchanged. These repeatedly examined recordings are now a development and
regression corpus, not an untouched final qualification dataset.

## Methods and results

All-frame MAE, equally weighting each of the 14 target captures:

| Estimator | Mean of capture MAEs |
|---|---:|
| Existing fixed empty-waveform subtraction + joint tone | 4.68 cm |
| Per-RX median of the same tone fits | 5.73 cm |
| Power/covariance difference + tone projection | 6.60 cm |
| Per-RX median of power/covariance fits | 10.00 cm |
| One empty-derived sinusoid per RX fitted as nuisance | 12.50 cm |
| Two empty-derived sinusoids per RX fitted as nuisance | 17.15 cm |

The recent GUI 30/50 cm captures have fixed-fit MAEs 12.43/18.30 cm.
Power/covariance difference reduces these to 6.24/6.34 cm, but worsens earlier
captures (e.g. initial HPF350 50 cm: 3.07 -> 24.31 cm). Therefore it is not a
replacement. Receiver medians are also not a general remedy. On the recent
50 cm capture the median frame-wise spread of independent RX fits is 59.20 cm;
on the 30 cm capture it is 10.09 cm. Receiver fits are diagnostics, not independent
truth measurements or proof that individual antennas are defective.

Power method: center each chirp, average outer products per RX, subtract average
empty covariance, maximize trace(Q^T delta_cov Q) on the fixed 5 mm grid. Q spans
DC-residualized sine/cosine. This removes fixed-phase waveform subtraction but
retains finite-record target/background cross terms. It is a hypothesis, not an
unbiased range estimator. All fits can yield a number in an empty scene; the
unchanged presence gate still has the recent empty false detection. No new
false-alarm guarantee is claimed.

Joint background trial uses only empty data to greedily select one or two tone
frequencies per RX over nominal .05–5 m, then residualizes the target basis
against these sinusoid bases. It uses existing fixed waveform subtraction;
additional nuisance terms allow phase/amplitude changes. This is exploratory:
near-collinear components can absorb the target, and broad real background need
not match a few tones. A controlled .9 m background with varying amplitude/phase
and distinct .3/.4/.5 m target passes 36 synthetic cases at 5 mm grid precision.
Real recordings fail despite that positive control. Results reside in sibling
../tone-background-1/report.json and synthetic.json. Not deployed.

## Implemented display correction

GUI now logs fit_boundary and fit_near_optimal_width_m (diagnostic width, not a
confidence interval). Search-endpoint fits are shown as unresolved candidates,
never as the main distance or a valid history point. Presence and raw candidate
remain recorded; no samples are removed. This catches 58/133 previously displayed
30 cm readings, leaving only 75/207 displayed readings, still with 9.86 cm MAE.
The 50 cm errors and empty false detection remain. This is a validity correction,
not achievement of accurate ranging. Existing open GUI processes require restart.

## Next discriminating physical experiment

Keep firmware and sensor fixed. Use a supported flat metal reflector facing the
sensor, if available, to compare against the box. Capture fresh empty training,
a separate empty run, stationary reflector at 30 cm then 50 cm, and empty after.
No handheld motion; keep supports/background fixed. These are new diagnostic
captures, not final qualification. Compare spectra and per-RX candidates, not
just GUI distance. A better reflector result would implicate scene/target
conditions; failure alone would not isolate firmware versus DSP. No flash needed.

Reproduce from project root:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_power_fit
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_tone_background
./range-v1 test
```

Original raw captures remain untouched. Scripts recompute experiment output files.
