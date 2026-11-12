# Motion-link inspection: live adapter and regression

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The existing `--experimental-weak` mode now records a separate
`weak_motion_result` and displays its link/association-stage status in the weak
inspection label. It does not replace the main distance, `motion_result`,
candidate bank or weak-candidate selection. There is no new firmware or flag.

The strict rule adds only three isolated inspection points over 15,534 frames
and zero scored stationary-hold points. Its useful result is a diagnosis of
the blocking stages, not a new range-readout policy. See
[the fixed-rule evaluation](../weak-motion-20261111/README.md).

## Validation

The enabled adapter is replayed on the same eleven recordings. Frozen baseline
decisions match saved and independent CA; RD masks and association match the
standalone algorithms; previously saved joint results remain unchanged.
Framewise comparison with the previous enabled weak replay checks that
`results`, `association`, `motion_result` and the existing weak selector are
unchanged, and that new link results exactly match the offline prototype.
Every linked point remains inspection-only and unpredicted.

All 183 tests pass, including six motion-link tests for current support,
revocation and motion reseeding. Optional-mode tests verify preserved default
results, invalid clearing, recorded current sequence and GUI clearing. The
snapshot is a replay of frame index 401 in
`recordings/rd-gui-20261111-133435-428121/live-001`; it illustrates an unseeded
weak candidate below the RD birth margin. It is not a coverage sample.
No new physical capture or live serial timing qualification was performed.

[Full joint audit](report.json) · [Framewise cached/offline/live parity](live-comparison.json) ·
[Enabled readings (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [GUI link status](link-status-gui.png) ·
[Usage and interpretation](../../docs/WEAK_MOTION_LINK.md)

## Reproduce

Run `tools.evaluate_joint_results --experimental-weak` with the recording paths
from `report.json`, in their listed order, into a fresh output directory.
Run `tools.evaluate_weak_motion` on the preserved prior weak replay into a
separate fresh directory. Then compare:

```sh
.venv/bin/python -m tools.review_weak_motion_live \
  --offline evidence/NEW-WEAK-MOTION --live evidence/NEW-WEAK-MOTION-LIVE
```

Use the documented input file or an equivalent audited previous weak replay;
the comparison pins it by hash and checks complete preserved output objects.
