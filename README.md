> **Short-range diagnosis:** [SHORT_RANGE_FINDINGS.md](SHORT_RANGE_FINDINGS.md) documents a fixed candidate-selection defect, improved 50 cm replay, and the remaining physical range limits.

> **November 2026 range-only takeover:** See [RANGE_V1.md](RANGE_V1.md) for the isolated MVP and [AUDIT_RANGE_V1.md](AUDIT_RANGE_V1.md) for current evidence. Historical setup/validation claims below are not proof of the flashed board or calibrated accuracy.

# Three-RX radar and glass-feature research

The primary objective is glass-obstacle detection that transfers across setups.
**That objective is not yet achieved.** The saved material model misses the
closed-door recordings, and generic obstacle returns do not establish glass
identity. The [experimental 3D view](docs/OBSTACLE_3D.md) is a secondary diagnostic,
not the glass-detection fix.

The [November 11 raw-signal audit](evidence/glass-signature-20261111/README.md)
finds repeatable door-state changes but no isolated glass signature. It includes
a [fixed-fixture panel/control capture plan](docs/GLASS_SIGNATURE_CAPTURE.md)
for the next hardware session.

On Linux, create a persistent project environment before running the GUI:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[material-cpu]'
.venv/bin/python -m radar gui --replay recordings/door03/closed-03 --obstacle-cloud
```

Use `.venv/bin/python` explicitly or activate `.venv`; installing into this
environment does not add PyQt6 to a separate system/Conda Python.

For the BGT60CUTR13AIP **experimental glass-versus-drywall classifier**, see
[the material testing guide](docs/MATERIAL_CLASSIFICATION.md). It adapts a public
XGBoost material-classification workflow to the existing recordings and USB
stream, with labeled capture, training, replay and live commands. The initial
result is a repeat comparison of one window and one wall; recognition of new
surfaces remains to be tested.

The saved model is included under `artifacts/material-glass-drywall-pilot/`.
Restore the archived session data with `python3 tools/restore_material_recordings.py`
before replaying or retraining. See the [recording archive instructions](data/material-study-2026-11-08/README.md),
[later live-test results](evidence/material-transfer-check/report.json), and
[team progress log](docs/progress/Wavvy_Progress_Report_Log.docx).

The [calibrated obstacle detector](docs/OBSTACLE_DETECTION.md) combines repeated
clear/blocked range profiles, supports saved replay and live indication, and
documents results on the door recordings. It requires a fixed-scene calibration.

For repeated glass-door open/closed raw capture and held-out scene comparison,
see [the door experiment workflow](docs/DOOR_CHECK.md). Run `python -m radar
door-check --help` for capture options. This is door-state evidence, not a glass
material classifier.

New CYSBSYSKIT-DEV-01 / BGT60CUTR13AIP firmware and a standalone Python Qt application. The sibling working demo is untouched. No camera, RGB-D, ROS2, cloud service, or GPU is required.

**Status:** firmware compiles with installed ModusToolbox 3.9 and official HAL/PDL/driver. Synthetic processing and Qt rendering run locally. No board has been flashed or measured. Three-RX ordering, raw chirp timing, RF scale, antenna coordinates, and restart behavior still require hardware verification. Material output remains **UNKNOWN**; there is no validated glass classifier.

## Run without hardware

From PowerShell in this directory, using Python 3.11 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m radar gui --synthetic
.\.venv\Scripts\python.exe -m radar synthetic recordings\synthetic01 --frames 100
.\.venv\Scripts\python.exe -m radar gui --replay recordings\synthetic01
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The six panes show range power, a range–azimuth elevation-zero beamforming slice, 3D phase detections, range–Doppler including stationary returns, selected-peak range history, and experimental material features. Blue detections are stationary; orange detections are moving. The status bar separates device drops, transport CRC/gaps, processing time, and display skips. The worker processes and records every accepted frame independently of GUI rendering; Qt can skip display updates when rendering is slow.

## Live box movement check

On macOS, launch the GUI from this repository with:

```bash
.venv/bin/python -m radar gui --port /dev/cu.usbmodem2103 --config configs/range-source-derived.json
```

The launcher stages PyQt6's installed platform plugins in a temporary directory because the virtualenv copies on this Mac carry a hidden file flag that makes Qt report the Cocoa plugin as missing. It removes the temporary copy when the GUI exits. An explicit `QT_QPA_PLATFORM_PLUGIN_PATH` is respected.

With the radar fixed, start the live GUI with a configuration matching its firmware. Remove the box and keep hands away from the radar, then click **Capture empty scene (30 frames)**. Wait for **Empty-scene reference ready** before placing or moving the box. The reference is recaptured by clicking the button again after returning to an empty scene; it is not saved between runs. Live capture is disabled during `--record` to keep a recording's processing metadata consistent.

After a live empty-scene capture, the blue range line shows raw-power change in dB versus that reference. The green ring selects a sustained positive change among usable bins 1 and above at config plot coordinates up to 2 m, rather than the strongest complex-subtracted reflection anywhere in the room. Bin zero is excluded as a leakage/DC region. It needs three associated frames and at least 3 dB excess over empty, with a 2 dB lead over nonadjacent short-range bins; neighboring bins may be part of the same broad return. Distant clutter cannot become the green-ring candidate. A missing return removes the ring immediately; the previous bin is remembered for at most two frames for reacquisition. This is an experimental short-range presence indicator, not proof the return is the box or that its plotted coordinate is physical distance. Other panels still show the original spectral processing. A preloaded complex background without a live empty-scene capture retains the old spectral-peak display.

The range-profile zoom centers on the first green-ring bin and then stays fixed, so movement is visible rather than hidden by a following axis. Change the window width, click **Recenter on green circle** after a jump, or uncheck **Zoom range profile** for the full view. The lower-middle plot shows the selected bin's config-derived coordinate over the last 100 displayed updates; missing/rejected updates leave gaps. The plot is provisional and does not add range resolution. In the source-derived configuration, FFT bin centers are about 0.35 m apart. In one recorded check, the 0.30 m box selected bin 1 and the 0.90 m box selected bin 3; their plotted coordinates must not be relabeled as calibrated object distances.

Keep the radar and surrounding objects still after capturing the reference. Moving the sensor, changing the room, or including the box in the empty-scene capture invalidates the comparison. The close-range analog filter and the unvalidated range scale are unchanged; software cannot recover a return the hardware does not provide. Use measured box positions and saved raw recordings to evaluate close-range misses and distance error before claiming tracking accuracy.

If a physically closer box appears at a *higher* bin than a farther box, do not use the green ring as a distance reading. Close the GUI so the serial port is free, then run this single guided raw-data check on macOS:

```bash
.venv/bin/python -m radar range-check recordings/box_range_01 --port /dev/cu.usbmodem2103 --config configs/range-source-derived.json
```

It prompts for an empty scene, a measured near position, and a measured far position; each starts after a three-second step-away delay and records six seconds of unchanged raw ADC. The sensor stays connected and a reader keeps draining the stream during position changes, matching the live GUI rather than restarting or accumulating old frames. Each scene's sensor-timestamp span is checked against wall time; a stale/backlogged capture is rejected. Keep the sensor fixed and report measured distances from its antenna face to the nearest box face. It writes a `range-check-report.json` comparing both the complex residual peaks and the same short-range amplitude selector used by the GUI. A bin changing or moving outward is only a diagnostic clue, not validation of box identity, close-range accuracy, or the meter scale. The output directory must not already exist; use a new name for another run. Re-analyze saved data with `python -m radar range-check-analyze recordings/box_range_01`.

## Build and connect

```powershell
powershell -ExecutionPolicy Bypass -File tools\build.ps1
```

Firmware output: `build/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex` and `.elf`. The build does not program hardware. See [Windows setup and explicit flashing](docs/WINDOWS.md) before connecting. After you explicitly approve and perform flashing:

```powershell
.\.venv\Scripts\python.exe -m radar gui --port COM7 --config configs\hardware-provisional.json
```

The hardware configuration file contains **illustrative, unverified** timing and geometry. Physical axes are provisional until [calibration and bring-up](docs/CALIBRATION.md) is completed; these example values are not decoded from the register list. The wire profile ID checks sample layout, not proof of physical calibration. Never report distances, speeds, or angles from this template as hardware measurements.

## Components

| Path | Purpose |
|---|---|
| `firmware/main.c` | Fresh HAL application, finite raw bursts, FIFO service, async serial, framed CRC32 |
| `firmware/vendor/` | Unmodified official three-RX RF/sequencer configuration, with original license |
| `bsps/` | Pre-existing local Infineon BSP, unchanged |
| `radar/protocol.py` | Bounded framing, header/payload integrity, resynchronization and loss accounting |
| `radar/processing.py` | Range/Doppler FFTs, stationary/moving paths, phase AoA, beamforming and features |
| `radar/calibration.py` | Complex channel corrections and surveyed range fit |
| `radar/storage.py` | Raw ADC sessions with configuration, labels and features |
| `radar/gui.py` | Qt/Matplotlib display with acquisition worker and bounded display queue |
| `tests/` | Synthetic recovery, detection, calibration and persistence tests |

Read [wire format and processing limitations](docs/DESIGN.md), [material collection and GlassFormer investigation](docs/GLASS_RESEARCH.md), and [local validation evidence](docs/VALIDATION.md).

For the current hardware investigation, use the documented [physical antenna geometry](docs/ANTENNA_GEOMETRY.md), [experimental static background subtraction](docs/STATIC_BACKGROUND.md), and [guided angular sweep](docs/ANGULAR_SWEEP.md). The sweep checks measured left/right/up positions and independent validation poses before generating any angle calibration; it is not a moving-sensor point-cloud mapper.
