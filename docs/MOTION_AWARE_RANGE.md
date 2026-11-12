# Experimental measured distance through motion and stopping

The later [weak motion-link investigation](WEAK_MOTION_LINK.md) adds separate
inspection status under `--experimental-weak`; it does not modify this v2
motion readout. Its strict continuity rule adds no scored stationary-hold
coverage in the preserved data, so no automatic weak-stop fallback is adopted.

The subsequent [sub-bin association investigation](SUBBIN_ASSOCIATION.md)
adds an optional cost metric for retreat ties and describes a targeted reflector
capture for the remaining biased-range problem.

`rd-gui --motion-aware` adds an experimental large readout driven by a unique
moving RD feature, while keeping the frozen 1D baseline visible underneath.
It does not smooth, extrapolate or hold a missed distance. Detector thresholds,
CFAR masks, feature association and fine-estimator rules are unchanged.

```sh
./range-v1 rd-gui \
  --replay recordings/gui-20261111-093723-246315/live-006 \
  --motion-aware --view-range-bins 8
```

Live use retains the current AVG16 firmware:

```sh
./range-v1 rd-gui --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL --motion-aware --view-range-bins 8
```

The OS flag is not required. Without `--motion-aware`, the main readout remains
the exact frozen 1D baseline. The experimental policy is computed and recorded
as `motion_result` on all shared-adapter readings so it can be compared offline.
Metadata also records which readout the GUI selected.

## Selection and clearing

**Stopped-support update (v2):** a new removal capture showed that a continuous
RD ID can shift onto a ~30 cm stationary scene return after the object is gone.
The stopped readout now additionally requires the current CA power at the RD
native range bin to exceed its reference threshold and be a local range maximum.
This uses the full usable CA profile, not just its scalar search mask, and does
not require the scalar detector to reconfirm. An unsupported stopped RD value
remains available for inspection but the large readout is blank with
`stopped_rd_without_current_range_support`. Nonzero-Doppler selection is
unchanged. This reduces weak stationary coverage; it is shared-data consistency,
not independent confirmation or validated object identity. See
[failure, replay correction and tradeoffs](../evidence/stopped-support-20261111/README.md).

Outside a motion episode, the policy uses the existing 1D fine measurement if
available. A stationary RD-only nuisance cannot seed an episode. Starting one
requires exactly one confirmed, current nonzero-Doppler RD feature, observed
for two consecutive frames with the same feature ID and phase sign. This extra
motion confirmation prevents one nonzero FFT-bin excursion from selecting a
previously stationary feature. Phase sign remains relative, not calibrated m/s.

Once selected, only that feature's current confirmed measurement can supply
distance, using its existing Doppler-conditioned fine refinement. It may
continue at zero Doppler when it stops, provided the same ID still has a unique
current measurement, valid fine range and the current range-profile support
described above. Neither an old position nor its
history of motion qualifies as a current measurement.

Competing current moving features, ambiguous/missing support, stale peak
sequence, boundary/competing fine fits and invalid timing/input withhold distance.
The policy does not jump to another reflector or substitute the baseline while
the active feature is missing. On track loss it publishes an explicit lost
frame with no point, then returns to baseline/possible new motion confirmation
on later frames. Rejections reset the episode and pending confirmation.

No detection-range mask is added to RD motion selection. Multiple confirmed
movers anywhere in the usable map can withhold selection; plot zoom does not
choose a target. This is a single-feature experimental readout, not multi-object
recognition, a calibrated obstacle detector or a moving-robot solution.

## History versus redraws

The worker now queues compact history summaries for every processed frame.
GUI history drains those summaries independently of the 4 Hz chart refresh.
Skipped redraws therefore do not create apparent algorithm misses. True sequence
gaps and withheld measurements remain gaps. Source/feature changes break the
experimental history line so it does not connect different identities as a
single smooth trajectory. Histories are measured values, not predictions.

`motion_result` records current frame, experimental range or null, source
(`RD motion`, `RD stopped`, or frozen baseline), feature ID, state and a reason.
`predicted` is always false. The existing `results.primary`, top-level baseline
range fields and standalone detector outputs are preserved for comparison.

## Evidence and limits

The [first labeled live motion check](../evidence/motion-aware-live-20261111/README.md)
has valid timing throughout. Across four movement interiors, numeric coverage
increases from 32/93 to 63/93 frames; retreat association losses and inconsistent
hold distances remain. This verifies live readout behavior, not physical-target
tracking or distance accuracy.

The motivating live-006 trace has confirmed refined signed RD peaks during
most movement frames where 1D either fails thresholding or is reconfirming.
The new policy can expose those measurements without waiting for 1D confirmation.
The trace tool reports raw peaks, confirmed features, refined points, policy
withholding reasons and baseline reasons separately.

Higher numeric coverage does not fix reflector identity or range bias. The
first and second near holds can still produce different ranges despite their
shared nominal 50 cm label. Operator/removal motion can also seed feature
episodes, and a feature can attach to a stationary scene reflector. Requiring
two consecutive same-sign measurements protects against a single-bin excursion
but cannot establish physical identity. The current replay has no output in
the scored empty interiors of live-003 or the live-005 operator-only control;
that is a finite regression result, not a general exclusion of such mistakes.
The feature ID and current measurement are algorithmic evidence, not proof
that the intended object remained selected. The mode stays opt-in.

[Replay comparison and failure cases](../evidence/motion-aware-joint-20261111/README.md)
preserve successful motion windows, missed placements and empty controls.
No broad new capture is needed for development. Before accepting this mode,
collect new labeled near/far passes, intermediate stops and matched operator-only
motion with fixed settings; score correct-reflector distance and misses together.

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --output evidence/NEW-MOTION-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_motion_range \
  --output evidence/NEW-MOTION-REVIEW
```
