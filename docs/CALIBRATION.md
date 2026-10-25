# Hardware bring-up and calibration

Run commands from `C:\Users\andre\radar-work\glass-radar`, not from its `radar` subfolder. `radar/calibration.py` is a library, not the calibration application. Use `python -m radar calibrate --help` or the recording-based command below. This command fits relative RX gain/phase only; range scale is a separate procedure in section 2. In the viewer, dB ADC² describes return strength; range is the horizontal coordinate and the numeric readout above the plots. Unverified meter values are explicitly provisional.

All items here remain hardware work. Compilation/simulation does not verify a radar measurement. Keep the known-good demo HEX available. The new firmware is idle on boot and emits only binary data after a host start command.

## Diagnosing repeated peaks before calibration

If moving the sensor between different scenes still produces estimates around 0.546, 0.625 or 0.703 m, the provisional configuration maps FFT bins 7, 8 and 9 to those numbers. They are not evidence of objects at those distances. Do not apply a single distance multiplier or hide these bins until raw captures establish whether the peaks move with a target. The example configuration's final range bin is about 2.50 m; that is only the configured scale, not a verified hardware range limit.

Close the GUI to release COM3, then capture separate sessions with a stationary metal plate or corner reflector facing the sensor at independently measured ranges. Keep background and board orientation fixed. For example:

```powershell
python -m radar record recordings\reflector_1m --port COM3 --config configs\hardware-provisional.json --metadata configs\measurement.json --seconds 10
python -m radar diagnose recordings\reflector_1m
```

Repeat at a different known range using a new directory. `diagnose` reports each RX's raw ADC extrema, fast-time variability, dominant FFT bin, spectral peaks, repeated ADC frames, sequence gaps and device counter changes. The raw recording preserves data for deeper packing/chirp-order checks. Its CRC counts apply to the saved validated stream; corrupted serial bytes discarded before recording are not recoverable from it. The `record` command separately prints live parser CRC/gap counts. A fixed peak can be internal coupling/interference or acquisition/packing error; a peak tracking target displacement with wrong meter values suggests scale error. Neither conclusion is established from the live readout alone. Cloth walls and cluttered ceilings are not isolated calibration targets.

## 1. Digital acquisition acceptance

After authorized flashing, use a debugger to confirm successful startup, three enabled `CS_IDX0_RXn` registers, `AVG_CTRL_SEQ0=0`, FIFO threshold 191 and no FIFO headers. Inspect the ADC packing/resolution controls; the wire carries 16-bit containers, whose effective ADC resolution/rail values must be confirmed. `saturation_fraction` currently tests container rails 0/65535 and may miss saturation when ADC bits are left/right justified differently.

Capture MOSI/MISO/CS, the radar timing/IRQ signals, and UART with a logic analyzer. Prove FIFO word order and byte order, and RX1/RX2/RX3 interleaving. If the configuration tool supports distinguishable per-RX test patterns, use them before relying on geometry. Validate every burst reset puts sample0/RX1 at the start of the payload. There are no embedded per-chirp headers in this profile: software framing cannot repair an incorrectly aligned hardware burst.

Confirm the first 17 raw chirps contain the same ramp and uniformly spaced sampling events, and determine whether the default one-chirp discard removes all settling samples. This is particularly necessary because firmware disables the official profile's factor-16 averaging and truncates its sequencer after a bounded raw window. Repeated start/stop/reset must not change interleaving. If the window includes a mixed startup waveform, generate a dedicated raw 3-RX sequencer with Infineon's XENSIV Radar CMOS Configuration Tool, update the vendor profile/ID and dimensions, and repeat this acceptance test.

Record ten minutes and confirm zero unexplained device errors, FIFO errors, CRC errors, sequence gaps and restarts at 10 Hz. Report exact duration, accepted frames, expected attempts, error counters and PC/USB configuration. Unplug/replug serial and simulate a slow reader; verify error/gap counters reveal loss and the next valid packet resynchronizes. Do not increase nominal frame rate until acquisition plus serial transmission fits the period with measured margin. Inspect the 1 MHz HAL timer counter across 65,536 µs and 2³² µs; the allocated timer must be 32-bit. Validate actual UART baud and sensor SPI clock on the pins.

## 2. Establish physical axes

`configs/hardware-provisional.json` deliberately has `verified=false`. Its 1 MHz sample rate, 30 THz/s slope, 60 GHz carrier, 1 ms chirp spacing and half-wavelength L geometry are **example parameters shared with the synthetic generator**, not recovered characteristics of the official sequencer.

Export authoritative waveform values from the configuration tool or derive them with the sensor documentation: actual ADC sample rate after decimation, slope during the sampled ramp, center frequency, unaveraged chirp repetition time and waveform stability. Measure sampling/trigger intervals on hardware and compare to the export. Do not substitute frame interval for chirp interval; the host nominal frame interval is 100 ms, not the coherent sampling interval. If raw chirps are nonuniform, this FFT Doppler pipeline is not valid until the sequencer is corrected or nonuniform processing is added.

Place a strong stationary corner reflector at several surveyed distances spanning the usable range, without nearby reflectors. Compare range-bin peaks to ground truth; range bin spacing is `c*sample_rate/(2*slope*N)`. Window main-lobe width is larger than bin spacing. Fit at least three points using `radar.calibration.fit_range(measured, truth)` and inspect residuals. For returned scale `a` and offset `b`, update slope to `old_slope/a` and offset to `a*old_offset+b`. This corrects an empirical scale/offset, not evidence the waveform itself is correct. Verify using additional distances excluded from the fit. Record RMS and worst-case errors and the analog high-pass near-range blind zone.

Use a controlled moving reflector with independently known radial velocity. Confirm Doppler sign, bin spacing, maximum unambiguous velocity `c/(4*carrier*chirp_interval)`, speed bias and aliases. Stationary wall detections should remain visible while a person moves at a different range. Very slow motion inside the excluded central Doppler band is not reliably separated from stationary structure.

## 3. RX geometry, gain and phase

Obtain the BGT60CUTR13AIP phase-center coordinates and shield mounting orientation from the exact package/board drawing. Do not reuse BGT60TR13C antenna ordering by name. Express right/up positions in wavelengths at the measured carrier, in FIFO channel order. Two independent baselines are required. Baselines longer than half a wavelength can alias with this principal-phase solver. Test reflector sweeps at known azimuth and elevation, separately and together, to establish axis polarity and channel order. A broadside gain/phase fit cannot establish baseline geometry or sign by itself.

Warm up the radar at a fixed temperature. Put a stationary isolated corner reflector at broadside at a previously verified range. Record at least 30–100 frames. Then:

```powershell
.\.venv\Scripts\python.exe -m radar calibrate recordings\reflector01 configs\calibrated.json --distance 1.0 --azimuth 0 --elevation 0
```

Calibration correlates each channel with RX1 at the selected range bin, removes the expected geometric phase for the surveyed direction, and computes relative complex gains. It refuses inter-channel coherence below 0.9 or a missing signal, but cannot distinguish coherent multipath from the intended target. Inspect the target and background manually; strong leakage can pass coherence checks. The resulting file retains `verified=false` until you have independently checked timing and geometry; it does not silently certify hardware. RX1 sets the arbitrary absolute amplitude/phase reference. No absolute RCS calibration is performed.

Apply the saved config to hold-out angle sweeps and report angular bias/RMS, invalid-angle fraction, gain balance and temperature drift. Use several range bins to test frequency-dependent phase offsets; the current calibration is one complex factor per RX, not a frequency-dependent correction. Recalibrate after mounting, gain/waveform or temperature changes. Keep the exact calibration ID in each session. Set `verified=true` manually only after completing the preceding checks and documenting their results.

## 4. Material measurement readiness

Record empty background, metal reflector and a stationary opaque panel before glass. Verify repeatable unsaturated amplitudes with all gains fixed. ADC counts are not calibrated reflection coefficients. A visible object and a second late peak do not establish glass or multipath respectively. Start the matched experiment protocol in `GLASS_RESEARCH.md` only when acquisition and calibration uncertainties are documented.
