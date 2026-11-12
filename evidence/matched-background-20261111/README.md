# Matched empty/box background investigation

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Follow-up completed: the [empty-trained one-tone/RX model](../empty-trained-tone-20261111/README.md)
allows phase/amplitude changes but still fails bare-box ranging, while retaining
plausible foil ranges. The updated next action is the
[same-position material-control capture](../../docs/EMPTY_TRAINED_BACKGROUND.md).
The original fixed-reference experiment and its decision are preserved below.

Recording: `rd-gui-20261111-223730-634059/live-001`; bare box, operator B
throughout quiet holds. The [capture review](../bare-box-b-20261111/README.md)
and [scene manifest](../../configs/bare-box-b-20261111.json) preserve the setup,
original timing labels, integrity audit and unchanged live-result replay.

**A strong scene change is measurable, but neither simple background method
recovers the nominal box distance. No live distance fallback is justified.**
This is an offline negative result, not a change to firmware, CFAR, RD,
weak-feature confirmation or the GUI. It does not prove that no weaker box
component exists among the mixed returns.

## Fixed experiment

The first 58 frames in the first two-second-trimmed empty interior train the
reference (sequences 124–181). The other half of that empty and every later
quiet hold are excluded from fitting. Training computes a per-RX mean
DC-centered waveform and a mean power spectrum, averaging all retained chirps.
The template is frozen; there is no target-label fit, phase rotation, gain
matching, nuisance-rank sweep, range offset or threshold sweep.

Three diagnostic spectra are compared on every quiet frame:

1. Raw power, with the same DC removal/Hann scaling as the live spectrum.
2. Power excess: positive part of current power minus the fixed empty mean.
3. Coherent residual: subtract the fixed waveform first, then calculate power.

Blind peak scans use the saved acquisition mask's half-bin boundaries,
**0.174–1.564 m**, without a window around the expected target. Plots extend to
2.8 m to retain the stronger farther scene response. The 2048-point FFT is
interpolation, not improved native resolution (native spacing is 34.76 cm).
The reported placement is used only to score the resulting peak afterward.
All methods are probes, including on empty frames: none of these peak values
is a published range or a demonstrated physical object.

## Range evidence

Median pooled blind peak, centimeters:

| Quiet target hold | Frames | Raw | Power excess | Waveform-subtracted |
|---|---:|---:|---:|---:|
| First 50 cm | 268 | 90.2 | 89.1 | 84.7 |
| Repeated 50 cm | 274 | 82.6 | 82.6 | 82.6 |
| 120 cm | 279 | 156.4 (upper boundary) | 156.4 (upper boundary) | 147.7 |

For every method, **zero of 821 target-frame blind maxima** are within half a
native bin (17.38 cm) of their nominal placement. This is a coarse diagnostic
check, not an accuracy acceptance criterion. Receiver agreement alone also
fails as proof: subtraction brings the first 50 cm RX peak spread down to a
median 10.9 cm, yet the pooled maximum remains around 85 cm. Waveform-subtracted
median RX spreads for the other two target holds are 21.7 and 43.4 cm.

Power subtraction is not a physical foreground power estimator when mixed
returns interfere: a target can reduce or reshape existing power. Clipping
negative differences only tests a positive-excess hypothesis. Similarly,
waveform subtraction assumes the background waveform is sufficiently stable;
a residual can contain changed background and multipath as well as the added
box. No result here identifies a residual peak as the box.

## Empty stability and change controls

Compared with the frozen waveform, median residual AC energy fractions per RX
are about **0.3–0.6%** in training, **0.4–0.8%** in the held-out same-empty half,
and **1.4–4.8%** in later empty holds. Thus coarse empty power profiles are
repeatable, but the waveform is not exactly stationary. This explicitly checks
sample alignment through fixed subtraction; no phase/gain adjustment was used
to conceal drift. It does not establish absolute phase calibration.

Two empirical change probes are fitted solely to training frames. The first
maximizes RX-averaged current/empty power ratio over the saved mask; its
threshold is the training maximum-score 99th percentile, 1.213. The second
compares coherent residual power against mean training residual power, with
the same maximum-scan/99th-percentile construction (threshold 3.239).
These deliberately expose generalization failures; they are not calibrated
CFAR tests, independent presence decisions or proposed live gate settings.

| Held-out empty portion | Frames | Power-change exceedances | Waveform-change exceedances |
|---|---:|---:|---:|
| Initial empty, second half | 58 | 1 | 6 |
| Empty B | 120 | 54 | 120 |
| Empty C | 121 | 31 | 121 |
| Final empty | 120 | 12 | 120 |
| Total | 419 | 98 | 367 |

All 821 target frames exceed both probes, but the empty failures prevent
interpreting change alone as reliable box presence. All later empty frames
exceed the waveform probe despite small total residual fractions; sensitivity
to a quiet training floor is not a useful distance backend. A positive empty
power-excess peak near 30 cm also appears in the final empty, so a newly
visible near residual cannot automatically become an object.

These are held-out intervals from one session, not independent physical
validation. Consecutive frames are correlated. All target spectra have now
been inspected; this capture must remain development evidence in future work.

## Decision and next model check

Do not add fixed waveform/power subtraction or choose one of the 37/83 cm
peaks as a live fallback. Do not lower thresholds to manufacture target output.
The useful improvement from this experiment is a reproducible background
comparison with explicit empty controls and blind range scoring.

The next concrete model check is an **empty-trained nuisance tone/subspace
model that permits background amplitude and phase to vary**, evaluated against
these same held-out empties and both placements, with the existing offline
`JointBackground` solver as a starting point. Freeze its complexity before
scoring; retain loss-of-identifiability, RX disagreement, boundary optima and
empty outputs. A lower fit residual or a forced numeric optimum is insufficient.
If that model also fails, a controlled reflector/range-transfer experiment is
more useful than additional confirmation tuning. The existing recordings are
sufficient for the next offline check; no immediate new capture is required.

## Artifacts and verification

[Per-RX profiles](profiles.png) · [Full metrics and hashes](report.json) ·
[Frame probes (gzip) (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [Frozen reference and median profiles (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)

The report pins raw/config/arrival/manifest and processing source hashes.
Two numerical controls check exact FFT parity with `core.range_spectrum`,
recovery of an added synthetic tone by fixed subtraction, and the important
counterexample of a phase-reversed background: unchanged power but a large
coherent residual. These pass; they validate the arithmetic, not physical
range recovery. The full saved detector replay was established in the linked
capture audit; no detector or GUI code changed here.

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.investigate_matched_background \
  --manifest configs/bare-box-b-20261111.json --output evidence/NEW-MATCHED-BACKGROUND
.venv/bin/python -m unittest tests_min.test_matched_background
```

Use a fresh output directory. The labels select quiet intervals and the first
training empty; they never select a favorable spectral peak.
