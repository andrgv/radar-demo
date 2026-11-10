# Fresh CFAR v2 validation: 50 cm and 80 cm

Both captures reproduce saved acquisition decisions and fine estimates under the current code. No thresholds or algorithms were tuned to these data.

State changes are approximately every six seconds. Primary metrics exclude two seconds at each side of nominal intervals. One-second-trim metrics are included to expose timing sensitivity. The 50 cm recording ends after 27.5 s, so the last nominal empty window is truncated.


## 2-second trim at each interval boundary

| Target / interval | State | Window (s) | Range outputs / frames | Median (cm) | 5th–95th (cm) | Conditional MAE (cm) |
|---|---|---:|---:|---:|---:|---:|
| 50 cm / 1 | empty | 2–4 | 0/20 | — | — | — |
| 50 cm / 2 | target | 8–10 | 20/20 | 51.6 | 45.8–54.1 | 2.6 |
| 50 cm / 3 | empty | 14–16 | 0/20 | — | — | — |
| 50 cm / 4 | target | 20–22 | 20/20 | 57.0 | 53.2–58.6 | 6.4 |
| 50 cm / 5 | empty | 26–28 (truncated) | 0/16 | — | — | — |
| 80 cm / 1 | empty | 2–4 | 0/20 | — | — | — |
| 80 cm / 2 | target | 8–10 | 8/20 | 83.2 | 71.1–84.4 | 4.5 |
| 80 cm / 3 | empty | 14–16 | 0/20 | — | — | — |
| 80 cm / 4 | target | 20–22 | 20/20 | 82.9 | 82.4–83.4 | 2.9 |
| 80 cm / 5 | empty | 26–28 | 0/20 | — | — | — |
| 80 cm / 6 | target | 32–34 | 6/20 | 75.2 | 73.2–80.7 | 4.5 |
| 80 cm / 7 | empty | 38–40 | 2/20 | 121.4 | 119.6–123.2 | — |

## 1-second trim at each interval boundary

| Target / interval | State | Window (s) | Range outputs / frames | Median (cm) | 5th–95th (cm) | Conditional MAE (cm) |
|---|---|---:|---:|---:|---:|---:|
| 50 cm / 1 | empty | 1–5 | 0/40 | — | — | — |
| 50 cm / 2 | target | 7–11 | 40/40 | 51.9 | 46.3–55.2 | 2.7 |
| 50 cm / 3 | empty | 13–17 | 0/40 | — | — | — |
| 50 cm / 4 | target | 19–23 | 34/40 | 56.8 | 52.4–62.8 | 7.5 |
| 50 cm / 5 | empty | 25–29 (truncated) | 0/26 | — | — | — |
| 80 cm / 1 | empty | 1–5 | 0/40 | — | — | — |
| 80 cm / 2 | target | 7–11 | 17/40 | 80.5 | 58.0–84.4 | 6.6 |
| 80 cm / 3 | empty | 13–17 | 0/40 | — | — | — |
| 80 cm / 4 | target | 19–23 | 40/40 | 82.9 | 78.9–83.6 | 2.5 |
| 80 cm / 5 | empty | 25–29 | 0/40 | — | — | — |
| 80 cm / 6 | target | 31–35 | 16/40 | 76.0 | 73.7–80.9 | 3.5 |
| 80 cm / 7 | empty | 37–41 | 6/40 | 121.5 | 118.5–126.5 | — |

## Main findings

- At 50 cm: 40/40 target-interior numeric outputs, and 0/56 unwanted empty-interior outputs. This pools the primary windows only; placement differences remain visible in the table.
- At 80 cm: 34/60 target-interior numeric outputs, and 2/80 unwanted empty-interior outputs. This pools the primary windows only; placement differences remain visible in the table.

The 80 cm threshold plot shows a strong, sustained return in the middle placement and much more marginal returns in the other placements. Their missing outputs include no-candidate and confirmation rejections, not serial errors. The physical cause of the strength difference is not isolated.

The two 50 cm placements give different peak medians despite the same reported distance. This argues against treating a single constant range offset or display smoothing as a complete fix. Preserve this validation set without retuning to it.

A useful next controlled capture is a supported 80 cm target left untouched for 30 seconds, then removed/replaced at marked lateral position and orientation for repeated 15-second holds, with marked timestamps and the operator out of the beam. This can distinguish within-placement fluctuations from placement-dependent changes; it is evaluation data, not an empty baseline requirement.

## Interpretation limits

- Coverage includes every available frame inside each labeled interior. Conditional errors use only numeric outputs, so they must be interpreted with coverage. No missing or wrong-range outputs are silently filled.
- Zero outputs during short empty interiors do not establish a calibrated false-alarm rate. There are no reported CRC errors, sequence gaps or acquisition rejections in either capture; incomplete wire tails at stop are retained.
- Approximate timing can assign removal/movement frames to nominal target windows. Neither low coverage nor a range outlier automatically identifies a specific physical cause.
- These are new recordings collected after v2 implementation and are useful prospective checks. The small fixed scene, approximate placements, correlated frames and few repetitions do not establish general accuracy.
- Fine spectrum peaks remain uncalibrated and can follow clutter/multipath. Presence qualification and peak estimation are assessed separately in JSON.

[Timeline and threshold plots](validation.png) · [Full metrics, reasons and hashes](report.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.validate_cfar_captures --manifest configs/cfar-validation-20261109-224819.json --output evidence/new-cfar-fresh-validation
```
