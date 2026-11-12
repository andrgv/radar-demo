# Experimental measured-only motion readout

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The replay audit covers 4,764 frames from live-003 through live-006. The frozen
1D outputs and independent RD masks/association are unchanged. The opt-in
`--motion-aware` readout uses one current refined RD feature through movement
and a same-ID supported stop; it publishes no held or predicted measurement.

## Motion-frame trace

The live-006 analysis uses the supplied windows trimmed by 0.2 seconds per
side. Counts are numeric output coverage, not correct-object detection accuracy.

| Movement | Frames | 1D numeric | Refined expected-sign RD frames | Experimental readout |
|---|---:|---:|---:|---:|
| Faster approach | 11 | 0 | 10 | 10 |
| Faster retreat | 11 | 5 | 9 | 10 |
| Slower approach | 22 | 11 | 18 | 21 |
| Slower retreat | 23 | 13 | 17 | 23 |

Some experimental points in a motion window are current zero-Doppler
measurements of the already selected ID near start/stop, so that column can
exceed nonzero expected-sign counts. Gaps include missed feature support and
one boundary refinement. They are not filled from old positions or the baseline.

At the first 50 cm hold, coverage rises from 25/97 to 97/97; at the middle
120 cm hold it rises from 8/105 to 105/105. The near-hold distance bias remains:
the first hold follows a bin-1 feature, unlike the second hold's bin-2 feature.
More complete output does not establish the correct physical reflector or fix
the previously observed inconsistent nominal-distance estimates.

## Controls and tradeoffs

The policy requires two consecutive current measurements of the same unique
confirmed nonzero-Doppler feature with the same sign before starting an episode.
This prevents a single nonzero-bin excursion from selecting a stationary track.
Stationary RD-only features cannot initiate a motion episode. Inside an episode,
current zero-Doppler measurements may continue the selected ID; misses,
competition and ambiguous/unresolved refinement withhold its distance.

- live-003: all four scored empty interiors remain blank. The failed second
  50 cm placement remains 0/218 because it supplies no qualifying motion episode
  or baseline. This mode does not solve stationary-from-start detection.
- live-004: the fixed-target A/B control preserves the baseline measurements;
  no RD motion episode is seeded.
- live-005: all 867 frames remain blank, despite the stationary RD nuisance.
- live-006: whole-recording numeric coverage changes from 468/757 to 742/757.

An earlier single-motion-frame trial could attach to clutter following operator
movement. The extra two-frame same-sign confirmation rejects that observed
excursion in these regression cases. It is a fixed motion-evidence rule, not
a calibrated false-alarm probability or proof that operator motion cannot seed
future episodes. Physical identity and new-scene acceptance remain open.

## Implementation and verification

Both algorithms still run on every frame. The baseline primary fields remain
unchanged, and `motion_result` separately records the experimental measurement,
source, feature ID, state and withholding reason. The GUI flag selects the
experimental large readout with a persistent baseline comparison below it.
Source/identity changes break history lines, and queued per-frame summaries
prevent skipped 4 Hz redraws from appearing as algorithm misses.

157 tests pass, including two-frame sign/ID confirmation, stopping with a new
current measurement, competing movers, no stale/held substitution, loss,
invalid/mismatched sequences, stationary-nuisance non-seeding, GUI clearing,
and preservation of all processed history frames through skipped redraws.
Live hardware verification of the new readout remains to be collected; no
firmware or threshold changes were made.

[Comparison timeline](motion-comparison.png) · [Moving-frame UI](moving.png) ·
[Stage-by-stage motion/window metrics](motion-review.json) ·
[Independent baseline/RD parity and source hashes](report.json) ·
[Usage and policy](../../docs/MOTION_AWARE_RANGE.md)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --output evidence/NEW-MOTION-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_motion_range \
  --output evidence/NEW-MOTION-REVIEW
```
