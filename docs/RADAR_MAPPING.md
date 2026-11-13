# Experimental radar mapping with external poses

This is a mapping consumer of SLAM/odometry poses. It does not implement visual
tracking, radar-only localization, loop detection, synthetic aperture imaging, or
a Viam SLAM service. A USB webcam path alone is not a metric pose source.

## Review of the requested repositories

Reviewed PanoRadar master 41e222f0939bc5aa5fe43eed62f826484a8178c5 and
CartoRadar master 0cc9a709e75cbe299a425c00f14312ef09a928de.

- [PanoRadar hardware/data assumptions](https://github.com/penn-waves-lab/PanoRadar/blob/41e222f0939bc5aa5fe43eed62f826484a8178c5/panoradar_SP/dataset.py):
  77 GHz start frequency, 5.12 MHz sampling, rotation-cycle segmentation,
  synchronized radar/IMU timestamps, synthetic antenna samples.
- [PanoRadar imaging](https://github.com/penn-waves-lab/PanoRadar/blob/41e222f0939bc5aa5fe43eed62f826484a8178c5/panoradar_SP/radar_imaging_3d.py):
  vertical and horizontal beamforming with rotation-radius and motion phase
  compensation. Moving this fixed three-RX radar does not provide equivalent
  phase-coherent aperture samples or interchangeable pretrained-model inputs.
- [CartoRadar inputs](https://github.com/penn-waves-lab/CartoRadar/blob/0cc9a709e75cbe299a425c00f14312ef09a928de/OccNet/dataset/panoradar_radar.py):
  panoramic range images, uncertainty and poses. Sparse echoes cannot simply be
  reshaped into these inputs. Unobserved space is not a depth measurement.
- [CartoRadar requirements](https://github.com/penn-waves-lab/CartoRadar):
  suggested RTX 3090, at least 16 GB GPU memory and 32 GB RAM, CUDA.
  That pipeline is not installed in the rover module.

This implementation is original code informed by the interface requirements.
Neither project's algorithms or weights are copied or claimed reproduced.
PanoRadar is BSD-3-Clause; CartoRadar is CC BY 4.0. Refer to their papers for
research attribution.

## New camera commands

Use DoCommand on the existing radar-pointcloud camera:

- `mapping_frame`: measured optical XYZ, host-receipt timestamp, frame ID,
  config hash, quality and calibration flags. Last 32 snapshots retained.
- `map_add`: attach an external pose to that exact frame.
- `map_points`: voxel-filtered measured endpoints in the external map frame.
- `map_update_poses`: apply external loop-closure corrections. Local observations
  are retransformed instead of leaving old geometry in place.
- `map_reset`: clear map and pending snapshots.

Memory is bounded to 500 keyframes. Re-adding an ID replaces that frame; it is not
additional evidence. Oldest inserted keyframes are evicted. Map/config changes
require reset. Maps are in-memory and disappear on restart. No background mapping
happens until a client supplies poses and calls these commands.

## Connect your pose source

Use calibrated stereo/RGB-D SLAM, metric visual-inertial SLAM, or wheel/IMU
odometry for initial tests. Odometry drifts; it is not loop-closing SLAM. The actual
pose resource must still be identified and integrated for this rover.

```python
frame = await radar_camera.do_command({'command': 'mapping_frame'})
# Obtain/interpolate your real external pose at frame['captured_at_unix'].
# map_from_radar_optical = map_from_base @ base_from_radar_optical
await radar_camera.do_command({
    'command': 'map_add',
    'frame_id': frame['frame_id'],
    'map_id': 'room-session-1',
    'pose_timestamp_unix': pose_timestamp_unix,
    'map_from_radar_optical': map_from_radar_optical.tolist(),
})
room = await radar_camera.do_command({'command': 'map_points'})
```

The pose variables above must come from your actual pose provider; they are not
implemented by this module. Do not supply identity poses while driving.
Matrices are rigid row-major 4x4 transforms; translations are **meters**. Viam
Pose translations commonly use millimeters: convert before supplying them.
Radar optical axes are X right, Y down, Z forward. For a perfectly forward-facing
radar and base X forward/Y left/Z up, the optical-to-base rotation is
`[[0,0,1],[-1,0,0],[0,-1,0]]`; include the measured mounting translation and rotation.

Pose time must match capture time within 0.1 s, with synchronized clocks.
Capture time currently means host receipt, not hardware exposure. Measure serial
latency and camera timing offsets. This compensates between frames, not motion
within a radar frame. Start with slow motion or stop-and-scan.

Default angular-width limit is 30 degrees. Observed widths of 55–120 degrees
will be rejected intentionally. For exploratory visualization only, map_points
can accept `max_angular_width_deg: 120`; that does not improve accuracy.
Width is a beam-response diagnostic, not calibrated covariance. Voxel size
(default 0.2 m) is not a claim about sensor resolution.

Apply external loop corrections with `map_update_poses`, the same `map_id`, and
`poses` mapping retained frame IDs to corrected 4x4 transforms. All updates are
validated before mutation. Correct all affected frames. Reset on a changed origin
if the backend cannot provide consistent corrections.

## Save a map

After connecting the SDK and providing poses, export without the hosted viewer:

```python
from pathlib import Path
import json
room = await radar_camera.do_command({'command': 'map_points'})
Path('room-radar.json').write_text(json.dumps(room, indent=2))
points = room['points']
header = (
    'VERSION .7\nFIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n'
    f'WIDTH {len(points)}\nHEIGHT 1\nPOINTS {len(points)}\nDATA ascii\n'
)
body = ''.join(f'{p["x_m"]} {p["y_m"]} {p["z_m"]}\n' for p in points)
Path('room-radar.pcd').write_text(header + body)
```

Map coordinates are already external-frame XYZ: do not apply optical conversion
again. The existing camera preview still shows current-frame echoes, not the map.

## Remaining limits

This is an experimental endpoint map, not an occupancy/free-space map or a
collision guarantee. No echo does not mean free space. It does not remove moving
people or correct multipath. Radar calibration remains unverified. Zero Doppler
on a moving rover is not a reliable stationary-object label.

Validate calibrated extrinsics, measured static targets, timestamps, a measured
trajectory and a return-to-start loop before relying on the map. Tests cover
transform math, pose-time rejection, duplicates, corrections, empty frames and
memory bounds. No physical-room SLAM performance has been established.
