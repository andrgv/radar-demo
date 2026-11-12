# Pitch-rotation calibration experiment (no new firmware)

This tool tests the PSoC6 / BGT60CUTR13AIP **physical receive-array model** using a *fixed target and support* while **pitching the antenna** in a new room. It does not assume the previous box-height experiment is transferable. It neither alters the radar configuration nor certifies a 3D calibration.

## Setup and coordinates

- Keep **one metal bottle (or a smaller isolated reflector) fixed in exactly the same location** on **one stable support** throughout the **entire target pass**. At each pitch you move **only the radar angle**, not the bottle/support.
- The radar points approximately along world `+Y`; `+X` is right when standing behind it; `+Z` is up above the floor. `+pitch` means the radar **looks upward**, with fixed yaw. Roll is the physical array mounting angle and must stay constant; use `+90` only if that matches the orientation established earlier.
- Measure the **antenna-package center** height and the **bottle's reflecting center** height, and forward separation. For a 23.5 cm upright bottle, midpoint = top of support + 11.75 cm is only an approximation to the true scattering center.
- Prefer a rigid pitch hinge whose axis passes through the antenna center. **If the antenna moves during pitch, edit the `antenna_xyz_m` for EACH pitch in the plan**, in world meters. Even centimeter-scale motions affect geometry at this frequency.
- Measure the pitch with an inclinometer/protractor, and **edit the actual `pitch_deg`** in the plan. Orient the mount reproducibly so each empty-background pose can be reproduced in the bottle-present pass. Keep roll/yaw fixed.
- Change rooms freely between the **old** experiment and **this** experiment. During **this** experiment, do not move the support or rearrange surrounding objects.

## Install

Unzip into the repository root, or copy `tools/pitch_sweep.py` and `tests/test_pitch_sweep.py` into the corresponding directories. Dependencies are the existing radar project, `numpy` and `matplotlib`.

```bash
.venv/bin/python -m unittest discover -s tests -p test_pitch_sweep.py -v
```

## 1. Generate a plan (example dimensions — replace with YOUR NEW measurements)

```bash
.venv/bin/python tools/pitch_sweep.py init \
  --config configs/qualification-hpf350.json \
  --output configs/pitch-sweep-plan-01.json \
  --forward 2.0 \
  --antenna-height 0.70 \
  --target-center-height 0.70 \
  --target-right 0.0 \
  --mount-roll 90
```

**0.70 m heights above are examples, not measurements or a requirement.** Replace those values with the setup at your new location. In the plan JSON, edit the per-pitch `antenna_xyz_m` whenever the antenna center translates; don't leave the assumed identical values if the pivot is elsewhere. Edit `pitch_deg` to the angles you actually achieve. Default pitches: -15, -10, 0, +10, +15, and a repeated 0. The **training set is -15, 0, +15**; **-10, +10, repeated 0** are never used to fit receiver phase offsets.

Check geometry before connecting to the radar:

```bash
.venv/bin/python tools/pitch_sweep.py check --plan configs/pitch-sweep-plan-01.json
```

The command prints the target's expected relative elevation for each pitch (negative when pitching the radar above a level target), range and range-bin association.

## 2. Record

```bash
.venv/bin/python tools/pitch_sweep.py record \
  --plan configs/pitch-sweep-plan-01.json \
  --port /dev/ttyACM0 \
  --output recordings/pitch-sweep-01 \
  --seconds 6
```

**Two-pass procedure:**

1. Without the bottle, record the support/room at every pitch. Keep other objects still.
2. Put the bottle into its measured marked location **once**. Do not move it or its support again.
3. Reproduce the same radar angles and antenna-center positions while recording target-present data.

The tool guides each capture and waits 3 seconds before starting. A new output directory is required; it refuses to overwrite recordings. `recordings/pitch-sweep-01/pitch_plan.json` and `config.json` preserve the geometry and acquisition configuration.

**Do not use `--handheld`.** If the antenna tilts by hand without a reproducible pivot, your background and target poses may not match and phase subtraction can fail.

## 3. Analyze (offline)

```bash
.venv/bin/python tools/pitch_sweep.py analyze \
  recordings/pitch-sweep-01 \
  --output artifacts/pitch-sweep-audit-01 \
  --domain mixed \
  --z-min 0.0 --z-max 1.5
```

`--domain mixed` applies the existing Infineon 3×3 angle matrix to the measured raw RX signals, then compares phase to the 3-RX physical array steering model. `--domain raw` is a separate diagnostic: it predicts the raw response by inverting that matrix. The two variants must be treated as model comparisons; don't select the better one based on held-out measurements and then claim an untouched test.

The pipeline subtracts a **separate complex spectral background per pitch**, checks raw packet/profile consistency, requires >=20 frames, coherence >=0.90, the configured >=12 dB local-contrast threshold, no saturated ADC samples, and a local range peak at the fixture's expected target range bin. It **never silently relaxes gates**.

It then:

1. Fits **only two static receive-channel phase offsets** using the three training pitch captures; there is no per-pitch correction or room-template fit.
2. Predicts complex receiver phase at the held-out -10, +10, and repeated 0 captures using measured geometry and physical antenna baselines. Reports independent phase errors.
3. Inverts the held-out phase to estimate the **same target's world height** over the explicitly declared `--z-min` to `--z-max` interval. The scan uses *known horizontal target position* (an experimental fixture), and flags multiple plausible heights, bad fits, or boundary solutions as ambiguous.

Outputs: `summary.json`, `phase_vs_pitch.png`, `height_inversion.png`. All remain **UNVERIFIED**. By default, no calibration JSON is exported.

**Optional**: Add `--export-pilot configs/pitch-phase-pilot.json` to the analysis command. This saves a separate phase-adjusted matrix configuration **only if all held-out captures pass** the original quality gate, show <=5 degrees error on both RX phases, recover height within 5 cm, and have no ambiguous height solution. The pilot retains `verified=false` and must not be presented as a validated 3D calibration. Never overwrite `configs/qualification-hpf350.json`. Even passing this test does NOT prove generalization beyond this bottle, height, or room.

## Scope and caveats

- This controls the earlier **support-height confound**: the target and support are unchanged when the radar pitches. It does **not** isolate all multipath or an extended bottle's moving scattering center.
- Background spectra are collected in a separate pass; returning the radar to the **same full pose** for target captures is essential.
- The analysis uses known target horizontal coordinates and fixture range bin, therefore it is **not a blind object-detection system**.
- Training and held-out angles use the **same stationary target at one height**; successful angle holdouts establish pitch response, but not generalization to new target heights, new targets, other rooms, or moving-robot operation. Later measurements will be required for that.
- Narrow range FFT bins do not resolve different parts of the bottle. The high-coherence criterion is not proof of isolated single-path scattering.
- If one of three training poses fails, **NO FIT** is reported. If heldouts are rejected or height solutions ambiguous, don't certify elevation.
- The `+90°` roll remains an **experimental hypothesis** from the prior dataset. Do not rotate the array numerically a second time on top of this setting.

## Correct an existing plan for a flat box and a bottom-edge pivot

**Do not record using the original fixed-antenna plan if the board tilts around its bottom edge.** Use the new `pivot` subcommand to create a separate corrected plan. It uses a fixed horizontal pitch axis and computes the antenna-center position at every angle. The original JSON remains unchanged.

Before running, measure:

- **Support-base height above floor (m)**: If the flat box rests on the floor, enter `0`. If it rests on a table, enter the tabletop's height above floor (e.g., `0.34` only if you measured that actual tabletop height).
- **Zero-pitch antenna-center height above floor (m)**: The antenna package center, not the laptop or table surface.
- **Pivot-up distance (cm)**: At zero pitch, vertical separation *antenna center minus fixed bottom-edge pivot*; positive if antenna is above hinge.
- **Pivot-forward distance (cm)**: At zero pitch, signed forward separation *antenna center minus pivot*, positive toward bottle, negative away from it. Use `0` only when the centers actually lie in the same vertical plane.
- Measure **forward distance at zero pitch** from the antenna center to bottle center; edit `target_xyz_m[1]` in the plan if not actually 2.0 m.

For user's 5.5 cm-high flat plastic box and 23.5 cm-high bottle:

```bash
.venv/bin/python tools/pitch_sweep.py pivot \
  --plan configs/pitch-sweep-plan-01.json \
  --output configs/pitch-sweep-pivot-corrected.json \
  --support-base-height 0.34 \
  --box-height 0.055 --bottle-height 0.235 \
  --antenna-zero-height 0.34 \
  --pivot-up-cm MEASURED_VALUE --pivot-forward-cm MEASURED_SIGNED_VALUE
```

**The `0.34` values are examples only**: replace with separately measured table (support base) and antenna-package heights. If box is on floor, support-base height is `0`, and bottle center `0.1725 m`; if on a 34 cm-high table, bottle center is `0.5125 m`. Incorrect height assumptions invalidate the geometric test.

Check calculated pitch geometry:

```bash
.venv/bin/python tools/pitch_sweep.py check --plan configs/pitch-sweep-pivot-corrected.json
```

Then record with `--plan configs/pitch-sweep-pivot-corrected.json` instead of the original. The bottom edge must remain a **fixed pitch pivot with no sliding or yaw**, and pitch angles must be measured. For a nonfixed pivot or hinge axis other than sensor-right, measured antenna xyz per pose is required; no mathematical rotation can correct unknown movement.

## Serial-integrity fix for pitch recording (November 2026)

The earlier recorder opened `/dev/ttyACM0`, cleared its input once, and
immediately sent `B`. Unlike a clean 30-second diagnostic, it did not first
send `c` and wait for the previous stream to stop. That startup difference
could produce partial/leftover frames. A 30-second stationary test with zero
errors is **not** proof the USB stream is always error-free while capturing.

The revised recorder now:

1. Opens the port and sends `c` (stop), waits 0.5 s, resets input, then sends
   `B` (start) — exactly the synchronization used by the successful test.
2. Warms up for one second, discarding decoded startup frames while retaining
   the parser's partial-packet state; reports startup and measurement errors
   separately in `transport_summary.json`.
3. Requires a clean measurement interval: **no CRC/header failures, sequence
   gaps, or restarts**, plus >=20 valid frames and zero firmware errors.
4. Retries a bad measurement up to two additional times automatically **at
   that same pitch and with the same bottle/support state**, using a new
   stream handshake each time. Rejected raw data remains in
   `...__FAILED_attempt1`, etc. Only a clean capture occupies the canonical
   `background_pitch_...` or `target_pitch_...` directory.

Example (the user's measured `pitch-sweep-plan-pivot.json` is not modified):

```bash
.venv/bin/python tools/pitch_sweep.py record \
  --plan configs/pitch-sweep-plan-pivot.json \
  --port /dev/ttyACM0 \
  --output recordings/pitch-sweep-04 \
  --seconds 6 --retries 2
```

Choose an **unused** recording directory. A recording created with the previous
script remains separate and is not overwritten. If all retries fail, inspect
USB hardware and `transport_summary.json` files inside the failed-attempt
directories; **do not disable the integrity gates**.

## 2026-11-12 follow-up: buffered serial capture and safe resume

The earlier streaming implementation wrote every serial chunk and decoded frame to disk
while its serial port was actively streaming. On this host the standalone read-only
30-second test showed 303 valid frames and zero integrity errors, but the original
recorder intermittently reported 1 bad CRC and 2-3 sequence gaps in six seconds.
This is evidence of an intermittent recording-path or transport issue, **not proof**
that logging was the root cause.

The revised `_capture_once` now uses the same `serial.read`/`Parser.feed` pattern as
the successful standalone stream test and buffers approximately 60 frames and the
wire bytes in memory. It stops the stream before writing GRD3 and wire files. Integrity
requirements remain unchanged: bad CRC, malformed headers, sequence gaps, restarts,
wrong profile or device-reported drops reject the entire attempt. Rejected attempts
are saved as `__FAILED_attemptN` and never silently reused.

A partially completed recording is resumable with `--resume`. The tool verifies
that the saved plan/config match, then checks metadata, transport summary, and
reparses the raw GRD3 recording with strict integrity rules before accepting any
preexisting pose. It never overwrites an existing clean capture.

Example continuing **the same** session after three successful backgrounds:

```bash
python tools/pitch_sweep.py record \
  --plan configs/pitch-sweep-plan-pivot.json \
  --port /dev/ttyACM0 \
  --output recordings/pitch-sweep-04 \
  --seconds 6 --retries 2 --resume
```

Keep the bottle absent until the entire background pass finishes. If corruption
continues under buffered capture, perform a read-only 30-second stream test with
the board at +10 degrees and check cable strain/USB port stability. This software
change is not a substitute for physical link verification. The tool still does
not certify 3D calibration or robot readiness.
