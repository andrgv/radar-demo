# Frozen 1D CFAR on AVG16

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development replay only. Saved ADC/device continuity checks apply; original host freshness gates are NOT replayed. Saved host states/reasons are reported separately. Placement errors do not certify reflector identity. Target-absent outputs may be legitimate scene reflectors. No matched AVG1/AVG16 comparison or physical accuracy acceptance.

Settings: guard 1, training/minimum 4, multiplier 2; per-recording bin mask and confirmation preserved. No detector, firmware or threshold changes.

| Recording / labeled window | Numeric / frames | Median cm | Placement MAE cm* |
|---|---:|---:|---:|
| recordings/gui-20261111-093723-246315/live-006 / 120 cm A (trim 1s) | 93/93 | 125.9 | 5.8 |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm A (trim 2s) | 73/73 | 125.8 | 5.8 |
| recordings/gui-20261111-093723-246315/live-006 / 50 cm A (trim 1s) | 27/117 | 35.5 | 14.0 |
| recordings/gui-20261111-093723-246315/live-006 / 50 cm A (trim 2s) | 25/97 | 35.4 | 14.2 |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm B (trim 1s) | 17/125 | 129.3 | 9.0 |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm B (trim 2s) | 8/105 | 130.7 | 10.8 |
| recordings/gui-20261111-093723-246315/live-006 / 50 cm B (trim 1s) | 120/120 | 60.9 | 10.8 |
| recordings/gui-20261111-093723-246315/live-006 / 50 cm B (trim 2s) | 100/100 | 60.9 | 10.9 |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm C (trim 1s) | 111/114 | 131.3 | 11.4 |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm C (trim 2s) | 94/94 | 131.2 | 11.3 |
| recordings/gui-20261111-093723-246315/live-006 / faster approach | 0/11 | — | — |
| recordings/gui-20261111-093723-246315/live-006 / faster retreat | 5/11 | 100.7 | — |
| recordings/gui-20261111-093723-246315/live-006 / slower approach | 11/22 | 85.3 | — |
| recordings/gui-20261111-093723-246315/live-006 / slower retreat | 13/23 | 95.9 | — |

*Conditional on numeric output; identity unverified. Read with coverage. Black dashed plot segments are nominal placements, not certified measured-reflector truth.

[Timeline](timeline.png) · [Full metrics and hashes](report.json) · [Recomputed frame results (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)

Existing captures were already examined during development. Fresh labeled sessions are needed for acceptance; see [capture protocol](../../docs/AVG16_CFAR_QUALIFICATION.md).
