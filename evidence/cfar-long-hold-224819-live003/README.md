# Long stationary hold and repeated empty intervals

Recording: `recordings/gui-20261109-224819-094246/live-003`. CFAR v2, guard 1, training/minimum 4, factor 2. No processing, threshold, firmware or raw recording was changed for this analysis.

## Confirmed scene sequence

The user confirms eight consecutive states: **80 cm, empty, 100 cm, empty, 50 cm, empty, 30 cm, empty**. Lap durations are 30.18, 15.64, 16.24, 15.78, 18.01, 16.04, 16.34 and 19.21 seconds, totaling 147.44 s. Recording started slightly before the stopwatch; the scene was changed after pressing lap, with a couple-second transition.

The table uses cumulative lap boundaries with three-second margins, except the initial hold uses 5–25 host seconds. Stopwatch total and host recording span differ by about 1.55 s, so labels remain approximate. No boundaries were chosen from estimated distance.

## Interval results

**Offline diagnostic estimates omit the live host-freshness gate. They do not restore valid live output.** The column is provided to inspect the saved raw signal after the live gate starts rejecting frames.

| State | Host window (s) | Saved live numeric outputs | Offline numeric outputs | Offline median (cm) | Offline 5th–95th (cm) | Conditional MAE (cm) |
|---|---:|---:|---:|---:|---:|---:|
| 1: 80 cm | 5.0–25.0 | 201/201 | 201/201 | 73.6 | 72.7–74.1 | 6.5 |
| 2: empty | 33.2–42.8 | 97/97 | 97/97 | 69.6 | 69.0–70.6 | — |
| 3: 100 cm | 48.8–59.1 | 101/103 | 101/103 | 82.7 | 74.2–87.8 | 17.8 |
| 4: empty | 65.1–74.8 | 74/99 | 99/99 | 71.1 | 70.2–72.3 | — |
| 5: 50 cm | 80.8–92.9 | 0/121 | 121/121 | 67.5 | 66.2–69.3 | 17.9 |
| 6: empty | 98.9–108.9 | 0/101 | 101/101 | 70.8 | 69.8–71.9 | — |
| 7: 30 cm | 114.9–125.2 | 0/104 | 104/104 | 24.3 | 22.3–28.1 | 5.7 |
| 8: empty | 131.2–144.4 | 0/133 | 133/133 | 71.0 | 70.1–72.3 | — |

## Initial 80 cm hold: stable but biased

All 201 frames in 5–25 host seconds produce live numeric outputs. The median is **73.65 cm**, with a 72.71–74.08 cm empirical 5th–95th interval and **0.45 cm standard deviation**. Mean absolute error against the reported 80 cm placement is **6.47 cm**, with no output within 5 cm.

Low variation while untouched is not accurate absolute ranging. Previous 80 cm placements gave other medians, including 82.9 cm, and the errors here have different signs/magnitudes at different placements. A global offset is not justified. All coordinates remain uncalibrated; measured placement uncertainty is unquantified.

## Persistent unwanted empty-scene return

All four empty interiors produce an offline peak near **70–71 cm**. The first empty interior also produces this reading in every saved live frame, before any timing rejection. It is therefore a detection/ranging failure independent of the later timing-gate failure.

The raw median spectra show a repeatable empty-scene spectral component. Its physical origin is not established: do not identify it as a particular object, leakage source, alias or multipath path without further evidence. Adding targets changes the spectrum and can pull a raw maximum away from the actual target placement. The 100 cm and 50 cm medians demonstrate that a fine peak is not automatically the target distance.

Further constant-offset calibration or display smoothing would not address this pattern. A next detector/estimator change should explicitly test separation of persistent scene structure from a target return across all empty/target cases, without simply blacklisting the 70 cm bin and losing legitimate targets there.

## Capture timing failure

There are **1,469 accepted raw frames**. Sensor elapsed time spans **146.9 s**, while host arrivals span **145.889 s**. Sensor-minus-host elapsed difference grows at about **0.00694 s per host second** (~0.694%). Median host spacing is 99.344 ms, versus 100 ms in sensor timestamps.

At **72.399 host seconds** (72.9 sensor seconds), the current 0.5-second relative-time gate is crossed. All **741 remaining frames** are rejected as `host_sensor_timing_mismatch`, clearing confirmation and numeric range. An earlier CRC error/sequence gap makes 742 capture rejections in total. That single corruption does not explain the steadily accumulating time difference.

Shorter live-001/002 captures also show about 0.7% endpoint rate differences but finish before the 0.5-second limit. Clock scale, timer configuration and acquisition timing need investigation; absolute frame freshness and the cause of the rate discrepancy are not established. Do not simply disable the freshness gate or relabel these rejections as target misses. No flashing was performed.

## Artifacts

- [Lap-aligned live/offline output and interval spectra](lap-aligned-diagnosis.png)
- [Full recording with timing drift](long-hold-diagnosis.png)
- [Metrics, hashes, confirmed lap labels and diagnostic bins](report.json)

These data are sufficient to demonstrate the two failure modes above. No additional general distance sweep is needed before investigating them. Scene labels are approximate, frames are correlated, and offline conditional errors must be read alongside output counts and the freshness limitation.
