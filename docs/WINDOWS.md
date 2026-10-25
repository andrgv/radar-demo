# Windows build, flashing, installation and execution

## Prerequisites

Install ModusToolbox **3.9**, its GCC ARM toolchain, Git for Windows, Python 3.11+ x64, and Infineon KitProg3 USB drivers. This workspace already has ModusToolbox at `C:\Users\andre\ModusToolbox\tools_3.9` and GCC 11.3.1 at `C:\Users\andre\Infineon\Tools\mtb-gcc-arm-eabi\11.3.1`. Do not replace the working sibling application's files or dependencies.

Use the board's KitProg3 USB connector. Serial data travels over the board debug UART through KitProg3's USB serial bridge (2,000,000 baud, 8N1, no flow control); this is not a native USB CDC firmware implementation. Use the same radar shield and feather adapter wiring as the working demo. `firmware/main.c` uses CS=`CYBSP_SPI_CS`, reset=`GPIOA5`, IRQ=`GPIO10`, LDO=`GPIO5`, boot straps=`GPIO13/GPIO11`, direction=`GPIOA2`; the data loop polls FIFO status instead of relying on edge interrupts.

## Dependencies and build

The existing `bsps/TARGET_APP_CYSBSYSKIT-DEV-01` is used directly. Manifests in `deps/` pin the official radar driver 1.1.0, HAL 2.7.4, PDL 3.24.0, core library 1.8.0, core-make 3.10.0, recipe 2.8.0, CMSIS 6.1.1, CM0+ image 1.11.0, and board Bluetooth support 1.0.0. Bluetooth is not started. Normal dependency resolution can regenerate `libs/mtb.mk`; the supplied file supports the already installed sibling `../mtb_shared` cache without network access. Preserve it when packaging an offline copy; it is build metadata, not application source.

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build.ps1 -Action getlibs
powershell -ExecutionPolicy Bypass -File tools\build.ps1 -Action build
```

Skip `getlibs` when the pinned dependencies are already in `../mtb_shared`, as they are on this machine. `getlibs` needs network and may populate/update the shared cache; the implementation's validation used only the existing cache. The wrapper uses the ModusToolbox Bash shell and a relative build directory to avoid Windows `/cygdrive` path creation issues. For another installation, pass `-ToolsDir 'D:\ModusToolbox\tools_3.9'` and set `CY_TOOLS_PATHS` if the makefile cannot discover it. You can also open the ModusToolbox shell in this folder and run `make build -j8 CY_BUILD_LOCATION=build`.

## Flash only after confirmation

Save the existing known-good HEX and its source/configuration before changing the device. The working demo's files are still in the sibling directory. Close terminals or other programs holding the KitProg3 COM port. Connect KitProg3, then deliberately invoke:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build.ps1 -Action program -ConfirmFlash
```

`-ConfirmFlash` is mandatory; the wrapper otherwise refuses programming. No flashing command was executed during development. ModusToolbox's `program` target selects the installed supported probe workflow; if it cannot locate the probe, use ModusToolbox's generated Launch/Program configuration or Infineon Programmer to load `build\APP_CYSBSYSKIT-DEV-01\Release\glass-radar-3rx.hex` via KitProg3 SWD. Select this board, not another attached device. Probe connection/programming remains untested here. Restore by deliberately programming the saved known-good demo HEX.

## Python installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m serial.tools.list_ports
.\.venv\Scripts\python.exe -m radar gui --synthetic
.\.venv\Scripts\python.exe -m radar gui --port COM7 --config configs\hardware-provisional.json
```

Activation is optional because the commands use the interpreter explicitly. Installation needs PyPI access unless packages are already installed. Tested package versions: NumPy 2.4.6, PyQt6 6.11.0, Matplotlib 3.11.2, pyserial 3.5 on Python 3.11.9. A synthetic GUI opens without a serial device. Do not use an ASCII terminal while the binary viewer owns the COM port. Firmware starts idle; the host sends `0x42` to start and `0x63` to stop. Serial port access does not reset the board intentionally; reconnect/reset must be checked on your actual bridge.

## Record, replay, calibrate

Edit a copy of `configs/measurement.json` with the specimen, scene, label and surveyed pose. Use a new output directory for every session (overwriting is refused).

```powershell
.\.venv\Scripts\python.exe -m radar record recordings\glass01 --port COM7 --config configs\hardware-provisional.json --metadata configs\measurement.json --seconds 60
.\.venv\Scripts\python.exe -m radar gui --replay recordings\glass01
.\.venv\Scripts\python.exe -m radar analyze recordings\glass01
.\.venv\Scripts\python.exe -m radar calibrate recordings\reflector01 configs\calibrated.json --distance 1.0 --azimuth 0 --elevation 0
.\.venv\Scripts\python.exe -m radar gui --port COM7 --config configs\calibrated.json --record recordings\live01 --metadata configs\measurement.json
```

Replay uses the session's stored config and nominal frame interval, not wall-clock arrival jitter. For reprocessing with a corrected calibration, supply `--config configs\calibrated.json` with `gui --replay`. Headless `analyze` uses the stored config. `Ctrl+C` stops headless capture and closes files. The duration deadline also applies when no frames arrive. `python -m radar benchmark --frames 200` measures processing, excluding acquisition and drawing.

## Troubleshooting

No packets: verify COM port ownership, baud support, power and shield orientation, and reset then reconnect. Firmware initialization failure currently halts with a distinct return code visible in a debugger; it emits no ASCII on the binary port. A blank GUI with an acquisition error is intentional when dimensions/profile mismatch. CRC/gap increases suggest serial/USB loss. Increasing device error/drop counts indicate capture/FIFO problems. Display skips alone indicate Matplotlib rendering cost and do not mean raw recording loss. See the bring-up procedure before changing sampling rates.
