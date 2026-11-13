# Raw mmWave point-cloud camera in Viam

The existing `carlyworkspace:upenn-mmwave` module now provides two resources:

| API | Model | Purpose |
|---|---|---|
| `rdk:component:sensor` | `carlyworkspace:upenn-mmwave:infineon-mmwave` | Owns USB acquisition and returns radar echoes |
| `rdk:component:camera` | `carlyworkspace:upenn-mmwave:mmwave-pointcloud` | Uses that sensor's buffered raw ADC to return a PCD point cloud and PNG preview |

Both resources should be enabled. Only the sensor opens USB. The camera declares
an implicit dependency using its `sensor` attribute and retrieves raw data through
`Sensor.DoCommand`; it works with Viam's dependency proxy, not an assumed local
Python object. It never opens or closes the dependency's serial port.

## Update and publish

On the development Mac (or other computer with your checkout and Viam CLI):

```bash
cd ~/upenn-mmwave-demo
git pull --ff-only origin demo-viam
viam module update
viam module build start --from-source --version 0.2.0
```

If `0.2.0` has already been published, use a new version. Follow the returned ID:

```bash
viam module build logs --id YOUR_BUILD_ID
```

Wait for the build matching the **machine with the USB sensor**: normally
`linux/arm64` for an ARM rover, `linux/amd64` for x86 Linux, or `darwin/arm64` for
an Apple Silicon Mac. Build success for a different platform is insufficient.
Run `uname -s` and `uname -m` on the machine if uncertain.

On the target Viam machine, select the new module version and Save. This upgrades
the sensor too, adding the `raw_frame` command required by the camera. Do not
create another module registration or duplicate the serial-reading sensor.

## USB sensor on the rover

A sensor plugged into the rover will not appear in your Mac's `/dev` directory.
For the user's `mm1` rover, reconnect from the Mac with:

```bash
ssh mm@mm1.local
```

After the prompt changes to `mm@mm1`, run:

```bash
ls -l /dev/serial/by-id/
```

Prefer the stable `/dev/serial/by-id/...` device path. If unavailable:

```bash
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

Set that path in the **sensor's** `serial_port` attribute. Keep its tested
`config_path`, such as `configs/exploratory-roll90-phase.json`. The Viam Agent and
module must run on the rover; the Mac may be used only for builds and the browser.
If SSH disconnects, reconnect before running Linux device commands. A Mac prompt
means you are no longer executing on the rover.

Keep the current `upenn-mmwave` sensor enabled; disable the older competing
`mmWave-module` sensor. First verify the current sensor reports `healthy: true`.

## Add the camera on the same machine

Open CONFIGURE → + → Blocks and search `mmwave-pointcloud` or `upenn-mmwave`.
Select the **camera** model `carlyworkspace:upenn-mmwave:mmwave-pointcloud`, and name
the resource `radar-pointcloud`.

Use these attributes (also in `configs/viam-camera-attributes.json`):

```json
{
  "sensor": "upenn-mmwave",
  "method": "deblend",
  "min_range_m": 0.5,
  "max_range_m": 3.0,
  "min_snr_db": 12,
  "min_model_fit": 0.8,
  "max_components": 8,
  "max_points": 64,
  "max_frame_age_s": 1.0
}
```

`sensor` is the exact **resource name** in your configuration, not a module/model
identifier. If you named the sensor `upenn-radar`, use that name instead. There
is no `serial_port` or `config_path` on the camera: those come from the dependency.
The camera follows sensor reconfiguration and invalidates its frame/config cache.

Save, then open the camera's Test/Control panel. `GetPointCloud` returns minimal XYZ ASCII
PCD (`pointcloud/pcd`). `GetImages` returns a labeled top-down PNG named
`radar-topdown`. This PNG is a diagnostic plot, not an optical or depth image;
no camera intrinsics are fabricated. The same-frame result is cached across
image/point-cloud requests. An empty valid frame has zero points and an empty
plot. GetPointCloud reports "No radar points" for that frame rather than sending
an empty cloud to viewers that cannot render it; no placeholder points are added.
Quality and Doppler remain available through DoCommand. A failed/stale sensor raises an error rather than returning a previous cloud.

Python SDK example, after connecting `robot` normally:

```python
from pathlib import Path
from viam.components.camera import Camera

camera = Camera.from_robot(robot, "radar-pointcloud")
cloud, mime_type = await camera.get_point_cloud()
Path("radar.pcd").write_bytes(cloud)
print(mime_type)
print(await camera.do_command({"command": "status"}))
```

## Reconstruction and what the points mean

Default `deblend` uses the repository's `SceneReconstructor` on original raw ADC:

1. Discard the configured startup chirp and remove per-trace DC.
2. Estimate sinusoidal components through a Hankel/subspace analysis and select
   model order with BIC.
3. Refine frequencies off the FFT grid using variable projection and least squares.
4. Fit receiver amplitudes and apply the sensor config's complex gains.
5. Analyze Doppler including the zero-Doppler stationary bin.
6. Match channel vectors against the array response using the configured geometry,
   rotation and non-diagonal angle matrix (the repository's 5-degree angular grid).
7. Reject low-SNR, poor-fit, boundary-angle and aperture-inconsistent hypotheses.
8. Apply camera range, quality, angular-width and response-count bounds.

This can separate some synthetic closely spaced returns that merge in a range
FFT. It does not establish super-resolution on arbitrary physical scenes.
The optional `method: "fft"` uses the repository's simpler range/Doppler local
maxima and array-fit cloud, retaining stationary returns. Use it for comparison
or if deblending is too slow on the target machine.

The camera uses the **same radar configuration** as its sensor, including the
exploratory calibration. It uses the full array model for 3D reconstruction,
not the sensor's optional known-height RX2 reference-angle path. It cannot infer
trustworthy elevation from a known-height-only azimuth experiment.

The cloud is raw-scene processing: sensor `capture_background` commands do not
alter it. `background_subtracted` is always false for the camera. This preserves
stationary scene returns and avoids passing complex-subtracted data into a raw
sinusoid reconstruction algorithm. The sensor's echo thresholds also do not gate
camera input. Camera-specific SNR and model-fit settings apply instead.

No temporal accumulation, sensor pose estimation, surface filling, object
tracking or material classification is performed. Each point is a candidate
radar scattering center, not an object or a pixel on a reconstructed wall.
Expect sparse clouds. Missing points are preferable to invented surfaces. Do
not interpret a 5-degree search grid as 5-degree physical accuracy. Array-response
widths and `angle_calibrated: false` expose the uncertainty.

## Coordinates and units

Repository coordinates are meters with X right, Y forward, Z up. PCD converts
these to camera optical axes:

```text
PCD X = radar X       (right)
PCD Y = -radar Z      (down)
PCD Z = radar Y       (forward)
```

**PCD values are meters**, matching Viam's PCD reader (which converts to internal
millimeters). Do not multiply the PCD coordinates by 1000. The PNG uses a top-down
view with radar forward pointing up on the plot. PCD color indicates relative
SNR, not a measured material/optical color.

## Camera commands and tuning

- `{"command":"status"}`: current frame ID, point count, age, processing time,
  effective config hash, calibration status and coordinate convention.
- `{"command":"points"}`: adds each point's optical XYZ in meters, range,
  SNR, array-model fit, angular-response widths and normalized Doppler.
- `{"command":"diagnostics"}`: adds the deblender's accepted/rejected component
  report and rejection reasons. `fft` has a smaller diagnostic summary.

Settings:

| Attribute | Default | Meaning |
|---|---:|---|
| `min_range_m`, `max_range_m` | 0.5, 3 | Allowed radial distance |
| `min_snr_db` | 12 | Minimum signal-to-background/noise estimate |
| `min_model_fit` | 0.8 | Minimum array response fit, not a probability |
| `max_components` | 8 | Deblender's maximum range-model order (1–12); not object count |
| `max_points` | 64 | Maximum returned points; strongest retained if truncated |
| `max_angular_width_deg` | 120 | Reject broader half-power responses in either axis; lower for stricter selection |
| `max_frame_age_s` | 1 | Freshness limit; the sensor's own limit also applies |

Start with a fixed sensor and a few isolated reflectors at measured distances.
Check positions, left/right/up/down signs and empty-scene behavior. Increasing
point count by lowering thresholds can add ghosts. Physical near-range HPF,
finite bandwidth and three-channel angular ambiguity remain. The module has
synthetic and API tests plus a Linux packaged self-test; hardware and rover
performance still require validation.
