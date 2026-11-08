# Second door, door07

Analyzed 2026-11-07 with `python -m radar door-check-analyze recordings/door07`.
User identifies this as another door. Manifest distance: 60 inches (1.524 m).
Notes are empty; door composition, frame, angle and background are undocumented.

## Quality

All six recordings passed implemented frame/config, continuity, ADC container
rail, and sensor/host timing checks. There are 1,821 frames total: 303 each in
open-01, closed-01 and open-02; 304 each in the other recordings. Sensor spans
are 30.2–30.3 seconds. Continuous transport counters remain zero for gaps, CRC
errors, bad headers, restarts and discarded bytes. These checks do not exclude
changes to physical scene geometry or people in the beam.

## Frozen selected rule fails the held-out open control

The first two pairs selected bin 7, with closed-minus-open changes +13.10 and
+12.62 dB. This direction differs from the strong later-bin reductions observed
on the first door. The final pair showed +6.28 dB at bin 7, but its open-state
power also shifted upward relative to the training open reference.

Using the unchanged 3 dB threshold and training reference, final-pair scores were
4.20 dB (open) and 10.49 dB (closed). Both were detected as closed. Therefore this
experiment fails its held-out open-control check, despite a clear paired change.
Do not describe the selected detector as successfully separating this door's
held-out states. The cause of the open-reference shift is not established.

## Evidence near the measured pane distance

The 60-inch measured distance lies between provisional bin centers 4 (1.390 m)
and 5 (1.738 m). At these bins, training median closed-minus-open changes were
+8.99 and +11.97 dB; held-out paired changes were +12.72 and +17.25 dB.
These increases make the neighborhood a candidate for follow-up surface-return
analysis, unlike the near-pane regions in door03 and door04. They do not prove
glass attribution, target ownership or calibrated distance. Frame/handle and
multipath remain confounds. Selecting these bins after examining this evaluation
pair is exploratory and requires NEW independent evaluation recordings.

## Cross-door transfer

Applying either first-door detector without refitting its bin, reference or
threshold marks all six new recordings closed, including all three open controls.
The door03 signed scores are 6.88–11.29 dB; door04 scores are 9.48–17.45 dB;
both have frozen thresholds of 3 dB. Neither absolute-reference rule transfers.

## Next step

Keep the radar fixed at this door and repeat with a fresh directory, documenting
the door and angle in notes. Keep people clear and the open door at the same
position every time. Treat bins 4–5 as a follow-up hypothesis, not a validated
detector. Use new data for any revised rule's evaluation and preserve this failed
open-control result. A repeat can test whether the open baseline shift recurs;
it cannot by itself isolate glass from frame/handle or background effects.

Artifacts: `door-check-report.json`, `door-profiles.csv`, `door-profiles.png`.
