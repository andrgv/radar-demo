# Motion-seeded weak support: inspection and stage review

Separate [weak-feature confirmation](WEAK_FEATURE_CONFIRMATION.md) now provides
stationary inspection IDs/history without requiring motion or changing this
link's strict rule. The user also clarified operator A / within range during
the bare-box 120 cm hold: its near return is operator-confounded, not an
established spurious obstacle or box range.

The strict motion-link prototype is implemented and replay-tested, and its
status is recorded/displayed under the existing `--experimental-weak` flag.
It adds only three isolated inspection points across 15,534 frames and **zero
additional scored stationary-hold frames**. It therefore does not replace or
supplement the main distance readout. Existing baseline, motion policy,
association and weak-candidate decisions remain unchanged.

## Rule

`radar_min/weak_motion.py` maintains a separate inspection state. It arms only
after two consecutive, same-sign, uniquely measured nonzero-Doppler frames of
the same confirmed feature, with current valid RD refinement and agreement
with the existing motion episode. This preserves the default episode selection
rather than substituting a different currently moving feature.

A zero-Doppler continuation additionally requires:

- The same current confirmed feature ID and a valid current Doppler-conditioned
  fine range, without a competing current mover.
- Current confirmed OS/raw-peak weak support identifying that exact RD native
  range/frequency peak, not just another return in the neighborhood.
- Agreement between its OS FFT estimate and RD fine range within half a native
  bin, inherited from the existing result-bank disagreement check.

The inspected value is the **current RD fine measurement**, not the OS scalar,
a rejected phase estimate, prediction or held range. Its original raw-model
acceptance/rejection stays explicit. A zero Doppler bin is not proof the world
object stopped; one new point occurs inside a labeled movement interval.

Sequence gaps, invalid/mismatched input, lost/missing/ambiguous feature state,
competing movers, unresolved refinement or an unsupported weak stop revoke
the seed immediately. Static reappearance cannot reseed it; new measured
motion must reconfirm. Already-supported current motion/strong stops retain
the seed but do not generate duplicate inspection points. These conservative
rules were fixed before replay and were not relaxed to increase coverage.

## Use and interpretation

Restart `rd-gui` and use the existing flag; no new flag or firmware is needed:

```sh
./range-v1 rd-gui --replay recordings/rd-gui-20261111-133435-428121/live-001 \
  --experimental-weak --view-range-bins 8
```

The weak-inspection label adds **motion link** state and the current RD stage,
such as **RD peak below birth margin** or **RD feature has no motion history**.
Its tooltip describes the exact current link reason. This explains why a
plausible weak candidate does not become a tracked/motion-linked measurement.
It does not change the large readout or add a smoothed history curve.

New enabled readings save `weak_motion_result` with current frame, state,
feature ID, reason, RD stage and optional inspection value. They explicitly
remain `inspection_only=true`, `primary_eligible=false`, `predicted=false`.
Metadata records the rule and source hash. Rejection/reset clears the state;
the optional label clears with the other stale/invalid measurements.

## What the data establish

The 120 cm hold's 19 operator-confounded ~32 cm candidates produce no linked
points. But neither do the 297 candidates in the ~80 cm stationary miss.
In that scored ~80 cm interior, 290 candidates are below the RD associator's
additional 3 dB track-birth margin; seven have valid refined static features
without motion history. All 19 near-range candidates are also below the birth
margin. Lowering that margin alone would admit both groups, not certify identity.

Across eleven recordings the only three linked points occur in two excluded
handling intervals and one slower-approach interval; each lasts one nominal
frame. Two already have a current baseline distance, leaving only one point
that adds a number where both baseline and existing motion output are blank.
There are no linked additions in 3,045 scored target-absent frames, and no new
settled-hold coverage. This is insufficient benefit for a live readout policy.

General stationary detection must remain possible without motion history.
The next investigation should separate **confirmation of weak scene features**
from **identification of the added object**, retaining both the weak ~80 cm
case and the wrong-range 120 cm case. Do not solve one by globally lowering
birth margins, bridging ambiguous IDs or holding an old distance. Another
identical stationary foil repeat is not needed to establish these limitations.

[Detailed replay and event review](../evidence/weak-motion-20261111/README.md) ·
[Live-adapter parity and GUI](../evidence/weak-motion-live-20261111/README.md)
