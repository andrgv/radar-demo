# Held-out two-axis angular calibration (no new radar firmware)

This workflow estimates inter-RX **phase corrections** from a fixed-radar,
known-position sweep and measures directional error on completely excluded
poses. It does not reconstruct an extended wall/door, estimate sensor motion,
or validate the entire room. Always retain range/Doppler and angle uncertainty.

## Acquisition (fixed radar, one isolated target)

The existing `radar sweep` command now saves a background and nine named target
positions: training = center, left, right, up; validation = check_right,
check_left, check_up, check_down, center_repeat. The latter five must **never**
be used to fit the calibration. Right/left are defined **behind** the radar
facing forward. Carefully measure the target's reflecting center at antenna
height, its forward distance, and the horizontal/vertical offsets. A handheld
target can be examined qualitatively, but is rejected for calibration.

```bash
# First verify the hardware port, profile, and range with a known compatible recording.
.venv/bin/python -m radar sweep recordings/angular-sweep-01 \
  --port /dev/ttyACM0 \
  --config configs/qualification-hpf350.json \
  --distance 2.0 --offset 0.4 --seconds 5
```

Port is an **example**, not an automatically detected device. Choose the
correct serial device. For a 350 kHz high-pass profile, avoid near-range
positions where the return is heavily attenuated. You can use any repeatable
isolated strong reflector you already have; the existing prompt calls it a
"bottle", and the scattering center/pose uncertainty still matters.

The script captures a background and pauses for each pose. It saves raw ADC
and records pose labels. It then runs the existing quality checks: a local
range peak, sufficient contrast, and per-channel coherence >=0.90. If a pose
fails, do not reduce the threshold just to get a passing calibration.

## Fit and independently validate

```bash
.venv/bin/python -m radar.angular_calibration recordings/angular-sweep-01 \
  --output configs/angular-heldout-01.json \
  --report artifacts/angular-heldout-01-validation.json
```

By default `physical` mode applies phase-only gains relative to RX1 and keeps
the configured physical RX geometry. A saved config requires:

- all nine required poses accepted by the original sweep quality gates;
- 2D training geometry, bounded training phase-model residual;
- observed phase slopes near configured physical antenna geometry (max
  coefficient difference 0.12 wavelengths);
- every held-out off-axis position within 7 degrees of its surveyed direction;
- independent return-to-center error within 5 degrees.

If rejected, the command writes a diagnostic validation report but **does not
write a calibrated config**. Older six-position sweeps lack vertical holdout
measurements and are intentionally not eligible for certification.

If the effective measured baselines disagree with the physical model, first
check antenna order/orientation, relative phase sign, target isolation,
static background, and saved calibration matrix. Only after understanding the
cause should you consider the explicit experimental alternative:

```bash
.venv/bin/python -m radar.angular_calibration recordings/angular-sweep-01 \
  --mode empirical --output configs/angular-empirical-01.json
```

`empirical` fits apparent receive baselines rather than asserting physical
antenna positions. It requires the same independent holdouts plus plausible,
nondegenerate baseline lengths. It removes the old angle correction matrix,
sets mount roll to 0 (the empirical basis already includes orientation), and
marks geometry as **unverified**. Do not use it to disguise multipath.

Both modes deliberately replace any old `angle_matrix` with identity because
corrections are estimated in the raw-RX domain; otherwise calibration can be
double-applied. Both retain global `verified=false`: angular held-out success
is not certification of RF timing, range, world pose, or room geometry.

## Replay and compare (no firmware changes)

```bash
.venv/bin/python -m radar gui \
  --replay recordings/door03/closed-01 \
  --config configs/angular-heldout-01.json --point-cloud
```

Use only if the recording's profile, waveform, RX order, and mounting match
the sweep; otherwise comparisons are invalid. The existing `SceneReconstructor`
uses `config.gains` and `SpatialMapper` uses the configured geometry/matrix, so
the resulting calibration affects both the new deblending path and the FFT
angular displays without changing the deblending code.

**Next for recognizable 3D geometry:** collect data at *multiple surveyed radar
poses* and transform measurements into a shared coordinate frame, with
multipath and uncertainty handling. Calibration alone cannot convert a
stationary three-RX single view into a dense room scan.

## Unit tests

```bash
.venv/bin/python -m unittest tests.test_angular_calibration
```

The tests use simulated phase observations. They verify software rejection
behavior, not real-hardware accuracy.
