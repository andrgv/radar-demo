# Controlled-orientation sweep and five-frame rolling average

The second sweep uses the same fixed fine-spectrum estimator and native-bin
presence gate as the first. Its own first 30 empty frames fit the background;
71 remaining initial-empty frames and 101 final-empty frames are held out.
Distance labels are used only to calculate errors, not to adjust the estimator.
All six raw captures contain 101 accepted frames with zero reported sequence
gaps, CRC/header errors, restarts or acquisition rejections. No firmware or live
processing was changed for this analysis.

## Results without averaging

| Measured placement | Median of all provisional peaks | Native accepted frames |
|---|---:|---:|
| 30 cm | 32.6 cm | 68/101 |
| 40 cm | 29.3 cm | 85/101 |
| 50 cm | 58.7 cm | 30/101 |
| 40 cm repeat | 28.8 cm | 96/101 |

Both empty checks have zero native detections. Empty spectra nevertheless have
maxima; their ungated peak coordinates must never be called distance readings.
All target medians above include rejected frames, preserving the estimator's
failures rather than showing only successful detections.

The two 40 cm medians differ by only 0.54 cm, compared with 9.78 cm in the first
sweep. This is improved repeatability in this pair, but both are about 11 cm short.
More controlled orientation may contribute; the comparison does not isolate it
from background/environment changes. The 30 cm median is larger than the 40 cm
median, so the mapping is not reliably monotonic. A single offset or gain does
not solve this across positions. The 50 cm median also shifts from 42.4 cm in
sweep 1 to 58.7 cm here: reliability across sessions remains unproven.

## Rolling-average experiment

Fixed beforehand: causal arithmetic mean of five consecutive accepted provisional
estimates (~0.5 s at nominal cadence). Require a full window; immediately clear
history on any rejected/nonfinite frame, and start fresh for each recording.
There is no held last distance and no smoothing across gaps. This tests display
smoothing only; native presence acceptance does not prove fine-peak association.

Compare raw and averaged estimates on exactly the same output frames to avoid
confusing a lower output count with an accuracy improvement:

| Placement | Averaged outputs / total | Raw MAE on same frames | Averaged MAE | Raw / averaged std dev |
|---|---:|---:|---:|---:|
| 30 cm | 53/101 | 11.1 cm | 8.3 cm | 12.5 / 9.4 cm |
| 40 cm | 70/101 | 10.3 cm | 10.6 cm | 3.5 / 3.0 cm |
| 50 cm | 7/101 | 8.5 cm | 7.9 cm | 4.7 / 2.8 cm |
| 40 cm repeat | 90/101 | 11.3 cm | 11.2 cm | 6.0 / 3.8 cm |

These are provisional estimator errors relative to user-entered positions, not
certified calibrated accuracy. Standard deviation measures variation, not bias.
The average reduces variation but does not remove substantial bias. At 50 cm it
also leaves 94/101 frames with no averaged output. Full-window startup and reset
costs are included, not hidden. Both empty checks have zero averaged outputs.

Do not deploy this smoothing as an accuracy fix. The next engineering task remains
measurement-model/configuration verification and target association, with the
previously discussed controlled HPF comparison as a possible isolated experiment.
No firmware should be flashed without explicit approval. Keep this sweep as
failed-accuracy evidence and require a fresh independent test after any change.

## Reproduction and artifacts

```sh
MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.analyze_distance_sweep recordings/distance-sweep-2 artifacts/new-sweep-2
MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.evaluate_range_average artifacts/new-sweep-2 artifacts/new-sweep-2-average
./range-v1 test
```

Use new output directories. Evidence is in `evidence/distance-sweep-2/`:
`estimator-report.json` includes raw hashes/transport details;
`average-report.json` includes all-frame, accepted-only and matched-frame metrics;
`rolling-average.png` shows rejected peaks, accepted peaks and averaging gaps;
`tests.txt` records 15 passing tests. Two added tests verify that averaging does
not retain a prior distance after rejection or use future data. The live detector
is unchanged; averaging is only in the offline evaluation tool.
