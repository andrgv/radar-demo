# CFAR group confirmation and baseline-free fine range

Threshold settings remain frozen at guard 1, training/minimum 4, factor 2. Before uses the saved v1 source; after uses v2. No smoothing or empty subtraction.

## Fresh recording intervals (approximate)

| Recording / state | Window (s) | Before output | After fine output | After median (cm) | After conditional MAE (cm) |
|---|---:|---:|---:|---:|---:|
| live-003 1: empty | 1–5 | 2/40 | 3/40 | 81.4 | — |
| live-003 2: 50 cm | 7–11 | 25/40 | 40/40 | 50.8 | 2.2 |
| live-003 3: empty | 13–17 | 0/40 | 1/40 | 100.1 | — |
| live-003 4: 50 cm | 19–23 | 23/40 | 40/40 | 50.0 | 3.5 |
| live-003 5: empty | 25–29 | 5/40 | 6/40 | 96.4 | — |
| live-002 initial empty | 1–3 | 16/19 | 16/19 | 74.5 | — |
| live-002 50 cm target | 8–24 | 83/160 | 141/160 | 50.7 | 7.0 |
| live-002 ending empty | 27–29.1 | 21/21 | 21/21 | 73.0 | — |

## Historical replay

All 30 labeled historical recordings were replayed, including empty captures and other profiles. Each recording has equal weight within target/empty classes.

| Method | Target range coverage | Empty presence | Empty numeric output |
|---|---:|---:|---:|
| before | 89.7% | 17.8% | 17.8% |
| after | 94.6% | 18.1% | 17.2% |

## Limitations

- Group overlap allows confirmation to survive a change of maximum by one bin. It does not prove object identity, and can also confirm clutter more readily. Empty presence and numeric outputs are reported separately.
- Refinement searches the current raw Hann spectrum within half-bin boundaries around the selected group. Boundary maxima or multiple local maxima within 3 dB of the strongest leave distance unresolved. Presence can remain true with no numeric distance.
- Native `range_bin` and `provisional_range_m` retain coarse coordinates. `experimental_range_m` is the new UI/history value. `range_m` remains null and calibration false.
- Fine sampling and interpolation do not add physical resolution or establish centimeter accuracy. Conditional error excludes unresolved/missing outputs; read it alongside coverage. Scene transition times and placements are approximate.
- These fresh recordings informed the change. Results are development evidence, not independent validation. Empty-scene failures remain; no threshold retuning or firmware changes were made.

[Before/after plot](fresh-comparison.png) · [Full per-session metrics and source hashes](report.json) · [Fresh-frame decisions](frames.jsonl)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.evaluate_cfar_group_range --baseline-source evidence/cfar-group-range-v2/baseline_cfar.py --output evidence/new-cfar-v2-evaluation
```
