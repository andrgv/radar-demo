# Position and clutter follow-up: live-005/006/007

No thresholds, processing or firmware changed. Saved/current detector outputs agree outside explicitly recorded transport faults. These are fresh observations, not parameter-tuning data.

## Whole captures

| Capture | Description | Numeric outputs / frames | Median (cm) |
|---|---|---:|---:|
| live-005 | Near original position; intended empty scene. | 241/244 | 83.9 |
| live-006 | Original position followed by attempted clutter removal; clutter not restored. User says earlier portions likely include movement; about ten seconds before the final few seconds are decluttered/clean. Sensor stability was not explicitly confirmed. | 36/490 | 85.2 |
| live-007 | Shifted position with box at reported 80 cm. Clutter had been changed previously; effects are not independently isolated. | 190/194 | 78.3 |

## Inspection windows

| Capture / window | Host seconds | Numeric outputs / frames | Median (cm) | 5th–95th (cm) | Conditional MAE (cm) |
|---|---:|---:|---:|---:|---:|
| live-005 near-original empty | 1–22 | 210/211 | 84.0 | 81.3–86.6 | — |
| live-006 early recording | 0.5–2.5 | 20/20 | 85.1 | 82.6–86.4 | — |
| live-006 approximate clean decluttered interior | 35–43 | 0/81 | — | — | — |
| live-007 80 cm target interior | 2–17 | 151/151 | 78.3 | 76.3–79.0 | 1.8 |

## Findings

- The early/approximately clean live-006 median power at native bin 2 drops by **17.51 dB**. All three RX channels show a large decrease. The approximately clean 35–43 s window has no accepted outputs. Earlier movement-contaminated data and the final few seconds are excluded from clean-scene metrics. Timing is approximate and sensor stability is not established.
- Near-original live-005 again produces persistent unwanted empty-scene readings, now near **84 cm**, rather than the earlier ~70 cm. The return is not pinned to one hardcoded displayed distance. Position/scene variation changes its apparent peak.
- Shifted live-007 gives **151/151** numeric outputs in 2–17 s, a **78.31 cm** median for the reported 80 cm target, **76.33–79.05 cm** empirical 5th–95th interval, and **1.82 cm conditional MAE**. All 151 outputs in that window are within 5 cm of the reported placement. This is one geometry/placement, not a general error bound.
- Whole live-007 includes one CRC error/sequence gap near startup. Live-006 also has one; live-005 has none. Neither run reaches the long-recording timing cutoff. The observed device/host rate mismatch remains.
- These results strengthen the environmental/geometry dependence diagnosis. They do not identify a specific reflection path or exclude effects from operator movement, small sensor-pose changes, support or cable coupling. Clutter was not restored, so there is no reverse intervention control.
- The shifted target capture occurs after clutter changes. It cannot isolate the effects of sensor relocation versus clutter removal. Nor does it by itself establish the empty-scene behavior at that exact final pose.
- The unwanted ~84 cm empty readout overlaps the intended 80 cm target region. Blacklisting a fixed range or adding a global offset would not provide target identity.

## Next work / captures

No more broad distance sweeps are needed to establish the present failure modes. The exact manipulation times and sensor stability remain unverified; do not score earlier movement as empty false alarms. The acquisition clock mapping/freshness logic remains the next software issue to address; no extra long capture is needed to reproduce it.

After that change is frozen, a short empty capture and repeated supported 50/80/100 cm placements at one marked pose in the cleaner setup would test transfer. The same sensor height, orientation and operator position should be maintained. A clutter-restoration reversal would strengthen causal attribution, but is not required to see that this operating scene changed substantially.

[Plots](clutter-followup.png) · [Full metrics, spectra, transport and hashes](report.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.evaluate_cfar_clutter_followup --root recordings/gui-20261109-224819-094246 --output evidence/new-clutter-followup
```
