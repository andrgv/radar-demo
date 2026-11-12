# Independent foil-box repeat: live-002

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Recording: `recordings/rd-gui-20261111-200448-409110/live-002`.
The user explicitly confirmed the same foil-covered cardboard box, operator
at position B throughout quiet holds, and antenna-face to foil-face measurements.
The prior setup describes a roughly 45 × 24 cm front face and a wall a little
over 2 m away; placement uncertainty is a few cm. No estimator/detector settings
were changed for this new capture.

The stationary detection result is good for this setup: all 657 scored target
frames have a numeric baseline/motion readout, and all 520 scored target-absent
frames are blank. The phase-aware estimator also accepts all 657 target frames,
but does not improve every hold. This supports foil-target repeatability,
not general acceptance on bare boxes, arbitrary scenes or during movement.

## Quiet-interior results

Durations are cumulative from the first saved frame, with no fitted offset.
Handling is excluded and the following windows trim two further seconds from
each side. A/B in the manifest identify repeated holds, not operator positions;
the operator remained at B.

| Scored host interval | Scene | Baseline / frames | Baseline median cm | Phase-fit median cm | Phase-fit 5th–95th cm |
|---|---|---:|---:|---:|---:|
| 2.00–13.69 | Empty | 0/117 | — | — | — |
| 36.59–58.33 | First 50 cm | 219/219 | 47.97 | 51.37 | 51.11–51.54 |
| 73.92–89.60 | Empty | 0/158 | — | — | — |
| 112.33–133.91 | Repeated 50 cm | 217/217 | 49.24 | 48.61 | 47.68–49.43 |
| 150.99–163.47 | Empty | 0/126 | — | — | — |
| 180.11–202.04 | 120 cm | 221/221 | 124.23 | 122.14 | 121.91–122.36 |
| 216.83–228.62 | Empty | 0/119 | — | — | — |

Both baseline and phase-fit coverage are complete in each target interior.
Mean absolute placement differences change from 2.03 → 1.34 cm,
0.79 → 1.41 cm, and 4.26 → 2.14 cm respectively. The second near hold becomes
slightly worse by that metric. The baseline's two near medians differ by
1.27 cm, versus 2.75 cm for the phase fit. Neither estimator is consistently
superior in every near-range repeat, and few-cm placement uncertainty limits
physical accuracy claims.

The second 50 cm fit explains about 59% of centered raw energy and passes
the existing two-RX gate (two supported RX); the first and far holds explain
about 84% with three supported RX. These are the unchanged empirical gates,
not calibrated confidence. The previous foil run's 38 cm anomaly does not
recur in this repeat. Both foil recordings contain useful phase-fit estimates,
but the older nonfoil/general-scene
failures documented in [the development review](../phase-range-20261111/REVIEW.md)
still prevent a universal live replacement.

All scored motion-aware outputs equal the frozen baseline fallback. In the
second empty interval a stopped RD episode remains, but the current-range
support rule withholds all 158 values. That is useful repeat evidence that the
earlier stationary-clutter handoff is suppressed in this control. It does not
certify target identity during transitions.

The offline OS comparison produces 361 numeric peak outputs across these
520 empty frames, mainly around 1.4 m; none passes the phase-fit gates. The
CA baseline supplies no empty candidates, so CA-phase silence is inherited
from CA rather than an independent absence test. OS remains unpromoted.

## Timing, labels and audit

There are 2,366 saved frames spanning 234.968 host seconds. All are accepted;
there are no reported CRC/header failures, sequence gaps, restarts or timing
rejections. A 332-byte partial packet at stop is preserved separately. Startup
clock fitting uses 200 frames; p95/max fit residuals are 1.19/10.97 ms.
Post-freeze p95/max relative errors are 6.34/95.93 ms, within the separate
500 ms progress bound. The 50 ms startup p95 requirement is not a per-frame
post-freeze limit.

The supplied durations end at 230.62 s, leaving a 4.348 s recording tail
unlabeled and unscored. Full original segments, one/two-second trimmed windows,
scene facts and label provenance are in the
[scene manifest](../../configs/foil-box-repeat-20261111.json).

The joint audit reproduces saved baseline, RD and association results; the
motion-policy replay also agrees. The separate phase comparison asserts the
unchanged CA presence, selected bin, fine estimate and reason on every frame.
The phase fit remains offline; no firmware, threshold, tracking or display
policy changed. Transitions here are handling intervals, not a labeled smooth
trajectory test, so this run does not establish moving-distance continuity.

This capture is sufficient for the current repeatability check. Next software
work should inspect residual scene components and RX disagreement in the older
failed captures before designing a more flexible estimator; another identical
stationary repeat is not the immediate priority. Any future live phase display
should remain explicitly experimental and preserve the original readout and
rejection reasons until the broader failures are resolved.

[Joint replay audit](report.json) · [Motion/timing metrics](motion-review.json) ·
[Baseline/motion timeline](motion-comparison.png) · [Phase comparison](phase/README.md) ·
[Phase timeline](phase/comparison.png) · [Capture catalog](../../docs/CAPTURE_CATALOG.md)

## Reproduce

Use fresh output directories:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --recordings recordings/rd-gui-20261111-200448-409110/live-002 \
  --output evidence/NEW-FOIL-REPEAT
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_motion_range \
  --output evidence/NEW-FOIL-REPEAT --manifest configs/foil-box-repeat-20261111.json --hold-spectra
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_phase_range \
  --manifest configs/foil-box-repeat-20261111.json --output evidence/NEW-FOIL-REPEAT/phase
```
