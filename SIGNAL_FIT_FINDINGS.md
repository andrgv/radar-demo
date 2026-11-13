# Joint signal fit: improvement, not yet reliable centimeter ranging

Implemented and tested an offline single-tone fit. Live processing and firmware
are unchanged. No additional dependency or distance-label calibration is used.

For each retained chirp/RX trace, fit `d + a*cos(2*pi*f*t) + b*sin(2*pi*f*t)`.
Frequency is shared across the frame; offset and the two phase/amplitude
coefficients are independent per trace. QR projection solves those linear
coefficients at each frequency; a fixed 0.15–1.50 m nominal frequency interval is
scanned every 5 mm then locally refined by golden-section search. No Hann window.
Both data AND sinusoid basis are residualized against a constant, mathematically
equivalent to fitting DC jointly. This differs from subtracting a mean and then
assuming the remainder is an unmodified sinusoid. Frequency-to-distance still
uses the source-derived, physically uncalibrated slope and sample rate.

Two variants were fixed before replay results: fit raw traces, or subtract the
first 30 empty frames' mean waveform at matching chirp/RX/sample positions first.
The latter assumes repeatable background phase/timing; this is not established
across sessions. Targets and unused empty frames never enter the reference.
No target label trains this physical estimator. Entire recordings are scored,
with no frame splits, fitted offsets, smoothing or search retuning. This remains
retrospective development on inspected data, not prospective validation.

## Synthetic verification

2,880 noise-free cases (eight distances, 360 phases each) recover known frequencies
within 5.3e-8 m numerical error. This is a numerical identity check under the exact
assumed model, NOT hardware accuracy. Unit tests additionally cover independent
RX/chirp offsets/amplitudes/phases, one seeded noisy case, constant traces and NaN
rejection. All 25 project tests pass. The earlier clean-tone phase bias is resolved
under this model, but real returns do not have to satisfy the model.

## Saved hardware recordings

Same 13 supported-box target recordings, 1,916 frames, and exclusions as the
calibration study. Mean absolute errors first average within each recording then
give each recording equal weight. All target frames, including presence misses,
contribute. Labels are user measurements, not instrument-certified distances.

| Method | Recording-balanced MAE |
|---|---:|
| Existing background-subtracted fine FFT peak | 8.74 cm |
| Joint fit on raw traces | 11.56 cm |
| Joint fit after empty-waveform subtraction | **4.74 cm** |

The combined background/estimator change improves 11/13 recordings; this does not
isolate how much improvement belongs to each change. Giving each distance equal
weight yields 4.34 cm for the background-subtracted fit. Only 17.4% of its target
predictions are within 1 cm (recording-average fraction). It is not a centimeter
accuracy result and has not established a useful worst-case error guarantee.

| Capture | Existing peak MAE | Joint fit with empty subtraction |
|---|---:|---:|
| Initial supported 50 cm | 8.75 | 1.97 |
| Aligned 35 cm | 2.28 | 2.09 |
| Aligned 50 cm repeat | 5.62 | 3.01 |
| Sweep 1, 30 cm | 4.43 | 2.88 |
| Sweep 1, 40 cm | 4.95 | 1.75 |
| Sweep 1, 50 cm | 19.69 | 1.18 |
| Sweep 1, 40 cm repeat | 15.97 | 6.82 |
| Sweep 1, 40 cm repeat 2 | 3.31 | 5.11 |
| Sweep 1, 40 cm untouched | 1.76 | 5.18 |
| Sweep 2, 30 cm | 13.51 | 10.03 |
| Sweep 2, 40 cm | 10.82 | 8.84 |
| Sweep 2, 50 cm | 11.38 | 6.50 |
| Sweep 2, 40 cm repeat | 11.19 | 6.24 |

All values above are cm. A median close to truth is insufficient: sweep 2 at
40 cm has a median estimate of 38.9 cm but MAE 8.84 cm because of frame variation.
Sweep 1 at 50 cm improves strongly while its unchanged presence detector accepts
zero frames. Thus estimator accuracy and usable live output remain separate.

## Model mismatch, ambiguity and empty scenes

Per-record median residual fractions after empty subtraction range from 0.39 to
0.76 on targets: the single tone leaves substantial centered signal energy
unexplained. This residual includes noise, clutter, transient response and other
model mismatches; it cannot identify which is responsible. Low residual alone
does not establish box identity: empty scenes sometimes fit as well as targets.

For sensitivity, report the span of grid candidates whose SSE is within 1% of
total centered energy of the best SSE. Median spans range from 4.5 to 17.5 cm
across target recordings. This fixed diagnostic is not a confidence interval or
a tuned rejection gate; no ambiguous frames were removed from reported errors.
Several fits hit the fixed search boundary and are counted in the report.

All 1,393 independent-of-reference empty frames also receive a numeric fit.
Their per-record median estimates are roughly 0.94–1.16 m. The unchanged native
presence gate rejects all of these frames, but the tone fit itself has no empty
detector. It must not be presented as a standalone live range sensor. Existing
617/1,916 target rejections remain; the prior mismatched-background false-alarm
case is not rerun or fixed by this study. Subtracted-fit gated errors are stored
alongside ungated errors without hiding the zero-accepted recording.

## Decision and actionable next experiment

Keep this estimator experimental. It resolves one demonstrated mathematical
bias and improves retrospective errors, but background sensitivity and physical
model mismatch remain. Do not install it as calibrated distance or request another
unchanged-profile distance sweep just to repeat these failures.

Next engineering step: prepare and compile the isolated 350/100 kHz HPF comparison
images already described in ACCURACY_PATH_FINDINGS.md, with register readback and
distinct identities, preserving the October 28 image for restoration. Review
the exact build/configuration differences before requesting explicit permission
to flash. This task has NOT compiled or flashed those variants. After approval,
compare 350 -> 100 -> 350 with fresh empty references, unused empty holdouts and
supported 30/40/50 cm placements, keeping timing/gain/geometry fixed. Replay both
the current estimator and this frozen candidate on every condition; report all
errors, misses, false positives and clipping. Lower HPF is an experiment, not a
guaranteed fix, and does not increase sampled bandwidth.

## Reproduce

From the isolated repository, choose an unused output directory:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.fit_range_signal artifacts/new-signal-fit
./range-v1 test
```

The command emits report.json, synthetic.json, comparison.png and frames.jsonl.
Tracked summary evidence is in evidence/signal-fit-1; the original per-frame
results are in artifacts/signal-fit-1/frames.jsonl. Raw recordings are unchanged.
