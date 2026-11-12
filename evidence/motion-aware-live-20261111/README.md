# Live motion-aware 120↔50 cm review

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Recording: `recordings/rd-gui-20261111-141606-847532/live-002`.
All 682 saved 1D and motion-policy decisions reproduce independently;
standalone RD masks and association match. No settings changed in this review.

## Timing and labels

Supplied absolute times start at the first saved frame: initial 120 cm hold;
approach 11.56–13.58; near hold to 25.06; retreat 25.06–27.02; far hold to 38.47;
approach 38.47–42.15; near hold to 53.30; retreat 53.30–56.61; far hold to end
at approximately 67.66 s. Motion windows trim 0.2 seconds per side and holds
two seconds. No offset was fitted. Operator geometry and exact trajectory are
not supplied; physical reflector identity remains unverified.

Zero timing rejections, CRC errors, sequence gaps or bad headers occurred.
The clock froze after the first 200 frames. Startup p95/max fit residual is
2.18/14.30 ms; post-freeze p95/max relative residual is 2.40/11.98 ms. One
trailing byte at stop is recorded separately.

## Moving-frame coverage

| Movement | Frames | Baseline | Motion-aware |
|---|---:|---:|---:|
| First approach | 16 | 5 | 15 |
| First retreat | 15 | 8 | 8 |
| Second approach | 33 | 7 | 21 |
| Second retreat | 29 | 12 | 19 |
| Total | 93 | 32 | 63 |

First approach has one ambiguous frame. First retreat withholds two ambiguous,
two competing-mover, one lost, one motion-confirmation and one boundary-fit
frame. Selected ID 13 fragments into ID 23 during retreat; no active episode
survives into the middle far hold, which uses the baseline.

Second approach has nine no-episode/no-baseline frames, two motion-confirmation
frames and one miss. Second retreat has eight ambiguous frames, one miss and
one lost frame; ID 31 does not survive to supply the final far hold. The policy
does not predict or substitute another reflector while an episode is active.
Numeric coverage is not correct-target accuracy; current zero-Doppler points
near start/stop can contribute to the motion-window count.

## Stationary holds

| Hold | Baseline / frames | Motion-aware / frames | Median cm | 5th–95th cm |
|---|---:|---:|---:|---:|
| Initial 120 cm | 0/76 | 0/76 | — | — |
| First 50 cm | 76/76 | 76/76 | 63.99 | 61.50–67.47 |
| Middle 120 cm | 46/75 | 46/75 | 123.80 | 120.82–126.96 |
| Second 50 cm | 61/72 | 72/72 | 36.75 | 35.54–38.73 |
| Final 120 cm | 71/71 | 71/71 | 147.30 | 144.55–149.71 |

The first and second near holds continue IDs 13 and 31 respectively. Initial
120 cm stays blank because no baseline distance exists and stationary RD-only
features cannot seed motion. Middle/final far holds revert to baseline after
feature loss. Identical nominal placements still produce different distances;
more complete output has not established correct identity or calibrated range.
Smoothing or a constant offset would not resolve those differences.

## Next work

Preserve this live check and prior controls. Focus the next software review on
retreat association fragmentation/ambiguity and the spectral peaks supplying
biased holds. Do not broaden gates or hold missing values merely to increase
coverage. No repeat is needed to establish these failures.

[Comparison timeline](motion-comparison.png) ·
[Stage counts, reasons, IDs and timing](motion-review.json) · [Replay audit](report.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --recordings recordings/rd-gui-20261111-141606-847532/live-002 \
  --output evidence/NEW-LIVE-MOTION-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_motion_range \
  --output evidence/NEW-LIVE-MOTION-REVIEW --manifest configs/motion-aware-live-20261111.json
```
