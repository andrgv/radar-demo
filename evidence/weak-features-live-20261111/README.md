# Weak-feature confirmation in the live GUI

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The existing `--experimental-weak` mode now records `weak_feature_result` and
shows **Confirmed weak scene feature (inspection)** with a separate `weak:` ID,
current OS FFT fine range and consecutive-hit count. Confirmation has its own
history trace, with gaps and ID boundaries. It does not alter the large readout,
strong RD birth margin/tracks, candidate bank, motion policy, weak selector or
motion-link inspection. No firmware or additional flag is needed.

The ~80 cm failure now has 267 confirmed inspection frames in its 714-frame
quiet interval. The operator-A/120 cm hold also confirms 15 near-range samples,
so the display explicitly says **Target identity unverified**. The later
operator clarification makes that case physically confounded, not proven
spurious. [Complete comparison and limits](../weak-features-20261111/README.md).

## Verification

Enabled-adapter replay covers all 15,534 frames in eleven recordings. CA and
primary match saved/independent baseline; RD masks/association match standalone
processing; saved joint results remain unchanged. Comparison against the prior
cached weak-motion readings checks exact equality of result banks, association,
motion/weak-motion results, RX diagnostics and weak selection. New feature
results match the independent cached-data review on every frame.

All 188 tests pass. Tests exercise three consecutive supported measurements,
the additional OS confirmation latency, stationary low-margin features,
revocation/reconfirmation, native/Doppler-wrap gates, original CFAR support,
stale inputs and ambiguity. GUI tests cover clearing, matching measurement
sequence and breaking the history line between IDs. No held/predicted current
range is shown. No new live serial timing or physical accuracy qualification
was performed.

[Joint audit](report.json) · [Exact cached/offline/live parity](live-comparison.json) ·
[Enabled readings (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [Illustrative confirmed ~80 cm scene feature](confirmed80-gui.png) ·
[Illustrative operator-confounded near feature](wrong-feature-gui.png)

Screenshots are eligible-frame illustrations, not coverage samples. They use
replay indices 403 in `recordings/rd-gui-20261111-133435-428121/live-001` and
1309 in `recordings/rd-gui-20261111-143819-360020/live-003`. The latter file's
legacy "wrong" name refers to correspondence with the box; it does not establish
that the nearer feature is a false measurement. Full-window metrics include
all misses and confirmations, not just the illustrated frames.

## Reproduce

Run `tools.evaluate_joint_results --experimental-weak` with the recording paths
in `report.json`, in their listed order, into a fresh output directory. Run
`tools.evaluate_weak_features` with the preserved previous audited weak-motion
readings into a separate fresh directory. Then compare:

```sh
.venv/bin/python -m tools.review_weak_features_live \
  --offline evidence/NEW-WEAK-FEATURES --live evidence/NEW-WEAK-FEATURES-LIVE
```

[Usage and clean operator-B capture protocol](../../docs/WEAK_FEATURE_CONFIRMATION.md)
