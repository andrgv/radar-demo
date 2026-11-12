# AVG16 controlled-motion review

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Source: `recordings/avg16-motion-01`, profile `0x33515403`.

[Full timeline](timeline.png) · [Motion midpoint maps](motion-midpoints.png) ·
[Numeric report](report.json)

## Result

Both approaches produce negative adjacent-phase progression and both retreats
produce positive progression at range bins 2–4. Nonzero native Doppler peaks
appear in the **full map with zero Doppler retained and no background
subtraction**. All five stationary holds return to zero-Doppler peaks. This
is a useful qualitative improvement over the earlier AVG1 experiment, whose
native peaks stayed at zero even during motion. It supports implementing a
replay 2D CFAR prototype on the AVG16 maps.

This is not yet object-detection accuracy or physical-velocity validation. A
fixed-bin phase probe can mix the target, operator, wall and multipath. The
range–Doppler transform has no CFAR threshold, clustering or target association.
The target and stationary clutter share zero Doppler when the target stops.

## Capture and labels

All 605 saved frames are valid under the replay checks, spanning 59.856 host
seconds. There are no packet CRC/header errors, sequence gaps, device errors,
device drops, host clock-fit rejects or edge overflows. Every frame has 272
edges. Group-period endpoint estimates have 5th/median/95th percentiles of
504.8125/504.9375/505.0625 nominal MCU microseconds. A partial wire packet at
capture stop is excluded from the complete saved-frame file.

The user's video windows are 11.35–12.80 s approach, **23.27–24.64 s retreat**
(explicit correction), 36.64–37.93 s approach, and 47.11–48.48 s retreat.
All other intervals are stationary. Times below use host seconds from the
first saved frame, with no fitted video offset. Primary movement windows trim
0.2 s from each end; holds trim 2 s at each end. Because motions are short,
offset sensitivity is also reported at -0.5, -0.25, 0, +0.25, +0.5 s. No
window was moved to maximize its response.

## Motion measurements

Fixed bins 2–4 cover the vicinity of the labeled target path and spectral
spread; they are exploratory probes, not an accepted target range gate.
The table reports native peaks independently at each range bin, without
removing the zero-Doppler row.

| Phase | Primary host window | Frames | Median phase, bins 2/3/4 (cycles/block) | Nonzero peak fraction, bins 2/3/4 |
|---|---|---:|---|---|
| Approach 1 | 11.55–12.60 s | 11 | -0.0439 / -0.0312 / -0.0326 | 45% / 55% / 45% |
| Retreat 1 | 23.47–24.44 s | 10 | +0.0497 / +0.0479 / +0.0396 | 100% / 90% / 60% |
| Approach 2 | 36.84–37.73 s | 9 | -0.0310 / -0.0344 / -0.0540 | 33% / 56% / 78% |
| Retreat 2 | 47.31–48.28 s | 10 | +0.0795 / +0.0700 / +0.0543 | 80% / 60% / 50% |

Across all five tested timing offsets, all three bins keep a negative median
for each approach and a positive median for each retreat. Peak fractions and
phase magnitudes vary with offset, so these fractions must not be interpreted
as detection rates. Full timelines preserve motion outside the nominal windows.
The four snapshot frames are chosen by video-window midpoint, not strongest
response. The native Doppler grid remains 1/16 = 0.0625 cycles per saved block;
Hann windowing broadens peaks, and a nonzero maximum does not prove that a weak
moving return is resolved independently from a stronger stationary return.

The five buffered holds contain 347 frames. For every one of these frames,
the full-map peak at every range bin 1–8 is at zero Doppler. The strongest
target-vicinity range bin is 2 in both near holds and 3 or 4 in the far holds;
the far-bin variation is another reason to defer fine-distance calibration and
avoid claiming target identity from one maximum. These stationary returns must
remain available to the future obstacle detector.

## Next engineering step

Keep the AVG16 test image and config as the working development profile. Add
replay 2D CA-CFAR with explicit guard/training regions and edge policies, export
noise/threshold maps, and cluster accepted cells into multiple candidates.
Retain zero Doppler and compare stationary holds as well as movement. Use this
recording as development data, then freeze settings before requesting a new
independent target/wall and operator-only control capture. No new sample or
firmware flash is needed before that software step.

Physical m/s labels remain unverified: the MCU timebase and RF carrier are not
independently calibrated, and target/operator identity and exact block timing
have not been directly measured. The observed direction response supports
prototyping without changing those verification flags.

## Reproduce

```sh
MPLCONFIGDIR=/private/tmp/mpl-radar .venv/bin/python -m tools.review_avg16_motion
```

The report preserves raw/source hashes, all tested windows, fixed-bin summaries,
and integrity statistics. `timelines.npz` contains full linear-power maps,
phase/resultant probes and raw range powers; no empty-scene subtraction is used.
