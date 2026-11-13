# UPenn mmWave Viam module

For the additional camera resource, see [Raw mmWave point-cloud camera](VIAM_CAMERA.md).
It shares this sensor's acquisition and supports rover/Linux deployment.

This branch packages `carlyworkspace:upenn-mmwave` / model
`carlyworkspace:upenn-mmwave:infineon-mmwave` using the repository's headless
acquisition and DSP. No GUI dependencies or firmware flashing are required.
It does not modify the original configuration files or GUI workflows.

## Start from scratch on your Mac

1. Clone the completed integration into a new folder. If that folder already
   exists, choose another empty destination; do not delete your old module.

   ```bash
   cd ~
   git clone --single-branch --branch demo-viam https://github.com/andrgv/radar-demo.git upenn-mmwave
   cd ~/upenn-mmwave
   ```

   Do **not** run `viam module generate` here: the wrapper, metadata and build
   scripts are already implemented. The clone includes research data and may
   take several minutes.

2. Install Python 3.11+ dependencies into the module's own environment:

   ```bash
   python3 --version
   bash setup.sh
   .venv-viam/bin/python -m unittest discover -s tests_viam -v
   .venv-viam/bin/python -m viam_module.main --self-test
   ```

   `PYTHON_BIN=python3.11 bash setup.sh` selects a specific installed Python.
   The self-test is synthetic and does not open USB or prove physical accuracy.
   Do not `pip install -e .` for Viam: the repository's full package installs GUI
   dependencies; `requirements.txt` is the headless dependency set.

3. Register the module in your existing Viam organization:

   ```bash
   viam login
   viam module create --name upenn-mmwave --public-namespace carlyworkspace
   viam module update
   ```

   If create reports **already exists**, keep the matching existing registration
   and continue with `viam module update`. Do not create another namespace or
   overwrite `meta.json`. The `update` command sends the checked-in metadata,
   model list and build settings to the registry.

4. Build from the GitHub branch, not the repository's default branch:

   ```bash
   viam module build start --ref demo-viam --version 0.1.0
   ```

   Then use the returned ID:

   ```bash
   viam module build logs --id YOUR_BUILD_ID
   ```

   Wait for the **darwin/arm64** build to succeed for an Apple Silicon Mac.
   Linux build success alone does not establish macOS success. This configuration
   also builds linux/amd64 and linux/arm64. Intel Macs need an additional
   darwin/amd64 build target; do not install an ARM binary on an Intel Mac.
   Use `uname -m` to check: `arm64` means Apple Silicon, `x86_64` means Intel.

   For later uncommitted edits, `viam module build start --from-source --version
   0.1.1` builds the current local source. Use a new unused version for each
   publication. `--ref demo-viam` builds only committed/pushed changes.

5. Release the serial port from the old mmWave module and any GUI/terminal.
   Disable or remove the old sensor component before adding this one. Check:

   ```bash
   find /dev -maxdepth 1 -name 'cu.usb*' -print
   lsof /dev/cu.usbmodem2103
   ```

   In Viam: **CONFIGURE → + → Blocks**, search `upenn-mmwave`, select
   `carlyworkspace:upenn-mmwave:infineon-mmwave`, and name it `upenn-radar`.
   Add these attributes (also saved in `configs/viam-upenn-attributes.json`), then Save:

   ```json
   {
     "serial_port": "/dev/cu.usbmodem2103",
     "config_path": "configs/exploratory-roll90-phase.json",
     "min_range_m": 0.5,
     "max_range_m": 3.0,
     "enable_angles": true,
     "stale_after_s": 1.0,
     "reconnect_delay_s": 1.0
   }
   ```

6. Test **GetReadings** for distance, azimuth and echo count. For full diagnostics,
   use **DoCommand** with `{"command":"status"}`. Expect `healthy: true`, `state: streaming`,
   `selection: nearest_range_echo_motion_independent`, `echo_count`, `echoes`,
   and `config_path` matching the above. `source_commit` identifies the packaged
   source revision. Empty scenes can legitimately return zero echoes and null
   distance. Check `angle_status` when angles are null. Firmware mismatch is an
   error rather than permission to silently change the configuration or reflash.

## Which configuration and why?

`configs/qualification-hpf350.json` is the raw HPF350 baseline: 17 chirps,
64 samples, profile `0x33514802`, source-derived range parameters, nominal
portrait geometry and vendor angle matrix. `configs/exploratory-roll90-phase.json`
adds +90-degree mounting rotation and saved RX phase corrections from the
box-angle study. Range settings are identical. The branch's `radar.range_azimuth`
and `radar.angle_lab` commands default to the exploratory file.

This adapter loads the chosen file unchanged. It does not blend calibration
matrices, copy someone else's range scale, or flip `verified` flags to true.
The exploratory file is the recommended starting point **only for the same
mounting/setup**; a different orientation requires a matching configuration and
measured off-center checks. Both configurations remain experimentally qualified,
not independently validated general-purpose angle calibration.

`config_path` is required. Relative paths resolve inside the module's bundled
repository configs, regardless of viam-server's working directory. An absolute
path can select a host-local config. Its SHA-256 is exposed in readings. Edit
that file and restart/reconfigure the component to load changes.

## Clean default readings

The sensor's default **GetReadings** panel contains only available `distance_m`,
`azimuth_deg`, and `echo_count`. Missing distance/angle values are omitted instead
of displayed as null; zero-degree azimuth is retained. A healthy empty scene
returns `{"echo_count": 0}`. Connection failures instead show `status` and an
`error` when available, so an offline sensor is not mistaken for an empty scene.
Viam controls the visual ordering of map keys.

Full echo lists, Doppler, calibration flags and diagnostics remain available:

- Sensor **DoCommand**: `{"command": "status"}`.
- **GetStatus**.
- Python: `await sensor.get_readings(extra={"detailed": True})`.

The fields described below are the full diagnostic response. This presentation
change does not change DSP, calibration, USB acquisition, or the camera's
`raw_frame` dependency command.

## Range-first behavior and returned values

One qualifying local range-power peak becomes one radar echo. Range detection
uses the repository's `range_fft`, `noise_threshold` and `interpolated_range`.
It never uses Doppler or angle validity to reject a range peak. The general
repository Processor still provides diagnostics, but its separate static/moving
candidate list is not used for echo counting: those entries can duplicate one
range cell or let motion influence a static candidate.

No slow-time mean subtraction or adaptive background removes stationary echoes
from this detection path. Nearest qualifying range selects the top-level echo.
This is not object tracking or a guarantee that the selected return is your
intended target. Two physical objects in one range cell can remain unresolved;
one physical object can produce several echoes. Multipath can produce ghosts.

- `echo_count`, `echoes`: count/list after range and signal-quality filtering.
- Each echo: distance, range bin, SNR, power, normalized Doppler, `moving`,
  azimuth/elevation when usable, angle coherence and validity/status.
- `distance_m`, `azimuth_deg`, `elevation_deg`: selected nearest echo.
- `doppler_cycles_per_chirp`: Doppler-bin estimate, independent of range validity.
  A zero-Doppler bin does not prove perfect stillness. Uniform chirp spacing is
  not established by these example files.
- `doppler_hz` requires verified chirp timing. `radial_velocity_mps` additionally
  requires verified carrier frequency; otherwise these fields are null.
- `features`: repository range entropy, phase consistency, temporal variation,
  angular width, late-energy ratio, moving-energy fraction and saturation proxy.
  These are diagnostics, not material labels or calibrated physical properties.
- `healthy`, `state`, `error`, frame age, CRC/header/gap counters, device counters,
  reconnect count, config hash and source commit identify operational state.
- Calibration flags remain honest: angle estimates are unverified; range status
  follows the selected config's `verified` field. No material classifier is run.

Range samples are roughly 0.35 m apart for these configs. The initial detector
excludes bins 0 and 1; practical nearest bin center is about 0.70 m. Setting
`min_range_m` below that does not restore those bins or defeat analog HPF limits.
Peak interpolation refines a peak coordinate, not physical range resolution.

## Two angle methods

Without a reference recording, `angle_method: matrix_phase` uses the repository's
angle matrix, mounting geometry and phase corrections. It requires coherent
channels and a physically valid direction. `angle_valid` means a usable
mathematical estimate, **not** calibrated accuracy.

The branch's specifically tested RX2 range–azimuth workflow also requires a
known-position reference recording. That recording (`box-angle-01/center_repeat`)
is not present in this checkout. To reproduce that method, keep your original
recording directory on the Mac running Viam, and add:

```json
{
  "angle_reference_path": "/absolute/path/to/recordings/box-angle-01/center_repeat",
  "reference_xyz_m": [0, 2, -0.1125],
  "target_z_m": -0.1125
}
```

These coordinates describe the repository's experiment, **not an assumption to
apply to arbitrary targets**. Use them only if that is your matching reference
and target support height; otherwise supply a measured matching reference.
The directory needs its `config.json`, `frames.grd` and optional saved background.
The adapter calls `load_reference` with its acquisition/quality checks, then
uses `infer_azimuth_rx2` for each detected echo. It averages angle-channel samples
for up to five frames, bounds inversion to +/-25 degrees and rejects invalid
fits. `angle_method` becomes `rx2_reference`. Elevation is null in this mode:
`assumed_target_z_m` is a supplied height, not measured elevation. Distance remains
per-frame and is returned even when angle estimation is rejected. No default
reference phase is fabricated from a synthetic or unrelated recording.

## Optional fixed background

Background subtraction is off initially. With the radar fixed, remove the
objects you want to detect and issue Sensor **DoCommand**:

```json
{"command": "capture_background", "frames": 30}
```

Poll readings until `background_capture_remaining` is zero and
`background_subtracted` is true, then introduce the target. An object present in
that reference will be removed even if it is stationary; this is expected for an
empty-scene comparison. A newly introduced object remains eligible after it
stops moving. Use the following to return to absolute echoes:

```json
{"command": "clear_background"}
```

The reference is never updated automatically. It is cleared after disconnect or
restart because mounting/background may have changed. Capture is bounded to
10–300 frames. `{"command":"status"}` returns the same operational snapshot.

## USB recovery and testing

The reader owns one serial connection, sends `B` to start and `c` to stop, and
closes it on every error/shutdown path. Transport errors trigger reconnection;
config/protocol errors stop with an explicit error. No valid frames for the
watchdog interval triggers a reconnect. The worker drops stale readings instead
of returning old distances with `healthy: true`. If macOS changes the device
name, update `serial_port`; the adapter deliberately does not guess another USB
device. Only one app/module should own this port.

Automated validation covers the SDK lifecycle, static/moving scenes, range/angle
independence, background capture/clear, normalized and physical Doppler gating,
configuration preservation, JSON serialization, serial cleanup/reconnect and
staleness. The build runs a bundled synthetic self-test. The existing repository
recording-based angle checks require recordings absent from this checkout.
Hardware behavior and physical accuracy still need testing on your Mac/board.
