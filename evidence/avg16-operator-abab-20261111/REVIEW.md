# Fixed-target operator A/B control

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

With the target left at nominal 50 cm, all four labeled quiet holds retain a
confirmed fine-distance output on every scored frame. The large dropout effect
in live-003 is not reproduced. Operator position still changes the CFAR reference
level, but this placement has enough headroom to remain detected in both states.
No settings, firmware or detector changes were made.

## Windows and results

Durations are interpreted consecutively from the first saved frame:
A1 0–17.01 s, B1 21.85–38.69 s, A2 45.85–62.36 s, B2 67.27–83.91 s.
Walking intervals are excluded; the table trims two further seconds per side.
One-second trims also have complete coverage and similar distances. The
recording spans 93.748 s; the final 9.838 s has no supplied label and is excluded.

| Position | Numeric / frames | Median cm | 5th–95th cm | Median bin-1 margin |
|---|---:|---:|---:|---:|
| A1, beside sensor | 131/131 | 47.22 | 46.04–49.21 | +1.31 dB |
| B1, described as out of range | 129/129 | 46.92 | 46.46–47.09 | +2.93 dB |
| A2, beside sensor | 126/126 | 46.79 | 45.42–48.53 | +1.83 dB |
| B2, described as out of range | 127/127 | 46.75 | 46.63–46.86 | +2.98 dB |

All 513 primary interior frames select native bin 1 and resolve fine range.
Position B has a narrower distance spread; both A intervals show more variation.
Median distances are about 3 cm below nominal in this placement. This is not
an independent calibrated accuracy claim or proof of reflector identity.

Median bin-1 power remains 62.30–62.34 dB across all four intervals. Thresholds
are 61.07/59.37/60.52/59.31 dB for A1/B1/A2/B2. Thus A raises the threshold by
approximately 1.2–1.7 dB relative to the following B interval, without removing
the signal. The repeated B levels agree closely. The direction differs from
the approximate operator comparison in live-003, so the labeled standing
positions alone do not predict the effect across placements/scenes.

## Interpretation and next action

This is evidence of current-scene reference sensitivity, not online learning or
calibration memorizing an operator. The active CFAR path has no trained empty
baseline and computes its reference from current-frame surrounding bins. Both
in-range and farther returns can affect that reference. Fixed empirical
settings can still generalize poorly, and the earlier replacement failures
remain unexplained by this successful control.

Do not repeat this same target-present A/B test or fit an offset from it. The
remaining useful matched control is target removed, with the same A/B/A/B
sequence and unchanged radar/support/settings. It distinguishes a target-linked
close return from operator-only output. Preserve this successful fixed-target
recording alongside the failed placements; avoid tuning to only this example.

All 946 recomputed decisions, fine distances and reasons match saved live
results. Capture reports zero host-quality rejections, CRC/sequence errors or
device errors/drops, with one trailing byte at stop. Original host freshness
is not independently certified by replay.

[Operator signal/threshold timeline](operator.png) · [Distance timeline](timeline.png) ·
[Spectra](spectra.png) · [Window metrics](report.json) ·
[Signal/threshold medians](operator.json) · [Candidate diagnostics](diagnostics.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.qualify_avg16_cfar \
  --manifest configs/avg16-operator-abab-20261111.json --output evidence/NEW-DIRECTORY
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_avg16_placements \
  --output evidence/NEW-DIRECTORY
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_avg16_abab \
  --output evidence/NEW-DIRECTORY
```
