# Fixed weak-candidate selector: development comparison

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

**Later physical-setup clarification (2026-11-11):** the operator was at A /
within range during the bare-box 120 cm hold. Its ~32 cm return is therefore
operator-confounded, not established as a false obstacle or as the box. Counts
below are unchanged; this later fact was not used to construct the selector.
See [the updated capture catalog](../../docs/CAPTURE_CATALOG.md) and
[subsequent confirmation review](../weak-features-20261111/README.md).

Implemented one fixed hypothesis: original confirmed single OS group + unique
current RD maximum, then an interior raw-tone optimum with bounded width and
two nearby interior RX frequency optima. Original phase-model acceptance stays
separate; the selector does not accept a rejected phase range. Its inspection
value is the existing OS FFT peak. No threshold sweep, label fit, range blacklist
or default primary change was performed.

## Results

All 15,534 frames in eleven recordings reproduce frozen CA presence, selected
bin, fine range and reason. OS also matches original saved OS readings where
present. RD inputs come from the independently audited ten-recording joint
replay and the saved/audited paired-80 comparison. Hashes preserve provenance;
no RF/firmware calibration is inferred.

| Scored case | CA numeric | Old OS + RD | New weak inspection | Additional values when CA blank |
|---|---:|---:|---:|---:|
| All quiet target-absent windows, 3,045 frames | 0 | 774 | 0 | 0 |
| Dedicated empty A/B/A/B, 498 frames | 0 | 402 | 0 | 0 |
| Approximately 80 cm stationary failure, 714 frames | 0 | 332 | 297 | 297 |
| Repeated 50 cm miss, 218 frames | 0 | 218 | 4 | 4 |
| Bare cardboard repeated 50 cm, 177 frames | 126 | 177 | 63 | 8 |
| Bare cardboard 120 cm, 178 frames | 0 | 105 | **19** | **19** |
| Paired 80 cm/operator B target holds, 539 frames | 539 | 539 | 539 | 0 |
| Latest foil target holds, 657 frames | 657 | 657 | 657 | 0 |

Rows overlap; do not sum them. The hypothetical CA-first fallback in the report
is a counterfactual evaluation, not a live policy. Target-absent means the added
target is absent, not a reflector-free scene; these are not calibrated
false-obstacle probabilities.

The ~80 cm candidates have median 87.67 cm, 5th–95th 84.64–91.86 cm. All 297
retain original phase-model rejection. Their 20 output episodes have longest
16.4 nominal seconds. No values are held through misses; this is not verified
physical accuracy or continuous tracking.

The 120 cm correspondence case prevents a box-range claim: its 19 values have median
32.06 cm, 5th–95th 31.12–34.93 cm, two episodes, longest 1.3 s. All retain
raw-model rejection. Geometry does not identify which reflector changed when
the box was added. Deleting this failure by a distance blacklist is unjustified.
The first stepped 80 cm hold also gains 31 values around 105 cm. The selector
retains some old biased near holds and barely recovers the repeated-50 miss.
It improves candidate filtering without establishing an object-distance backend.

## Reproduce

[All metrics, settings and hashes](report.json) · [Eleven timelines](comparison.png) ·
[Frame decisions (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [Usage and method](../../docs/WEAK_CANDIDATE_EXPERIMENT.md)

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_weak_candidates \
  --output evidence/NEW-WEAK-CANDIDATES
```

The default RD sidecar is the preserved
`evidence/rx-diagnostics-20261111/results.jsonl.gz`; use `--rd-results` to
substitute another audited sidecar. Sidecar, saved readings, raw inputs,
configuration, source and scene manifests are hashed. Existing two-second
quiet interiors are primary; one-second variants and approximate operator
subwindows are not pooled. No timing offset was fitted.

These are development data, including scenes motivating the hypothesis,
not new independent validation. Quarter-bin RX agreement, half-bin width and
1%-energy near-optimal criteria were inherited unchanged from the phase study.
Global range-model rejection remains explicit. See the separate
[enabled-adapter review](../weak-candidates-live-20261111/README.md).
