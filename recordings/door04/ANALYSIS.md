# Door04: 25-inch follow-up

Analyzed 2026-11-07 with `python -m radar door-check-analyze recordings/door04`.
Manifest distance: 25 inches (0.635 m). Treated as the same-door distance follow-up
based on conversation; the recording notes are empty, so door identity and other
geometry changes are not independently documented.

All six recordings passed the implemented quality checks: 303 frames and 30.2
sensor seconds each (1,818 frames total). The continuous transport log has zero
gaps, CRC errors, bad headers, restarts, and discarded bytes throughout.

## Within-position evidence

Using the first two pairs only, the workflow selected bin 16, with a median
closed-minus-open change of -13.52 dB. The final pair showed -13.66 dB at that bin.
Frozen signed scores against the training open median were -0.33 dB (open) and
13.34 dB (closed), with a 3 dB threshold. The final open recording was rejected
and the closed recording detected. This is recording-level evaluation with one
pair, not a general accuracy estimate.

The provisional bin nearest the measured glass position is bin 2 (0.695 m).
Its training change was -0.76 dB and held-out change -0.71 dB, below the 3 dB
threshold. The selected bin's provisional coordinate is 5.56 m, not a measured
glass distance. Thus this is again evidence of a repeatable scene change, not
direct localization of the pane. Background attenuation/path changes remain
hypotheses; moving frame/handle and other scene changes remain confounds.

## Comparison with the 44-inch experiment

At 44 inches, the independently selected bin was 18, with a training reduction
of 9.89 dB and final-pair reduction of 10.33 dB. At 25 inches the selected bin
changed to 16, and the change at bin 18 remained large (-10.53 dB training,
-11.09 dB held out). These are changes in scene spectra, not proof of target
range tracking or range calibration.

Applying the original 44-inch bin-18 reference, direction and 3 dB threshold to
the 25-inch recordings WITHOUT refitting gives:

| Recording | Signed change score (dB) | Original rule detects closed |
|---|---:|---|
| open-01 | 6.64 | Yes (false detection) |
| closed-01 | 16.95 | Yes |
| open-02 | 6.72 | Yes (false detection) |
| closed-02 | 17.48 | Yes |
| open-03 | 6.02 | Yes (false detection) |
| closed-03 | 17.11 | Yes |

The detector separates door states after fitting a fresh reference at each
position, but the original absolute reference fails on all three new open
recordings. This is direct evidence that this particular reference-based rule
does not transfer to the changed setup. It must not be presented as a portable
glass-obstacle detector. No thresholds were changed for this comparison.

Next: collect another glass door with a fresh open reference and repeated pairs,
documenting door identity, distance, angle, and background in notes. Preserve
these experiments for comparison. A deployable obstacle detector will require
further work to separate material/surface evidence from background geometry;
fresh-reference door-state success alone does not solve that problem.

Artifacts: `door-check-report.json`, `door-profiles.csv`, `door-profiles.png`.
