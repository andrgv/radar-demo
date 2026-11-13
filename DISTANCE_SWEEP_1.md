# First distance sweep: no calibration justified

Source: user-reported 30/40/50 cm placements and return to 40 cm, bracketed by
empty captures. Each capture contains 101 accepted raw frames. All have zero
sequence gaps, CRC errors, header errors, restart indications and acquisition
rejections. Partial byte tails at stop are retained in original wire captures.
The initial 30 empty frames train the unchanged native-bin detection gate and
the median linear-power reference. Remaining 71 initial-empty frames and all
101 final-empty frames are excluded from fitting. Both have zero detections.

The exploratory distance estimator is fixed before examining these labels:
per-chirp mean removal, symmetric Hann, 4096-point zero-padded FFT of 64 acquired
samples, average power across valid chirps/RX, subtract per-frequency median
empty linear power, select maximum over provisional 0.15–1.50 m interval. No
label-dependent fit, offset, smoothing, threshold adjustment or search narrowing.
A spectral maximum in an empty scene is not a reading. These are provisional
coordinates; target association and absolute calibration remain unverified.

| User-measured placement | Median of per-frame ungated peaks | 5th–95th percentile | Native presence gate |
|---|---:|---:|---:|
| 30 cm | 32.6 cm | 25.0–38.0 cm | 58/101 |
| 40 cm | 34.8 cm | 32.6–40.7 cm | 93/101 |
| 50 cm | 42.4 cm | 32.6–132.5 cm | **0/101** |
| 40 cm repeat | 25.0 cm | 15.2–28.2 cm | 92/101 |

These percentile ranges describe variation across frames, not confidence intervals
for physical distance. Ungated peaks deliberately include rejected frames. In
particular, the 42.4 cm median at 50 cm is not an accepted distance measurement.
The native gate's presence decisions are not proof that a fine-spectrum maximum
comes from the box. At the repeated 40 cm position, 12/101 maxima hit the lower
search boundary, which invalidates treating that tail as a resolved range.

The two 40 cm medians differ by **9.78 cm**. A constant calibration offset cannot
resolve that discrepancy. Zero-padding improved numerical grid density but did
not establish centimeter accuracy. The 50 cm native gate failure differs from the
earlier well-aligned 50 cm experiment; scene/placement/reference changes remain
unresolved. The new empty-derived thresholds for bins1–4 are approximately
3.96, 17.32, 16.14 and 7.53 dB, and were not tuned after observing targets.

Before another calibration attempt, establish whether box lateral position,
orientation, support, radar position or nearby people changed, especially in the
40 cm repeat. If everything remained fixed, the estimator/scene fails the
repeatability requirement and requires a controlled reflector/placement experiment
and analysis of multipath and analog response. Do not refit an offset or suppress
outliers to make these values match the labels. No firmware or live estimator
change was made for this analysis.

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.analyze_distance_sweep recordings/distance-sweep-1 artifacts/new-sweep-analysis
```

`evidence/distance-sweep-1/report.json` includes hashes, all gate counts, provisional
errors, full search-boundary counts and both gated/ungated summaries.
`distance-estimates.png` shows all per-frame peak coordinates, including rejected
frames and large excursions; green markers denote native-gate acceptance only.
Local `artifacts/distance-sweep-1-analysis-full-scale/per-frame.jsonl` preserves the
individual provisional estimates. Raw captures remain unchanged and ignored by Git.
