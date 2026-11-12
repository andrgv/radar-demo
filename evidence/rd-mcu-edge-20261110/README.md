# MCU chirp-edge capture review: `edge-timing-02`

Source: `recordings/edge-timing-02`, profile `0x33515401`, protocol version 2.
The 20-second capture contains 201 accepted frames, no device sequence gaps,
header errors, or CRC errors. The wire log ends with a partial packet because
capture stopped; the 201 complete frames remain intact. The frame acquisition
path is 3,529–3,594 nominal MCU timer microseconds, with median 3,529.

All **201/201 frames report exactly 112 CHIRP_ACTIVE rising edges**. All frames
set the overflow flag because this first firmware version stored only the first
64 timestamps. The stored prefix has four groups of 16 edges. Median gaps
between groups, after edges 16, 32, and 48, are 239, 241, and 233 MCU timer
microseconds. Within-group observed adjacent intervals range from 6 to 30
microseconds, with a median of 17. The pattern is nearly identical frame to
frame. This short-interval variation is too large to treat individual GPIO ISR
timestamps as precise radar chirp starts without investigating interrupt delay.
The [exported prefix CSV](chirp-edges-prefix.csv) is marked `partial` by burst.

The 112:17 edge-to-ADC-block mismatch is the main result. A CHIRP_ACTIVE edge
cannot yet be assigned to each of the 17 saved raw blocks. The 16 saved
slow-time samples after discarding the first block therefore do **not** have a
verified uniform sampling schedule. The current range–Doppler map remains a
diagnostic in cycles per saved block; its frequency axis must not be converted
to m/s from these edges. The stationary raw profiles have similar shape and
phase, but this does not establish edge/block correspondence or coherence under
motion. We also cannot infer which edge groups were missed by the 64-slot log.

The revised [128-edge diagnostic](../../docs/MCU_EDGE_TIMING.md) has profile
`0x33515402` and protocol version 3. The user subsequently flashed it and
recorded `recordings/edge-timing-03`.

## Complete capture: `edge-timing-03`

The new 20-second capture has 201 accepted frames, no CRC/header errors,
sequence gaps, or device rejects. The saved frame file parses to completion.
All **201/201 frames contain 112 ordered rising-edge timestamps**, and none
overflow. They form **seven groups of 16**. The six inter-group gaps have
median durations of 239, 241, 233, 238, 239, and 234 nominal MCU microseconds.
Group starts recur at about 503–506 microseconds. Within-group measured
intervals have a median of 17 microseconds and range from 6 to 30; GPIO ISR
delay is a plausible contributor, so these individual intervals are not a
validated RF chirp period. The final edge occurs at a median 3,459 microseconds
after the acquisition start, about 77 microseconds before the acquisition path
completes. The [full edge CSV](chirp-edges-full.csv) preserves every timestamp.

The vendor-generated profile declares 17 SEQ0 output chirps with AVG16. The
current firmware overrides `AVG_CTRL_SEQ0` to AVG1 and drains only 17 raw blocks
before stopping the sequencer. One possible explanation is that the MCU reads
the earliest FIFO blocks while the radar continues to emit later chirps during
the slower SPI drain. That would put a long group gap between the 16th and 17th
saved blocks, but the capture does **not** directly timestamp when each FIFO
block was produced or prove FIFO-to-edge ordering. The stationary raw blocks
show small extra phase shifts at transitions 0→1 and 15→16 compared with most
adjacent blocks, consistent with but not proof of a group boundary.

An independent cross-check uses the earlier wheeled-target recording
`recordings/gui-20261110-162410-575208/live-002`, which used the same AVG1 raw
acquisition but did not log edges. At range bin 2, the median adjacent complex
phase step across all three RX channels in the predeclared middle-half phase
windows is:

| Phase | Saved frames | Interior pairs 1→2 through 14→15, median | Pair 15→16 |
|---|---:|---:|---:|
| Initial wall | 102 | -0.0005 rad | -0.0049 rad |
| Approach 1 | 48 | -0.0058 rad | -0.0535 rad |
| Retreat 1 | 29 | +0.0067 rad | +0.0692 rad |
| Approach 2 | 27 | -0.0068 rad | -0.0652 rad |
| Retreat 2 | 34 | +0.0076 rad | +0.0706 rad |

These values use the user-provided stopwatch windows, not fitted timing. The
approximately tenfold boundary phase step and its motion-dependent sign support
the hypothesis that saved block 16 follows the first 16-edge group after a long
gap. Mixed wall/target returns, variable speed and unknown FIFO ordering still
prevent treating this as a direct mapping proof.

The present 16-block FFT should therefore remain a diagnostic only. Before
building a velocity detector, establish FIFO block timing/order or run a
separately identified test with the vendor AVG16 setting and full-burst capture.
Then test stationary and controlled moving targets for phase coherence and
useful velocity separation. No physical velocity scale or Doppler resolution is
validated by these stationary timing captures.

The separately identified [AVG16 test image](../../docs/AVG16_TIMING_TEST.md)
was subsequently flashed and captured. The
[AVG16 review](../rd-avg16-20261110/README.md) found the expected 272 edges and
consistent stationary phase, supporting a controlled motion test. The image
logs up to 320 edges and verifies the vendor averaging register at startup.
