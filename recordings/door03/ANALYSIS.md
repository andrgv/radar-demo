# Door03 analysis

Analyzed 2026-11-07 using `python -m radar door-check-analyze recordings/door03`.
Measured closed-glass distance: 44 inches (1.1176 m). Profile: HPF350.

## Data quality

All six recordings passed the implemented raw/config, continuity, container-rail,
and sensor/host timing checks. Each has 303 frames spanning 30.2 sensor seconds
(1,818 frames total). The saved continuous-stream transport log reports zero
gaps, CRC errors, bad headers, restarts, or discarded bytes throughout.
These checks do not independently verify RF configuration or physical calibration.

## Door-state result

The first two pairs selected bin 18 using only training data. Closing the door
reduced median power at this bin by 9.71 dB and 10.06 dB, respectively. Training
open medians differed by just 0.114 dB. The frozen change threshold was 3 dB.

The held-out final pair showed a 10.33 dB closed-minus-open reduction at bin 18.
Against the training open reference, its signed scores were -0.10 dB (open) and
10.23 dB (closed). The held-out open recording was correctly rejected and the
closed recording detected under the selected rule. This is one recording per
state in evaluation, not a general accuracy estimate.

Eight bins (13, 14, 15, 17, 18, 19, 26, 27) passed the training repeatability rule;
all correspond to reductions on closing. Adjacent bins are correlated and should
not be counted as eight independent observations.

## Obstacle interpretation

The measured pane distance falls between provisional bin centers 3 and 4.
Training median changes at those bins were +0.12 and -0.31 dB; held-out changes
were +0.65 and -0.64 dB. Neither passed the 3 dB threshold. Thus this analysis
does not demonstrate a directly localized glass return at the measured distance.

Bin 18 has a config-derived coordinate of 6.26 m, which must not be presented as
the pane's measured range. The strong reductions in later bins suggest changes
to background returns/path propagation when the door closes. Attenuation and
multipath are hypotheses; frame/handle movement and other scene changes have not
been excluded. No claim of glass material identification is justified yet.

## Next experiment

Keep this dataset as the original-position reference. Before tuning thresholds,
repeat the same door at a second measured sensor distance, keeping its orientation
and background otherwise as similar as possible. Use a fresh directory and record
any changed geometry in notes. Analyze the complete profile rather than assuming
bin 18 will remain useful. This tests whether the observed signature depends on
the current radar/background geometry. Then repeat on another glass door, with
independent open/closed recordings, to assess transfer beyond this scene.

Artifacts: `door-check-report.json`, `door-profiles.csv`, `door-profiles.png`.
