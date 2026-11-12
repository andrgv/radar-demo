# Repeated 50 cm placements and operator position

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

This capture demonstrates placement and scene sensitivity. It does not show
online learning of the operator position. The active `range-ca-cfar-v2` path
has no saved empty baseline or learned range calibration: power, reference
thresholds and fine range are computed from the current frame. Confirmation
retains short history, but does not learn scene statistics across runs. Fixed
empirical thresholds can still be overly specific to development scenes;
generalization remains unvalidated.

## Labels and validity

Consecutive durations are interpreted from the first saved frame. The ignored
interval is 28.67–48.68 s and is excluded from scoring. Holds are 48.68–79.44,
107.86–133.45 and 166.98–192.21 s. The third hold's operator switch is approximated
by its midpoint, 179.595 s, with two seconds excluded on each side. This is not
an observed switch time. One- and two-second trims are available for the other
quiet intervals. The full timeline includes unscored handling/ignored frames.

Supplied durations end at 211.64 s; the recording extends to 217.295 s. That
additional 5.655 s is unlabeled and excluded from scene metrics. No timing
offset was fitted to improve correspondence.

All 2,194 recomputed decisions, fine distances and reasons match saved live
results. There are zero capture rejections, CRC/sequence errors or device
errors/drops. The clock freezes after 200 frames and maximum corrected error
after freezing is approximately 45 ms. One trailing byte at stop is preserved.

## Quiet-interior results

| Labeled interval | Numeric / frames | Coverage | Median cm | 5th–95th cm |
|---|---:|---:|---:|---:|
| First 50 cm placement | 270/270 | 100% | 58.4 | 58.1–58.7 |
| Second 50 cm placement | 0/218 | 0% | — | — |
| Third 50 cm placement, full interior | 132/214 | 61.7% | 47.0 | 42.3–50.5 |
| Third, first approximate half | 87/87 | 100% | 46.3 | 42.0–50.6 |
| Third, second approximate half | 5/87 | 5.7% | 46.4 | 45.2–48.9 |

The halves overlap the full third-hold summary; do not pool them as additional
independent trials. All four empty interiors have zero presence/numeric outputs
(0/372 frames) within the configured bins 1–4 search mask. Farther scene returns
are not covered by that empty-output statement.

Second placement failure is at the candidate stage: all 218 frames have no
above-threshold candidate. The third full interior has 139 candidate frames,
132 confirmed numeric frames, seven confirmation frames and 75 no-candidate
frames. There are no unresolved fine estimates among confirmed interior
measurements. The first placement is stable but about 8.4 cm above nominal;
the earlier sweep's 50 cm median was 71.9 cm. These differing outcomes do not
support a single fitted distance offset.

## What changes during the last hold

In the approximate first/second halves, median bin-1 power stays near 60.6/60.5
dB, while its median threshold rises from 59.4 to 61.2 dB. The median threshold
margin changes from +1.28 to -0.74 dB. Bin 2 also crosses below threshold.
This is evidence for a changing CFAR reference level rather than complete
disappearance of near-range power. It does not prove that the remaining power
belongs to the target, or that the operator alone caused the change.

Shifting the assumed midpoint by -2, -1, 0, +1, +2 s yields 100% first-side
coverage in every case and respectively 23%, 15%, 6%, 1%, 0% second-side
coverage. The contrast survives this modest timing sensitivity check; exact
operator start/stop times would still strengthen the causal interpretation.

The CFAR reference window extends beyond the displayed detection mask. With
guard 1 and training 4, bin 1 uses bins 3–6, and bin 2 uses bins 4–7. Thus a
person outside the bins 1–4 output region can still affect the threshold of a
near return. Being away from the direct sensor-target line also does not
establish absence of radar influence. These are current-frame scene effects;
neither an empty recording nor prior calibration is consulted.

## Next experiment

Keep one target placement untouched at measured 50 cm and mark two operator
positions. Alternate A → B → A → B, with 15–20 s stationary at each position
and separately logged walking intervals. Record exact position-change times
and approximate operator ranges. Then remove the target and repeat the same
operator sequence. Keep the radar, cables, support, target orientation,
firmware and thresholds fixed. This tests repeatability and whether close
outputs appear with the operator alone without confounding target replacement.
Do not lower the threshold or fit an offset to this recording.

[Full timeline](timeline.png) · [Final-hold signal/threshold plot](operator.png) ·
[Native spectra](spectra.png) · [Window metrics](report.json) ·
[Candidate diagnostics](diagnostics.json) · [Midpoint sensitivity](operator.json)

Reproduce into a new evidence directory with `tools.qualify_avg16_cfar` using
`configs/avg16-repeat50-20261111.json`, followed by
`tools.review_avg16_placements --output NEW-DIRECTORY`. The fixed-path
`tools.review_avg16_operator` creates the operator plot and sensitivity report
in this directory. None of these commands changes live detector behavior.
