# Foil-covered box: repeated 50 cm and 120 cm holds

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Recording: `recordings/rd-gui-20261111-200448-409110/live-001`.
The same cardboard box now has its front face covered in tin foil. Prior user
details describe a roughly 45 × 24 cm front face, front-face distance origin
and a background wall a little over 2 m away. This is a sequential scene
comparison, not proof that the surface material alone caused every change.

## Recorded results

Durations are consecutive from the first saved frame, with no fitted offset.
Hold windows are 32.95–54.11 s (50 cm A), 88.07–108.78 s (50 cm B), and
139.96–160.84 s (120 cm). Handling is excluded and quiet windows trim two
additional seconds per side. The supplied final empty interval ends at 185.14 s;
the recording continues to 192.486 s, and that additional 7.346 s is unlabeled.

| Quiet interval | Numeric / frames | Median cm | 5th–95th cm |
|---|---:|---:|---:|
| Initial empty | 0/116 | — | — |
| First 50 cm hold | 173/173 | 51.38 | 50.63–51.61 |
| Empty after first removal | 0/73 | — | — |
| Second 50 cm hold | 168/168 | 38.05 | 36.42–39.63 |
| Empty after second removal | 0/69 | — | — |
| 120 cm hold | 170/170 | 122.66 | 121.86–123.49 |
| Final empty | 0/116 | — | — |

The baseline and motion-aware values are identical throughout the scored
target holds: each is a baseline fallback without an active motion episode.
The wrong second 50 cm reading therefore is not introduced by RD selection.
All 374 scored empty frames are blank. In the third empty window an RD episode
does survive on a stationary scene return, but the v2 stopped-support rule
withholds all 69 values; the original handoff failure is not republished.

The foil run detects the far target reliably where the previous bare-box run
did not, but repeated near placement remains inconsistent. This is not a
calibration pass and a constant offset cannot explain all three holds.

## Raw waveform diagnostic gives a more specific estimator lead

The current estimator finds a peak in a mean-removed, Hann-windowed spectrum.
A pre-existing raw sinusoid-plus-DC fitter was applied offline at a fixed
every-fifth-frame cadence, with independent amplitudes/DC per chirp/RX, shared
frequency, the original fixed 0.15–1.5 m search grid and no empty subtraction.
No labels were fitted and no live output was changed.

| Hold | Recorded FFT-peak median | Diagnostic raw-fit median | Median unexplained centered-signal energy |
|---|---:|---:|---:|
| First 50 cm | 51.38 cm | 50.75 cm | 35.6% |
| Second 50 cm | 38.00 cm* | 46.80 cm | 40.3% |
| 120 cm | 122.61 cm* | 122.92 cm | 22.2% |

*Recorded values in this table use the identical fixed subsample, hence minor
differences from whole-window medians above.

An isolated-tone phase sweep using the current 64-sample mean-removal/Hann
processing produces apparent peaks at 42.9–48.3 cm for an exact synthetic
50 cm tone, and 39.1–45.6 cm for a 47 cm tone. At 120 cm the apparent peak is
essentially unchanged. These are processing checks, not a model of all hardware
effects. They identify a phase-dependent near-range peak-estimation contribution;
the second hold's raw fit moves substantially toward the supplied position.
The large residuals still show that a single tone does not explain the complete
waveform, so the diagnostic fit is not promoted as calibrated target range.

The next software investigation should compare a phase-aware/model-based range
estimate within current candidate support across all preserved captures and
empty controls, retaining boundary/multiple-reflector rejection. No further
broad capture sweep is needed before that comparison. Avoid an ad hoc offset
or declaring the diagnostic fit accepted from this recording alone.

## Timing and reproducibility

All 1,937 saved frames are accepted, with zero CRC errors, sequence gaps or
timing rejections. Clock state freezes after 200 frames. Startup p95/max fit
residual is 2.11/32.11 ms. Post-freeze p95/max relative error is 59.31/65.28 ms,
within the separate unchanged 500 ms progress-error bound. The 50 ms startup
fit-p95 criterion is not a per-frame post-freeze bound. A one-byte tail at stop
is preserved separately.

All saved baseline, RD and motion-policy decisions reproduce independently.
No live detector, firmware, threshold or timing policy changed in this review.

[Timeline](motion-comparison.png) · [Window/timing metrics](motion-review.json) ·
[Raw-fit and synthetic phase diagnostics](model-check.json) · [Replay audit](report.json)

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --recordings recordings/rd-gui-20261111-200448-409110/live-001 \
  --output evidence/NEW-FOIL-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_motion_range \
  --output evidence/NEW-FOIL-REVIEW --manifest configs/foil-box-live-20261111.json --hold-spectra
.venv/bin/python -m tools.diagnose_foil_range \
  --output evidence/NEW-FOIL-REVIEW --manifest configs/foil-box-live-20261111.json
```
