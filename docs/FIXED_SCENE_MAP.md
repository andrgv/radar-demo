# Test the persistent 2D object map with the actual radar

This mode builds a **persistent map of object reflection regions** around a fixed
radar. Repeated usable range/angle detections are grouped, assigned stable map
IDs and averaged into positions. Missing returns leave remembered positions on
the map. It does not identify object types or reconstruct full object outlines.

Keep the radar fixed throughout reference capture, mapping and saved-map reuse.
The map origin is the antenna center: +X right, +Y forward, all distances meters.

## 1. Find the board's serial port

From `radar-demo`, with the board connected and other radar readers closed:

```sh
.venv/bin/python -m serial.tools.list_ports
```

Use that port in both commands below. `/dev/cu.usbmodem1103` is an example,
not an automatically selected device. The acquisition config must match the
firmware/profile running on the board. The example uses Andrea's portrait
mounting/phase config; it does not establish that your mounting is correct.

## 2. Record a reference, once per fixed setup

Put one strong isolated reflector **directly ahead, 2 m forward, with its
reflecting center at the antenna's height**. This gives reference XYZ `0 2 0`.
Measure those dimensions; if your position differs, use its measured XYZ instead.

```sh
.venv/bin/python -m radar gui \
  --port /dev/cu.usbmodem1103 \
  --config configs/exploratory-roll90-phase.json \
  --record recordings/map-reference-01 --seconds 5
```

Wait for recording to finish and the serial port to close. If re-running, choose
a new reference directory. This uses the existing recording GUI; it is not the
persistent-map window. The mapper checks that reference quality and acquisition
settings are valid before opening its live stream. A quality failure needs a
better isolated reference or sound recording, not a bypassed check.

## 3. Start mapping real returns

Remove the reference reflector if it is not part of the scene you want to map.
Place two or three objects at **different ranges and left/right bearings**.
For the first controlled test, keep their reflecting centers near reference
height and within approximately +/-25 degrees of forward. Do not move the radar.

```sh
.venv/bin/python -m radar.cfar_map \
  --port /dev/cu.usbmodem1103 \
  --config configs/exploratory-roll90-phase.json \
  --reference recordings/map-reference-01 --reference-xyz 0 2 0 \
  --min-range 0.7 --max-range 4 --plot \
  --output recordings/object-map-test-01
```

This command reads the **actual radar**, not a simulation. Use a fresh output
directory for each run. Leaving `--output` out of a live/interactive run creates
a unique `recordings/fixed-map-...` directory and prints its location.

## What should happen

- The left panel displays the measured spectrum and adaptive CFAR threshold.
- Repeated localized returns build blue tentative regions, then green mapped
  regions labelled **Object 1**, **Object 2**, etc. Labels show range and bearing.
- The table shows each region's averaged position, support count/score and age.
- Brief misses or unresolved angles leave mapped regions **amber: remembered**.
  They are not being claimed as current detections. Fresh nearby measurements
  refresh the same map ID, even if the detector's short-lived track ID changed.
- After 30 seconds without a localized observation, a region becomes **gray:
  stale**. Its saved position remains available until the map is cleared.
- **Clear map** discards accumulated regions and starts fresh evidence while
  retaining the reference. Use it after changing the scene for a new test.
- **Save map** writes the current map immediately. Saving is also automatic
  after each processed frame and when the run stops.
- Closing the window or pressing Ctrl-C stops the board and saves the map.

Map confirmation defaults to three distinct localized frames **after** the CFAR
detector's own confirmation. At nominal 10 Hz with an uninterrupted signal, a
new region can become mapped on the fifth frame, about half a second after
startup. Rejections/misses increase that delay. Many neighboring returns in a
single frame count as one observation, not many independent confirmations.
Live acquisition, detection and raw logging run on a background worker. The
dashboard consumes the latest result through a bounded mailbox; a slow render
can skip display observations and delay map confirmation, but does not pause
serial acquisition. Results older than 0.5 seconds cannot refresh mapped regions.
The dashboard redraws at most five times per second and pumps events between
draws, including during partial serial reads. Timing/backlog checks remain active.

## Saved files and resume

`recordings/object-map-test-01/` contains:

- `map.json`: latest persistent regions, averaged coordinates, ages, observed
  scatter, support and status. On stop, retained regions are marked remembered.
- `map_history.jsonl`: map evolution, including clear/save/stop events.
- `obstacles2d.jsonl`: per-frame CFAR/angle observations, including rejections.
- `frames.grd`, `serial-wire.bin`, arrival/transport logs, `config.json` and
  `metadata.json`: raw measurements and processing/reference provenance.

If the radar **has not moved**, continue the same scene with the same config,
reference, XYZ and target-height assumption; add:

```sh
--load-map recordings/object-map-test-01/map.json
```

Use a new `--output` directory. Loaded positions start as remembered/stale and
require new measurements to become current. A configuration/reference mismatch
is rejected; even a matching file cannot detect that somebody physically moved
the radar. Capture a new reference and start a new map after any radar movement.

## Tuning and limits

- `--map-merge-radius 0.35`: spatial clustering/association distance in meters.
  Larger values merge more returns; smaller values can split one noisy region.
- `--map-min-observations 3`: distinct localized frames needed to map a region.
- `--map-remember-seconds 30`: age at which remembered regions become stale.
- `--target-z`: common assumed reflector height relative to radar. Height is
  not measured by this estimator; arbitrary object heights can bias positions.
- CFAR thresholds and angle controls remain documented in [CFAR_MAP.md](CFAR_MAP.md).

The circles show a minimum marker size plus measured positional scatter; they
are **not object footprints or calibrated uncertainty bounds**. The support
percentage is a decaying evidence score, **not an occupancy probability**.
Map IDs identify spatial return regions, not verified physical objects. Nearby
objects can merge; extended objects can produce several regions. Clutter and
multipath can build persistent false regions. Same-range objects can remain
unresolved. A removed object may remain as memory; missing reflections do not
prove free space. This fixed-sensor map does not implement SLAM or motion tracking.

Record measured object positions and compare them with the map. Test empty scenes,
weak/strong reflectors and missed returns as well as favorable placements. The
software has synthetic and replay tests; real scene accuracy remains to be measured.

## Optional software demo

```sh
.venv/bin/python -m radar.cfar_map --demo --plot
```

Only this `--demo` command is simulated. Demo maps cannot be loaded as measured
live maps. The live command in step 3 uses real board data.
