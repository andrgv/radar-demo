# November 11 AVG16 placement review

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The recording is useful as a distance sweep. Same-distance repeated placements
are the next control, especially at 80 cm; this capture does not need discarding.
No processing, threshold, search-mask or firmware changes were made.

## Labels and transport

User timings are interpreted as consecutive durations from the first saved
frame. Nominal holds are 22.74–44.20 s (50 cm), 79.57–103.28 s (80 cm), and
128.86–150.97 s (120 cm). The last empty interval begins at 156.03 s and runs to
173.14 s. Transitions are excluded. Primary summaries trim two additional
seconds from both ends of quiet intervals; one-second trims are in report.json
and give the same qualitative conclusions. No time offset was fitted.

All 1,747 recomputed decisions, fine distances and reasons match saved live
results. Capture reports zero rejected frames, CRC errors, sequence gaps or
device errors/drops. Clock mapping froze after 200 frames; maximum recorded
corrected error after freezing is approximately 60 ms. One trailing byte at
stop is recorded. The clean transport does not establish absolute frame age.

## Results

| Placement | Numeric / interior frames | Coverage | Median distance | 5th–95th percentile |
|---|---:|---:|---:|---:|
| 50 cm | 176/176 | 100% | 71.9 cm | 66.8–76.4 cm |
| 80 cm | 85/199 | 42.7% | 103.1 cm | 100.4–106.8 cm |
| 120 cm | 123/183 | 67.2% | 149.6 cm | 146.9–152.2 cm |

All four empty interiors have zero numeric outputs and zero confirmed presence:
0/144, 0/118, 0/118, 0/132 (512 frames total). This is useful scene-specific
rejection evidence, not a general false-alarm rate. The 1D search mask remains
native bins 1–4: these are not all-range empty-scene claims. Strong farther
scene returns are visible outside that mask in spectra.png.

Every confirmed presence frame in these interiors has a resolved fine estimate.
At 80 cm, 110/199 frames have a qualifying candidate, but only 85 confirm;
89 have no candidate and 25 are checking persistence. The longest numeric gap
is 4.1 s. At 120 cm, 149/183 have candidates, 123 confirm, 34 have no candidate,
and 26 are checking persistence; the longest gap is 0.7 s. No candidate is lost
to the outside-mask stronger-neighbor flank rejection in these interiors.

Selected native bins progress 2 → 3 → 4 with increasing placement distance.
The display responds to the placement changes, but readings exceed the supplied
distances by roughly 22–30 cm. This is a comparison against nominal placement,
not error conditional on verified reflector identity. A common offset is worth
investigating, but this one sweep cannot establish a calibration correction or
its cause. Check antenna-face-to-reflecting-surface measurements before fitting
an offset; reflector selection, geometry, analog response and nominal range
scale remain possible contributors. Smoothing cannot fix these differences.

## Recommended next capture

Keep the radar, firmware and CFAR settings unchanged. First collect an 80 cm
repeat with the target footprint, height and orientation marked:

- 15 s quiet empty.
- Place at measured 80 cm; step out of the beam; hold untouched for 25–30 s.
- Remove, step out, and leave 15 s quiet empty.
- Replace at the identical marks and orientation; hold untouched for 25–30 s.
- Repeat removal/replacement once more if convenient, then finish with 15 s empty.

Log actual handling start/end separately from each quiet hold, or film the scene
and stopwatch. Keep the operator out of the beam for every scored hold. Measure
from the antenna face to the intended reflecting surface, and note the distance
reference used in this first sweep. Then repeat the same protocol at 50 cm to
check whether its distance discrepancy reproduces, followed by 120 cm. Repeated
80 cm holds take priority because the current candidate is marginal and
intermittent. This separates within-placement fluctuations from changes caused
by replacement; changing distance every time cannot separate those effects.

[Timeline](timeline.png) · [Native power and threshold margins](spectra.png) ·
[Window metrics](report.json) · [Candidate/persistence diagnostics](diagnostics.json)

Reproduce:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.qualify_avg16_cfar \
  --manifest configs/avg16-placements-20261111.json --output evidence/NEW-DIRECTORY
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_avg16_placements \
  --output evidence/NEW-DIRECTORY
```
