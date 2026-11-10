# Repeated empty/50 cm toggle diagnosis

User reports approximately six seconds per state; transitions inferred, not instrumented. One second removed from each end of each nominal interval.

Teal shading in the plot indicates approximate target interiors; gray shading indicates empty interiors. Other frames are excluded from interval metrics.

| Interval | Interior (s) | Frames | Has CFAR candidate | Accepted | Both bins 1/2 qualified | Candidate switches | Raw dense-peak median (cm) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1: empty | 1–5 | 40 | 15 | 2 | 1 | 4 | 79.6 |
| 2: target | 7–11 | 40 | 40 | 25 | 40 | 9 | 50.8 |
| 3: empty | 13–17 | 40 | 9 | 0 | 1 | 2 | 38.6 |
| 4: target | 19–23 | 40 | 40 | 23 | 39 | 11 | 50.0 |
| 5: empty | 25–29 | 40 | 12 | 5 | 0 | 2 | 93.4 |

## Main findings

Both target interiors contain a qualifying CFAR candidate in **40/40 frames**.
The UI accepts only **25/40** and **23/40**. Every withheld target-interior frame
is marked `checking_persistence`, rather than failure to exceed the threshold.
Candidate bin switches number 9 and 11. Bins 1 and 2 are grouped together in
40/40 and 39/40 target-interior frames respectively. Exact-bin persistence is
therefore discarding a continuously qualifying broad group in these windows.

Without subtracting any empty reference, the diagnostic dense-FFT peak has
medians **50.8 cm** and **50.0 cm** in the two target interiors. Their empirical
5th–95th percentile intervals are **47.8–57.1 cm** and **46.7–57.1 cm**. These
are observed peak distributions under nominal axes, not validated accuracy or
confidence bounds. This supports investigating a baseline-free sub-bin estimator.

The three approximate empty interiors have **7 accepted outputs out of 120
frames**, including five in the final interior. Empty-scene rejection remains an
issue. Live-003 has no reported accepted-frame CRC errors, sequence gaps or
acquisition rejections. An incomplete raw-wire tail at stop is retained.

No additional data are needed to establish the exact-bin confirmation mechanism
in these recordings. Fine estimation and confirmation across an associated broad
peak group should be evaluated next against all existing empty/target evidence,
with fresh labeled captures used after those changes are frozen.

## Interpretation

Compare candidate availability against accepted output: a broad return can exceed threshold in two adjacent cells while its strongest bin changes. The detector groups adjacent cells, but persistence is keyed to the group maximum’s exact bin. Changes of maximum restart confirmation even if both bins remain in one group.

This identifies a possible rejection mechanism; it does not establish the cause of the empty-scene return in live-002. Different empty behavior between these recordings argues against treating one fixed threshold as a universally validated solution.

Dense-spectrum peaks are diagnostics of the raw signal, including clutter and leakage. Zero padding samples the spectrum more finely without adding physical resolution. A peak near the placement is not proof of target association or an accurate distance estimator; inspect all intervals and per-RX distributions in JSON.

No live algorithm, threshold, baseline, smoothing, or firmware was changed. These intervals are approximate and operator motion at transitions can contaminate them.

[Plot](toggle-diagnosis.png) · [Full metrics and provenance](report.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.diagnose_cfar_toggle recordings/gui-20261109-215257-942086/live-003 --output evidence/new-toggle-diagnosis --interval-seconds 6 --trim-seconds 1 --target-m 0.5
```
