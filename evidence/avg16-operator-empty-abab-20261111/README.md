# Frozen 1D CFAR on AVG16

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development replay only. Saved ADC/device continuity checks apply; original host freshness gates are NOT replayed. Saved host states/reasons are reported separately. Placement errors do not certify reflector identity. Target-absent outputs may be legitimate scene reflectors. No matched AVG1/AVG16 comparison or physical accuracy acceptance.

Settings: guard 1, training/minimum 4, multiplier 2; per-recording bin mask and confirmation preserved. No detector, firmware or threshold changes.

| Recording / labeled window | Numeric / frames | Median cm | Placement MAE cm* |
|---|---:|---:|---:|
| recordings/gui-20261111-093723-246315/live-005 / A1 (trim 1s) | 0/142 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / A1 (trim 2s) | 0/122 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / B1 (trim 1s) | 0/148 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / B1 (trim 2s) | 0/128 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / A2 (trim 1s) | 0/146 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / A2 (trim 2s) | 0/126 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / B2 (trim 1s) | 0/142 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / B2 (trim 2s) | 0/122 | — | — |

*Conditional on numeric output; identity unverified. Read with coverage. Black dashed plot segments are nominal placements, not certified measured-reflector truth.

[Timeline](timeline.png) · [Full metrics and hashes](report.json) · [Recomputed frame results (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)

Existing captures were already examined during development. Fresh labeled sessions are needed for acceptance; see [capture protocol](../../docs/AVG16_CFAR_QUALIFICATION.md).
