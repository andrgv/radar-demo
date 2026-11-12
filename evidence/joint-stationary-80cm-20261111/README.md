# Hardware timing retry and approximately 80 cm stationary target

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Recording: `recordings/rd-gui-20261111-133435-428121/live-001`.
The user describes a stationary object at approximately 80 cm; no independent
reflector identity, exact placement or operator geometry labels are supplied.

## Timing retry passes in this recording

All 758 saved frames are accepted over 75.225 host seconds, with zero rejected
frames, CRC errors, sequence gaps or bad headers. The clock collects for the
first 200 frames and freezes on the next frame, near 20 device seconds. Startup
fit p95/max residuals are 1.081/15.869 ms (limits unchanged at 50/100 ms).
After freezing, p95/max relative error is 4.303/6.554 ms through the end.
This is a successful hardware retry after the GUI redraw optimization, not a
universal guarantee against host scheduling delays. A 4,567-byte incomplete
tail at stop is preserved separately from complete saved frames.

## Blank distance is an actual detection failure

The primary readout has zero values across all 758 frames. The frozen 1D path
has no qualifying cells in its bins 1–4 search region in any frame, always
reporting `no_candidate_above_noise`. This is neither a timing rejection nor
an unresolved fine-range fit nor a GUI-only display problem.

At nominal target-region bins 2 and 3, median margins relative to 1D CFAR are
-6.09 and -4.31 dB. Stronger farther returns at bins 6 and 7 contribute a
median 91.8% of bin 2's reference power and 86.1% of bin 3's reference power.
Those bins are outside the tested 1D mask but deliberately remain training
references. They elevate thresholds above the observed near-range power. Their
physical origin is unverified; they must not be automatically labeled a wall.
This quantifies reference contamination/masking but does not determine all
physical causes of the weak target-region return.

RD confirms a stationary bin-6 feature on 756/758 frames, with median fine
inspection range 222.4 cm. That feature cannot be substituted for the 80 cm
target. Confirmed endpoint-region RD peaks occur in only 16/758 frames (bin 2:
14, bin 3: two). Bin-2 fine values exist in 14 frames with median 84.0 cm; bin 3
has one resolved value at 88.9 cm and one unresolved boundary fit. These brief
features do not constitute sustained target detection or establish identity.

## Consequence

The timing/display workload change is supported by this run. Range detection
remains experimental and failed for this placement. Keep the capture as a
regression case for clutter-aware reference estimation and candidate selection;
do not lower timing limits, force the persistent 2.22 m feature into the primary
readout, or fit a distance offset. No repeat of this timing scene is needed.

All saved 1D decisions/reasons/fine outputs reproduce with an independent 1D
detector. The shared adapter's 2D masks and associations match independent RD
processing on every frame. The replay exporter now reads saved `one_d` fields
for joint captures and top-level fields for legacy scalar captures; neither
live detector nor timing policy was changed during this review.

[Timing, spectra and RD inspection timeline](scene-review.png) ·
[Scene metrics and reference contributions](scene-review.json) ·
[Independent parity audit and processing timings](report.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --recordings recordings/rd-gui-20261111-133435-428121/live-001 \
  --output evidence/NEW-STATIONARY-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_joint_stationary \
  --recording recordings/rd-gui-20261111-133435-428121/live-001 \
  --output evidence/NEW-STATIONARY-REVIEW --nominal-target-m 0.8
```
