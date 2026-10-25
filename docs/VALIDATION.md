# Local validation and hardware boundary

Validated on Windows with Python 3.11.9, NumPy 2.4.6, PyQt6 6.11.0, Matplotlib 3.11.2, pyserial 3.5, ModusToolbox tools 3.9 and Infineon's GCC ARM 11.3.1. No flashing, GitHub push or serial hardware access was performed.

## Completed checks

- `powershell -ExecutionPolicy Bypass -File tools\build.ps1`: successful Release compile/link with official driver 1.1.0, local official HAL/PDL and unchanged BSP. ELF and HEX are in `build/APP_CYSBSYSKIT-DEV-01/Release/`. Reported flash utilization: **47,272 bytes**. Static `.bss`: **15,088 bytes**, `.data`: **1,048 bytes**. The linker reserves remaining RAM as heap; it is not actual heap allocation.
- `python -m unittest discover -s tests -v`: **20 tests pass**, covering protocol fragmentation, CRC/header corruption, byte loss/resynchronization, sequence wrap/restart/gaps, synthetic stationary+moving returns, signed Doppler, phase angles, invalid geometry/directions, noise-only behavior, channel correction recovery, range scaling, configuration mismatch, temporal reset, raw session round-trip, acquisition start/stop and a silent-device path. Grouped-baseline tests check train/test artifacts and reject shared specimens/unverified configurations. These are synthetic/software tests, not RF validation.
- `python -m compileall -q radar`: modules compile.
- `python -m radar benchmark --frames 200`: observed **3.93 ms median / 5.50 ms p95** processing per 17×64×3 frame on this PC. This excludes UART, USB, disk and Qt drawing; it is not a measured hardware frame rate.
- `python -m radar synthetic artifacts/synthetic --frames 30` followed by `python -m radar analyze artifacts/synthetic`: complete 30-frame ADC recording and replay with finite features and expected target locations.
- `$env:PYTHONPATH='.'; python tools/gui_smoke.py`: offscreen Qt acquisition, processing, plotting and shutdown pass; screenshot in `artifacts/gui-smoke.png` visually inspected. The GUI renders the six requested/research panes; Matplotlib can skip display updates under load while acquisition/recording continue.

The synthetic default scene places a stationary target at range bin 7, azimuth −20°, elevation +10°, plus a moving target at range bin 17, azimuth +30°, elevation −8°, velocity +0.35 m/s. Tests recover range bins exactly, angles within 1° and velocity within one Doppler bin. Injected channel gain/phase errors are recovered within 0.01 complex gain. These tolerances demonstrate internal mathematical consistency only; they do not include antenna/RF uncertainties, multipath, nonuniform chirps or real ADC artifacts.

Final HEX SHA256: `67c01d441fa7e8a078f189cedf1d76aaa0d438b499eac2148158ddfa611b685c`. Build output is retained in `artifacts/build.log`. The sibling demo's pre-existing `python_scripts/continuous.py` modification was left untouched; no file in that application was edited by this implementation.

The logistic research test uses deliberately artificial separable feature fixtures solely to verify software behavior. Its AUC/accuracy are not material experiment results and must not be reported as glass-detection performance.

## Still requiring the board

The hardware checklist in `CALIBRATION.md` is mandatory before reporting physical measurements: RF profile suitability, reset-to-chirp alignment, uniformly spaced raw chirps after averaging override, antenna order/phase centers, actual ADC format, sample rate/slope/carrier/chirp interval, SPI/FIFO throughput, actual UART baud, timer width/wrap, sustained transport errors, controlled-range/velocity/angle errors, temperature drift and probe flashing. The default host hardware config is illustrative and marked unverified.

The official generated RF profile is unchanged on disk, but the fresh firmware's runtime raw-mode overrides and bounded restart behavior are **unverified on silicon**. A successful build cannot establish their operation. If raw chirp timing/order differs, correct the sequencer/configuration before interpreting the plots.

There are no labeled hardware sessions or trained/validated glass results. The delivered system measures radar features and supplies a controlled experiment/evaluation path; it does not certify glass presence. Ordinary camera-free operation and synthetic operation are supported; later fusion would need extrinsics and clock synchronization.
