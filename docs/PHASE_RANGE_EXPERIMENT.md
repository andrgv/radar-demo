# Candidate-constrained phase-aware range experiment

The follow-up [residual/RX investigation](PHASE_RESIDUAL_INVESTIGATION.md) is now
complete. A separate farther component reduces unexplained energy, but does
not resolve biased/boundary estimates or receiver disagreement. Lower residual
alone is unsuitable as an acceptance gate, and live output remains unchanged.

The raw real-tone/DC estimator and saved-data comparison are implemented.
The result supports a near-range FFT peak-bias explanation for the foil-box
repeat, but does **not** support replacing the live distance estimator. Range
comparison remains offline; the original phase acceptance/rejection, motion
policy, firmware and frozen detectors are unchanged. The separate optional
[weak-candidate inspection](WEAK_CANDIDATE_EXPERIMENT.md) reuses raw peak geometry
without accepting rejected phase ranges. See the
[comparison review](../evidence/phase-range-20261111/REVIEW.md).

The subsequent independent foil-box repeat also accepts every scored hold:
phase medians 51.4 / 48.6 / 122.1 cm versus baseline 48.0 / 49.2 / 124.2 cm,
with 657/657 target outputs and 0/520 scored empty outputs. It improves two
placement comparisons and slightly worsens the second near hold; it does not
resolve the earlier general-scene failures. See the
[repeat review](../evidence/foil-box-repeat-20261111/README.md) and
[setup/timing catalog](CAPTURE_CATALOG.md).

## Method and decisions

`radar_min/phase_range.py` fits one shared fast-time frequency to the current
retained ADC traces. Each chirp/RX has its own DC, cosine and sine coefficients.
Both data and basis are projected off DC before least squares. This avoids
assuming the maximum of a windowed real FFT is the actual sinusoid frequency,
particularly near DC where its positive/negative frequency components overlap.
There is no Hann window, empty-scene subtraction, label fit or smoothing.

The caller must first supply a confirmed current contiguous CFAR group. The
frequency search stays inside that group's half-bin boundaries. It cannot
recover missing detections, and it does not establish which physical reflector
produced a return. It combines raw traces without selecting a Doppler component;
its result cannot be copied into individual RD feature rows.

The initial quality settings were fixed before the nine-recording comparison:

- Reject an optimum at either support boundary or comparable competing optima.
- Require the fit to explain at least half the centered trace energy.
- Require the near-optimal frequency span to be at most half a native range bin.
  Near-optimal means within 1% of total centered energy of the best fit.
- Require at least two RX fits to be interior, explain half that RX's centered
  energy and lie within a quarter native bin of the shared fit.

These are empirical model checks, not calibrated confidence intervals or proof
of target identity. RX observations share the scene and are not independent
confirmations. Rejected results have `range_m=null`; a provisional fit and its
reason remain available for investigation. The model does not improve the
approximately 35 cm native bin spacing or resolve arbitrary nearby reflectors.

## Replay

From the repository root, using the existing Python environment:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_phase_range \
  --output evidence/phase-range-repeat
```

Choose a new output directory. The command compares nine preserved recordings
(11,623 frames), independently replays frozen CA and optional OS, checks CA
decisions against saved readings, and fits only their current confirmed groups.
It writes frame decisions, rejection reasons, coverage, output episodes, range
percentiles, conditional placement differences, source/input hashes and a
timeline figure. Placement labels are used only for scoring after estimation.
The two-second-trimmed interiors use the existing scene manifests; motion
intervals remain explicitly labeled. No threshold sweep is performed.

Use `--manifest configs/foil-box-repeat-20261111.json` to evaluate only the new
repeat (or supply several scene-manifest paths). The default comparison keeps
its original development set. Use a fresh output directory for each evaluation.

## Findings and next capture

The foil-box hold medians change from 51.4 / 38.1 / 122.7 cm to
50.7 / 46.7 / 122.9 cm, with complete numeric coverage in each scored hold.
That is useful evidence for phase-dependent near-range peak bias, rather than
a single constant distance offset. However, the same settings reject all 513
scored fixed-target operator A/B frames and every baseline detection in the
bare-cardboard holds. Some accepted older holds remain biased near 59 or 64 cm
for nominal 50 cm. Relaxing the gates just to produce distances would hide this
model mismatch. The current single-tone model is unsuitable as a universal
replacement or a solution for motion dropouts.

No additional data was needed to build and assess this experiment. The
**independent repeat of the foil-box test** below has now been collected in
`rd-gui-20261111-200448-409110/live-002` and reviewed above. Another identical
stationary repeat is not required before residual-model investigation. The
protocol is retained for future regression captures with unchanged
settings: empty 20 s, foil-front box at measured 50 cm for 20 s, empty 15 s,
repeat 50 cm for 20 s, empty 15 s, 120 cm for 20 s, final empty 15 s. Take as
much transition time as needed and label it separately. Keep the operator in
position B during every hold; keep sensor/box height and box orientation fixed.
Use the current live recording command from [the joint GUI guide](JOINT_RANGE_DOPPLER.md),
and save raw frames as usual; there is no new live phase-estimator flag.

Measure antenna face to foil face, mark the placements, and provide hold/transition
times. Note box angle and any obvious changes to foil flatness or surrounding
objects. This tests repeatability on new data, without selecting settings from
its labels. Further work should investigate residual scene components and
reflector selection before adding a more flexible multi-return model or
promoting a number to the demo display.
