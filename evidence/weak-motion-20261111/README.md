# Motion-linked weak support: fixed-rule comparison

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

**Later clarification:** the operator was at A / within range during the
bare-box 120 cm hold. Its near return is an operator-confounded correspondence
case, not established as a spurious obstacle. This does not change the link
counts or rules; it changes their physical interpretation. See
[the subsequent feature-confirmation review](../weak-features-20261111/README.md).

The strict motion-seeded link is implemented and evaluated on all 15,534 frames
from eleven preserved recordings. It suppresses the known wrong-range weak
selection but provides no meaningful stopped-target coverage improvement.
It remains inspection-only; baseline, existing motion output, RD and original
weak selection are not changed. [Method and GUI usage](../../docs/WEAK_MOTION_LINK.md).

## Fixed protocol

Two consecutive same-ID/same-sign current confirmed and refined motion frames
must also agree with the existing motion episode to seed the link. A weak
zero-Doppler point then requires the same current confirmed feature, current
weak OS/raw-shape support at its exact RD peak, valid current RD refinement
and OS/RD agreement within half a native bin. The original phase range-model
rejection is not changed or bypassed as a range-estimator acceptance decision.

Any sequence gap, missing/ambiguous/lost feature, competing mover, invalid
input, unresolved refinement or unsupported weak stop revokes the seed.
Static data cannot restore it; new measured motion must reconfirm. Strong
current motion/stops preserve the episode without duplicating their readout.
No label fitting, gate sweep, stored background, prediction or held distance
was added. This is a development comparison, not independent validation.

The input is the previously audited enabled weak-adapter replay, pinned by
hash. Existing `motion_result` is checked for mutation. Host windows use the
same arrival timestamps and manifests without offset fitting; original
two-second quiet interiors are primary. All frame counts and reasons are
retained, including unscored handling.

## Outcome

| Scored case | Weak candidates before linking | Added linked points |
|---|---:|---:|
| All quiet target-absent windows, 3,045 frames | 0 | 0 |
| ~80 cm stationary failure, 714 frames | 297 | 0 |
| Bare-box 120 cm hold, 178 frames | 19 around 32 cm | 0 |
| All scored stationary target holds | See per-window report | 0 |
| Live-006 slower approach, 22 frames | See report | 1 |

The complete recording timelines contain only these three additional points
relative to the existing motion policy:

| Recording | Host time | Track | Current RD inspection | Baseline at same frame | Label context |
|---|---:|---:|---:|---:|---|
| `093723/live-003` | 19.820 s | 13 | 52.88 cm | 51.82 cm | Excluded placement handling |
| `093723/live-006` | 44.935 s | 1 | 80.77 cm | Blank | Scored slower approach |
| `141606/live-002` | 14.406 s | 13 | 51.39 cm | 52.64 cm | Buffer just after first approach, outside scored hold |

Each is a single nominal 0.1 s frame. Only one adds a number where both the
baseline and existing motion output are blank. There is no instantaneous
surveyed range label during movement/handling, so these are not accuracy
samples. Zero Doppler here is not proof of a physical stop. Full recording
paths, sequences, values and exact scored-window memberships are in
`report.json` under `linked_events`.

The hypothetically supplemented policy is only a comparison channel; it is
not used by the GUI primary or `--motion-aware`. Original output is preserved
where already numeric. Plot axes include the existing policy's farther scene
returns; per-window metrics are not restricted to the labeled target range.

## Measured bottleneck

Of the 297 scored weak ~80 cm candidates, **290 have RD disposition below the
track-birth margin**, while seven already have a valid static refined feature
with no nonzero-Doppler history. All 714 frames have no motion seed. The
capture starts with the object stationary; a linker must not invent a seed.

The **19 operator-confounded near-range candidates** in the 120 cm hold are also below the same
birth-margin guard and have no motion seed. Thus simply lowering the existing
additional 3 dB birth margin would admit useful-looking and misleading
candidates together. In the moving recordings, association loss/ambiguity,
unresolved refinement and absent weak support revoke the proof; waiting or
bridging them without new evidence would undo the removal-control safeguards.

Next separate weak-feature confirmation from physical object correspondence;
preserve these two counterexamples together. No new primary policy is
justified, and another identical foil hold capture is not the immediate need.

## Reproduce

[All windows/events/stages and hashes](report.json) · [Eleven timelines](comparison.png) ·
[Per-frame link states (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [Enabled-adapter parity](../weak-motion-live-20261111/README.md)

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_weak_motion \
  --output evidence/NEW-WEAK-MOTION
```

Default input is the preserved
`evidence/weak-candidates-live-20261111/results.jsonl.gz`; `--input` accepts
another audited enabled weak replay. Source, input, config, arrival and
manifest provenance is preserved. Synthetic tests exercise the supported
continuation, reference isolation, ambiguity/miss/loss, wrong/stale support,
range disagreement, gaps, invalid input and required motion reseeding.
