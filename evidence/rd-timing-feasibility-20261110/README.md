# Timing feasibility checkpoint — November 10, 2026

The source/register [timing trace](../../artifacts/qualification/timing-trace.json)
was regenerated. It supports nominal 5 MHz ADC sampling, a 12.8 μs 64-sample
window, and 100 ms MCU frame scheduling. It still does not decode the 42-word
radar sequencer into chirp start times or establish carrier frequency.

The prepared HPF350 scope variant compiled successfully with ModusToolbox 3.9 on
this Mac. Its HEX is
`../../build/scope-timing/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex`,
profile ID `0x33515301`, SHA-256
`a48ed6f40e42b627c037c10321baab1c89ef53d96ed4ca0e5649399847b3a5d5`.
The build used `RADAR_QUALIFICATION=1 RADAR_HPF_KHZ=350 RADAR_SCOPE_OUTPUT=1`;
the compile response file confirms these flags. At the time of this initial
audit, the image had not been flashed and no board or scope was connected.

After the audit, the user connected the board. KitProg3 serial
`170D0E8300023400` identified a `CY8C624AFNI-S2D43` with normal chip protection.
A read-only OpenOCD `verify_image` comparison of
`artifacts/hpf-pair-2/hpf350/glass-radar-3rx.hex` against board flash succeeded:
**47,100 programmed bytes verified**. The archived image hash is
`a68e0646857d76d1511be8a5ec9ba2c8130a7d3ff897966afd6e391073163897`.
OpenOCD briefly halted and resumed the CM4; it did not program or erase flash.
This establishes the current programmed application bytes at all addresses in
that HEX, rather than inferring exact identity from the profile ID. It does not
compare unused flash addresses. The user subsequently flashed the scope image.

The new `recordings/scope-timing-01` has 201 valid frames with profile
`0x33515301`, no CRC/header errors or sequence gaps, and acquisition-path
elapsed time at 3,464 µs for the 5th, median and 95th percentiles. The scene
was unspecified, which is acceptable for the timing measurement. No
CHIRP_ACTIVE scope waveform or rising-edge times are present in the workspace
yet. The serial capture has no per-chirp timestamps, so it cannot establish
chirp period on its own. A new raw capture should overlap an external trace
or a validated MCU edge-timestamp capture; use a new recording directory.

The two November 10 recordings contain 17 acquired and 16 retained chirps per
frame. Their MCU acquisition-path elapsed fields run from about 3,461 to
3,472 μs. This is the complete trigger/FIFO/readout/stop path. **Conditional
bound:** if all 16 retained blocks are consecutive, uniformly spaced radar
chirps inside this window, their 15 start-to-start intervals each cannot exceed
3,472/15 = **231.5 μs**. The true spacing could be much shorter. This bound
does not establish uniformity, same-waveform timing, raw-block/edge alignment or
phase coherence. It is not a period estimate obtained by dividing the path time.

The native 16-chirp Doppler grid is 1/16 = 0.0625 cycles/chirp. At an
**illustrative, unverified** 60 GHz carrier, the conditional 231.5 μs bound
implies at least **0.675 m/s** nominal velocity-bin spacing. At 100 μs spacing,
it would be about **1.56 m/s**; at 50 μs, about **3.12 m/s**. Hann windowing
broadens peaks. This grid limit does not prohibit estimating a small isolated
phase slope, but it cautions against expecting 2D CFAR to resolve a slow small
obstacle from a strong zero-Doppler wall in the current burst. The previous
recordings' zero-bin peaks are consistent with that concern; the physical cause
remains unverified.

The 1 ms chirp interval in legacy broad-pipeline configurations cannot be
treated as measured. Under the stated sequential/uniform conditions it would
not fit the observed acquisition window. Do not convert current Doppler axes to
m/s or change a velocity verification flag based on this bound.

Next timing measurement: save sensor CHIRP_ACTIVE rising-edge times for multiple
bursts along with a matching raw recording. The
[scope procedure](../../docs/SCOPE_TIMING.md) is one method. Without a scope,
a separate MCU GPIO interrupt timestamp diagnostic can use the signal already
routed to GPIO10, provided its timing and interrupt latency are validated. This
diagnostic is now implemented and built but has not been flashed or tested on
the board; see [MCU capture procedure](../../docs/MCU_EDGE_TIMING.md). Device
data-sheet clock and RF limits do not specify the modified firmware's chirp
start times. The host's
1 ms chirp interval is a placeholder, not vendor metadata.
`tools/analyze_chirp_edges.py` accepts `burst_id,time_us` CSV exports and reports
within-burst spacing/deviation without joining restarted bursts. Also confirm
which markers match the 16 saved chirps and that their waveform/sample phase is
consistent. Only then calculate physical velocity resolution and decide whether
a longer coherent burst is needed. A scope marker alone does not prove the
raw chirps are coherent.

[Machine-readable capture bounds](feasibility.json) include raw/input/source and
HEX hashes. Reproduce the bound with:

```sh
.venv/bin/python -m tools.assess_rd_timing_feasibility
```
