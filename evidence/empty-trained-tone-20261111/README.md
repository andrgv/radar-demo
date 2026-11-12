# Empty-trained background with variable phase and amplitude

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Analysis completed November 12, 2026 on the preserved November 11 captures.

**One empty-trained nuisance tone per RX is insufficient for the bare-box
scene. It does recover plausible foil-box ranges, so a global range offset or
scale change is not supported by this experiment. No live estimator changes.**

This follows the [fixed-subtraction comparison](../matched-background-20261111/README.md).
The user explicitly placed the operator at B in the latest bare-box capture
and the foil repeat. The earlier foil capture's operator position is not
explicitly known. See the [catalog](../../docs/CAPTURE_CATALOG.md) for provenance.

## Frozen model

Each session uses exactly the same protocol. The first half of the first
2-second-trimmed empty hold (58 frames here) estimates **one nuisance frequency
per receiver** from mean raw covariance. The empty-only frequency scan is
0.05–5 m at 5 mm steps, using the existing offline `JointBackground` solver.
Frequencies are then frozen. All later frames independently fit sin/cos
coefficients per chirp/RX, allowing amplitude and phase to vary without learning
a new frequency from the target. DC is removed. No fixed waveform is subtracted.

A candidate tone is projected orthogonally to each learned background basis,
then scored across RX/chirps on the saved acquisition half-bin bounds,
0.174–1.564 m. The grid is 1/64 native bin (5.43 mm); that is numerical search
spacing, not physical resolution or accuracy. There is no nominal-target
window, rank sweep, fitted offset, gain adjustment or parameter retuning
between recordings. A conditional probe exists even in empty scenes and
without a CFAR candidate; it is not an established physical object.

The diagnostic quality check uses fixed conventions from the prior phase
investigation: reject scan boundaries, competing optima within 1% of
post-nuisance energy, width over half a native bin, conditional residual over
0.5, or fewer than two consistent RX. RX frequencies must be interior and within
one-quarter native bin of the pooled optimum; their residual is measured
relative to post-nuisance RX energy. Projected basis singular values are saved;
values at or below 1e-6 lose that basis direction. These are empirical model
checks, not calibrated confidence or an unchanged live acceptance policy.

A separate energy-change check requires conditional explained energy per trace
to exceed the training-empty 99th percentile. Its intersection with quality is
called **inspection output** below. No live presence detector or primary range
is replaced. Coefficients are fitted to the current frame; only nuisance
frequencies and the empirical energy threshold are learned from training.

## Target results

| Recording / nominal hold | Frames | Quality + energy inspection frames | Inspection median cm | Blind probe median when rejected |
|---|---:|---:|---:|---:|
| Bare box B / first 50 cm | 268 | 0 | — | 17.4, lower boundary |
| Bare box B / repeated 50 cm | 274 | 0 | — | 27.7 |
| Bare box B / 120 cm | 279 | 0 | — | 17.4, lower boundary |
| Earlier foil / first 50 cm | 173 | 173 | 51.1 | — |
| Earlier foil / repeated 50 cm | 168 | 168 | 46.7 | — |
| Earlier foil / 120 cm | 170 | 170 | 123.3 | — |
| Foil repeat B / first 50 cm | 219 | 219 | 50.0 | — |
| Foil repeat B / repeated 50 cm | 217 | 217 | 49.4 | — |
| Foil repeat B / 120 cm | 221 | 221 | 122.2 | — |

All **1,168 foil target frames** pass this diagnostic. All **821 bare-box target
frames** are withheld. These are stationary holds; motion performance is not
established. The foil repeat already had complete baseline and single-tone
phase coverage, so these results do not establish additional target coverage.
The earlier foil repeat-placement bias also remains. Few-centimeter placement
uncertainty precludes subcentimeter accuracy claims from close nominal fits.

For the bare-box capture, the learned nuisance coordinates are
2.240/2.195/2.220 m, descriptive scene parameters rather than surveyed wall
ranges. One nuisance tone still leaves about 50% of empty AC energy unexplained.
It leaves about 42%, 88% and 42% of raw energy in the three target holds.
The candidate accounts for some of that remaining energy, but the median
conditional residuals are **0.592, 0.615 and 0.526**, all above the fixed 0.5
check. In the repeated 50 cm hold, median RX spread is **61.4 cm** and at most
one RX supports the pooled candidate. The other two holds hit the scan boundary.
Lower joint residual is therefore not evidence that the box was recovered.

The model underfits the empty scene itself. This rejects the **one-tone
background model**, not all possible variable-background models, and does not
prove that the bare-box return is absent. Increasing component count after
seeing these failures would constitute new development, not validation.

## Empty controls and identifiability

| Recording | Held-out empty frames* | Energy-change-only frames | Quality + energy inspection frames |
|---|---:|---:|---:|
| Bare box B | 419 | 340 | 0 |
| Earlier foil | 316 | 0 | 0 |
| Foil repeat B | 462 | 30 | 0 |

*The training half of the first empty is excluded. The held-out half and all
later empty holds are included. All 1,197 held-out empty frames produce no
inspection output. Empty suppression coexists with complete bare-box misses;
it does not establish useful detection by itself. Consecutive frames are
correlated, and these previously inspected sessions are development evidence.

In the foil repeat, RX2's empty-trained frequency is **0.05 m, the lower
nuisance-search boundary**, while RX1/RX3 are about 2.20/2.19 m. This is saved
explicitly in the report. It may act as a smooth low-frequency basis; its
physical interpretation and frequency identifiability are unresolved. The
warning is not hidden, turned into a distance calibration, or used to retune
the search. Quality-only output is not proof that the nuisance frequency is
physically valid. RX2's boundary also limits claims about universal model fit.

## Decision

Do not promote this probe to the main distance or implement it as a bare-box
fallback. The foil results support nominal range transfer in those scenes,
while bare-box identification remains unresolved. They do not establish a
firmware fault, a defective receiver, a particular multipath path, or material
as the sole causal difference: these captures also differ in placement/scene.

The next useful evidence is a **same-position bare → foil → bare comparison**,
without moving the box footprint, sensor or background between material holds.
That separates a reflector/material change from the placement variation in
existing recordings. The [capture protocol](../../docs/EMPTY_TRAINED_BACKGROUND.md)
starts at 50 cm, uses the existing firmware/command, includes empty controls,
and specifies what to log. A 120 cm repetition is optional after the near test.
A lower-clutter geometry can be tested separately, not silently mixed into the
same material comparison. Avoid another threshold or nuisance-rank sweep before
that control; preserve this failing bare-box case in future regression work.

## Artifacts and verification

- Bare box B: [metrics/hashes](report.json), [timeline](comparison.png),
  [frame probes (archived)](../ARCHIVED_ARTIFACTS.md#archived-files), [frozen bases (archived)](../ARCHIVED_ARTIFACTS.md#archived-files).
- Earlier foil: [metrics/hashes](foil-first/report.json),
  [timeline](foil-first/comparison.png), [frame probes (archived)](../ARCHIVED_ARTIFACTS.md#archived-files).
- Foil repeat B: [metrics/hashes](foil-repeat/report.json),
  [timeline](foil-repeat/comparison.png), [frame probes (archived)](../ARCHIVED_ARTIFACTS.md#archived-files).

The four new numerical controls cover variable-amplitude/phase background with
added 50/120 cm tones, background-only changes when target/background are not
separable, scan-boundary withholding, and independent joint least-squares
agreement with the orthogonal-projection residual. Together with the existing
background-tone and fixed-subtraction controls, **7 tests pass**. Synthetic
success checks the implementation, not hardware qualification. Raw/config/
arrival/manifest and processing hashes are pinned in each report.

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl OPENBLAS_NUM_THREADS=1 .venv/bin/python \
  -m tools.investigate_empty_trained_tone \
  --manifest configs/bare-box-b-20261111.json --output evidence/NEW-EMPTY-TONE
```

Repeat with `configs/foil-box-live-20261111.json` and
`configs/foil-box-repeat-20261111.json`, each with a fresh output directory.

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m unittest \
  tests_min.test_empty_trained_tone tests_min.test_background_tone \
  tests_min.test_matched_background
```
