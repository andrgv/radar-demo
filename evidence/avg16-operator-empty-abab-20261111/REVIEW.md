# Target-absent operator A/B control

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

There are no confirmed detections or numeric distances in any of the 867 saved
frames, including walking transitions and the unlabeled tail. This completes
the operator-only control requested after live-004. No re-recording or threshold
change is needed for this control.

## Quiet-interior results

| Operator interval | Nominal host window (s) | Outputs / two-second-trimmed frames | Median bin-1 threshold margin |
|---|---:|---:|---:|
| A1 | 0–16.23 | 0/122 | -3.98 dB |
| B1 | 20.77–37.48 | 0/128 | -1.90 dB |
| A2 | 43.41–59.94 | 0/126 | -2.79 dB |
| B2 | 63.78–79.94 | 0/122 | -1.80 dB |

All 498 primary interior frames have no above-threshold candidate in the
configured bins 1–4 search mask. One-second-trimmed summaries also have zero
outputs. This is not an all-range absence-of-reflections claim or a general
false-alarm rate. Durations are interpreted from the first saved frame without
a fitted offset. The final 6.181 s of the 86.121-second capture is unlabeled and
excluded from scene metrics.

The matching live-004 target-present A/B control has outputs on 513/513 primary
interior frames, with medians of 46.8–47.2 cm for a nominal 50 cm target. Both
captures use the same config fingerprint, bin mask and guard/training/factor
settings. Near-range bin-1 median power falls by 6.9–7.1 dB with target removal
in each corresponding operator interval. Thresholds change too, so this is a
power comparison, not an absolute calibrated SNR measurement.

The combined controls support a close return linked to target presence in this
placement; the operator alone does not reproduce it. They do not certify the
physical reflector identity for every measurement or resolve the earlier
replacement failures. Operator A changes reference levels in both controls,
while target presence determines which side of threshold the close return
falls on here. The active algorithm performs no learned scene calibration.

All 867 recomputed decisions, fine distances and reasons match saved live
results. The capture reports zero host-quality rejections, CRC/sequence errors
or device errors/drops. There are 187 incomplete bytes at capture stop, recorded
in the summary; complete saved frames are unaffected. Replay does not
independently certify original absolute host freshness.

Keep these controls frozen alongside live-003's failures. They are sufficient
to proceed with the shared 1D/RD candidate/result layer; do not tune a threshold
or distance offset to this successful scene. Independent placements and farther
targets remain part of later combined-pipeline validation.

[Matched signal/threshold comparison](matched-comparison.png) ·
[Matched medians and provenance](matched-comparison.json) ·
[Window metrics](report.json) · [Spectra](spectra.png) ·
[Candidate-stage diagnostics](diagnostics.json)

Reproduce into a new directory with `tools.qualify_avg16_cfar` and manifest
`configs/avg16-operator-empty-abab-20261111.json`, followed by
`tools.review_avg16_placements --output NEW-DIRECTORY`. The fixed-path
`tools.compare_avg16_abab` compares the saved live-004 and live-005 evidence
directories and generates the matched figure and JSON. No live algorithm or
firmware was changed.
