# Shared 1D / range–Doppler result diagnostics

`--experimental-weak` now includes [separate confirmation of weak scene
features](WEAK_FEATURE_CONFIRMATION.md), with `weak:` IDs, current inspection
range and a history trace that breaks on gaps/ID changes. Confirmation is not
physical target identity; it never changes the main or motion-aware readout.

`--experimental-weak` now also records/displays [motion-link and RD-stage
status](WEAK_MOTION_LINK.md), explaining why a weak candidate remains untracked
or lacks a motion seed. This adds no primary or motion-aware fallback.

The optional [weak-candidate inspection](WEAK_CANDIDATE_EXPERIMENT.md) is now
available with `--experimental-weak`. It implies the OS comparison and adds a
separate current candidate label, preserving raw-model rejection and known
wrong-reflector failures. It never feeds the primary or motion-aware distance.

The Results tab now includes [current-frame RX inspection](RX_DIAGNOSTICS.md):
per-receiver peaks/unresolved states, spread and waveform-model limitations.
These are recorded and clear with stale/invalid measurements; no extra flag is
needed. They do not change the existing distance policy.

Use [the capture catalog](CAPTURE_CATALOG.md) to find known physical setups,
scene-label manifests and saved acquisition/processing provenance for replay.

An offline [phase-aware range experiment](PHASE_RANGE_EXPERIMENT.md) now compares
raw-tone fits against the existing peak estimates. It improves one foil-box
repeat but fails broader target coverage checks, so it does not replace the
live readout. The separate weak-candidate experiment reuses peak geometry while
preserving the phase estimator's original acceptance/rejection decision.

For experimental current measurements through movement and stopping, use
[`--motion-aware`](MOTION_AWARE_RANGE.md). It keeps the baseline visible,
selects one motion-confirmed RD feature, and withholds misses rather than
predicting. It remains opt-in because operator/scene identity is unresolved.

An optional [clutter-reference experiment](CLUTTER_REFERENCE_EXPERIMENT.md) is
available with `--experimental-os`. It adds an inspection-only OS reference and
candidate selector; the default CA primary remains unchanged because the new
branch also admits target-absent scene features.

`rd-gui` now runs both frozen detectors on each accepted frame, builds a shared
candidate bank, and estimates experimental range separately for confirmed RD
features. No firmware change or new data collection is needed to try it.

```sh
./range-v1 rd-gui \
  --replay recordings/gui-20261111-093723-246315/live-006 \
  --view-range-bins 8
```

Live capture uses the same current AVG16 firmware and matching configuration:

```sh
./range-v1 rd-gui --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL --view-range-bins 8
```

Only one serial reader may run. **Start live + record** saves raw frames and
the combined diagnostics in the usual recording directory. Replay never opens
serial or creates a new live recording. The original `gui --detector cfar` and
`range-doppler --detector cfar2d --associate` remain standalone comparisons.

## Display policy

The **Results + comparison** tab contains:

- The exact current fine-distance output of the frozen nearest-group 1D baseline.
  It blanks across misses and faults. Its label explicitly says 1D baseline;
  no RD-only feature is automatically promoted to the large distance readout.
- A candidate table showing separate 1D and Doppler-conditioned fine estimates,
  source/confirmation states, motion evidence, association and decision reasons.
- Current 1D power/reference/threshold profiles and candidate peaks. Selecting
  a table row highlights its range support and shows its native RD Doppler slice.
- Recent processed-frame history for the 1D baseline and selected RD estimate.
  Gaps remain gaps; history is not smoothing or a held current measurement.
  The worker supplies per-frame history even when display redraws are skipped;
  replay snapshots also fill history from processed frames.

The **RD maps + feature states** tab retains full-map power, threshold margin,
accepted cells, raw maxima, measured IDs, ambiguous support and the original
native-bin feature table. Plot zoom never filters detections or candidate rows.

Select any candidate row to inspect its current estimates. Selection affects
only diagnostics. When that candidate loses current support, its inspection
readout clears; a different feature is not silently substituted. Historical
points remain labeled as history. Invalid/stale/mismatched frames clear current
plots, table and readouts together.

Plot/table refresh is capped at 4 Hz and only the visible tab's canvas redraws;
freshness is checked at 10 Hz. Every accepted sensor frame still runs through
both algorithms and is recorded. Rejection/stall clearing bypasses the display
cap. Plot artists are reused rather than rebuilding three axes every update.

If startup timing is rejected, current measurements clear while raw recording
continues. The quality line reports fit p95/max residuals when available.
Stop and start a new capture to retry the latched clock check; after a code
update, close and relaunch the GUI first. Timing limits are unchanged. See the
[November 11 timing investigation](../evidence/joint-gui-timing-20261111/README.md).

The fixed 1D defaults **in rd-gui** are guard 1, training/minimum 4 and multiplier
2, matching the qualification captures. Override with `--cfar-guard`,
`--cfar-training`, `--cfar-min-training`, `--cfar-factor` if intentionally testing
another preset. Original 1D command defaults remain unchanged. The saved
configuration supplies the 1D range mask and confirmation count; 2D processing
still tests every usable range bin. Existing `--rd-*` and `--track-*` settings
are unchanged and all settings/source hashes are saved.

## Candidate bank and range refinement

The frozen scalar 1D detector is preserved verbatim as `one_d`. The result bank
also consumes **all** its current candidate groups. Each group confirms with
the configured consecutive frame count using reciprocal unique overlapping
support and at most one-bin peak movement. A miss resets this supplementary
confirmation. Its group IDs and RD track IDs are feature hypotheses, not objects.

A 1D group merges with a current RD observation only when the RD peak lies in
its accepted range bins and the match is unique in both directions. Raw peaks
that have not confirmed still participate in ambiguity checks. Multiple RD
peaks within one 1D group remain separate hypotheses with an explicit ambiguous
cross-path association. No common range estimate is copied into those rows.
Both paths share ADC data, so agreement is not independent confirmation.

For confirmed current RD peaks, processing computes a dense fast-time Hann
spectrum, retains complex chirp/RX values, then applies the slow-time Hann FFT.
The candidate profile averages RX power and its peak Doppler row plus the two
neighboring rows. Doppler edge handling follows the existing wrap/truncate
setting. A nearby competing raw maximum (within one range bin and two Doppler
bins) withholds refinement rather than risk copying a stronger reflector.

Fine ranging uses only the candidate native range cell's half-bin boundaries.
Boundary maxima, comparable competing dense peaks and nonconcave fits remain
unresolved, using the existing fine-estimator rules. Confirmed 1D groups use
their own group support and the original integrated-power profile. The dense
transforms are shared across candidates per frame.

If both fine estimates exist, a difference greater than half a native range
bin is reported as disagreement and the bank's common estimate is withheld;
the separate source values and frozen baseline remain visible. This geometric
comparison is not a calibrated uncertainty bound. No source values are averaged.

Unconfirmed, missing and ambiguous RD hypotheses receive no RD fine measurement.
A uniquely matched confirmed 1D group may still have a current 1D estimate while
its RD evidence is confirming; the table labels both states separately.

## Recorded result fields

Each valid reading retains the original `association` and `cfar_clusters` and
adds `one_d` plus `results`:

- `results.candidates`: current support, source list, association reason, group
  confirmation and RD state/ID; separate `one_d_range_m`, `rd_range_m` and fine
  diagnostics; `range_method`, `experimental_range_m`, `primary_eligible`.
- `results.primary`: exact frozen 1D fine distance and source row ID, or null.
- `results.primary_policy`: explicit baseline-only automatic selection.

Top-level `experimental_range_m` mirrors the frozen baseline. `range_m` stays
null, calibration stays false, and motion is signed phase progression or
no resolved radial motion. No verified m/s, world motion, bearing or XY is added.

The target-absent RD bin-1 feature is intentionally retained as an inspection
result. Hiding it would disguise the existing detector's behavior. This milestone
improves traceability and per-feature estimation; it does not certify improved
physical-target recognition or select a new automatic obstacle policy.

## Regression and next validation

```sh
QT_QPA_PLATFORM=offscreen MPLCONFIGDIR=/private/tmp/radar-mpl \
  .venv/bin/python -m unittest discover -s tests_min -v
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --output evidence/NEW-JOINT-REVIEW
```

The audit exports compressed per-frame results, source/settings/input hashes,
timings and parity checks on live-003 through live-006. It compares each scalar
1D decision/fine estimate to saved live output and an independent baseline,
and compares every RD accepted mask and association with standalone processing.
These are development regression cases. After freezing a candidate primary
selection policy, new labeled placements, empty controls and motion/stop holds
must assess correct-reflector coverage and distance error together.
