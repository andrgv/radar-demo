# Conservative association of 2D CFAR features

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

[First-run tracks](first-tracks.png) · [Follow-up tracks](followup-tracks.png) ·
[Numeric audit](summary.json) · [Algorithm/CLI](../../docs/RANGE_DOPPLER_ASSOCIATION.md)

The optional replay association layer is implemented and evaluated on both
AVG16 motion recordings, using the same initial association settings in both.
The original CFAR source, settings, accepted masks and thresholds are unchanged;
the review checks the arrays against the earlier saved replays exactly.
No background reference, range blacklist, distance calibration or firmware
change is involved.

## What is now available

- Persistent feature IDs with tentative, measured, ambiguous, missed and lost
  states. IDs are radar-feature hypotheses, not certified object identities.
- Three consecutive peaks with at least 3 dB headroom above CFAR to seed/confirm.
  Confirmed features may continue on a weaker accepted current peak.
- Reciprocal unique-best native-bin association, gated at one range bin and
  two Doppler bins, with cost ambiguity gap 0.25. Doppler edge policy follows
  CFAR; range never wraps. Distinct peaks within one connected component can
  have separate IDs.
- Current accepted-cell support for unresolved/merged features. It cannot seed
  or confirm a feature, move its anchor, or renew its age since the last peak.
  Support/competition expires after five frames without a unique peak; no
  support expires after two. Tentative confirmation fails immediately when
  quality or uniqueness is interrupted.
- Current confirmed point measurements only. Ambiguous/missed/lost features
  have no measurement. There is no range prediction, smoothing or held point.
  The replay overlay shows measured IDs in cyan and ambiguous support in orange.

The audit covers all **1,754 frames** (605 + 1,149). Every published point is a
confirmed, current-frame accepted local maximum, with matching sequence and
no extrapolated point. Every ambiguous/missed/lost report has a null measurement;
every support cell is actually accepted in that frame. There are zero violations.

## Stationary-hold nuisance candidates

| Recording | Buffered hold frames | Frames with any raw nonzero local maximum, all ranges | Frames with any confirmed nonzero measurement, all ranges |
|---|---:|---:|---:|
| First, 120↔60 cm | 347 | 86 | 0 |
| Follow-up, 120↔30 cm | 464 | 120 | 0 |

This demonstrates rejection of weak/intermittent nonzero candidates in these
two development recordings. It is not a general false-alarm rate or object
accuracy measurement. Stationary clutter tracks are deliberately retained and
can confirm. Both recordings use a fixed radar; moving-robot behavior is not
validated here.

Both 30 cm holds retain a confirmed current zero-Doppler point in every buffered
frame (120/120 and 98/98). The first 60 cm hold also retains 65/65 points in the
original bins 2–4 analysis region. The second 60 cm hold still peaks mainly at
bin 1, outside that original region; the association layer does not relabel
that measurement as an accurate 60 cm observation.

## Motion coverage and the conservative tradeoff

Windows and analysis regions are inherited unchanged from the earlier reviews:
bins 2–4 in the first run, bins 1–4 in the follow-up. These regions score the
evidence only; CFAR and association process every usable range. Ambiguous
support can coexist with a measured feature elsewhere in the same region, so
the last column is not disjoint from the measurement column.

| Run / movement | Frames | Raw nonzero candidate frames in analysis region | Confirmed nonzero measurement frames | Ambiguous support frames |
|---|---:|---:|---:|---:|
| First approach 1 | 11 | 6 | 6 | 0 |
| First retreat 1 | 10 | 10 | 10 | 0 |
| First approach 2 | 9 | 6 | 5 | 4 |
| First retreat 2 | 10 | 8 | 7 | 0 |
| Follow-up fast approach | 13 | 9 | 8 | 2 |
| Follow-up fast retreat | 15 | 11 | 11 | 0 |
| Follow-up slow approach | 29 | 13 | **6** | **14** |
| Follow-up slow retreat | 32 | 19 | 19 | 1 |

The slow approach exposes the cost of quality and unambiguous-assignment gates:
some genuine motion-sensitive evidence is left tentative/ambiguous instead of
being published as a point. Settings were not retuned to increase that count.
Coverage here is not intended-target detection accuracy, and video timing
uncertainty from the previous reviews still applies.

The first run's feature ID 6 continues through its first approach, stop/near
hold and retreat; the follow-up's ID 47 continues through the first fast
motion/30 cm hold/retreat sequence. Other portions fragment into new IDs.
These are geometric feature associations only: in particular, the follow-up's
far hold often supplies a close bin-1 feature, not an isolated 120 cm return.
The same ID can therefore attach to different physical reflectors without a
cost tie. No cart/obstacle identity accuracy is claimed from ID continuity.

## Ambiguity, loss and target-absent controls

The follow-up final 120 cm hold produces confirmed zero-Doppler points in the
path region in only 7/67 frames, plus ambiguous support in 4 frames. Earlier
cell-level CFAR evidence exists throughout that hold, but the ridge is not
consistently separable into a target peak. The association layer expires the
unsupported hypothesis instead of displaying its old distance as fresh.
Association cannot recover an independently measured object from an unresolved
shoulder, or create an initial track without a local maximum.

In the follow-up initial target-absent window, zero-Doppler local maxima occur
in 28/121 frames in bins 1–4; confirmed zero-Doppler measurements remain in
8/121 frames. The conservative quiet post-removal interval has no measured
path-region output in 38 frames. The later operator-confounded interval retains
zero-Doppler measurements in 34/73 frames. These are scene features, not an
added-target presence decision. The layer does not suppress an operator or
classify a wall as harmless.

The first recording has 81 feature hypotheses, of which 12 confirm; the
follow-up has 178 hypotheses, of which 31 confirm. Most tentative hypotheses
expire on interrupted quality or persistence. Persistent clutter and ambiguous
physical identity remain unresolved even where a feature confirms.

## Verification and practical limits

Focused tests cover startup stationary confirmation, moving-to-zero continuity,
multiple maxima inside a merged component, competing tracks, bounded accepted
support, rejection of support-only births/confirmation, transient/weak peaks,
loss/reacquisition, Doppler wrap/truncate, no range wrap, timestamp wrap, invalid
maps/candidates, sequence/counter resets, JSON replay exports and unchanged CFAR
arrays. The prior CFAR and range–Doppler tests also pass.

Association computation is around 0.1 ms median on this machine, with larger
outliers recorded in the numeric report. This excludes serial/UI latency and
does not certify original host freshness. Outputs remain native bins and cycles
per saved block, with no calibrated meter or m/s estimate.

The next acceptance work should freeze a concrete output policy for ambiguous
features and compare on independent target/wall and operator-only controls.
Additional range/angle/scene information may be necessary for genuinely merged
stationary obstacles. The current replay layer is inspectable and ready for
that work, but it is not yet an autonomous obstacle decision.
Keep the current AVG16 firmware; no reflash is required.

Subsequently, a [live GUI adapter](../rd-live-gui-20261110/README.md) was added
and checked for exact processing parity with both saved replays. It preserves
these feature-identity limits and adds explicit host-quality/staleness clearing.

## Reproduce

Export directories must be new:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl-radar ./range-v1 range-doppler \
  recordings/avg16-motion-01 --detector cfar2d --associate \
  --output evidence/rd-association-20261110/first
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl-radar ./range-v1 range-doppler \
  recordings/gui-20261110-221227-169414/live-001 --detector cfar2d --associate \
  --output evidence/rd-association-20261110/followup
MPLCONFIGDIR=/private/tmp/mpl-radar .venv/bin/python -m tools.review_rd_association
```

The numeric report preserves association/CFAR/input/source hashes, all phase
summaries, observation dispositions, ended reasons and nonzero-to-zero ID
transitions. The latter include every such transition, not selected successes.
