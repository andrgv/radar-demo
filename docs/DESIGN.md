# Acquisition and processing design

## Firmware

This is a fresh bare-metal HAL application, not a modified copy of demo `main.c`. It uses the pre-existing official BSP and Infineon's radar platform/driver. The RF setup and sequencer are the **unmodified** official `presence_detection_tracking.h` at Infineon example commit `f6e9c82b28d0022790b0905201e1d6720615063d` (file blob `69c83f6006d4cfabe1d055b99d6940ae0d213d68`). The original notice is retained in that file. Its three RX enables are read back during startup.

After the official initialization and ADC calibration, firmware stops the sequencer and overrides `AVG_CTRL_SEQ0=0` (averaging factor 1) and `FIFO_CTRL=191<<16` (192 32-bit words, no embedded FIFO headers). The host receives **unaveraged ADC words**, not on-chip range FFT or motion outputs. This deliberately changes the original profile's averaging factor 16. Consequently, its published output-chirp timing cannot be reused without checking the raw sequencer timing.

Every capture resets FSM/FIFO, clears IRQ flags, triggers sequence 0, drains available FIFO words in chunks of at most 192 words, and stops after 17 × 64 × 3 samples. This is a bounded window of the running official sequencer, not a claim that an entire original 17-averaged-chirp sequence has finished. Excess samples after the window are discarded by the next FIFO reset. The first stored chirp is excluded from DSP by default to allow settling; verify whether more are needed. There is no stitching across restarts. Hardware tests must prove the first raw word starts RX1/sample0, and that the next 16 chirps are uniformly spaced and share one waveform. If the sequencer includes startup/dummy chirps in this window, adjust the acquisition sequence and metadata before using Doppler.

FIFO underflow/overflow, SPI/register failure, or a 200 ms capture timeout rejects the entire frame. No partially filled frame is transmitted. IRQ/FIFO status is polled, so missing an IRQ edge does not hide data. The polling loop must be timed on hardware; its timeout does not interrupt a stalled blocking operation inside the vendor SPI driver. The driver supports FIFO reads in 32-bit entries (two 16-bit samples); MCU packet storage is 32-bit aligned. Do not infer FIFO SRAM capacity from the threshold or blindly enlarge a frame to its capacity.

Two static packet buffers remain valid during asynchronous UART transmission. A new capture is admitted only if the UART has finished the prior packet. The nominal schedule is 10 Hz. A busy transmitter skips the scheduled capture, increments the sequence and drop counters, and avoids overwrite. This initial implementation serializes acquisition and transmission for deterministic bring-up, leaving deliberate dead time between bursts. It is not gapless continuous ADC acquisition. Payload is 6,528 bytes; header+CRC adds 52 bytes. At 2 Mbaud 8N1, 6,580 bytes require about **32.9 ms**; 10 Hz uses **65,800 bytes/s**, below the 200,000 bytes/s UART ceiling. Acquisition time adds to the 32.9 ms; measure it before raising the rate. UART errors increment device counters. There is no automatic retransmission or claim of lossless USB delivery.

Initialization return codes 1–9 identify BSP, UART, timer, shield, SPI open, radar initialization, runtime override, and RX readback failures in a debugger. The binary port never carries printf output. Successful initialization stays idle until command `0x42`; `0x63` stops scheduling. Commands received while a capture is active take effect afterward, with a capture deadline of 200 ms. A disconnect does not automatically stop firmware because the UART bridge provides no host-presence handshake.

## Binary wire protocol v1

All fields and ADC words are little endian. CRC32 is reflected IEEE (`0xedb88320`, initial/final XOR `0xffffffff`), identical to Python `zlib.crc32`.

| Offset | Type | Meaning |
|---:|---|---|
| 0 | 4 bytes | ASCII `GRD3` |
| 4 | u16 | Version = 1 |
| 6 | u16 | Header size = 48 |
| 8 | u32 | Payload byte count = 6528 |
| 12 | u32 | Attempted capture sequence, including skipped/failed captures |
| 16 | u32 | Trigger timestamp, microsecond counter modulo 2³² |
| 20 | u32 | Acquisition profile ID `0x33525801` |
| 24 | u16 | Chirps = 17 |
| 26 | u16 | Samples per chirp per RX = 64 |
| 28 | u8 | RX count = 3 |
| 29 | u8 | Container bits = 16 |
| 30 | u16 | Flags, bit 0 = unaveraged ADC |
| 32 | u32 | Cumulative device skipped/failed capture count |
| 36 | u32 | Cumulative device acquisition/UART error count |
| 40 | u32 | Reserved = 0 |
| 44 | u32 | CRC32 of header bytes 0–43 |
| 48 | u16[] | ADC in `[chirp][sample][RX1,RX2,RX3]` order |
| 6576 | u32 | CRC32 of header and payload |

Profile ID must change with layout/waveform changes; the current ID alone does not encode or verify RF/timing settings. This is a fixed-profile firmware, with physical parameters stored in an explicit host configuration. Verify register overrides and generated configuration together. A self-describing configuration handshake is a future improvement.

The parser first validates header CRC, version, dimensions and bounded length, then waits for and validates the complete packet. It slides forward to the next magic after corruption, keeps partial headers across arbitrary serial read boundaries, and rejects bad payloads. It counts forward sequence gaps modulo 2³² and detects duplicates/restarts. A device reset and an out-of-order sequence both increment `restarts`; exact reset diagnosis is not possible without a boot ID. Timestamps wrap every 71.6 minutes and are not UTC; recordings retain host Unix arrival times separately. Temporal feature state resets on sequence discontinuity.

## DSP and coordinates

ADC shape is `(chirps, samples, 3)`. Per-chirp fast-time mean removal suppresses DC without subtracting stationary objects across slow time. A Hann range window precedes the real FFT; coefficients are normalized by `2/sum(window)`, then complex per-channel corrections are applied. Range is `beat_frequency*c/(2*slope)+offset`. The Nyquist/DC normalization is not used for detection. Low range bins 0/1 and the final bin are excluded.

A second Hann window precedes the slow-time complex FFT. Radial velocity is `doppler_frequency*c/(2*carrier)`. The full range–Doppler image retains zero Doppler. Detection also uses a slow-time mean-subtracted path for moving objects. The stationary path uses coherent mean channel amplitudes and the moving path uses the strongest noncentral Doppler return at each range peak. A local median reference with two guard bins and up to ten reference bins per side supplies an adjustable SNR threshold; it is **not a statistically calibrated CFAR false-alarm probability**. A stationary candidate must exceed 10% of the moving peak power to suppress finite-burst leakage. Very slow movers within ±1 Doppler bin, weak stationary returns beside strong movers, and multiple movers at one range are limitations of this baseline.

`geometry_wavelengths` gives each RX's right/up phase-center coordinate in carrier wavelengths, in actual FIFO order. The two relative phases to RX1 solve `phase=2*pi*baseline*direction` for right/up direction cosines; forward is the positive square root. Azimuth is `atan2(right,forward)` and elevation is `asin(up)`. Points outside the unit direction disk are marked invalid. There is no two-way factor in receive-baseline AoA. This convention assumes incoming FFT phase matches the positive simulated steering convention; confirm polarity experimentally. Configure half-wavelength-or-shorter independent baselines for unambiguous principal-phase operation. Longer baselines require a phase-unwrapping/array-search method not implemented here. Rear-hemisphere ambiguity is resolved by assuming targets in front of the board.

Three receivers provide two phase baselines, not a dense imaging array. Unresolved coherent reflectors/multipath bias phase estimates, and many objects cannot be resolved in one range–Doppler cell. The heatmap is conventional beam power on the elevation-zero slice, not an independent high-resolution image or an elevation marginal. The 3D viewer shows only angle-valid detections; unverified axes are prominently marked. Calibration does not fix insufficient aperture.

## Storage and future fusion

Sessions contain `frames.grd` (validated raw frames re-encoded without changing sample values or counters), `arrivals.jsonl` (host arrival timestamps), `config.json`, `metadata.json`, and `features.jsonl`. This preserves ADC for revised processing, not the corrupted bytes discarded by the serial parser. GUI counters expose those transport errors. Files flush every ten frames and on close; power loss can truncate the final packet. Replay recovers complete preceding packets and ignores an incomplete tail. Recording does not overwrite existing sessions.

`Frame`, `Result`, and `Detection` are independent of Qt and contain device timestamps and frame IDs; `export_detections` provides a structured radar-frame interface for later fusion. Future camera support should attach calibrated extrinsics and a synchronized host/device clock mapping without changing raw ADC files. No fusion dependencies are imported now. Current timestamps are insufficient for precise camera synchronization without further clock alignment.
