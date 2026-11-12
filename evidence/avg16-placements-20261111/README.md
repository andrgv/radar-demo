# Frozen 1D CFAR on AVG16

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development replay only. Saved ADC/device continuity checks apply; original host freshness gates are NOT replayed. Saved host states/reasons are reported separately. Placement errors do not certify reflector identity. Target-absent outputs may be legitimate scene reflectors. No matched AVG1/AVG16 comparison or physical accuracy acceptance.

Settings: guard 1, training/minimum 4, multiplier 2; per-recording bin mask and confirmation preserved. No detector, firmware or threshold changes.

| Recording / labeled window | Numeric / frames | Median cm | Placement MAE cm* |
|---|---:|---:|---:|
| recordings/gui-20261111-093723-246315/live-001 / initial empty (trim 1s) | 0/164 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / initial empty (trim 2s) | 0/144 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / 50 cm (trim 1s) | 196/196 | 72.0 | 22.1 |
| recordings/gui-20261111-093723-246315/live-001 / 50 cm (trim 2s) | 176/176 | 71.9 | 22.2 |
| recordings/gui-20261111-093723-246315/live-001 / empty after 50 cm (trim 1s) | 0/138 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / empty after 50 cm (trim 2s) | 0/118 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / 80 cm (trim 1s) | 95/219 | 103.1 | 23.2 |
| recordings/gui-20261111-093723-246315/live-001 / 80 cm (trim 2s) | 85/199 | 103.1 | 23.1 |
| recordings/gui-20261111-093723-246315/live-001 / empty after 80 cm (trim 1s) | 0/138 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / empty after 80 cm (trim 2s) | 0/118 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / 120 cm (trim 1s) | 143/203 | 149.5 | 29.6 |
| recordings/gui-20261111-093723-246315/live-001 / 120 cm (trim 2s) | 123/183 | 149.6 | 29.7 |
| recordings/gui-20261111-093723-246315/live-001 / final empty (trim 1s) | 0/152 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / final empty (trim 2s) | 0/132 | — | — |

*Conditional on numeric output; identity unverified. Read with coverage. Black dashed plot segments are nominal placements, not certified measured-reflector truth.

[Timeline](timeline.png) · [Full metrics and hashes](report.json) · [Recomputed frame results (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)

Existing captures were already examined during development. Fresh labeled sessions are needed for acceptance; see [capture protocol](../../docs/AVG16_CFAR_QUALIFICATION.md).
