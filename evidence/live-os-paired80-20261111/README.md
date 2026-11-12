# Live CA/OS paired 80 cm placements, operator B

Recording: `recordings/rd-gui-20261111-135229-775366/live-001`.
Both placements have continuous current distance output and the quiet empty
intervals have no CA, OS or selected OS output. CA and OS fine values are
identical in each scored target interval. This is a successful live check and
repeat-placement example, not evidence of OS superiority or general accuracy.

## Labels

Supplied durations are consecutive from the first saved frame:

- Initial handling: 0–5.53 s.
- Empty: 5.53–26.49 s.
- Placement handling: 26.49–44.38 s.
- First 80 cm hold: 44.38–75.11 s.
- Removal handling: 75.11–84.05 s.
- Empty: 84.05–104.64 s.
- Placement handling: 104.64–116.80 s.
- Second 80 cm hold: 116.80–147.61 s.

The recording extends to 153.397 host seconds. Its last 5.787 s is unlabeled and
excluded from scene scoring. Operator B is the supplied quiet-hold position.
No video offset was fitted. Two-second quiet-interior trims are primary;
one-second summaries are also included and give the same qualitative result.

## Two-second-trimmed results

| Interval | Frames | CA numeric | OS numeric | Unique-RD-support OS selection | Median cm | 5th–95th cm |
|---|---:|---:|---:|---:|---:|---:|
| Initial empty | 171 | 0 | 0 | 0 | — | — |
| First 80 cm hold | 269 | 269 | 269 | 269 | 81.53 | 81.26–81.77 |
| Second empty | 167 | 0 | 0 | 0 | — | — |
| Second 80 cm hold | 270 | 270 | 270 | 270 | 82.84 | 82.35–82.96 |

The two placements differ by about 1.30 cm in median output. The difference
from nominal is approximately +1.53/+2.84 cm, conditional on these placements
and their outputs; it is not independent calibrated reflector-identity error.

Median native bin-2 power rises from approximately 41 dB in the empty intervals
to 65 dB with the target present, about 24 dB higher. CA median bin-2 margins
are +1.09 and +0.74 dB in the holds: stable enough here, but still modest
threshold headroom. Compared with the previous failed ~80 cm capture, near
power is stronger and the reference threshold is lower. The physical cause of
the scene/placement difference was not isolated, so do not attribute this solely
to operator B or to the new reference method.

RD also confirms a close bin-1 feature throughout both empty interiors, but
neither CA nor OS promotes it in this scene. That feature was admitted by OS
in the earlier live-005 control. This successful example does not erase that
known failure or justify changing the default primary.

## Timing and implementation parity

All 1,545 frames are accepted, with zero timing rejections, CRC errors, sequence
gaps or bad headers. The clock collects for 200 frames and freezes for the
remaining 1,345. Startup fit p95/max residuals are 2.20/14.72 ms. After freezing,
p95/max relative errors are 7.43/15.68 ms. All timing limits remain unchanged.
A 549-byte incomplete tail at stop is recorded separately.

Every saved CA and OS presence/bin/fine-range/reason result matches independent
replay. Every saved OS selection matches recomputation using its current saved
RD local maxima. No detector, firmware or threshold change was made for this
review. No repeat of this live-check protocol is needed.

[Timeline and threshold margins](comparison.png) · [Metrics and hashes](report.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_live_clutter \
  --manifest configs/live-os-paired80-20261111.json \
  --output evidence/NEW-LIVE-OS-REVIEW
```
