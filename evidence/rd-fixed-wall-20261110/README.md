# Preliminary fixed-radar / moving-target / nearby-wall review

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Recording: `recordings/gui-20261110-162410-575208/live-001`.
The existing CFAR GUI command correctly preserved raw data for Doppler replay.
No algorithms, thresholds, firmware, range calibration or scene subtraction were
changed for this review.

## Timing labels and capture health

The user confirmed consecutive approximate phase durations, with uncertain
transitions: 18.58 / 28.03 / 31.01 / 25.53 / 30.71 / 33.64 seconds. These sum to
167.50 s; the recording spans 165.73 host seconds. We assume the stopwatch starts
near the first saved frame, without fitting an offset or stretching time. Use
host time rather than raw device elapsed time. Windows exclude three seconds
at both ends, except approach's end excludes six seconds because the last few
seconds were already stationary. The phase boundaries remain approximate.

All 1,670 frames pass range–Doppler replay validity checks. Capture reports zero
CRC/header failures, sequence gaps, device restarts and rejected frames. The raw
wire has a one-byte incomplete tail at stop, not a lost complete frame. Clock
mapping remains frozen, with maximum post-fit progress error about 144 ms and
no timing rejection. This is transport validity, not verification of RF timing.

## What the data show

[Timeline](timeline.png) · [Spectra and phase probes](spectra-and-phase.png) ·
[Full numeric report](report.json)

The full range map shows a return sweeping inward during approach and outward
during retreat, with a stable near interval in between. A strong broad return
around nominal 2.1–2.4 m dominates the wall-only phase. The timing and scene are
consistent with a target moving in front of a wall, but reflector identity is
not independently established. Target motion also changes the strength of the
far return; occlusion, multipath and operator reflections are possible contributors.

The following summarize **recorded 1D CFAR output**, not a Doppler detector:

| Approximate phase | Buffered host window (s) | Frames | Numeric output coverage | Conditional median range |
|---|---:|---:|---:|---:|
| Initial far hold | 3.00–15.58 | 127 | 0.0% | — |
| Approach | 21.58–40.61 | 192 | 49.0% | 48.2 cm |
| Near hold, about 30 cm | 49.61–74.62 | 252 | 90.1% | 34.2 cm |
| Retreat | 80.62–100.15 | 196 | 53.1% | 96.2 cm |
| Second far hold | 106.15–130.86 | 248 | 6.5% | 35.1 cm |
| Wall only | 136.86–164.50 | 278 | 0.0% | — |

Near-hold presence is 245/252 (97.2%); numeric output is 227/252. The conditional
5th–95th percentile is 32.0–36.5 cm. This is encouraging stability, not a verified
4.2 cm bias: placement is approximate, and coverage/misses remain material.
The sparse second far-hold outputs do not establish target range or identity.
Moving-interval medians summarize changing ranges and are not distance errors.

The live detector searches only native bins 1–4 (nominal centers 0.35–1.39 m).
That limits interpretation of far-hold misses and wall-only silence. It does not
limit stored ADC or the full-map review. The wall-only result does not demonstrate
general clutter rejection when a strong wall return is outside the search mask.

## Doppler result

At each of range bins 1–8, the strongest full-map Doppler cell is zero in every
buffered phase, including movement. Thus this capture does **not** demonstrate
resolved separation of moving target from stationary wall on the native map.

There is a small direction-dependent phase trend. At fixed range bin 2, median
adjacent phase increments are approximately -0.00045 cycles/chirp during
approach and +0.00036 during retreat. Bins 3–5 show a similar directional trend.
Those are far below the native 1/16 = 0.0625 cycles/chirp bin spacing, with
overlapping per-frame distributions. Fixed-bin probes mix returns, so this is
suggestive evidence of a motion-sensitive phase response, not calibrated sign,
velocity, timing or target coherence verification.

The mean-removed map is much weaker: median total moving/full power over range
bins 1–8 is -28.6 dB during approach, -28.7 dB during retreat, -26.9 dB during
the near hold and -32.2 dB for wall only. Near hold has a larger ratio than the
moving intervals, illustrating why this ratio must not be used alone as a motion
or obstacle detector. Retained noise, hand tremor, mixed reflections and the
different full-power denominators can affect it.

The result is consistent with motion too small over the current coherent window
to produce useful native FFT separation, but unverified timing and mixed returns
prevent identifying one cause. Establish chirp timing and repeat a controlled
motion test before selecting a longer burst. Do not stitch the independently
restarted frames or label cycles/chirp as m/s.

## Changes for the next experiment

The current run is useful; keep it as the difficult nearby-wall condition.
It need not be discarded or replaced by a wall-free scene.

1. Put the far target position **closer to the radar**, leaving more separation
   from the existing wall. A path roughly 0.6–1.2 m from the antenna face may fit
   the current live mask while providing more separation from the observed far
   return. Choose measured positions that fit the room. A 20 cm target/wall gap
   is below the approximately 35 cm native range grid and is a difficult
   resolution case, especially with Hann broadening. It is not a clean first
   test of two-reflector separation.
2. Use marked endpoints and a repeatable slide/cart. Start with 10–15 s holds;
   make one smooth approach over about 3–5 s, hold, retreat over about 3–5 s,
   then hold. Repeat three cycles. Measure actual travel distance/time. Faster
   motion than this run may expose a clearer phase response, but does not
   guarantee a nonzero Doppler-bin peak with the current profile.
3. Record wall only at both start and end, with the operator in the same
   out-of-beam position. Record who/what moves along with the target; a person
   moving behind the target can be the strongest moving reflector. A nonmetallic
   support helps make placement and orientation repeatable without a hand hold.
4. Log approximate phase-change times relative to recording start, or make a
   video showing target motion and the stopwatch. Keep a few seconds of margin.
   Do not retune thresholds or adjust fine distance against this run.

After one clearer fixed-radar repeat, collect the matched moving-radar
obstacle-plus-wall and wall-only passes from the
[capture protocol](../../docs/RANGE_DOPPLER_DIAGNOSTIC.md). The immediate engineering
priority remains timing/coherent-window feasibility; collecting many similar
slow-motion runs will not resolve that unknown by itself.

## Reproduce

Use a new/absent maps output directory for the first command:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/radar-mpl ./range-v1 range-doppler \
  recordings/gui-20261110-162410-575208/live-001 \
  --output evidence/rd-fixed-wall-20261110/maps

MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.review_rd_fixed_wall
```

Map provenance and normalization are in `maps/metadata.json`; the review report
records input/config/source hashes and all buffered windows. These are development
observations from one scene, with approximate labels and no accuracy acceptance.
