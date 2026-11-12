# Raw-signal signature audit, fixed before the new run

Question: do elementary measurements around the surveyed pane range show a
repeatable closed-minus-open change with the same direction across setups?
This is a signal audit, not model training or glass-identity validation.

## Inputs and exclusions

- Use all complete door03, door04 and door07 experiments: three open/closed
  pairs per setup, 18 recordings. Door03 and door04 share one physical door;
  door07 is the second door according to the retained research notes. These
  are previously inspected development data, not a blind test.
- Explicitly list incomplete door experiments as excluded. Never substitute
  partial or missing captures for complete experiments.
- The archived window/drywall comparison is excluded from paired effects:
  corrected labels say the sensor faced different directions/backgrounds and
  the wall distance is unknown. Later user controls lack matched panel-absent
  scenes. They cannot isolate the effect of inserting glass.
- Surveyed distance defines the ROI, deliberately giving the analysis the
  pane location. This is not a deployable localization procedure. Unverified
  RF scale and unresolved returns can still put the pane outside that ROI.

## Processing and quality

Use the recorded configuration, uncorrected per-RX ADC, chirp-wise sample-mean
removal, Hann window, and native (uninterpolated) real FFT. Preserve stationary
energy. Reject config mismatch, ADC container rails, packet corruption,
sequence discontinuities, changed device counters, sensor timestamp faults,
arrival mismatches or relative host/device timing faults. Hash every recording
and check for identical ADC frames across recordings.

Skip the first ten frames; use consecutive nonoverlapping ten-frame windows,
discarding and reporting the final incomplete window. Each recording contributes
one median per metric; windows are retained for inspection, not counted as
independent trials. Check the requested recording duration.

The pane ROI comprises usable native bins within +/-1 bin of the nominal
surveyed pane coordinate. Reference bins lie >1 and <=5 bins from that same
coordinate, excluding DC and Nyquist; require at least three. Later energy uses
all usable bins beyond the upper edge of the ROI. Do not tune an ROI to a peak.

## Fixed measurements

For RX1, RX2, RX3 and equal-weight combined RX power:

1. Pane power: 10 log10 of mean power over ROI bins.
2. Local contrast: pane power / median reference-bin power, in dB.
3. Pane fraction: ROI energy / all usable range energy.
4. Later/pane ratio: energy after the ROI / ROI energy, in dB. This is a
   background/spectral-tail proxy, not an attributed transmission path.
5. Chirp stationary fraction: coherent chirp-mean energy / total chirp energy,
   integrated over the ROI and window. No verified velocity scale is needed.
6. Temporal CV: population standard deviation / mean of ROI power across the
   ten frames. Warm-up and short windows limit its interpretation.

For all three RX pairs, also measure ROI power-weighted cross-RX coherence:
sum over ROI bins of |mean(chirp,frame)[Xa conj(Xb)]| divided by the sum of
sqrt(mean |Xa|^2 mean |Xb|^2). It measures coherent scene energy, not material.
This yields 27 fixed metrics. Do not select a winning receiver, feature subset,
sign, cutoff, FFT scale or model using the observed results.

## Descriptive comparisons

For every metric export all six recording medians per setup, three paired
closed-minus-open effects, and every within-state repeat difference. Compare
the smallest absolute paired change with the largest within-state change;
require all three paired effects to have the same sign before calling this
strict descriptive repeatability criterion satisfied. Report overlap of the
open/closed recording ranges and recording-level rank AUC (higher means
closed). This is not an inferential significance test or an accuracy estimate.

Across setups report whether all nine paired effects share one sign, whether
the repeatability criterion holds in every setup, and whether any single
direction and threshold could separate all recording medians in this inspected
dataset. Do not report statistical confidence from correlated frames or three
repeats. Export whole-spectrum closed/open power differences as context so a
local effect is not mistaken for proof that the pane caused the change.

## Interpretation and next experiment

Even a common, repeatable effect identifies a candidate for controlled testing,
not glass. Moving a door also moves its frame/handle and changes occlusion and
multipath. No matched opaque-panel insertion control is present. Failure of
these fixed summaries does not establish impossibility of radar-only glass
recognition. The next capture must distinguish panel insertion from fixture,
background and generic material effects before adding another classifier.
