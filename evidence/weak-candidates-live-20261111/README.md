# Optional live weak-candidate inspection

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

`rd-gui --experimental-weak` implies the original OS comparison and adds a
separate **Weak scene candidate (inspection only)** label. It records selection
and the original raw phase-model decision. Primary, motion-aware output,
candidate bank and default mode remain unchanged. This is not an automatic
object-distance fallback. Original-model rejection remains explicit even when
frequency-peak geometry supports a candidate.

The useful empty-control result and the 120 cm/32 cm failure are both preserved
in [the offline comparison](../weak-candidates-20261111/README.md). Missing,
multiple, boundary or unconfirmed support clears the comparison. Rejection,
timeout and stream reset clear current data; recovery must reconfirm. The mode
is disabled by default and requires no firmware change.

## Validation

The enabled live adapter is replayed on all 15,534 frames in eleven recordings.
CA matches saved and independent baseline decisions/ranges; the primary stays
equal to CA; RD masks and association match standalone RD; previously saved
joint result banks remain unchanged. Every optional selector result is compared
to the independently assembled offline review. Historical motion-policy version
differences are preserved, not introduced by this branch.

All 177 tests pass, covering boundary/broad/competing optima, stale/support
mismatch, insufficient RX geometry, preserved raw-model rejection, original
OS/RD confirmation requirements, optional parity, rejection/recovery and GUI
clearing. No new hardware capture or serial/clock timing qualification was made.

[Joint audit](report.json) · [Framewise live/offline comparison](live-comparison.json) ·
[Enabled adapter readings (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [Illustrative weak 80 cm frame](weak80-gui.png) ·
[Illustrative wrong-range scene return](wrong-return-gui.png)

Screenshots illustrate eligible frames, not unbiased coverage samples. Replay
indices are 401 (~39.85 s) in
`recordings/rd-gui-20261111-133435-428121/live-001` and 1309 (~130.08 s) in
`recordings/rd-gui-20261111-143819-360020/live-003`. Whole-window coverage and
failures are measured separately, not inferred from screenshots.

## Reproduce

Run `tools.evaluate_joint_results --experimental-weak` with the recording paths
in `report.json`, in their listed order, and a fresh output directory. Compare
with a fresh offline weak-candidate review:

```sh
.venv/bin/python -m tools.review_weak_live \
  --offline evidence/NEW-WEAK-CANDIDATES --live evidence/NEW-WEAK-LIVE
```

[Usage and limits](../../docs/WEAK_CANDIDATE_EXPERIMENT.md) describes the next
motion-linked identity investigation. Another identical foil hold capture is
not needed first.
