# Residual diagnosis and expanded component experiments

No live estimator or firmware change. Current optional associated GUI estimator
remains unchanged. All 2,349 evaluation frames (14 target captures and seven
empty segments) were scored for each new trial. These recordings are development
and regression evidence, not untouched final validation. Labels score errors and
do not enter fitting; observed failures nevertheless informed these experiments.

## Residual findings

Reconstructed every returned joint-component-1 fit from its saved near and three
RX nuisance frequencies. The recomputed residual energy matches its saved
residual_fraction to 1e-8. Diagnostics are conditional on returned fits; they do
not characterize rejected frames.

Recent 30 cm returned fits leave median 27.8% centered waveform energy unexplained;
recent 50 cm leave 37.7%. The energy of the mean residual across chirps divided by
mean per-chirp residual energy is median 98.35% / 98.05% respectively. Thus the
residual is highly repeatable within each frame, rather than being predominantly
uncorrelated chirp noise. This does not establish physical origin or stationarity
across different recordings, and does not prove averaging can never help.

RX residual spectrum maxima are around nominal 1.0–1.2 m in those recordings.
The previous nuisance search started at 1.5 m, leaving that region unmodeled.
These are spectral coordinates computed with the provisional scale, not evidence
that an actual object is present at those distances. A rectangular time record,
DC handling and multiple components can affect observed residual peaks.

## Corrections evaluated

1. Expanded nuisance search: search .05–5 m, excluding the connected detected
   bin group's support (same +/- one native bin support as associated v3).
   Alternately update one shared target frequency and one nuisance per RX.
   This avoids the arbitrary 1.5 m lower cutoff without using known box distance.
2. Three-component fit: one shared target frequency plus two nuisance frequencies
   per RX, both outside that same support. Greedy initialization, then alternating
   orthogonal projections with per-chirp amplitudes/phases/DC. Near grid 5 mm,
   nuisance grid 1 cm; these numerical increments are not accuracy/resolution.
   SVD rank threshold 1e-6 avoids normalizing absorbed directions. The extra
   flexibility can fit reflections or model error and is not automatically better.
3. Eight and 32 iterations for the three-component method. At eight, 43 returned
   recent 30 cm fits and three 50 cm fits had not converged. At 32 all returned
   recent target fits converge, but their metrics barely change. Both runs are
   retained. No fitted labels, smoothing, held distances or new presence gate.

## Recent target comparison

Mean absolute errors are conditional on reported frames. Availability and large
errors must be considered alongside them.

| Method | 30 cm MAE / reports of 207 | 50 cm MAE / reports of 206 |
|---|---:|---:|
| Associated v3 (existing optional GUI) | 8.88 cm / 70 | 1.83 cm / 141 |
| Prior joint fit, nuisance >=1.5 m | 5.86 cm / 107 | 3.61 cm / 141 |
| Expanded nuisance, two components total | 5.72 cm / 116 | 3.20 cm / 141 |
| Three components, 8 iterations | 3.52 cm / 123 | 4.11 cm / 141 |
| Three components, 32 iterations | 3.51 cm / 123 | 4.11 cm / 141 |

For the converged three-component run, recent 30 cm median is 29 cm, with 58/207
total frames reported within 2 cm; eight reported errors still exceed 10 cm,
95th-percentile error is 10.95 cm, and 84 frames have no report. At 50 cm median
is 47.5 cm, only 32/206 total frames are reported within 2 cm (associated v3 has
111/206), ten errors exceed 10 cm, and one adjacent >20 cm jump remains.
All methods retain the recent empty false detection (1/208) and earlier 0/516.
The three-component empty estimate is nominal 143.5 cm, still a false detection.

More components explain more waveform energy (about 16% / 19% residual on recent
30/50 cm returned fits in the 8-iteration run), but do not produce uniformly more
accurate target distance. Earlier target reports also include regressions; see
comparison.json for every capture, not just the recent two. No trial is promoted.

## Validation and reproduction

41 tests pass, including known near signals with nuisance below the previous
cutoff, a known three-component mixture, nondecreasing fitting objectives and
preservation of input samples. Across saved trial histories the comparison checks
find no objective decrease exceeding 1e-8. These are solver checks, not hardware
qualification. comparison.json includes raw hashes, all metrics, convergence
counts, and metrics after explicitly excluding nonconverged fits.

```sh
OPENBLAS_NUM_THREADS=1 python3 -m tools.analyze_joint_residuals
OPENBLAS_NUM_THREADS=1 python3 -m tools.evaluate_supported_nuisance
OPENBLAS_NUM_THREADS=1 python3 -m tools.evaluate_multi_components --iterations 8
OPENBLAS_NUM_THREADS=1 python3 -m tools.evaluate_multi_components --iterations 32
python3 -m tools.summarize_residual_trials
./range-v1 test
```

Residual frame diagnostics are in this directory. Expanded-search results are
../supported-nuisance-1; three-component results are ../multi-component-1 and
../multi-component-2. Original recordings and earlier reports were preserved.

Decision: the extra nuisance component is a useful 30 cm development lead, but
not a generally accurate replacement. Selecting it only when the known label is
30 cm and associated v3 when the label is 50 cm would be circular. Any future
selection rule must use observed signal evidence, expose ambiguity/misses and
pass the whole regression corpus, followed eventually by fresh qualification.
No additional recording is required merely to reproduce these findings.
