# First GUI stationary validation

Capture order inferred from the requested protocol and user's “done”: live-003
empty, live-004 stationary 30 cm, live-005 stationary 50 cm. These labels are user
measurements, not synchronized external ground truth. Original recordings retained.

| Scene | Accepted / total | Accepted median | Accepted mean absolute error |
|---|---:|---:|---:|
| Empty | 1 / 208 | 117.0 cm (false detection) | not applicable |
| 30 cm | 133 / 207 | 15.8 cm | 12.10 cm |
| 50 cm | 141 / 206 | 49.95 cm | 16.94 cm |

Only 2/133 accepted 30 cm estimates and 91/141 accepted 50 cm estimates were
within 2 cm. These conditional counts exclude misses; across all captured frames,
accepted-and-within-2-cm counts are 2/207 and 91/206 respectively.
58 accepted 30 cm estimates hit the 15 cm search boundary. That boundary belongs
to the software search and does not establish a physical sensor minimum range.
34 accepted 50 cm estimates exceeded 75 cm, reaching 131.1 cm. A good median
therefore does not establish reliable individual readings. No smoothing applied.

All 621 complete frames replayed successfully. Presence decisions and fitted
ranges match live logs (range tolerance 1e-8 m). Zero timing rejections, CRC errors,
gaps, restarts or bad headers. The final run stopped with 6562 partial bytes;
these remain preserved in serial-wire.bin and are not a complete extra frame.
The other runs each retained one partial byte. No recordings or thresholds changed.

The presence gate does not validate the separately fitted range. Next analysis
should compare per-RX fit objectives, residual spectra and background dependence
on these failure frames before changing acceptance criteria. Do not train a
30–50 cm clamp or threshold on these evaluation labels and claim validation.
Further physical captures are not needed to reproduce the present failures.

Reproduce from repository root:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m evidence.gui-static-1.analyze
```

`report.json` includes raw hashes and counts; `analyze.py` verifies raw replay.
