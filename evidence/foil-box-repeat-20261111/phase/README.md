# Candidate-constrained phase-aware range comparison

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../../ARCHIVED_ARTIFACTS.md).

Development comparison, no label fit or threshold sweep. Phase estimates require existing confirmed candidate support; rejected fits remain null. CA/OS settings unchanged. Conditional placement error does not establish physical identity or independent calibrated accuracy; read with coverage and empty outputs.

| Recording / window | CA peak frames | CA phase frames | Phase median cm | Phase placement MAE cm* |
|---|---:|---:|---:|---:|
| recordings/rd-gui-20261111-200448-409110/live-002 / empty A (trim 2s) | 0/117 | 0/117 | — | — |
| recordings/rd-gui-20261111-200448-409110/live-002 / 50 cm A (trim 2s) | 219/219 | 219/219 | 51.4 | 1.3 |
| recordings/rd-gui-20261111-200448-409110/live-002 / empty B (trim 2s) | 0/158 | 0/158 | — | — |
| recordings/rd-gui-20261111-200448-409110/live-002 / 50 cm B (trim 2s) | 217/217 | 217/217 | 48.6 | 1.4 |
| recordings/rd-gui-20261111-200448-409110/live-002 / empty C (trim 2s) | 0/126 | 0/126 | — | — |
| recordings/rd-gui-20261111-200448-409110/live-002 / 120 cm (trim 2s) | 221/221 | 221/221 | 122.1 | 2.1 |
| recordings/rd-gui-20261111-200448-409110/live-002 / final empty (trim 2s) | 0/119 | 0/119 | — | — |

*Conditional placement differences are not identity-verified range error.

[Full CA/OS metrics and hashes](report.json) · [CA timeline comparison](comparison.png) · [Frame decisions (gzip) (archived)](../../ARCHIVED_ARTIFACTS.md#archived-files)
