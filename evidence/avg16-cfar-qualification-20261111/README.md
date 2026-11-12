# Frozen 1D CFAR on AVG16

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development replay only. Saved ADC/device continuity checks apply; original host freshness gates are NOT replayed. Saved host states/reasons are reported separately. Placement errors do not certify reflector identity. Target-absent outputs may be legitimate scene reflectors. No matched AVG1/AVG16 comparison or physical accuracy acceptance.

Settings: guard 1, training/minimum 4, multiplier 2; per-recording bin mask and confirmation preserved. No detector, firmware or threshold changes.

| Recording / labeled window | Numeric / frames | Median cm | Placement MAE cm* |
|---|---:|---:|---:|
| recordings/avg16-timing-01 / unspecified stationary scene | 67/201 | 32.4 | — |
| recordings/avg16-motion-01 / 120 cm A | 2/74 | 115.4 | 4.6 |
| recordings/avg16-motion-01 / 60 cm A | 65/65 | 85.0 | 24.7 |
| recordings/avg16-motion-01 / 120 cm B | 33/81 | 149.0 | 29.1 |
| recordings/avg16-motion-01 / 60 cm B | 53/53 | 48.7 | 11.5 |
| recordings/avg16-motion-01 / 120 cm C | 73/74 | 121.8 | 2.7 |
| recordings/avg16-motion-01 / approach 1 | 6/11 | 105.5 | — |
| recordings/avg16-motion-01 / retreat 1 | 10/10 | 81.4 | — |
| recordings/avg16-motion-01 / approach 2 | 5/9 | 95.3 | — |
| recordings/avg16-motion-01 / retreat 2 | 10/10 | 82.0 | — |
| recordings/gui-20261110-221227-169414/live-001 / 120 cm A | 0/82 | — | — |
| recordings/gui-20261110-221227-169414/live-001 / 30 cm A | 120/120 | 35.1 | 5.7 |
| recordings/gui-20261110-221227-169414/live-001 / 120 cm B | 3/97 | 105.8 | 14.5 |
| recordings/gui-20261110-221227-169414/live-001 / 30 cm B | 98/98 | 37.8 | 8.2 |
| recordings/gui-20261110-221227-169414/live-001 / 120 cm C | 0/67 | — | — |
| recordings/gui-20261110-221227-169414/live-001 / fast approach | 8/13 | 95.0 | — |
| recordings/gui-20261110-221227-169414/live-001 / fast retreat | 9/15 | 44.9 | — |
| recordings/gui-20261110-221227-169414/live-001 / slow approach | 17/29 | 93.8 | — |
| recordings/gui-20261110-221227-169414/live-001 / slow retreat | 25/32 | 85.6 | — |
| recordings/gui-20261110-221227-169414/live-001 / initial target absent | 6/121 | 116.2 | — |
| recordings/gui-20261110-221227-169414/live-001 / post-removal quiet | 0/38 | — | — |
| recordings/gui-20261110-221227-169414/live-001 / target absent, possible operator motion | 17/72 | 48.9 | — |

*Conditional on numeric output; identity unverified. Read with coverage. Black dashed plot segments are nominal placements, not certified measured-reflector truth.

[Timeline](timeline.png) · [Full metrics and hashes](report.json) · [Recomputed frame results (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)

Existing captures were already examined during development. Fresh labeled sessions are needed for acceptance; see [capture protocol](../../docs/AVG16_CFAR_QUALIFICATION.md).
