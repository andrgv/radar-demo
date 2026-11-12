# 3D obstacle implementation and replay evidence

User approved the revised 3D host-side approach and requested other recordings
also be used for testing and research. No board was accessed or flashed.
The implementation is experimental; the full glass-anywhere goal is unverified.

## What was run

```
python -m tools.evaluate_obstacle3d recordings /tmp/glass-material-analysis-20261109/recordings --output artifacts/obstacle3d-evaluation-04
```

The supplemental root was restored using the checksum-verifying archive script.
The complete frozen-setting inventory and per-recording scores are in
`summary.json`. Per-window outputs and reports are under the artifact directory
above. This is not training or a blind held-out study; prior analyses inspected
these recordings. All 109 sufficiently long, integrity-checked recordings have
distinct raw SHA-256 hashes, but that does not make recordings or windows from
the same setup statistically independent.

- 119 raw folders considered, 22,492 frames processed.
- 109 recordings contain full valid windows with no detected continuity faults.
- 10 empty/too-short recordings are explicitly incomplete/rejected.
- Incomplete door05 and door06 experiments are listed separately as exclusions.
- Additional data include both distance sweeps, 350/100/350 kHz captures, nested
  GUI captures, target/reference captures and archived window/drywall tests.
- Corrected archived material labels supersede the inaccurate original OPEN/CLOSED
  notes. Unknown wall distance is not replaced with the window distance.
- No surveyed angular ground truth exists in these datasets. Hardware XYZ accuracy
  is not measured. Coherent background/multipath can still yield a plausible fit.

At +/- .25 nominal native bins around the surveyed pane location:

| Setup | Closed persistent candidate / provisional XYZ windows | Open persistent candidate / provisional XYZ windows |
|---|---|---|
| door03 | 84 / 0 of 90 | 0 / 0 of 90 |
| door04 | 0 / 0 of 90 | 0 / 0 of 90 |
| door07 | 84 / 28 of 90 | 83 / 0 of 90 |

Door03's weak RX2 response is now retained as an unresolved warning rather than
lost through averaging or converted to invented XYZ. Door04 has candidates within
one native bin in 84/90 windows in both states, but this looser match cannot fix
its range bias or establish pane attribution. Door07's open detections may be real
background obstacles. No open control is a certified empty/clear-path scene.

Settings are identical across inputs: 1 s windows, 3-window persistence, 6 dB
contrast, 8x FFT interpolation, .25-bin association, .9 coherence and .65 array
energy fit; XYZ additionally requires corresponding peaks on all three RXs and
an interior angular maximum. Output material is unknown. Default initial
persistence delay is approximately 3 s and is not a validated collision latency.

The largest per-recording p95 DSP push time in this run was 9.35 ms on this host.
This measures CPU processing, not end-to-end USB freshness or detection latency.

## Verification

`focused-tests.txt`: 25 related tests pass, covering known synthetic directions,
complex channel/array correction, stationary/moving returns, weak RX-only signals,
incoherent direction rejection, no stale detection hold, continuity/restart/rails,
replay/live parity, raw preservation on timeout/unplug, incomplete input, existing
point clouds/spatial processing, and GUI/export agreement. A subsequent GUI test
also passed after adding a display stale-result timeout.

`full-suite.txt`: 144 tests run; 141 pass, 1 skips, and 2 error because this checkout
lacks the external `mtb_shared/.../xensiv_bgt60cutrxxb_register_hal.h` header. These
are `test_model_audit.test_register_profile_reveals_highpass_corner` and
`test_qualification.test_scope_mux_preserves_spi_and_io_voltage_fields`. Their
firmware-source requirements remain unverified; the tests were not edited or
silently skipped to produce a green result. The test runner's unrelated generated
qualification manifest path change was restored.

The actual new CLI GUI mode was run offscreen with replay and automatic duration
exit. `artifacts/obstacle3d-display/door04.png` shows the new view with provisional
points and separate unresolved warnings; this verifies rendering, not target
location. The existing live GUI and material classifier remain separate modes.

## Remaining requirements

Independent pane-present/absent association with stable frame/background,
known left/right/up targets for angular calibration and blind validation,
new glass/angles/backgrounds, and fresh USB hardware tests. Moving-board operation
needs pose/motion testing and shorter validated latency. The user has no hardware
available now. Neither a numerical XYZ output nor a candidate near a labeled
range establishes reliable 3D glass-obstacle detection.

See `docs/OBSTACLE_3D.md` for run commands, output fields and method limits.
