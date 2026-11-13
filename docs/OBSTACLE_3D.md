# Experimental 3D obstacle detection over USB

This mode scans range on each receiver, keeps stationary energy, and estimates
sensor-relative XYZ from joint three-RX observations where supported. A weak
return visible on one receiver survives as an unresolved-direction warning.
Material remains `unknown`: the glass/drywall score does not gate obstacles.
No empty-scene calibration, training, firmware change or flashing is required.

It is an experimental implementation, **not verified glass detection anywhere**.
Door03's door-associated return is retained, but its direction remains unresolved.
Door04 has a biased local range maximum, and door07 contains nearby returns in
both open and closed states. Fresh physical calibration and validation remain
necessary; replay success does not establish pane ownership or accurate XYZ.

## Run

Use the project's environment with NumPy, PyQt6, matplotlib and pyserial installed.
On Linux, setup is `python -m venv .venv` followed by
`.venv/bin/python -m pip install -e .`. XGBoost is unnecessary for this diagnostic
view. Activate `.venv` before the `python` commands below, or use `.venv/bin/python`
explicitly. A separate system/Conda Python does not inherit these dependencies.

This view is secondary to glass detection: unclassified reflector points and
warnings are not evidence that glass has been identified.

Replay and inspect the new 3D view:

```bash
python -m radar gui --replay recordings/door03/closed-03 --obstacle-cloud
```

Export deterministic replay without a GUI to a **new** directory:

```bash
python -m radar obstacle3d-replay recordings/door03/closed-03 --output artifacts/door03-3d-replay
```

USB live view and recording (replace the port with the board's port):

```bash
python -m radar gui --port YOUR_PORT --config recordings/door03/config.json --obstacle-cloud --record recordings/obstacle3d-live-01 --start-delay 5 --seconds 60
```

Or run text/JSON output and save raw acquisition without opening Qt:

```bash
python -m radar obstacle3d-live recordings/obstacle3d-live-02 --port YOUR_PORT --config recordings/door03/config.json --seconds 60
```

The example configuration matches the door03 acquisition profile. Use a config
matching the board's reported profile, sample count, rate and chirps. A different
profile is rejected; do not change RF values merely to make the display match a
known distance. A replay `--config` may supply geometry/calibration, but acquisition
fields must still match the recording. GUI `--mount-roll` rotates the specified
array model and does not establish the correct mounting or calibrate phase.

`--obstacle-cloud` selects its own 3D display. It cannot be combined with
`--background`, `--phase-probe`, `--point-cloud` or `--spatial-map`. Existing
point-cloud and material-classifier modes remain available separately.

## Meaning of the display and exports

- Blue points: persistent, **provisional** XYZ reflector candidates. Axes are
  right/forward/up in the sensor frame. Angular calibration remains unverified.
- Orange triangles: persistent returns with unresolved direction, plotted by
  provisional range and local contrast. These have `xyz: null`, not zero-valued
  or guessed positions. An unresolved return can still indicate an obstacle.
- `UNCERTAIN`: no currently persistent return, startup, missing data, stop or
  error. This does **not** assert a clear or glass-free path.

The view-range control limits rendering only; detection scans all available
non-DC/non-Nyquist bins starting at native bin 1. The angular search spans
approximately +/-60 degrees in azimuth/elevation. This is not 360-degree coverage.
Neither the excluded bins nor the nominal spectrum limits establish a verified
physical minimum/maximum glass detection range.

Exports contain `obstacles3d.jsonl`, `settings.json`, `config.json` and `report.json`.
USB captures also preserve `frames.grd`, arrival times and original serial wire
chunks. Raw data are written before detection, even for rejected frames. Replay
does not rewrite its input or duplicate raw files into the result directory.
Each window contains tentative and persistent returns, receiver support,
contrast, coherence, array-model fit, angular response width and direction
rejection reasons. The report retains quality events and incomplete tails.
Stopping/EOF withdraws current candidates with a terminal `uncertain` record.

## Method and limits

Defaults are fixed engineering settings: one-second nonoverlapping median-power
windows, 6 dB local contrast, and three consecutive windows of per-RX peak
agreement within .25 native bins. A Hann FFT is interpolated 8x to sample peak
location; interpolation adds no independent range resolution. Local contrast
uses the median of valid reference samples at +/-2,3,4,5 native bins, requiring
at least three samples. It is not calibrated CFAR or a glass probability.

Nearby receiver peaks are grouped within .25 native bins. Direction fitting
requires matching peaks and sufficient local contrast on all three receivers,
pairwise coherence >=.9, matched array energy fraction >=.65, and a maximum
away from the angle-search boundary. Configured complex channel gains and the
existing raw-domain physical-array steering model are used. A covariance over
chirps and frames cancels common phase without subtracting stationary targets.

These tests are necessary diagnostics, not proof of correct direction. Coherent
background/multipath can fit an incorrect direction. The reported half-power
angular width is not a confidence interval. There is at most one direction per
range cluster; arbitrary coherent returns sharing that cluster cannot be
separated by these criteria. Moving energy is retained, but the new detector
does not estimate velocity or separate arbitrary same-range Doppler targets.
The existing `--point-cloud` mode still provides range/Doppler extraction.

Default initial persistence delay is about **three seconds**. This is not a
validated collision response time. No world-map accumulation, sensor pose,
moving-board compensation or verified moving-board detection is implemented.
Shorter window settings exist in the Python API for experiments; they require
new validation rather than an assumed equivalent accuracy/latency claim.

Configuration/ADC faults, sequence gaps, changed device error/drop counters and
serial corruption clear the pending window and persistence. A restart requires
a new detector. Timeout, backlog and excessive relative host/device timing
drift withdraw detections. Replay rejects empty/too-short files and reports raw
corruption/truncation. Live relative timing cannot prove absolute freshness
without a firmware handshake. No candidate is carried forward after a failed
window merely to make the plot stable.

Archived `radar_min` configurations are accepted for research, using their
acquisition values and an explicitly unverified physical portrait array default.
Those captures have no calibrated receiver mounting/phase model; interpreting
their displayed XYZ as validated geometry would be incorrect.

## Evaluation

Reproduce frozen-setting evaluation over all raw recordings, including nested
GUI sessions, without fitting to their labels:

```bash
python -m tools.evaluate_obstacle3d recordings --output artifacts/obstacle3d-evaluation-new
```

Optionally restore the material archive into a separate fresh directory with
`tools/restore_material_recordings.py --destination ...` and pass its `recordings`
directory as another root. The retained run includes 22,492 frames across 119
raw recording folders, plus explicit exclusions for incomplete door05/door06.
Empty and too-short files remain listed as rejected rather than successful tests.
The complete evaluation summary is in `evidence/obstacle3d-20261109/summary.json`;
per-window exports are in `artifacts/obstacle3d-evaluation-04/`.

At the surveyed pane neighborhood (within .25 nominal bins), after default
persistence, the door development data yield:

| Setup | Closed windows with candidate / provisional XYZ | Open windows with candidate / provisional XYZ |
|---|---|---|
| door03 | 84 / 0 of 90 | 0 / 0 of 90 |
| door04 | 0 / 0 of 90 | 0 / 0 of 90 |
| door07 | 84 / 28 of 90 | 83 / 0 of 90 |

Door04 has candidates within one nominal bin in 84/90 windows in both states;
the closed windows have provisional XYZ there. A larger match tolerance does
not demonstrate that the maximum belongs to glass or fix its range bias. The
first two windows per recording cannot have persistence, leaving at most 84/90
for each setup/state. Windows are correlated and all these data were inspected
during development. There are only two physical doors across three setups.

Other tested data include the 30/40/50 cm sweeps, 350/100/350 kHz filter studies,
reference scenes, GUI sessions and archived window/wall tests. They expose
near-range misses and angular ambiguity. An empty/reference scene still contains
walls and objects, so its reflector count is not a certified false-obstacle rate.
None supplies surveyed 3D ground truth. Numerical synthetic tests verify known
XYZ recovery, complex correction, weak single-RX retention, continuity, USB/replay
parity and display/export agreement; they do not establish physical accuracy.

The full goal remains unverified until independent pane-present/absent controls,
surveyed angles/ranges, new panes/backgrounds and fresh USB hardware tests are
available. See [the physical geometry notes](ANTENNA_GEOMETRY.md) before using
direction estimates for collision boundaries.
