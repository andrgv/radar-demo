# Candidate-constrained phase-aware range comparison

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Development comparison, no label fit or threshold sweep. Phase estimates require existing confirmed candidate support; rejected fits remain null. CA/OS settings unchanged. Conditional placement error does not establish physical identity or independent calibrated accuracy; read with coverage and empty outputs.

| Recording / window | CA peak frames | CA phase frames | Phase median cm | Phase placement MAE cm* |
|---|---:|---:|---:|---:|
| recordings/gui-20261111-093723-246315/live-001 / initial empty (trim 2s) | 0/144 | 0/144 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / 50 cm (trim 2s) | 176/176 | 1/176 | 76.0 | 26.0 |
| recordings/gui-20261111-093723-246315/live-001 / empty after 50 cm (trim 2s) | 0/118 | 0/118 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / 80 cm (trim 2s) | 85/199 | 0/199 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / empty after 80 cm (trim 2s) | 0/118 | 0/118 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / 120 cm (trim 2s) | 123/183 | 0/183 | — | — |
| recordings/gui-20261111-093723-246315/live-001 / final empty (trim 2s) | 0/132 | 0/132 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / initial empty (trim 2s) | 0/118 | 0/118 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm A (trim 2s) | 270/270 | 270/270 | 59.1 | 9.1 |
| recordings/gui-20261111-093723-246315/live-003 / empty after A (trim 2s) | 0/115 | 0/115 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm B (trim 2s) | 0/218 | 0/218 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / empty after B (trim 2s) | 0/69 | 0/69 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / 50 cm C (trim 2s) | 132/214 | 0/214 | — | — |
| recordings/gui-20261111-093723-246315/live-003 / final empty (trim 2s) | 0/70 | 0/70 | — | — |
| recordings/gui-20261111-093723-246315/live-004 / A1 (trim 2s) | 131/131 | 0/131 | — | — |
| recordings/gui-20261111-093723-246315/live-004 / B1 (trim 2s) | 129/129 | 0/129 | — | — |
| recordings/gui-20261111-093723-246315/live-004 / A2 (trim 2s) | 126/126 | 0/126 | — | — |
| recordings/gui-20261111-093723-246315/live-004 / B2 (trim 2s) | 127/127 | 0/127 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / A1 (trim 2s) | 0/122 | 0/122 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / B1 (trim 2s) | 0/128 | 0/128 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / A2 (trim 2s) | 0/126 | 0/126 | — | — |
| recordings/gui-20261111-093723-246315/live-005 / B2 (trim 2s) | 0/122 | 0/122 | — | — |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm A (trim 2s) | 73/73 | 71/73 | 127.9 | 7.9 |
| recordings/gui-20261111-093723-246315/live-006 / 50 cm A (trim 2s) | 25/97 | 0/97 | — | — |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm B (trim 2s) | 8/105 | 0/105 | — | — |
| recordings/gui-20261111-093723-246315/live-006 / 50 cm B (trim 2s) | 100/100 | 100/100 | 64.1 | 14.2 |
| recordings/gui-20261111-093723-246315/live-006 / 120 cm C (trim 2s) | 94/94 | 0/94 | — | — |
| recordings/gui-20261111-093723-246315/live-006 / faster approach | 0/11 | 0/11 | — | — |
| recordings/gui-20261111-093723-246315/live-006 / faster retreat | 5/11 | 0/11 | — | — |
| recordings/gui-20261111-093723-246315/live-006 / slower approach | 11/22 | 2/22 | 82.4 | — |
| recordings/gui-20261111-093723-246315/live-006 / slower retreat | 13/23 | 2/23 | 100.3 | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / 120 cm A (trim 2s) | 0/76 | 0/76 | — | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / 50 cm A (trim 2s) | 76/76 | 0/76 | — | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / 120 cm B (trim 2s) | 46/75 | 0/75 | — | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / 50 cm B (trim 2s) | 61/72 | 0/72 | — | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / 120 cm C (trim 2s) | 71/71 | 0/71 | — | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / approach 1 | 5/16 | 0/16 | — | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / retreat 1 | 8/15 | 3/15 | 94.9 | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / approach 2 | 7/33 | 1/33 | 74.9 | — |
| recordings/rd-gui-20261111-141606-847532/live-002 / retreat 2 | 12/29 | 0/29 | — | — |
| recordings/rd-gui-20261111-143819-360020/live-003 / empty A (trim 2s) | 0/119 | 0/119 | — | — |
| recordings/rd-gui-20261111-143819-360020/live-003 / 50 cm A (trim 2s) | 184/184 | 0/184 | — | — |
| recordings/rd-gui-20261111-143819-360020/live-003 / empty B (trim 2s) | 0/82 | 0/82 | — | — |
| recordings/rd-gui-20261111-143819-360020/live-003 / 50 cm B (trim 2s) | 126/177 | 0/177 | — | — |
| recordings/rd-gui-20261111-143819-360020/live-003 / empty C (trim 2s) | 0/82 | 0/82 | — | — |
| recordings/rd-gui-20261111-143819-360020/live-003 / 120 cm (trim 2s) | 0/178 | 0/178 | — | — |
| recordings/rd-gui-20261111-143819-360020/live-003 / final empty (trim 2s) | 0/148 | 0/148 | — | — |
| recordings/rd-gui-20261111-200448-409110/live-001 / empty A (trim 2s) | 0/116 | 0/116 | — | — |
| recordings/rd-gui-20261111-200448-409110/live-001 / 50 cm A (trim 2s) | 173/173 | 173/173 | 50.7 | 0.7 |
| recordings/rd-gui-20261111-200448-409110/live-001 / empty B (trim 2s) | 0/73 | 0/73 | — | — |
| recordings/rd-gui-20261111-200448-409110/live-001 / 50 cm B (trim 2s) | 168/168 | 168/168 | 46.7 | 3.2 |
| recordings/rd-gui-20261111-200448-409110/live-001 / empty C (trim 2s) | 0/69 | 0/69 | — | — |
| recordings/rd-gui-20261111-200448-409110/live-001 / 120 cm (trim 2s) | 170/170 | 170/170 | 122.9 | 3.0 |
| recordings/rd-gui-20261111-200448-409110/live-001 / final empty (trim 2s) | 0/116 | 0/116 | — | — |
| recordings/rd-gui-20261111-133435-428121/live-001 / 80 cm stationary | 0/714 | 0/714 | — | — |

*Conditional placement differences are not identity-verified range error.

[Full CA/OS metrics and hashes](report.json) · [CA timeline comparison](comparison.png) · [Frame decisions (gzip) (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)
