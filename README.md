# Three-RX radar and glass-feature research

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

The six panes show range power, a range–azimuth elevation-zero beamforming slice, 3D phase detections, range–Doppler including stationary returns, reflection history, and experimental material features. Blue detections are stationary; orange detections are moving. The status bar separates device drops, transport CRC/gaps, processing time, and display skips. The worker processes and records every accepted frame independently of GUI rendering; Qt can skip display updates when rendering is slow.

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

See [detection research and the carly implementation](docs/DETECTION_RESEARCH.md)
for the sensor/configuration audit, algorithm recommendations and synthetic
comparison. Try the experimental main detector with
`python -m radar gui --synthetic --moving-detector range_doppler` or add
`--moving-detector range_doppler` to a replay command. It preserves separate
moving peaks at the same range; the existing `range_profile` mode remains the
default pending measured-scene evaluation.

For the current hardware investigation, use the documented [physical antenna geometry](docs/ANTENNA_GEOMETRY.md), [experimental static background subtraction](docs/STATIC_BACKGROUND.md), and [guided angular sweep](docs/ANGULAR_SWEEP.md). The sweep checks measured left/right/up positions and independent validation poses before generating any angle calibration; it is not a moving-sensor point-cloud mapper.
