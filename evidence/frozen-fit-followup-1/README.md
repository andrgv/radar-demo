# Frozen trial follow-up

The user followed the requested order in the existing GUI session:
live-006 40 cm, live-007 50 cm, live-008 20 cm, live-009 empty.
They report shifting the box right during the 50 and 20 cm recordings. These
are nominal placement labels, not synchronized instantaneous radial ground truth.
No frames were trimmed, including motion/transitions. No settings were tuned.

The trial is frozen to the earlier local selection: energy ratio >=2, no purity
or receiver-agreement restriction, five-frame candidate span <=10 cm,
three-frame confirmation, causal median of up to five accepted candidates.
The original calibration supplies 20 reference and 10 threshold frames. The
existing GUI detector is also replayed, exactly reproducing the saved log.

| Nominal placement | Trial reports | Median reported distance | MAE among reports |
|---|---:|---:|---:|
| 40 cm | 193/211 (91.5%) | 43.79 cm | 3.78 cm |
| 50 cm, repositioned | 107/269 (39.8%) | 48.27 cm | 4.22 cm |
| 20 cm, repositioned | 49/211 (23.2%) | 70.35 cm | 43.65 cm |
| Empty | 12/222 false reports (5.4%) | 96.07 cm | Not applicable |

All decoded streams have zero reported CRC errors, sequence gaps, restarts or
rejected frames. Each capture has a partial trailing packet at stop, documented
in report.json; it is not treated as a complete measurement.

The existing GUI reports 25/211, 12/269, 11/211 and 0/222 respectively.
Its accepted estimates are not automatically accurate: the 50 and 20 cm runs
have large errors under that rule too. Keeping it unchanged is not an accuracy
certification; it avoids deploying a failed replacement.

The 50 cm recording's last two chronological quarters have MAE 1.99 and
1.87 cm among reports, with 33 and 60 reports respectively. Earlier quarters
have only 6 and 8 reports and include large errors. This is compatible with
scene/alignment sensitivity but does not identify the movement time or prove
its cause. Quarters are fixed time partitions, not selected best segments.
The 40 cm run has bias throughout all four quarters even without reported movement.

The trial does not pass this follow-up. No abrupt >20 cm jumps between adjacent
accepted frames were counted, yet very wrong outputs remain: gaps and stable
wrong components mean that this jump statistic cannot certify accuracy.
These new recordings are separate follow-up captures but use the same background
and physical session, not an independent-session generalization test.

Reproduce from wavvy-range-v1:

```sh
MPLCONFIGDIR=/tmp/wavvy-mpl OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_frozen_followup
```

report.json includes provenance hashes, full-record metrics, transport summaries
and all chronological quarters. frames.jsonl contains every candidate and output.
No firmware, GUI or DSP default was changed. No new unchanged capture is needed
to establish this failure; the next acquisition step remains the supported profile
and timing inquiry in docs/INFINEON_CONFIGURATION_REQUEST.txt.
