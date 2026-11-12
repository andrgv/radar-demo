# Radar-only glass research

## November 11 raw-signal audit

The [paired signal audit](../evidence/glass-signature-20261111/README.md) checks
27 fixed pane-range measurements across 18 recordings from the two physical
doors. RX1/RX2 coherence increases consistently, but most of that effect is
reproduced by a stationary-scene mean/power surrogate without material identity.
No single measurement separates all recording medians across setups. The next
step is the [fixed-fixture panel/control capture](GLASS_SIGNATURE_CAPTURE.md),
which isolates panel insertion from frame/handle, handling and background effects
before fitting another classifier. No new hardware data or glass model is added.

## Current glass-obstacle transfer result

Glass detection remains the primary objective; the experimental 3D obstacle
view is a secondary diagnostic and is not its completion. The saved window/wall
model reports no glass detections in 261 closed-door windows. Fixed-scene door
state recognition also does not establish recognition of glass in new scenes.

A subsequent glass-specific test adds raw cross-receiver phase/coherence to
full-spectrum relative power without using XYZ or measured pane positions.
Door03/door04 are grouped as the same physical door during exclusion. It still
misses all six closed captures of that held-out door, and other folds falsely
classify open/drywall controls as glass-blocking. This candidate was not deployed.
See [the protocol and results](../evidence/glass-transfer-20261109/README.md) and
`tools/audit_glass_transfer.py`. These are development results on inspected
recordings, not proof that every possible radar method fails.

## What was investigated

GlassFormer was inspected at repository commit `233a97a8b139421621561fa1bd24063abd114210`:

- [Acconeer IQ acquisition](https://github.com/Suhani92/GlassFormer/blob/233a97a8b139421621561fa1bd24063abd114210/ros2_ws/src/acconeer_ros2_driver/acconeer_ros2_driver/acconeer_iq_node.py) publishes range-bin mean magnitude, amplitude variance and unwrapped phase standard deviation from Acconeer A121 complex subframes. It is not a BGT60CUTR FMCW range/Doppler implementation.
- [Radar mask node](https://github.com/Suhani92/GlassFormer/blob/233a97a8b139421621561fa1bd24063abd114210/ros2_ws/src/acconeer_ros2_driver/acconeer_ros2_driver/radar_mask_node.py) selects the strongest radar peak, projects a radar-FOV region into the camera, and marks pixels with invalid depth or RGB-D depth farther than the radar peak plus a threshold. Morphological operations clean this mask.
- [Model](https://github.com/Suhani92/GlassFormer/blob/233a97a8b139421621561fa1bd24063abd114210/glassformer/models/glassformer.py) uses a SegFormer RGB backbone with radar-mask attention at deep stages. Its learned RGB segmentation model is not a radar-only material classifier.

The present implementation adapts amplitude and temporal/phase consistency concepts, using FFT-derived complex per-RX data. It does not port the RGB-D mismatch mask, RGB transformer, pretrained weights, Acconeer driver or ROS2. No GlassFormer source is copied into the Python implementation. This investigation does not establish transfer of any published GlassFormer result to this sensor.

## Implemented exploratory features

The GUI and per-frame JSONL expose features at the strongest usable range peak. These are descriptors to test against labels, not glass probabilities.

| Feature | Measurement | Principal confound |
|---|---|---|
| `reflection_db` | Mean range-FFT power across chirps/RX, dB ADC² | Distance, incidence, gain, thickness, coatings and RCS |
| `range_entropy` | Entropy of normalized range energy | Room clutter and multiple unrelated objects |
| `angular_width_deg` | RMS spread of the peak's elevation-zero beam power | Very small three-RX aperture; broad beam and elevation bias |
| `temporal_cv` | CV of peak-bin power over up to 30 valid consecutive frames | Hand motion, target switching, thermal/gain drift |
| `phase_consistency` | Circular resultant of successive chirp phase increments | A steady moving object can also score near one |
| `late_energy_ratio` | Energy at bins ≥3 beyond the strongest peak, divided by peak power | Background objects and sidelobes, not proof of multipath |
| `moving_energy_fraction` | Mean-subtracted noncentral Doppler energy/full Doppler energy | Motion and central-bin exclusion |
| `saturation_fraction` | Fraction at 16-bit container rails | Effective ADC packing must be verified |

`temporal_frames` identifies warm-up; history clears on sequence gaps. Peak-bin hopping can alter these features even when the material is unchanged. This initial implementation uses the strongest scene return, not a glass-specific segmentation mask or tracked surface. For controlled experiments isolate the specimen as that return, verify its range manually and reject scenes where a background object dominates. A future ROI/track-specific feature extractor is needed for unconstrained environments.

Inspect the range–angle slice, range–Doppler map, 3D points and amplitude history alongside these numbers. Multipath experiments should compare the same scene with panel absent/present, change the background reflector, and check whether late peaks move in a geometry-consistent way. The implemented late-energy proxy alone does not identify path order or distinguish transmission through glass from unrelated clutter. Planar surfaces can disappear at oblique incidence; a missing radar return does not exclude glass.

## Labeled collection procedure

1. Complete digital acceptance and calibration first. Fix gain, waveform, board pose, warm-up time and calibration ID. Save the tool export, board/antenna drawing and measured parameter uncertainty.
2. Use multiple distinct panes: clear float glass, tempered/laminated/coated glass, several thicknesses. Include hard negatives such as acrylic, polycarbonate, mirrors, metal, glossy ceramic, painted wood, drywall and empty scene. Record exact composition when known, and `unknown` when not.
3. Use matched range/incidence grids within the verified usable range. Start at normal incidence then ±10°, ±20°, ±40°, using measured geometry and a fixture. Repeat each specimen/pose in independent sessions on different days, not merely repeated frames in one recording.
4. For each pose record an empty fixture, specimen with empty background, specimen with a strong reflector behind it at surveyed separations, and the same reflector without the specimen. Keep all other geometry fixed. Include stationary and controlled moving background cases. Survey distances to both panel and background.
5. Record at least 30–60 seconds per condition with `radar record`; use a fresh directory and populated metadata JSON. Set session label `glass`, `non_glass`, `empty` or `unknown`. Label the actual specimen, not whether the viewer happened to detect it. Photograph/measure the fixture for experiment records if desired; no camera is required by this system.
6. Record room/day in `scene_id`, physical item in `specimen_id`, material, thickness/coating, range, incidence, background geometry, temperature and notes. Review ADC clipping, errors/gaps, peak ownership, noise floor, features and calibration. Preserve rejected sessions and rejection reasons separately to avoid hiding failures.
7. Split by room/day **and physical specimen**. Never randomly split adjacent frames. Keep a blind held-out test set untouched by thresholds, feature selection or calibration fitting. Report confusion matrices, precision/recall, ROC/PR curves, uncertainty across sessions, and performance by range/incidence/background. Report missed panels separately from misclassified detected panels.

## Optional session-level baseline

After collecting labels, an intentionally small NumPy logistic baseline is available:

```powershell
.\.venv\Scripts\python.exe -m radar research recordings artifacts\pilot-report --heldout-scenes room03-day04 room04-day05
```

It requires at least eight usable labeled sessions, both classes in train and test, verified configs, a single profile ID, ten quality-controlled feature frames per session after temporal warm-up, explicit scene/specimen IDs, and disjoint physical specimens across partitions. It summarizes each session by median features, fits standardization and regularized logistic weights on train sessions only, and writes `sessions.csv`, held-out predictions, AUC, accuracy and confusion counts in `report.json`. This is a pilot protocol, not a statistically sufficient sample-size recommendation.

The score is an uncalibrated exploratory model output; it is deliberately not used by the live GUI. Tiny datasets and manual `verified` flags do not establish validity. Compare to intensity-only and background-only controls, perform feature ablations, vary acquisition conditions and obtain enough independent held-out specimens/scenes for uncertainty estimates. Glass/non-glass cannot be inferred reliably from these features without that evidence. No labeled hardware data or validated trained model is included.

## Other sources

The [working demo](https://github.com/andrgv/CYSBSYSKIT_DEV_01_CMOS_Radar_Standard_Mode) supplied local pin/interleaving reference only. The [official driver](https://github.com/Infineon/sensor-xensiv-bgt60cutrxx/tree/release-v1.1.0) supplies SPI, ADC initialization, register definitions and FIFO access. The [official people-tracking example](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-people-tracking/tree/f6e9c82b28d0022790b0905201e1d6720615063d) supplies the three-RX register/sequencer profile. Existing BSP and external dependencies retain their own licenses; this project does not relicense them.
