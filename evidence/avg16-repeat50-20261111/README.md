# Frozen 1D CFAR on AVG16

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development replay only. Saved ADC/device continuity checks apply; original host freshness gates are NOT replayed. Saved host states/reasons are reported separately. Placement errors do not certify reflector identity. Target-absent outputs may be legitimate scene reflectors. No matched AVG1/AVG16 comparison or physical accuracy acceptance.

Settings: guard 1, training/minimum 4, multiplier 2; per-recording bin mask and confirmation preserved. No detector, firmware or threshold changes.

| Recording / labeled window | Numeric / frames | Median cm | Placement MAE cm* |
|---|---:|---:|---:|
| recordings/gui-20261111-093723-246315/live-003 / initial empty (trim 1s) | 0/138 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / initial empty (trim 2s) | 0/118 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm A (trim 1s) | 290/290 | 58.4 | 8.4 |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm A (trim 2s) | 270/270 | 58.4 | 8.4 |
| recordings/gui-20261111-093723-246315/live-003 / empty after A (trim 1s) | 0/135 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / empty after A (trim 2s) | 0/115 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm B (trim 1s) | 0/238 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm B (trim 2s) | 0/218 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / empty after B (trim 1s) | 0/89 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / empty after B (trim 2s) | 0/69 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm C (trim 1s) | 142/234 | 46.9 | 3.3 |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm C (trim 2s) | 132/214 | 47.0 | 3.2 |
| recordings/gui-20261111-093723-246315/live-003 / C first half, operator possibly in range (trim 2s) | 87/87 | 46.3 | 3.7 |
| recordings/gui-20261111-093723-246315/live-003 / C second half, usual operator position (trim 2s) | 5/87 | 46.4 | 3.3 |
| recordings/gui-20261111-093723-246315/live-003 / final empty (trim 1s) | 0/90 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / final empty (trim 2s) | 0/70 | — | — |

*Conditional on numeric output; identity unverified. Read with coverage. Black dashed plot segments are nominal placements, not certified measured-reflector truth.

[Timeline](timeline.png) · [Full metrics and hashes](report.json) · [Recomputed frame results (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)

Existing captures were already examined during development. Fresh labeled sessions are needed for acceptance; see [capture protocol](../../docs/AVG16_CFAR_QUALIFICATION.md).
