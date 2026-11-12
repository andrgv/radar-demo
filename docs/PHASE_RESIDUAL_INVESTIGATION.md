# Residual signals and receiver disagreement

The next investigation is complete: a separated background component explains
part of the single-tone rejection, but does not reliably recover the target's
physical range. The remaining receiver disagreement and boundary/biased fits
prevent promoting this model to the live distance display. See
[the measured review](../evidence/phase-residuals-20261111/README.md).

## What was implemented

`tools/phase_residual_model.py` adds an offline diagnostic model with one shared
candidate frequency and one farther nuisance frequency per RX. Every retained
chirp/RX has its own DC/cosine/sine amplitudes. It uses the current frame only,
without an empty waveform, target labels, temporal smoothing or a prediction.

The candidate stays inside the original confirmed CA/OS group's half-bin
boundaries. The nuisance search starts one native bin beyond that support's
upper boundary and ends half a bin below Nyquist; it is not anchored to the
reported wall distance. It uses a fixed 1/16-bin nuisance grid and 1/64-bin
candidate grid, up to four alternating grid updates, then candidate refinement
inside the winning grid cell. Both data and sinusoid bases are projected off
DC; candidate bases are also projected off the nuisance span before the
conditional search. No filter/threshold setting was swept against these labels.

The output is explicitly `diagnostic_range_m`, with no accepted `range_m`.
It retains the unchanged single-tone decision, raw-energy residual, unique
candidate/nuisance energy contributions, conditional per-RX optima, RX spread,
support-boundary/competing-optimum flags, and grid convergence. Unique candidate
energy is the additional explained energy over a nuisance-only fit; a strong
background cannot turn its own explained energy into candidate evidence.

This is a deliberately limited far-background hypothesis, not a general
multi-object model. A lower training residual is expected with extra parameters.
It is neither independent validation nor a calibrated uncertainty, and its
nuisance grid can introduce additional estimation error. Nearby mixed returns,
non-sinusoidal response and source selection can remain unresolved. There is
no Doppler conditioning, so no fitted value is assigned to an RD feature ID.

## Evaluation and reproduction

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.investigate_phase_residuals \
  --output evidence/NEW-PHASE-RESIDUALS
```

The command audits frozen CA on every frame across the original development
set plus the independent foil repeat: 13,989 frames in ten recordings. It
compares presence, selected bin, fine range and reason to saved readings.
For the expensive diagnostic it selects every tenth frame from each existing
quiet interior, anchored at that window's beginning: 796 samples. These are
diagnostic samples, not a new full-frame detection-coverage result.

CA and OS fits require their own current confirmed group. A separately labeled
probe also runs across the fixed saved acquisition mask, including frames
without detection. That probe tests whether the model would invent or pin a
near-range optimum in empty/undetected scenes; it cannot supply presence.
Transitions and approximate operator subwindows are excluded. No scene window
was moved to improve the fit. Snapshot plots use the middle of each fixed
sampled set, rather than a favorable frame. Source, manifest, configuration
and raw-input hashes are preserved in the report.

## Findings and implementation decision

- In the fixed 50 cm A/B control, a fitted background near 2.2–2.3 m reduces
  median unexplained energy from about 67–70% to 39–41%. Yet 47/53 sampled
  candidate fits reach their support boundary, and the per-RX optimum span
  remains roughly 35 cm. Removing that background alone does not establish a
  common reliable range.
- The older biased nominal 50 cm holds remain near 59.5 and 64.2 cm after
  fitting the background. The first bare-cardboard hold moves to about 63 cm,
  rather than recovering the supplied 50 cm placement. Global residual
  improvement therefore cannot be used as a distance-accuracy gate.
- In the dedicated target-absent control, the fixed-mask probe reaches its
  artificial lower boundary in all 52 sampled frames, even though the
  two-component residual drops near 30%. That boundary is not a measured
  17 cm obstacle. The frozen detector still supplies no candidate there.
- The approximately 80 cm failure also remains undetected. Its diagnostic
  probe is unstable/boundary-sensitive despite substantially lower residuals.
  A better waveform fit does not repair the detection-stage miss.
- The foil estimates change relatively little. They remain useful controlled
  target measurements, but do not erase the older failures.

Keep the baseline, phase-fit quality gates and live policies unchanged. Do not
loosen the global residual threshold or expand candidate support to make this
model emit more distances. [Current-frame RX inspection](RX_DIAGNOSTICS.md) now
exposes receiver disagreement, unresolved peaks and waveform-model mismatch
beside existing measurements. Next investigate detection-stage candidate support
using the weak-target and empty controls. Any new selector must preserve missing
and ambiguous states and be evaluated across those controls before promotion.
There is no need for another identical foil hold capture for this step.

The receiver differences establish model/scene inconsistency; they do not prove
a defective RX, an RF calibration error, multipath, or a particular reflector's
identity. Distinguishing those physical causes may eventually require a changed
geometry control, rather than more repeats of the same room arrangement.
