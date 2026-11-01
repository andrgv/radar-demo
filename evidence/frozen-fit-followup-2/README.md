# New stationary-sequence evaluation

Session gui-20261101-163602-348990. Labels follow the user-confirmed requested
order: independent empty, 30 cm, 40 cm, 50 cm, independent final empty.
No synchronized measurement of position or motion is available. All frames
were evaluated; no thresholds, reference windows or median settings were tuned.

| Recording | Frames | Existing GUI reports | Frozen trial reports |
|---|---:|---:|---:|
| Empty before | 214 | 0 | 0 |
| 30 cm | 295 | 0 | 0 |
| 40 cm | 260 | 0 | 0 |
| 50 cm | 278 | 0 | 1, at 58.68 cm |
| Empty after | 254 | 0 | 0 |

The frozen fit-based trial uses the earlier threshold vector [2,0,999,0.1],
three-frame confirmation and causal median of up to five candidates. Its
reference and energy calibration come from the first 20 and following 10
frames of this session's empty capture. Existing GUI replay matches every
saved detection and displayed-distance decision.

All five streams have zero reported CRC errors, gaps, restarts or rejected
frames. Partial packet tails at stop are retained in capture summaries and
are not interpreted as complete measurements. This is not a serial dropout.

Existing rejection reasons are overwhelmingly no_candidate_above_noise.
For the trial, the fitted-energy ratio must reach 2. Among frames with a fitted
candidate, median ratios are 0.73 at 30 cm, 0.95 at 40 cm and 0.43 at 50 cm.
Only 0, 1 and 6 frames respectively reach 2, before stability/confirmation.
The initial independent empty's 95th percentile ratio is 0.98, illustrating
overlap; these are engineering scores, not SNR or probability estimates.

Rejected candidate medians are approximately 26.4, 42.8 and 51.8 cm for the
three target records. Those are not accepted distances or certified accuracy.
This result establishes failure of the tested detector settings across the new
background, not proof that the hardware contains no target information or that
a uniquely identified physical cause explains the failure.

Reproduce from wavvy-range-v1:

```sh
MPLCONFIGDIR=/tmp/wavvy-mpl OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.evaluate_frozen_followup --session recordings/gui-20261101-163602-348990 --output evidence/frozen-fit-followup-2 --sequence stationary-five
```

report.json contains hashes, full metrics and transport summaries. frames.jsonl
retains every trial candidate and output. rejection-diagnostics.json summarizes
gate failures. No firmware, GUI, detector defaults or recordings were changed.

Next useful software analysis is calibration sensitivity and overlap of empty
versus target fitted signals using these saved recordings; no repeated capture
is needed to reproduce this failure. Any lower threshold must be assessed on
all earlier independent empty and close-target records, not only this session.
