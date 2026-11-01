# Close-range diagnosis: background and interfering components

No live estimator replacement from this round. Current associated v3 remains
available unchanged. Every experiment scores misses, outliers, and empty runs;
no reference, channel, or threshold is selected using the true target distance.
This corpus has informed development repeatedly; it is not independent final
validation. Scene labels are the user's stated distances/capture order.

## Results on the recent stationary GUI captures

Mean absolute error among reported readings; report counts expose selection.

| Method | 30 cm MAE / reports out of 207 | 50 cm MAE / reports out of 206 |
|---|---:|---:|
| Associated v3, original reference | 8.88 cm / 70 | 1.83 cm / 141 |
| Refresh waveform only | 7.06 cm / 105 | 2.33 cm / 141 |
| Refresh detector only | 9.25 cm / 55 | 3.13 cm / 121 |
| Refresh both | 6.90 cm / 78 | 3.42 cm / 121 |
| No waveform subtraction | 9.19 cm / 62 | 20.01 cm / 118 |
| Chirp-averaged empty reference | 8.89 cm / 70 | 1.83 cm / 141 |
| Consistently Hann-weighted joint fit | 11.16 cm / 65 | 9.70 cm / 112 |
| Per-frame far-component nuisance fit | 5.35 cm / 129 | 3.58 cm / 141 |

Refreshing the reference only partly addresses the 30 cm problem and harms the
50 cm result. Removing subtraction is much worse at 50 cm. Chirp-index matching
of the stored reference is not a substantial contributor in this comparison.
Window tapering is not a successful fix. Modeling a faster component gives the
largest 30 cm improvement tested here and increases availability, but is not
accurate enough: median 26 cm, 95th-percentile error 12.8 cm, 17 reported errors
above 10 cm, and 78 misses. At 50 cm it introduces 4 adjacent jumps >20 cm versus
1 for associated v3; 10 errors above 10 cm remain versus 4. Not deployed.

The far-component trial improves several earlier target captures, but regresses
some (e.g. initial 350-a 50 cm 3.50 -> 3.89 cm); full earlier/empty results are
retained, not hidden. The original empty false detection remains under this model.

## What the signal says

waveforms.png compares empty-subtracted chirp averages from earlier and recent
30 cm recordings, sampling every twentieth frame across all three wire RXs.
Both contain faster oscillations superimposed on a slow shape. This is evidence
against treating the entire return as one clean sinusoid, not proof of the
physical origin (multipath, another reflector, electronics, etc.).

At the nominal 30 cm coordinate, the original objective loses a median 1.88% of
total centered signal energy relative to its preferred frequency in the recent
capture; earlier 30 cm runs lose .57%, .08%, and .10%. The fit prefers a shorter
coordinate, but the objective difference is small enough that a biased signal
model matters. This is diagnostic, not a confidence interval or a demonstrated
sensor minimum range. No calibration mapping or true-distance clamp was fitted.

## Reference experiment protocol

Original training = first 30 empty-before frames. Recent alternative = first 30
frames of the separate live-003 empty run, acquired before the stationary targets.
Evaluate only its remaining 178 frames for BOTH original and refreshed methods.
Earlier-series alternative = last 30 frames of empty-before; evaluate the middle
41 frames plus all 101 empty-after frames. No evaluation empty frames enter either
reference. Common empty denominator is 604 frames, not the original 724.
Original detector: 1/604 false detections. Refreshed detector: 0/604, but the GUI
empty test is now within the refreshed training recording, not a separate empty
holdout. Do not promote this to a validated false-alarm improvement. Target runs
remain wholly outside reference training. Three earlier independent empty-after
recordings remain in the comparison. Full report and per-frame outcomes retained.

## Additional model details

WeightedFit uses sqrt(Hann) on both data and sinusoid basis, with the weighted DC
component projected out of both. A simple windowed-data/unwindowed-model mismatch
is therefore not the reason for rejection. It passes phase-swept synthetic tones,
but fails real data. Results: ../weighted-fit-1.

FarComponentFit estimates one nuisance tone per RX from the current residual
waveform over nominal 1.5–5 m at 1 cm grid intervals, then jointly projects that
basis out of both the data-fitting objective and target bases. Target frequency
is shared across receivers over the existing .15–1.5 m grid. SVD discards nearly
absorbed directions at 1e-6 singular value; this avoids arbitrary normalization
when a target basis coincides with the nuisance basis. Existing presence,
association support and boundary rejection apply. No temporal smoothing used.
The nuisance coordinate is spectral, not identification of a physical far object.
This is a one-pass alternating approximation, not a global two-tone optimum.
It passes a stronger-far-tone synthetic control but does not resolve arbitrary
multiple reflections, calibration, close-in ambiguity or empty presence errors.
Results: ../far-component-2. Only presence-accepted frames need expensive fitting;
all other frames remain in report denominators as misses.

## Reproduction and validation

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.diagnose_close_range
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_weighted_fit
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_far_component
./range-v1 test
```

37 tests pass, including weighted signal/model consistency and a known near tone
with stronger far interference. Existing associated fit tests still pass. The
small AssociatedFit.prepare refactor preserves its default centering operation;
weighted-fit baseline replay reproduced associated v3 report counts and errors.
No new hardware recording, flash, firmware or GUI algorithm change.

Next offline hypothesis: refine nuisance and target frequencies jointly rather
than estimating the nuisance once. It must preserve the 50 cm result and earlier
captures while improving 30 cm; lower aggregate error alone is insufficient.
