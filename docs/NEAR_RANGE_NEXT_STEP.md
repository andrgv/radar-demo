# Near-range investigation, 2026-11-01

Status: **not fixed**. No candidate below is installed in the live pipeline.
All raw captures and current firmware remain unchanged.

The confirmed fresh order is calibration empty, independent empty (live-002),
30 cm (003), 40 cm (004), 50 cm (005), independent final empty (006), under
recordings/gui-20261101-153737-539230. These recordings have no reported CRC,
sequence-gap or timing errors. Transport success does not certify distances.

## Replay results

The first four rows use the same 2,279 target frames and 1,221 empty evaluation
frames across the paired HPF series and two labeled GUI sessions. Training
frames are excluded. Counts describe displayed experimental distances;
presence alone may also be accepted when a boundary fit prevents distance output.

| Method | Target reports / 2,279 | Within 2 cm / 2,279 | False empty reports |
|---|---:|---:|---:|
| Existing associated estimator | 732 | 349 | 1 / 1,221 |
| Joint spectral gate, pooled RX | 2,134 | 829 | 248 / 1,221 |
| Joint spectral gate, per RX | 2,138 | 829 | 402 / 1,221 |
| Empty-covariance weighted sinusoid | 2,199 | 502 | 339 / 1,221 |
| Longer, refreshed empty covariance | 2,166 | 620 | 258 / 790 |

The last row changes training: 60 empty frames fit the waveform/covariance and
30 subsequent empty frames set the threshold. For GUI sessions these come from
the independent empty-before recording, leaving its later frames for evaluation.
It therefore has a different empty denominator and is not a like-for-like
false-alarm comparison. The final empty is never used for training.

On the fresh session, the longer-calibration trial reports 212/214 frames at
30 cm, but their median is **40.5 cm**, MAE 10.58 cm, with zero within 2 cm.
At 40 cm its median is 35 cm; at 50 cm it is 53.5 cm. It falsely reports a
distance in **159/217 final-empty frames**. A smooth trace and high hit rate
would conceal failure here. No offset or moving average resolves these results.

## Assumptions and limits

Joint gating models covariance of five native log-power bins, pooled or per
receiver. Its chi-square-derived thresholds are engineering choices, not
validated false-alarm probabilities. Its distance component remains the
associated sinusoid fit. Whitening models the averaged raw waveform with
per-RX regularized empty covariance and a shared sinusoid frequency. It learns
only from empty data, but assumes that future clutter resembles that empty.
Thresholds use twice the maximum score of a separate short calibration segment;
this is also not a guaranteed false-alarm rate. Three consecutive accepted
frames are required, and current-frame rejection clears the reading.

All these captures are now development data because we inspected the results.
They remain useful regression evidence, not untouched validation of future tuning.
Synthetic tone tests pass, including fractional-bin estimation. That supports
the frequency-fitting implementation, but does not prove the real waveform is
a single target tone. It does not rule out every acquisition/configuration issue.

The nominal 64 samples at 5 MHz and slope 33.69140625 THz/s span approximately
431.25 MHz over N/Fs (424.5 MHz over N-1 intervals). Native FFT spacing is
0.347585 m. This is not a hard accuracy floor for an isolated strong sinusoid;
it does limit separation of nearby mixed returns. Zero-padding does not add
measurement bandwidth. At 30 and 50 cm, nominal beat frequencies are roughly
67.4 and 112.4 kHz, below the present 350 kHz HPF corner. This attenuates near
signals; the corner is not a hard minimum range. Prior 100 kHz trials did not
establish a general fix. None of this proves one unique cause of the failures.

## Acquisition work blocked by missing supported configuration

The generated sensor header refers to the Xensiv Radar CMOS Configuration Tool.
Infineon's June 2026 moderator response says custom configurations are not
supported, the tool is under maintenance, and there are no immediate plans for
public availability:
https://community.infineon.com/t5/Radar-sensors/BGT60CUTR13AIP-Custom-chirps-samples-RX-configuration-tool/td-p/1230723

The official localization example also uses 64 samples at 5 MHz; switching to
it alone is not evidence of greater sampled bandwidth:
https://github.com/Infineon/mtb-example-psoc6-cmos-radar-clutter-clustering

Next action is to obtain a supported raw-acquisition profile and its timing/filter
metadata for 0.15–0.55 m, or a documented existing profile suitable for that task.
A ready-to-send request is in INFINEON_CONFIGURATION_REQUEST.txt. It has not
been sent. Do not guess coupled sequencer registers or merely change the host's
sample count. No new capture is needed with unchanged settings to repeat this failure.

Once a supported configuration is available: review and build it offline,
confirm packet dimensions, save rollback firmware, then obtain approval before
flashing. Validate register identity and raw transport first. Freeze estimator
settings before collecting calibration empty, independent empty, stationary
30/40/50 cm and final empty, with identical box orientation. Score misses and
false alarms alongside error, never only accuracy on selected successful frames.
Centimeter-level accuracy remains an unfulfilled requirement.

## Reproduction

From the wavvy-range-v1 folder:

```sh
./range-v1 test
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_joint_presence
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_whitened_range
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_long_whitening
```

Scripts rewrite their corresponding evidence reports, never recordings.
Per-frame results and summaries are in evidence/joint-presence-1,
evidence/whitened-range-1 and evidence/whitened-long-1. The input manifest records
SHA256 hashes of raw recordings and configurations. All 46 MVP tests pass;
test success is not physical range validation.
