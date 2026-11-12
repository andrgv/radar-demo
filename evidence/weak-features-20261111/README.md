# Separate confirmation of weak scene features

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Implemented one fixed rule confirming consecutive OS/RD/raw-shape-supported
current peaks into an inspection-only `weak:` namespace. The original strong
RD birth margin, masks, association, motion policies, range estimators and
primary outputs are unchanged. This confirms scene features, not objects.
See [method/use](../../docs/WEAK_FEATURE_CONFIRMATION.md).

## Fixed comparison

All 15,534 frames in eleven recordings were processed from the previously
audited weak-motion adapter readings. Settings inherit the existing association
confirmation count/native gates and Doppler edge policy. The existing RD
refinement isolation guard rejects nearby competitors, and unresolved strong
association dispositions are not overridden. Confirmation resets immediately
on gaps/missing/ambiguous/invalid support; no old point or ID is revived.

No threshold/rank sweep, label fit, background learning, region blacklist,
distance correction or primary promotion was performed. The original phase
model's acceptance/rejection is retained. Original result bank, association,
motion and weak-selection objects are checked for mutation. Scoring uses the
existing host-time manifests, with two-second quiet trims and no fitted offset.
State is processed through full recordings, not restarted at scoring boundaries.

| Scored case | Eligible weak frames | Confirmed weak-feature frames | Median inspection range |
|---|---:|---:|---:|
| ~80 cm stationary failure, 714 frames | 297 | 267 | 87.72 cm |
| All target-absent windows, 3,045 frames | 0 | 0 | — |
| Bare-box 120 cm hold, 178 frames | 19 | 15 | 31.83 cm |
| Repeated 50 cm miss, 218 frames | 4 | 0 | — |
| Bare-box repeated 50 cm, 177 frames | 63 | 51 | 52.22 cm |
| Paired 80 cm/operator B holds, 539 frames | 539 | 539 | Per-hold report |
| Latest foil holds, 657 frames | 657 | 657 | Per-hold report |

Rows overlap in scope and must not be summed as independent samples. The
~80 cm case retains about 90% of eligible candidate frames; its eight confirmed
episodes have longest duration 16.2 nominal seconds and 5th–95th range
84.82–91.68 cm. Gaps remain gaps. Its baseline stays blank. Confirmation gives
a persistent scene-feature inspection without certifying the supplied target
or calibrated front-surface accuracy.

The 120 cm hold has two confirmed episodes (longest 1.1 s), 5th–95th range
31.04–34.96 cm. **Later user clarification: operator was at position A / within
range during this hold.** The near return is therefore confounded with another
potentially nearer object, not a demonstrated false-obstacle output. It is not
established as the box return either. Counts remain unchanged; no rule used
this later clarification. The capture catalog preserves the new physical fact
separately from the original frozen timing manifests.

Persistence also preserves biased older outputs: the original repeated-50
first hold stays near 58.4 cm, and the old foil repeat remains near 38.4 cm.
The four sporadic candidates in the repeated-50 miss do not survive three
consecutive eligible frames. Thus this component improves feature confirmation,
not general recall, range accuracy or physical object correspondence.

Zero empty outputs are inherited from the weak-candidate prerequisite; they
are not independent validation of the confirmation stage or a calibrated Pfa.
Data remain developmental. A new bare-box 80/120 cm capture with the operator
at B, including matched empty intervals, is the useful next validation.

## Reproduce

[Full metrics/settings/hashes](report.json) · [Eleven timelines](comparison.png) ·
[Per-frame IDs and confirmation (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [Enabled adapter review](../weak-features-live-20261111/README.md)

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_weak_features \
  --output evidence/NEW-WEAK-FEATURES
```

Default input is the preserved
`evidence/weak-motion-live-20261111/results.jsonl.gz` and its adjacent audited
`report.json`. `--input` accepts another audited equivalent; its report supplies
the actual association settings. Input, upstream audit, config, arrivals, source
and timing manifests are pinned by hash. Synthetic tests cover low-margin
stationary confirmation, rejected model preservation, gaps/loss, strong and raw
ambiguity, native gates/Doppler wrap, stale support and original CFAR requirements.
