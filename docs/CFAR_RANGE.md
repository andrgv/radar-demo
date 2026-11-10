# Baseline-free range CA-CFAR

The current `range-ca-cfar-v2` mode confirms associated peak groups and estimates
range within their support from the current raw spectrum. No empty recording or
waveform subtraction is used. It remains experimental and uncalibrated; static
scene returns can still produce false close-range outputs.

## Launch

From this repository, install the Python environment if needed:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Try the previously selected experimental HPF350 settings with the new processing:

```sh
./range-v1 gui --detector cfar \
  --config artifacts/hpf-pair-2/hpf350/range-config.json \
  --port /dev/cu.usbmodem1103 \
  --cfar-guard 1 --cfar-training 4 --cfar-min-training 4 --cfar-factor 2
```

Use the actual USB port and a configuration matching the running firmware. Close
other serial readers. Click **Start live + record** directly; empty capture is
disabled. Restart an already running GUI to load the new processing.

The graph shows native-bin power, local reference, threshold and candidate peaks.
The large readout and history now show the within-group **experimental peak
estimate**, instead of jumping between bin-center coordinates. No temporal
smoothing or held-last-value behavior is applied. Accepted presence can have an
unresolved distance: that leaves the readout blank and explains the reason.

Live raw frames, original serial bytes, settings, algorithm version, fine-range
diagnostics and readings are saved under `recordings/gui-<timestamp>/live-001/`.
Stop/window close stops capture, preserves recordings and closes serial.

Omitting `--detector cfar` retains the original empty-reference detector and its
fine waveform fit. Threshold defaults have **not** changed: CFAR defaults are
still guards 2, training/minimum 8, multiplier 6. The explicit flags above select
the experimental settings; they are not a universal hardware/profile preset.

## Replay and terminal use

```sh
./range-v1 gui --detector cfar \
  --config artifacts/hpf-pair-2/hpf350/range-config.json \
  --replay recordings/gui-20261109-215257-942086/live-003 \
  --cfar-guard 1 --cfar-training 4 --cfar-min-training 4 --cfar-factor 2

./range-v1 replay recordings/hpf350-b-40cm --detector cfar \
  --cfar-guard 1 --cfar-training 4 --cfar-min-training 4 --cfar-factor 2 \
  > /tmp/cfar-readings.jsonl

./range-v1 live recordings/new-cfar-run --detector cfar \
  --config artifacts/hpf-pair-2/hpf350/range-config.json \
  --port /dev/cu.usbmodem1103 --seconds 30 \
  --cfar-guard 1 --cfar-training 4 --cfar-min-training 4 --cfar-factor 2
```

Click **Start replay** in the GUI. Replay neither connects to serial nor creates
a new recording; it recomputes decisions with current processing. Adding
`--snapshot /tmp/cfar.png` starts replay and saves a screenshot after 1.8 seconds.
Saved readings from older versions remain unchanged.

`--baseline` is incompatible with CFAR. `--estimator fixed/associated` belongs to
the empty-reference path; CFAR automatically uses its own raw-spectrum peak
estimator, and `--estimator associated` with CFAR is rejected.

## Detection and confirmation

1. Validate ADC layout/profile and rails. Discard the configured startup chirps,
   remove each chirp/RX fast-time sample mean, apply Hann and compute a real FFT.
   Average squared magnitude over chirps/RX. This DC removal is not subtraction
   of a captured scene.
2. For each cell under test, mean surrounding **linear power**, excluding the
   cell and guard cells. DC and Nyquist are always excluded. References can extend
   outside the configured detection mask into the usable spectrum.
3. Threshold = local reference × factor. Near spectrum edges truncate the window,
   with no wrapping or replacement from more distant cells. Require the minimum
   total reference count. Export actual counts and null untestable thresholds.
4. Test configured `min_bin..max_bin`. Group contiguous qualifying cells and keep
   one strongest-bin candidate per group. Reject a flank whose neighboring
   usable bin is stronger, even when that neighbor is outside the search mask.
   Select the nearest qualifying group and export all candidates.
5. Require the configured consecutive confirmation count (currently three).
   Confirmation continues when the selected group's bin support overlaps its
   previous support **and** the maximum moves no more than one bin. Disjoint
   groups and larger maximum jumps restart confirmation. Overlap is an association
   heuristic, not proof that a physical object is the same.
6. A miss, invalid frame, sequence/time gap, restart or transport rejection clears
   confirmation and the readout. Timeout clears the readout and stops capture.
   There is no smoothing or extrapolation across a missing return.

| Option | Default | Meaning |
|---|---:|---|
| `--cfar-guard` | 2 | Excluded bins per side |
| `--cfar-training` | 8 | Maximum training bins per side |
| `--cfar-min-training` | 8 | Minimum total references after edge clipping |
| `--cfar-factor` | 6 | Empirical linear-power multiplier |

These are engineering thresholds, not a calibrated false-alarm probability.
Windowing, integration, asymmetric edges and clutter affect the statistics.

## Fine range estimation

After confirmation, compute the current-frame Hann range spectrum with at least
4096 FFT points (or eight times acquired samples, whichever is greater), average
power over chirps/RX, and search **only** the selected group's support. Support
extends half a native bin beyond the first and last qualified cells. Local
three-point log-power interpolation refines the dense-grid maximum.

A maximum at the support boundary leaves distance unresolved. Multiple interior
local maxima within 3 dB of the strongest also leave it unresolved. Neither case
is forced to a boundary value or averaged into a plausible middle distance.
Presence remains recorded separately. No captured reference, distance-label fit,
arbitrary offset, Doppler or temporal smoothing enters the estimate.

Zero padding improves numerical sampling of a peak, not physical resolution.
Leakage, multipath, broad lobes and the existing analog response can bias the
peak. Fine decimal output is not a claim of centimeter accuracy.

Reading fields:

- `range_bin` and `provisional_range_m`: native-bin center, retained for diagnostics.
- `experimental_range_m`: accepted within-group estimate used by UI/history, or null.
- `fine_range`: estimator method, group support, boundary/ambiguity reason and estimate.
- `selected_group_bins`, `confirmation_hits`: association/confirmation diagnostics.
- `range_m`: always null; `calibrated`: always false.

Power plots use dB relative to ADC units squared. The candidate signal/reference
ratio is not dBm or calibrated SNR. Candidate plot markers retain native bin
coordinates; the distance history uses fine estimates.

## Evidence and checks

[Before/after results](../evidence/cfar-group-range-v2/results/README.md) compare
frozen v1 source with v2 at identical threshold settings on 30 historical
recordings and live-001/002/003. The before source is preserved alongside the
report so the comparison can be reproduced without relying on Git history.

In live-003's approximate target interiors (7–11 s and 19–23 s), fine output
coverage is 40/40 in both, versus 25/40 and 23/40 coarse outputs before. Median
estimates are 50.8 and 50.0 cm; conditional mean absolute errors against the
approximate 50 cm placement are 2.2 and 3.5 cm. These recordings informed the
change and are development evidence, not independent accuracy validation.

The three empty interiors produce 10/120 numeric outputs, versus 7/120 before.
Live-002 still has persistent false close-range readings during its empty
portions. Across the 30 historical recordings, presence in empty frames rises
slightly; unresolved fine peaks reduce numeric outputs slightly. This update
addresses exact-bin confirmation and coarse ranging, **not reliable empty-scene
rejection or target identity**. Thresholds and firmware were not changed.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests_min -v

MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.evaluate_cfar_group_range \
  --output evidence/new-cfar-v2-evaluation
```

Tests cover adjacent-bin maximum swaps within a group, disjoint/large-jump
resets, misses/faults, fractional tones, support boundaries, competing fine peaks,
blank unresolved/stale readings, recording and actual baseline-free Qt replay.

## Automated threshold study

The historical [v1 sweep](../evidence/cfar-sweep-1/README.md) selected the explicit
settings above on HPF350-b, then evaluated HPF350-a and other profiles/sessions.
Its native-bin metric cannot establish fine distance accuracy. The study manifest
`configs/cfar-study.json` documents labels, split groups and provenance.

```sh
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.sweep_cfar \
  --manifest configs/cfar-study.json --output evidence/new-cfar-sweep
```

New sweeps use current detector code and report source hashes. They still score
native-bin agreement, so use the group/fine evaluation for distance errors and
coverage. Existing reports preserve their original versions/results. Do not use
previous validation data for further tuning and still call them independent
validation; obtain fresh captures after settings and processing are frozen.

## Long-run host/device clock handling

Capture now uses a bounded startup clock mapping (`bounded-startup-clock-v1`)
instead of assuming that a device timestamp second equals a host second exactly.
Restart an already open GUI to load the fix; commands and buttons are unchanged.
The mapping uses only timestamps/arrivals, not scene content. It requires no empty
capture and does not change range calibration or CFAR settings.

For the first approximately 20 device seconds, the nominal-rate timing check
remains active and the UI can display accepted frames. Once at least 100 valid,
continuous, nonqueued single-frame arrivals are available, fit and freeze a mapping
from elapsed device time to elapsed host time. Accept at most ±2% rate difference,
with maximum startup fit error 100 ms and 95th-percentile error 50 ms. A fit must
be available by 30 device seconds or timing is invalidated.

After freezing, the existing 0.5-second progress-error limit applies to the mapped
time. The mapping never adapts to later delays or silently resets its origin.
Queue/backlog checks, CRC/frame continuity handling and the one-second stream
timeout remain active. Restart/duplicate device timestamps, unstable/out-of-bound
fits or excessive progress error invalidate timing for that capture. Stop and
start a new capture to retry; raw data remain recorded even while timing is
invalid. No hardware programming is involved.

New metadata records the clock policy. Each reading records:

- `relative_timing_error_s`: absolute mapped progress error (nominal while fitting).
- `raw_relative_timing_error_s`: absolute elapsed difference without rate correction.
- `clock_sync`: collecting/frozen/invalid state, host-seconds/device-second rate,
  intercept, signed errors, elapsed times, fit sample count and rejection reason.

A frozen mapping cannot prove absolute frame freshness, identify an initial
constant backlog, or distinguish every smooth latency ramp during startup from
clock skew. Device start acknowledgment/identity and physical clock verification
remain separate work. Later oscillator changes can still trigger rejection;
the fix does not continually learn away a latency problem.

[Validation report](../evidence/clock-sync-fix/README.md) covers the seven saved
captures, including removal of the long run's 741 timing-only rejections in
arrival-timeline replay. It also documents tests for an hour of synthetic clock
skew, injected delay/stale readings, rate/jitter limits, wraps/restarts, queued
bursts, timeout handling and preservation of raw data. Saved arrival replay is a
proxy for original reader timing; live hardware validation follows app restart.
