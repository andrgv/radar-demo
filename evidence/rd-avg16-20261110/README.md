# Stationary AVG16 capture review

Source: `recordings/avg16-timing-01`, profile `0x33515403`. The user flashed the
AVG16 test image and followed the ordinary stationary-scene protocol; the exact
reflector layout is unspecified.

[Timing and phase figure](timing-and-phase.png) · [Numeric report](summary.json)

All 201 saved frames have valid packet CRCs and headers, continuous sequence
numbers, zero device errors/drops, and complete edge logs. Every frame contains
exactly **272 rising edges in 17 groups of 16**, with no buffer overflow. This
matches the vendor profile's 17 AVG16 outputs. Group starts span a median
504.75 nominal MCU microseconds per group when measured across all 16 group
intervals. Individual GPIO ISR start-to-start intervals range 501–508 µs;
interrupt latency and MCU clock accuracy remain limits on physical timing.
The median acquisition path is 8,812 µs.

After discarding the first saved block, stationary phase is very consistent
across the remaining 16 blocks. At fixed range bin 2, median adjacent-phase
resultants by RX are approximately 0.99995, 0.99995, and 0.99998. Its median
phase steps stay close to zero through the final block pair; the large final
boundary step in the earlier AVG1 moving-target recording is not present in
this stationary AVG16 capture. Stationary data alone does not prove coherence
under motion, which reflectors dominate, or exact group-to-block alignment.

The host reports one `clock_fit_unstable` rejection at the final frame, when
the 20-second startup clock fit is attempted. That is a host arrival-time
quality failure, not a packet or onboard edge-timing failure. The raw frame
and its edge log are preserved. The original wire log also ends with a partial
packet at capture stop; the saved `frames.grd` contains only complete frames.
Do not relax the clock gate to make this recording pass.

If each saved AVG16 block corresponds to one group and the illustrative 60 GHz
carrier is correct, this schedule would give about **0.31 m/s native 16-block
velocity-bin spacing** and approximately **±2.47 m/s unambiguous radial speed**.
These are conditional model values, not calibrated velocities or guaranteed
two-object resolution. Hann windowing broadens peaks, and a stronger wall may
still mask a nearby slow target.

The next useful capture is controlled target motion with this same image and
config; no additional firmware change is needed. See the
[motion protocol](../../docs/AVG16_TIMING_TEST.md#next-capture-controlled-motion).
Keep stationary returns in the full map, preserve the raw stream, and retain
timing-unverified labels until direction-dependent phase and Doppler response
are demonstrated.

Reproduce the report and figure:

```sh
MPLCONFIGDIR=/private/tmp/mpl-radar .venv/bin/python -m tools.review_avg16_timing
```
