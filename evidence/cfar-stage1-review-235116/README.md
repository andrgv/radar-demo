# CFAR stage-one review: fresh post-clock-fix capture

## Clock / acquisition result

The capture contains **1386 frames over 137.7 host seconds**. The mapping freezes at **19.85 s** and stays fixed at **0.992584125 host seconds per device second**. There are **zero clock invalidations or timing-gate rejections**.

After freezing, maximum corrected error is **49.6 ms** (95th percentile **36.1 ms**), while raw elapsed error grows to **0.999 s**. This is live hardware confirmation of the fix, beyond earlier saved-timeline replay.

Two CRC failures cause two sequence-gap rejections; the stream recovers and continues. There are no device drop/error counter increments, restart indications or serial backlog rejections. The original raw wire includes discarded bytes and a one-byte incomplete tail at stop.

## Range result boundary

Tentative scene labels have now been supplied; see below. The user may have mixed distances, and transition times came from the UI graph rather than a stopwatch. Raw output distributions are measurable, but label-dependent errors remain conditional. No thresholds or algorithms were tuned to this capture.

## Stage decision

The implementation is ready to freeze as an experimental range-CFAR baseline, with the long-capture clock defect resolved in this run. Physical ranging accuracy, clutter robustness and detection acceptance remain conditional on scene labels and the prior failed-scene evidence. No further coding change is identified from the clock/transport review alone; preserve the two CRC events as a transport limitation.

[Capture plot](capture-review.png) · [Full metrics and provenance](report.json) · [Next-stage plan](../../docs/CFAR_RANGE_DOPPLER_PLAN.md)

## Tentative scene-label follow-up

User recollection: empty initially; approximately 30 s → 60 cm, 60 s → 30 cm, 90 s → 100 cm, 120 s → 70 cm. Distances/order may be mixed. The following windows remove three seconds around nominal transitions; the final row is a narrower late portion inspected because the user described a stable final readout. It is not an independent performance sample.

| Tentative state | Host window (s) | Numeric outputs / frames | Median (cm) | Empirical 5th–95th (cm) |
|---|---:|---:|---:|---:|
| empty | 3–27 | 0/241 | — | — |
| 60 cm tentative | 33–57 | 89/240 | 55.9 | 47.8–68.4 |
| 30 cm tentative | 63–87 | 224/242 | 37.7 | 35.8–40.7 |
| 100 cm tentative | 93–117 | 223/242 | 109.6 | 106.8–112.1 |
| 70 cm tentative | 123–135 | 104/121 | 82.8 | 72.9–98.8 |
| late 70 cm tentative | 130–135 | 50/50 | 83.1 | 81.3–84.5 |

The initial empty window has no numeric output. The first target interval is noisy and has low coverage (89/240). If recalled distances are correct, the later medians suggest appreciable bias (~8 cm at 30 cm, ~10 cm at 100 cm, ~13 cm in the stable late 70 cm portion). These cannot be treated as verified errors because labels are uncertain. Do not fit an offset or retune CFAR against these tentative labels.

Freeze stage one as an experimental implementation baseline, with confirmed clock stability, not as accepted physical range accuracy. A single carefully labeled repeat is worthwhile before physical acceptance: fixed supported target, antenna-face measurements, written order empty/30/60/70/100 cm/empty, approximately 20 s per state, and recorded transition times with step-away margins. This need not block replay-first Doppler/timing-feasibility work.
