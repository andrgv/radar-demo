# Frozen 1D CFAR on AVG16

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development replay only. Saved ADC/device continuity checks apply; original host freshness gates are NOT replayed. Saved host states/reasons are reported separately. Placement errors do not certify reflector identity. Target-absent outputs may be legitimate scene reflectors. No matched AVG1/AVG16 comparison or physical accuracy acceptance.

Settings: guard 1, training/minimum 4, multiplier 2; per-recording bin mask and confirmation preserved. No detector, firmware or threshold changes.

| Recording / labeled window | Numeric / frames | Median cm | Placement MAE cm* |
|---|---:|---:|---:|
| recordings/gui-20261111-093723-246315/live-004 / A1 (trim 1s) | 151/151 | 47.2 | 2.7 |
| recordings/gui-20261111-093723-246315/live-004 / A1 (trim 2s) | 131/131 | 47.2 | 2.6 |
| recordings/gui-20261111-093723-246315/live-004 / B1 (trim 1s) | 149/149 | 46.9 | 3.2 |
| recordings/gui-20261111-093723-246315/live-004 / B1 (trim 2s) | 129/129 | 46.9 | 3.2 |
| recordings/gui-20261111-093723-246315/live-004 / A2 (trim 1s) | 146/146 | 46.8 | 3.1 |
| recordings/gui-20261111-093723-246315/live-004 / A2 (trim 2s) | 126/126 | 46.8 | 3.2 |
| recordings/gui-20261111-093723-246315/live-004 / B2 (trim 1s) | 147/147 | 46.8 | 3.3 |
| recordings/gui-20261111-093723-246315/live-004 / B2 (trim 2s) | 127/127 | 46.8 | 3.3 |

*Conditional on numeric output; identity unverified. Read with coverage. Black dashed plot segments are nominal placements, not certified measured-reflector truth.

[Timeline](timeline.png) · [Full metrics and hashes](report.json) · [Recomputed frame results (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)

Existing captures were already examined during development. Fresh labeled sessions are needed for acceptance; see [capture protocol](../../docs/AVG16_CFAR_QUALIFICATION.md).
