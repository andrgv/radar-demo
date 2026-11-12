# Candidate-constrained phase-aware range comparison

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development comparison, no label fit or threshold sweep. Phase estimates require existing confirmed candidate support; rejected fits remain null. CA/OS settings unchanged. Conditional placement error does not establish physical identity or independent calibrated accuracy; read with coverage and empty outputs.

| Recording / window | CA peak frames | CA phase frames | Phase median cm | Phase placement MAE cm* |
|---|---:|---:|---:|---:|
| recordings/rd-gui-20261112-094114-038104/live-001 / empty A (trim 2s) | 0/135 | 0/135 | — | — |
| recordings/rd-gui-20261112-094114-038104/live-001 / bare A 50 cm (trim 2s) | 0/309 | 0/309 | — | — |
| recordings/rd-gui-20261112-094114-038104/live-001 / foil 50 cm (trim 2s) | 280/280 | 280/280 | 51.0 | 1.0 |
| recordings/rd-gui-20261112-094114-038104/live-001 / bare B 50 cm (trim 2s) | 0/274 | 0/274 | — | — |
| recordings/rd-gui-20261112-094114-038104/live-001 / final empty (trim 2s) | 0/135 | 0/135 | — | — |

*Conditional placement differences are not identity-verified range error.

[Full CA/OS metrics and hashes](report.json) · [CA timeline comparison](comparison.png) · [Frame decisions (gzip) (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)
