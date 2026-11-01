# Calibration study: some error reduction, no reliable distance model

Compared a peak correction and a small spectral model using existing supported-box
captures. **Neither demonstrates centimeter accuracy or reliable generalization.**
No model was installed in the live pipeline; firmware and original raw data remain
unchanged. Frozen coefficients are for research/prospective comparison only.

## Data and boundaries

13 target recordings, 1,916 frames, across four independently fitted empty-reference
setups. User-reported labels: 30 cm (2 recordings), 35 cm (1), 40 cm (6), 50 cm (4).
These are not independent rooms or days. Setup one includes only one 50 cm target;
35 cm has especially weak repeat coverage. The 40 cm untouched capture and its
prior placement remain in the SAME setup, never opposite sides of a setup fold.

Excluded the operator-held 1 m captures, the capture with admitted mid-recording
repositioning, and the 12 cm/October distances outside this study's interval.
Exclusions are explicit in the machine-readable report, not chosen by model error.
Previously observed failures remain valid evidence elsewhere in the repository.

For each setup, use its first 30 empty frames for reference fitting; other empty
frames are not used to fit references or regression coefficients. Each test setup
can use its own empty-only reference, just as a new physical session would. No test
target labels are used in features, normalization or regression fitting.

Primary evaluation: hold out an entire setup, including ALL target recordings
sharing its reference. Secondary evaluation: hold out ALL recordings at one distance.
The latter may share an empty reference with training distances, so it is a weaker
scene-isolation test; endpoint folds (30/50 cm) also require extrapolation.
No random neighboring-frame split. Existing recordings had already been inspected:
this is retrospective development evaluation, not an untouched prospective test.

## Fixed models and features

Models/hyperparameters were fixed before examining this benchmark:

- Raw fine-spectrum peak: the uncalibrated baseline.
- Constant: predicts training-set mean distance; ignores radar features entirely.
- Linear peak: ordinary least-squares affine mapping from fine peak to distance.
- Spectral ridge: linear model with fixed ridge penalty 0.1 after training-only
  standardization. Features are fine peak, positive residual spectral centroid,
  residual width, integrated ROI power ratio, and four native-bin positive-residual
  energy fractions. No record name, frame number, setup ID or distance label feature.

All use the existing mean-removal/Hann/averaged-power processing. The spectrum is
sampled with a 4096-point padded FFT; positive changes refer to the median linear
empty-power reference. Fixed search/feature ROI is provisional 0.15–1.50 m. This
is not new bandwidth. Each recording gets equal total regression weight regardless
of its duration. No fitting only on successful detections, prediction clipping,
new thresholds, smoothing, label-dependent window or hyperparameter search.

## Held-out error

Values are mean absolute errors (cm), first averaging frames within each recording,
then equally averaging recordings. All frames are included, including misses.

| Model | Entire setup held out | Entire distance held out |
|---|---:|---:|
| Raw fine peak | 8.74 | 8.74 |
| Constant training-mean predictor | 5.88 | 7.46 |
| Linear peak calibration | **5.16** | **6.96** |
| Spectral ridge calibration | 5.84 | 8.18 |

The constant baseline is essential: the narrow label interval and many 40 cm
recordings make predictions near 40 cm look relatively good. The linear mapping
beats that constant by only 0.72 cm in setup holdouts and 0.50 cm in distance
holdouts. The spectral model does not clearly improve on the simpler mapping.
These small differences have no established statistical significance with this
limited, correlated dataset. A low training error would not resolve this.

Giving each DISTANCE equal weight rather than each recording produces setup-holdout
MAEs of 7.65 / 7.13 / 6.22 / 6.46 cm for raw / constant / linear / spectral models.
For withheld distances those values are 7.65 / 8.69 / 8.02 / 8.65 cm: neither fitted
model improves on raw peaks under that distance-balanced metric. This is another
reason not to claim broadly better ranging from the headline average alone.

Only about 15% of predictions from the fitted models are within 1 cm in setup
holdouts (recording-average fraction, before presence rejection). Linear calibration
has held-out MAE ~10.5 cm at actual 30 cm and ~7.6 cm at actual 50 cm. It performs
best near the overrepresented 40 cm label. When 35 cm is entirely withheld,
linear/spectral MAEs are 5.60/5.05 cm; when 40 cm is withheld they are 1.57/3.88 cm.
That uneven performance is not a usable general distance guarantee.

The full-data frozen linear model is approximately:

`predicted_m = 0.331682 + 0.205909 * raw_peak_m`

This heavily compresses different peak estimates toward ~40 cm. It is a diagnostic
finding, NOT a correction to install. A whole family of unrelated measurements
could look smoother and closer to the training mean under this mapping.

## Detection and empty scenes remain separate

The unchanged native detector accepts 1,299/1,916 target frames, missing 617 (32.2%).
Per-record gated and ungated errors, biases, percentiles and acceptance fractions
are all in the report. A regression prediction does not override a missed target.

The 9 within-setup empty evaluations total 1,393 unused frames and yield zero
native detections. The regression models themselves still produce plausible
numbers for empty scenes (e.g. the spectral model returns about 42 cm in one empty
recording). **Only the existing presence gate rejects those outputs.** The new
models have not learned empty-scene rejection and are not confidence estimators.
The known mismatched-background failure (35/61 positives) is unchanged and is
not erased by these within-setup zero counts.

## Decision and next work

Do not deploy either calibration as reliable range. It is possible that a better
physical estimator, features or training design could help; this small experiment
does not prove that calibration or every nonlinear model is impossible. However,
these simple models do not justify requesting more arbitrary calibration captures
or claiming centimeter accuracy. No fixed ±1 cm validation claim is supported.

Both full-data candidate models are frozen for optional future prospective tests,
marked EXPERIMENTAL_NOT_LIVE_NOT_VALIDATED. Do not silently retrain on proposed
32/45 cm validation captures. If a future model is chosen and tested, retain this
failed benchmark and evaluate miss/false-alarm rates alongside prediction errors.
Measurement-model/target-association and the previously identified RF/filter
configuration questions still require resolution before a distance guarantee.

## Reproduce

```sh
MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.calibrate_range_offline recordings artifacts/new-calibration-study
./range-v1 test
```

The output directory must be new. `tools/calibrate_range_offline.py` contains the
explicit record/label/setup manifest. `evidence/calibration-study-1/report.json`
records hashes, train/test lists, per-fold coefficients, gating counts and all
metrics. `frozen-models.json` records the final research-only models and training
hashes; `held-out-predictions.png` shows per-record medians and 5th–95th percentiles,
not uncertainty intervals on physical range. Full arrays/recordings remain local.
Five tests cover setup/distance separation, known affine recovery, no clipping,
equal record weighting and training isolation. All 20 tests pass.
