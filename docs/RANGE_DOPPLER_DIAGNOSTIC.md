# Replay range–Doppler diagnostic and capture protocol

The replay-only diagnostic retains stationary returns and complex chirp phase.
The default mode does not detect objects, apply CFAR, calibrate distance, or certify RF timing.
An optional [replay 2D CFAR candidate mode](CFAR_2D.md) is available with
`--detector cfar2d`; it exports full-map thresholds and candidate groups while
retaining stationary returns.
Add `--associate` to that mode for
[confirmed feature IDs and explicit ambiguity/loss](RANGE_DOPPLER_ASSOCIATION.md).
For live capture with that processing, use the separate
[`rd-gui` mode](LIVE_RANGE_DOPPLER.md).
No firmware change is needed to replay existing recordings or collect raw data.

## Replay

```sh
./range-v1 range-doppler recordings/gui-20261109-235116-484020/live-001

# Save artifacts without an interactive window; use a new output directory.
MPLBACKEND=Agg ./range-v1 range-doppler \
  recordings/gui-20261109-235116-484020/live-001 \
  --output evidence/rd-first-review

# Save artifacts and open the interactive frame slider.
./range-v1 range-doppler recordings/rd-fixed-01 \
  --output evidence/rd-fixed-01 --show
```

The two panels share a 60 dB display span relative to each frame's full-map
maximum. The left panel includes zero Doppler. The right subtracts the unweighted
complex slow-time mean before windowing; it can attenuate slow or stopped
obstacles and is an optional diagnostic, not the obstacle output path. There is
no central-bin notch. Scales change between frames; exported linear powers retain
their absolute numerical scale.

Processing reuses `range_spectrum()` (discard startup chirp, remove fast-time
mean, Hann, real FFT, amplitude normalization). A slow-time Hann and complex FFT
follow, normalized by the window sum, with FFT shift and RX power averaging.
The native map includes DC/Nyquist; only the diagnostic strongest-peak search
excludes those range bins. No range search mask or target-selection gate is used.

Output artifacts:

- `maps.npz`: `[frame, shifted Doppler, range]` full and moving linear-power maps,
  native cycles/saved block and nominal range coordinates, and a frame-validity mask.
  Invalid maps contain NaN, rather than a held previous map.
- `diagnostics.jsonl`: sequence/time, validity/rejection reason, DSP time, strongest
  cell, and a per-RX phase/amplitude probe at the strongest usable range bin.
- `metadata.json`: config, input/source hashes, normalization and verification limits.
- `preview.png`: the initial frame, including an invalid-state label if rejected.

Frames with invalid ADC/profile/flags or device continuity are blanked. CRC/header
damage or an incomplete `frames.grd` causes replay to fail rather than silently
skipping corruption. A complete frame following a sequence gap is rejected;
subsequent continuous frames may recover. Replay does not certify original host
freshness; original serial-wire/transport logs remain the source for that audit.
All maps are loaded in memory, so split very long experiments into short runs.

## Timing and coherence status

The working AVG16 development profile now has a
[controlled-motion review](../evidence/rd-avg16-motion-20261110/README.md) showing
repeatable direction-dependent phase and nonzero full-map peaks. This supports
replay 2D CFAR development while physical velocity calibration remains open.

The active shape gives 16 retained slow-time samples and 1/16 cycles/saved-block FFT
spacing. Both MCU timing captures found 112 sensor CHIRP_ACTIVE edges for 17
saved raw blocks, with the second capture preserving all 112 edge times.
Edge/block correspondence is unverified. Uniform spacing,
actual block timing, carrier and physical Doppler sign
remain unverified. No velocity axis in m/s is offered. Phase resultant near one
indicates consistent adjacent phase increments at the probe bin, not proof of
uniform timing, target identity or hardware coherence. The bin may switch returns.
Stationary targets with low phase variation are expected; controlled motion is
needed to test useful Doppler response. Bursts are processed independently.

The source timing audit in `tools/timing_trace.py`, the
[first MCU capture review](../evidence/rd-mcu-edge-20261110/README.md), and the
[revised sensor timing procedure](MCU_EDGE_TIMING.md) document the remaining
hardware verification. Do not infer chirp spacing from
the acquisition elapsed field or the 100 ms frame interval.

Once wavelength lambda and chirp period T are verified, nominal Doppler-bin
spacing is lambda/(2*16*T), with unambiguous speed approximately +/-lambda/(4*T).
Hann broadens peaks. Determine whether this resolves the intended robot speeds
before choosing a longer-burst profile. Zero padding cannot fix insufficient
observation time. The range profile's approximately 35 cm native grid and
near-range HPF response still deserve a feasibility check; fine-distance
calibration can wait.

## Samples to collect next

Use the same firmware/configuration throughout this first comparison. Keep raw
frames, serial-wire logs and config; do not collect only screenshots or numeric
readouts. No empty-reference training is needed. Wall-only recordings below are
comparison controls, not data to subtract.

For raw capture, replace the port with the actual board port and use a new name:

```sh
./range-v1 capture recordings/rd-fixed-01 \
  --config artifacts/hpf-pair-2/hpf350/range-config.json \
  --port /dev/cu.usbmodemACTUAL --seconds 90
```

Alternatively use the existing CFAR GUI's **Start live + record** with the same
config and existing settings. Its distance output is not the label or ground truth.

1. **Fixed radar, moving target (about 90 seconds).** Keep the radar rigid.
   Record 0–15 s with the target already present and held still; 15–30 s approach;
   30–45 s hold; 45–60 s retreat; 60–75 s hold; 75–90 s target removed.
   Use a supported box/reflector, mostly radial motion, and a clear path. Repeat
   once with slower motion and once at a different range. Record actual transition
   times if movement does not match the intended schedule.
2. **Fixed radar, wall plus target.** Repeat the motion in front of a wall,
   plus a matched wall-only control. Initially separate target and wall by at
   least roughly 1 m in range to make interpretation easier; this is not a
   guaranteed resolving distance. Keep operator/body returns outside the beam
   where possible and document unavoidable motion.
3. **Moving radar, stationary scene.** Rigidly mount the radar on a cart/robot.
   Record a straight approach toward a stationary obstacle and wall, stop/hold,
   then retreat. Repeat the same path with the wall alone. Start/end with at
   least 10 s stationary and include a 10 s stop mid-run. Repeat with a side wall
   if available. Start with straight translation; reserve turns for a later test.
   Record odometry/IMU if available, otherwise measured path distance and timed
   travel. Both obstacle and wall ahead can share closing Doppler.

Repeat each condition at least twice, preserving unsuccessful runs. A phone video
or written timestamp log should document target presence, actual start/stop times,
approximate antenna-face ranges, direction, travel distance/time, target dimensions
and material, radar height/orientation, wall geometry, and session/run IDs. Exact
centimeter labels are not needed yet, but known direction and stop intervals are.
Approximate speed can test the expected trend; it cannot calibrate the velocity
scale without verified chirp timing/carrier.

First assess: phase progression changes with approach/retreat; full-map response
persists during holds; moving view attenuates holds; obstacle return remains
distinguishable near a wall; and maps remain usable under radar translation.
These are feasibility observations, not object-detection acceptance metrics.
