# Joint GUI startup timing rejection

Recording: `recordings/rd-gui-20261111-132433-610820/live-001`.
The original `clock_fit_unstable` decision reproduces exactly using the saved
monotonic host/device elapsed times and unchanged clock policy.

- 358 saved frames; zero CRC errors, sequence gaps or bad headers.
- At sequence 2774 / device elapsed 20 s, startup fit p95 absolute residual is
  **50.620 ms**, exceeding the **50 ms** limit by 0.620 ms.
- Maximum fit residual is 75.380 ms, within its separate 100 ms limit.
- Candidate host/device rate is 0.993877, within the permitted ±2% interval.
- The first 200 frames are accepted; the remaining 158 are rejected because
  clock failure latches. Raw capture continues, so complete saved ADC frames
  remain available for offline processing. That does not establish original
  live freshness. A 4,989-byte incomplete tail at stop is recorded separately.

## Display workload and change

Before changing the GUI, an offscreen replay benchmark on frames 10–39 measured
redraw p50/p95/max of 239.49/264.28/274.79 ms. The GUI requested redraws at 10 Hz
and scheduled both the visible comparison canvas and hidden RD canvas, while
rebuilding three axes and legends on each comparison update. Acquisition and
GUI share a process and GIL. This is substantial avoidable contention, although
the capture alone cannot prove it is the exclusive cause of arrival jitter.

After the change, the same replay-only benchmark measures p50/p95/max of
77.74/93.83/94.19 ms. Comparison axes/lines/legends are reused, only the active
tab redraws, and plot/table refresh is capped at 4 Hz. Freshness polling stays
at 10 Hz, and rejected/stale snapshots bypass the cap to clear immediately.
Repeated invalid frames do not continuously rebuild blank plots.

Both detection algorithms, per-frame processing/recording, and all timing
limits remain unchanged. New `clock_sync.fit_diagnostics` telemetry records the
candidate fit's rate/offset and actual p95/max residuals and limits, including
failed fits. The GUI explains the rejection and the need to restart capture.
The original recording remains rejected; no gate was relaxed to make it pass.

## Verification and hardware retry

Tests cover active-tab-only rendering, the redraw cap with immediate rejection
and stale clearing, preserved clock limits, and fit diagnostics. Existing
clock skew, excessive jitter, delay/backlog, recording and GUI tests remain.
The benchmark is rendering workload, not sensor-to-screen latency or a live
hardware success test.

Close and relaunch the updated `rd-gui`, then collect an ordinary stationary
scene for about 60 seconds. No scene choreography, firmware change, calibration
or threshold adjustment is needed. Check that host clock transitions from
collecting to frozen after about 20 seconds and stays frozen through the run.
If it rejects again, retain the full directory; new telemetry will expose the
failed fit directly. Do not loosen timing gates to bypass it.

[Exact diagnostic metrics, source/input hashes and current benchmark](report.json) ·
[Recorded relative timing](timing.png) · [Cleared rejection display](rejected.png)

Reproduce into a new output directory:

```sh
QT_QPA_PLATFORM=offscreen MPLCONFIGDIR=/private/tmp/radar-mpl \
  .venv/bin/python -m tools.diagnose_joint_timing \
  --output evidence/NEW-TIMING-REVIEW --benchmark-gui
```

The benchmark never opens serial. The before-change numbers above were measured
before editing the GUI in this investigation; the tool benchmarks current code.
