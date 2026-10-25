# Paired target/control analysis

Reproduce from the project root:

```powershell
python -m radar paired-audit recordings --config configs/range-vendor-matrix-experimental.json --output artifacts/paired-audit
```

The command reads existing data without modification and emits `report.json`,
paired FFT spectra, signed angular response plots and power time series.
The nine recordings currently in this workspace do not include newly described
left/right position series or screenshots. The two pair associations below come
from directory names and prior experimental descriptions. Metadata still contain
template labels and cannot independently establish matching geometry.

| Pair | Bin 4 target/control change | 95% moving-block bootstrap interval |
|---|---:|---:|
| bottle_only_03 → target_with_bottle_03 | +5.187 dB | +4.969 to +5.300 dB |
| empty_usb_left_02 → target_bottle_usb_left_02 | +0.169 dB | -0.006 to +0.452 dB |

The first pair retains the bottle; the second also changes the bottle and is
confounded. In the first pair per-RX changes are +5.35, +5.04 and +5.12 dB.
All target-condition frames exceed the first half of control's 99th percentile;
none of its held-out control frames do. These are within-session descriptive
checks, not calibrated detection probabilities or general false-alarm rates.
Operator/body motion, changed occlusion and reflected paths can contribute.
The return is associated with the target condition; it is not uniquely assigned
to the iPad metal back or a direct ray.

## Angles, stability and uncertainty

The analysis uses raw complex channel covariance and subtracts the mean control
covariance from the target covariance. This avoids requiring coherent phase
alignment between separate sessions. It retains negative eigenvalues and signed
beam power, rather than forcing a PSD covariance that can manufacture a target.
The steering signatures use the candidate factory matrix and nominal geometry;
range power comparisons do not depend on that matrix.

The cleaner pair has a differential peak at (-10, -25) degrees on a 5-degree
grid. Per-frame peak 5th/50th/95th percentiles are (-15,-30), (-15,-25),
(-5,-15) degrees. Raw RX2/RX1 and RX3/RX1 phase circular standard deviations are
9.94 and 5.72 degrees. Its angular half-power region extends across the entire
sampled azimuth field and elevation approximately -60 to +10 degrees. Neither
the mean peak nor temporal stability establishes accurate angles.

Bootstrapping 200 replicates in 5-frame circular blocks quantifies limited
within-session repeatability. A collapsed angular interval means all bootstrap
maxima landed on the same grid cell, not zero uncertainty. Model error, physical
RX mapping, coefficient convention, carrier, pose and angle signs are not
included. The weak/confounded pair's maximum lies on the grid boundary and is
not a useful iPad direction. No calibration parameters were fitted or installed.

## Recurring bin 23

Bin 23 is a local peak in 98% of bottle-only frames and 100% of target-with-bottle
frames. Its target/control change is only +0.905 dB, much less than bin 4.
It also exists in other controls. Its shape is window dependent: in the two
bottle sessions, it is not a local maximum under a rectangular window. Other
sessions retain a rectangular-window maximum. Changing windows changes leakage
and resolution; this observation alone does not establish an FFT artifact.

It is visible in independently processed raw sample spectra, prior to angle
correction and plotting. Therefore the angular matrix and 3D rendering cannot
be its origin. It remains a background-associated high-frequency feature of
unknown physical origin: clutter, multipath, leakage, interference and acquisition
effects are not distinguished by these static captures. It was not notched or
converted into a presumed obstacle. The JSON records power per RX, variability,
local contrast and peak frequency for every session. Interpret distances only
under the selected nominal model: bin 4 is 1.390 m and bin 23 is 7.994 m before
interpolation, not hardware-calibrated coordinates.

## Acquisition investigation and instrumentation

The reported counters rose by 22 sequence gaps and 22 CRC errors. A rejected
frame may explain a sequence gap, so these totals must not be added as separate
loss counts. Zero device errors/drops means no corresponding firmware counter
increase was reported; it does not prove the UART/USB/host path is clean.
Firmware uses 2 Mbaud UART, 6580-byte frames and a 100 ms frame schedule: roughly
0.658 Mbit/s including UART start/stop bits. Nominal bandwidth is sufficient,
but receiver scheduling, bridge buffering and physical serial errors remain
possible. Static source inspection does not identify the actual failure.

Saved packets are re-encoded after CRC validation. All nine saved files parse
without CRC errors; only plate_0_6m contains a missing sequence. This cannot
reproduce the user's newer live CRC counters. No original rejected serial bytes
were saved, so a retrospective transport root cause would be speculation.

New `record` and GUI `--record` sessions preserve `serial-wire.bin` plus
`transport.jsonl`, with chunk offsets, timestamps and cumulative parser counters.
`frames.grd` is unchanged and remains clean replay input. The original byte log
can reproduce parser resynchronization and corrupted frames. Parser discarded-byte
accounting now includes bytes removed at header/CRC failure. Logging is buffered
and only enabled while recording. Synthetic corruption/resynchronization tests
verify preservation and one rejected packet leading to one missing sequence.
Firmware, baud rate, commands and packet format have not changed.
