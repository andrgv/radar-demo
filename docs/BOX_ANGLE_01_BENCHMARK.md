# Bottle position benchmark: box-angle-01

Primary recording: `recordings/box-angle-01`. The user identifies the target
as a long, narrow metal water bottle and the two supports as plastic boxes.
The directory's historical name does not mean the boxes are the target.

The manifest records a 23.5 cm upright bottle, antenna height 34 cm,
box dimensions 27.5 cm long and 5.5 cm thin, and 2 m forward distance.
Coordinates are right, forward, up, viewed from behind the radar. Labels use
the bottle's geometric midpoint; its radar scattering center may differ.

## What this tests

Ten stationary placements, each with a matched support-only background,
provide a benchmark for detecting target repositioning. They do not contain
a surveyed continuous trajectory and cannot establish tracking velocity,
latency, or continuity during movement.

- Horizontal movement: left/center/right at -30/0/+30 cm lateral offset,
  with the same two-flat-box support arrangement.
- Independent horizontal checks: check_left/check_right at -15/+15 cm.
- Height changes: down, center, and up, with independent check_down/check_up.
  Support geometry changes with height, so vertical comparisons also change
  the scene even though each pose has a matched background.
- Repeatability: center versus center_repeat.

Keep manifest `fit=false` poses held out from calibration and parameter tuning
when reporting held-out accuracy. If used for tuning, report them as development
data and obtain new independent captures for validation. Evaluate all poses,
including misses; never report accuracy only on favorable accepted returns.

## Baseline diagnostics (2026-11-12)

Reproduce from repository root:

```bash
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python tools/box_sweep_followup.py diagnose recordings/box-angle-01 --output evidence/box-angle-01-benchmark.json
```

Results: [JSON](../evidence/box-angle-01-benchmark.json) and
[plot](../evidence/box-angle-01-benchmark.png).

The existing sweep quality gate accepts 5/10 poses: up, check_right,
check_left, check_up, and center_repeat. It rejects center, left, right,
down, and check_down. This is quality-gate coverage, not detection accuracy.

For the same-support check_left → check_right pair, measured RX2/RX3 phase
changes are -26.7/-14.5 degrees versus 0.0/-25.3 predicted by the configured
geometry. Left → right gives -64.6/-22.4 versus 0.0/-50.2 degrees.
Center → center_repeat changes +3.7/-7.3 degrees despite identical labels.
These observations support using this dataset to expose failures, but do not
validate the current angular model. They do not uniquely identify a cause.

Future processing comparisons should report per-pose acceptance, position
error against measured labels, horizontal and vertical ordering, and center
repeat drift. Separate same-support horizontal comparisons from changing-
support vertical comparisons. Preserve raw recordings and matched backgrounds.
Continuous-motion performance needs a separate recording with time-aligned
position ground truth.
