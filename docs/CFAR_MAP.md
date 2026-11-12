# Multiple-obstacle CFAR range / azimuth map

For the actual-radar setup and **persistent fixed-sensor object map**, start with
[FIXED_SCENE_MAP.md](FIXED_SCENE_MAP.md). Persistence is now enabled by default in
this command; the detector underneath still withdraws missed current detections.

This combined mode uses Amanda's baseline-free CA-CFAR peak groups and dense
within-group range refinement, followed by Andrea's reference-based RX2–RX1
physical angle inversion for **every** candidate group. Each group receives
independent consecutive-frame confirmation. The original single-target modes
are unchanged.

## Quick demo (no radar required)

From the repository root:

```sh
.venv/bin/python -m radar.cfar_map --demo --plot
```

The demo simulates three isolated reflectors at different ranges and bearings,
then runs their real-valued ADC samples through the FFT, CFAR and angle pipeline.
It is a software demonstration, not measured radar performance. Close the window
or press Ctrl-C to stop. For a headless image and reproducible raw recording:

```sh
MPLBACKEND=Agg .venv/bin/python -m radar.cfar_map --demo --seconds 1 \
  --output /tmp/cfar-map-demo-01 --snapshot /tmp/cfar-map-demo-01.png
```

Every output directory must be new. `--snapshot` captures the map on stop. Live
and interactive runs save `map.json` and `map_history.jsonl` automatically.

## Replay measured data

Use an existing known-position reference from the **same mounting and acquisition
settings**. Raw frames are required locally; they are not all included in Git.

```sh
.venv/bin/python -m radar.cfar_map \
  --replay recordings/box-angle-01/check_right \
  --config configs/exploratory-roll90-phase.json \
  --reference recordings/box-angle-01/center_repeat \
  --reference-xyz 0 2 -0.1125 \
  --min-range 1.5 --max-range 2.5 --plot
```

Reference XYZ is measured right/forward/up in meters relative to the antenna
center. At least ten reference frames must pass Andrea's existing contrast,
coherence and local-peak checks. A changed mount or channel response requires a
new reference. The common target height defaults to reference Z and can be set
with `--target-z`; it is **assumed, not measured**. A reference may use its own
saved background for calibration, as in Andrea's existing workflow. Detection
never subtracts an empty scene, including during replay. Calibration acquired
with subtraction does not guarantee that cluttered raw returns remain isolated.

## Live acquisition

If you do not have the reference recording locally, place an isolated reflector
at a measured position and capture it using the existing GUI:

```sh
.venv/bin/python -m radar gui --port /dev/cu.usbmodem1103 \
  --config configs/exploratory-roll90-phase.json \
  --record recordings/cfar-map-reference-01 --seconds 5
```

Keep the radar mounting fixed. Use `recordings/cfar-map-reference-01` as
`--reference` below and supply its **actual measured** XYZ, not the example
coordinates. If the reference fails quality checks, improve target isolation,
position or recording integrity before proceeding.

Replace the example port with the board's actual serial device:

```sh
.venv/bin/python -m radar.cfar_map \
  --port /dev/cu.usbmodem1103 \
  --config configs/exploratory-roll90-phase.json \
  --reference recordings/box-angle-01/center_repeat \
  --reference-xyz 0 2 -0.1125 \
  --min-range 0.7 --max-range 4 --plot \
  --output recordings/cfar-map-live-01
```

Live startup stops and flushes the previous stream before starting. Output saves
the processing configuration, calibration reference, settings, original wire
bytes, raw frames, arrival times and `obstacles2d.jsonl`. Raw recording precedes
processing. Live timing uses Amanda's bounded startup clock mapping. Serial
corruption, backlog, sequence/time gaps and invalid ADC withdraw current tracks;
one second without a complete frame stops the run. Closing/stopping logs a
terminal `UNCERTAIN` record and closes the serial connection. Replay needs no
hardware. Text/JSON-only operation omits `--plot`.

## Reading the map

- Green regions: currently observed mapped reflection clusters. Amber regions
  are remembered, gray regions are stale, and blue regions are tentative.
  Labels show stable map ID, averaged slant range and azimuth.
- Orange arcs: confirmed returns whose distance or direction is unresolved.
  The arc's radius uses the estimated range, or the provisional bin center if
  fine range is unresolved; it is not a localized obstacle or uncertainty bound.
- The table includes tentative returns, confirmation hits, coherence and reasons.
- The profile shows raw power and the adaptive CA-CFAR threshold.
- Detector tracks disappear on a miss, but mapped regions remain as memory.
  Map IDs survive detector re-confirmation when positions associate spatially.

Defaults preserve Amanda's threshold settings: two guard bins per side, eight
training bins per side, eight required total training bins, multiplier six.
`--cfar-guard`, `--cfar-training`, `--cfar-min-training`, and `--cfar-factor`
change these empirical settings; they do not specify a calibrated false-alarm
probability. Strong nearby peaks can contaminate the training cells and mask a
weaker obstacle. `--confirmation-frames` defaults to three; `--window` defaults
to five associated frames for phase statistics. Range uses the current frame.

Association requires overlapping group support, peak movement of at most one
native bin, and at most eight degrees bearing change when both bearings are
usable. Matching is greedy and one-to-one; crossings, split/merged groups and
unresolved angles can reset or exchange IDs. A miss immediately removes a track.

## Limits and validation

This is a persistent fixed-radar reflection-region map, not SLAM or a free-space
map. No robot pose, moving-sensor accumulation, verified height estimation,
object/material identification or universal clutter rejection is implemented.
All measurements remain experimental and uncalibrated. The range axis requires
`range_scale=1` and `range_offset_m=0`; fine estimates do not imply fine physical
resolution. The search uses native bins >=2 and excludes Nyquist, and is limited
by the selected waveform and analog filters. Requested range limits are not
certified detection coverage.

The default display interval is 0.7–10 m to include all synthetic demo targets;
this is not a claim of measured 10 m hardware performance. Select a physically
tested interval for live operation, as in the 0.7–4 m example above.

There is **one angle per resolvable range group**. Same-range reflectors can
merge or produce a plausible mixed angle even at high coherence. The three-RX
array and multipath limit angular separation. Andrea's angle model remains
locally tested near 2 m at fixed height; wider-range operation requires physical
validation. A missing return does not establish clear space.

First measure two/three isolated reflectors at distinct ranges/bearings, including
unequal strengths, and record empty scenes. Then test same-range reflectors,
nearby ranges, changing heights, motion, deliberate misses and transport faults.
Report misses, spurious returns, range/bearing errors, unresolved outcomes and
latency on fresh captures after settings are frozen.

```sh
MPLBACKEND=Agg .venv/bin/python -m unittest discover -s tests -p test_cfar_map.py -v
.venv/bin/python -m unittest discover -s tests_min -p 'test_cfar*.py' -v
```
