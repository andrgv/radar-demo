# Fixed-position bare → foil → bare control

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Recording: `recordings/rd-gui-20261112-094114-038104/live-001`.
The user reports all target holds at **50 cm**, operator **B** throughout quiet
captures, and explicitly confirms the **box footprint and orientation stayed
fixed while only foil was added/removed**. Earlier dimensions (about 45 × 24 cm),
antenna/front-face measurement convention and wall a little over 2 m are prior
setup context; this message does not remeasure them. No other changes reported.

**The foil produces a clear, physically plausible range response, while the
bare-box response remains mixed and cannot be reliably identified as the
50 cm front face. Temporal weak-feature confirmation is not sufficient.**
No thresholds, model complexity, timing gates or display policies were changed
for this evaluation. This is the requested new material-control check, not a
parameter sweep on a fresh capture.

## Primary quiet-window results

Consecutive durations are relative to the first saved frame, with no fitted
offset. Transitions are excluded, followed by two seconds trimmed on each side.
The [manifest](../../configs/material-control-20261112.json) preserves every
original duration plus one-second sensitivity windows.

| Scene | Host interval (s) | Frames | Baseline distance | Confirmed weak feature | Independent phase / empty-trained nuisance |
|---|---:|---:|---|---|---|
| Initial empty | 8.66–22.12 | 135 | None | None | None |
| First bare, 50 cm | 52.36–83.10 | 309 | None | None | None |
| Foil, 50 cm | 117.66–145.49 | 280 | 280/280; median **46.14 cm** | 280/280; **46.14 cm** | 280/280 each; **51.02 / 51.05 cm** |
| Bare again, 50 cm | 181.20–208.38 | 274 | None | **257/274; 29.07 cm** | None |
| Final empty | 228.29–241.71 | 135 | None | None | None |

The independent phase fit uses current CA/OS candidate support and unchanged
quality gates. The empty-trained nuisance model is a different offline probe,
not dependent on CA presence; it trains only on the first **67** initial-empty
frames. Both methods fit the foil response near 51 cm. Agreement uses the same
ADC data and is not independent sensor confirmation or subcentimeter calibration.
Reported placement uncertainty in the established setup is a few centimeters.
The baseline's 46 cm foil result also illustrates why dense FFT peak location
and an unwindowed real-tone model can differ; it does not justify a global +5 cm
offset for other scenes.

The one-second trim gives the same qualitative result: baseline 0/329 bare A,
300/300 foil, 0/294 bare B; confirmed weak 0/329, 300/300 and 277/294 respectively.
Neither trim variant is a separate validation capture.

## What the control establishes

With operator B and fixed box footprint, adding foil enables a stable
near-50 cm model fit. Removing it removes that fit again. This supports a
reflector-dependent/mixed-signal limitation rather than a GUI/timing stall,
tracking dropout alone, or a universal range-scale error. It does not determine
which RF path causes the bare response, prove the cardboard is invisible, or
isolate foil reflectivity from all effects of attaching/removing the foil.

The two bare responses are not numerically identical despite unchanged
footprint. Raw OS chooses about **127.8 cm** before foil and **29.1 cm** afterward.
CA margins remain below threshold in both bare holds. The first OS phase fit
is pinned to its support boundary; the second fails `poor_single_tone_model`
in all 274 frames. Neither OS peak is demonstrated to be the box front.

The weak selector correctly rejects all first-bare values, but selects 267/274
second-bare values, and the temporal confirmer retains 257/274. Thus the
confirmed-weak readout near 29 cm is a repeatable scene feature **inconsistent
with the nominal 50 cm box-front distance**. The operator is out of range in
this control, so an operator-at-A explanation cannot account for this particular
result. This is a target-correspondence failure, not proof that there is no
physical scene reflector at the selected range. Do not call this box tracking
or promote its distance to the primary.

The current GUI appropriately labels this as a weak scene-feature inspection,
but its strong typography/history can still look convincing. The
[bare-return snapshot](bare-return-gui.png), taken at replay frame 1960 inside
the second bare hold, preserves the actual display behavior for review.

## Fixed background-model comparison

The unchanged one-tone/RX model learns nuisance coordinates of
**2.165 / 2.285 / 2.150 m** from the initial-empty training half. None is on its
0.05–5 m search boundary. These are descriptive model coordinates, not surveyed
wall measurements. Its blind candidate scan remains 0.174–1.564 m, with no
nominal-target window.

| Hold | Blind nuisance-conditioned probe | Conditional residual median | Supported RX median | Quality/energy inspection |
|---|---:|---:|---:|---:|
| Bare A | 17.38 cm, lower boundary | 0.567 | 1 | 0/309 |
| Foil | 51.05 cm | 0.092 | 3 | 280/280 |
| Bare B | 23.90 cm | 0.586 | 0 | 0/274 |

All 203 held-out empty frames (68 initial-half + 135 final) have no accepted
nuisance-model inspection output. The empirical candidate-energy-only check
still flags 140 of those frames; quality withholding, rather than stable
change detection alone, is essential. All target frames exceed the energy
check, including the bare misses.

The unchanged fixed-subtraction comparison also fails bare-box recovery:
power-excess peaks are about **106.4 cm** and **26.1 cm** in the two bare holds;
waveform residual peaks are about **28.2 cm** and the **17.4 cm scan boundary**.
For foil those maxima are about 46.7 cm, consistent with the windowed spectral
peak rather than the raw-tone model. Fixed waveform subtraction still flags
all final-empty frames as changed. It is not a useful automatic distance gate.

## Timing and processing integrity

All **2,532 saved frames** are accepted; no CRC/header failures, gaps, restarts,
discarded bytes or timing rejections are reported. One partial trailing byte
is retained. Startup clock fit collects 200 frames, then remains frozen for
2,332; startup p95/max residuals are **1.59/22.55 ms**. Post-freeze p95/max
relative errors are **87.69/96.07 ms**, within the separate 500 ms progress bound.
Do not compare post-freeze progress errors with startup fit residual limits.

The recording spans 251.577 host seconds. User labels end at **243.71 s**;
the final **7.867 s** is unscored. All recorded detector source hashes match the
current code. The standalone audit verifies frozen CA/RD/association parity;
the focused review additionally verifies the saved result bank, association,
motion/RX diagnostics, OS/phase/weak selection and weak-feature results against
replay. No saved readings or raw data were rewritten.

## Recommended next software step

No immediate repeat is needed. This control answers the placement/operator
question well enough to proceed with software diagnostics.

Add a clearly separate **model-qualified experimental range/status** to the
GUI, preserving the original baseline and current weak-feature inspection.
The existing weak-candidate line already says the raw model is withheld; retain
that warning and surface numeric residual, supported RX and boundary/ambiguity
status alongside the prominent confirmed-feature readout. A temporally confirmed weak feature
must not be presented as a model-qualified box distance when the raw model
fails. This control supplies both a positive foil case (near 51 cm) and a
negative bare case (persistent weak peak near 29 cm but rejected range model).

That would improve diagnostic/demo honesty and show the capabilities already
supported by the data; it is not a promise of reliable bare-cardboard tracking.
A subsequent detector/model change still needs held-out scene/session testing,
empty controls and motion/stop checks before main-distance promotion. Do not
relax the existing model gate to accept the 29 cm return or blacklist that
range. A stronger target and cleaner scene may eventually define a practical
demo envelope, but arbitrary-object recognition remains an open deliverable.

## Evidence and reproduction

[Live-channel/timing review](capture-review.json) · [Timeline](comparison.png) ·
[Raw per-RX spectra](spectra.png) · [Joint replay audit](report.json) ·
[Phase comparison](../material-control-20261112-phase/README.md) ·
[Nuisance-model metrics](../material-control-20261112-tone/report.json) ·
[Nuisance timeline](../material-control-20261112-tone/comparison.png) ·
[Fixed-reference metrics](../material-control-20261112-background/report.json) ·
[Fixed-reference profiles](../material-control-20261112-background/profiles.png)

Each processing report pins its source/input/manifest hashes. All settings were
fixed from prior work; the geometry-confirmation answer is preserved in the
manifest and catalog. Use fresh output directories:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --experimental-weak --recordings recordings/rd-gui-20261112-094114-038104/live-001 \
  --output evidence/NEW-MATERIAL-CONTROL
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_weak_capture \
  --manifest configs/material-control-20261112.json --output evidence/NEW-MATERIAL-CONTROL
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_phase_range \
  --manifest configs/material-control-20261112.json --output evidence/NEW-MATERIAL-PHASE
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.investigate_empty_trained_tone \
  --manifest configs/material-control-20261112.json --output evidence/NEW-MATERIAL-TONE
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.investigate_matched_background \
  --manifest configs/material-control-20261112.json --output evidence/NEW-MATERIAL-BACKGROUND
```
