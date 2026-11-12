# Wheeled target repeat: fixed radar, 120↔60 cm, nearby wall

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Source: `recordings/gui-20261110-162410-575208/live-002`.
No detector thresholds, calibration, firmware or background subtraction changed.

[Full timeline](timeline.png) · [Phase detail](phase-detail.png) ·
[Spectra](spectra-and-phase.png) · [Numeric report](report.json)

## Labels and analysis policy

User supplied consecutive durations of 20.48, 5.86, 17.29, 9.63, 18.24, 6.04,
17.51, 5.46, 18.09, 6.74, 16.21, 17.43 s: initial wall, placement, 120 cm,
approach, 60 cm, retreat, 120 cm, approach, 60 cm, retreat, 120 cm, removal/wall.
Durations total 158.98 s; saved capture spans 159.79 host seconds. Assume stopwatch
near first saved frame, with no fitted offset or timing stretch.

Primary summaries use the middle 50% of each interval, including stationary
intervals, without adjusting windows against favorable output. Full timelines
retain transitions and failures. Motion is hand driven and speed variable.
The operator stands to the side but may contribute radar returns. The last phase
is interpreted as removal followed by wall only; its exact transition is unknown.

## Capture quality

1,603 complete frames were saved; 1,596 pass Doppler replay checks. The live
summary records seven CRC failures and seven sequence gaps, with seven rejected
frames and no restarts. Raw wire has a 1,929-byte incomplete tail at stop.
The seven complete frames following gaps are blanked by continuity checks.
Seven missing sequence numbers are not saved frames and cannot be reconstructed.
Coverage below uses saved frames, including rejected frames, as denominator.
This capture has transport losses, unlike live-001; they do not explain the
sustained changes during the static holds.

The host/device mapping remains frozen. Maximum corrected post-fit progress error
is about 406 ms, below the existing 500 ms gate but closer to it than live-001.
No recorded timing rejection occurs. Neither clock mapping nor valid packets
verify the radar's intra-burst chirp period or coherence.

## Range output is not repeatable enough yet

These are **recorded 1D CFAR** results for the middle-half windows, not Doppler
detector performance or validated target identities:

| Phase | Window (host s) | Saved frames | Numeric coverage | Conditional median | Conditional 5th–95th |
|---|---:|---:|---:|---:|---:|
| Initial wall | 5.12–15.36 | 104 | 13.5% | 100.3 cm | 97.5–105.6 cm |
| 120 cm A | 30.66–39.31 | 87 | 6.9% | 102.0 cm | 101.6–103.0 cm |
| 60 cm A | 57.82–66.94 | 92 | 100% | 54.7 cm | 45.4–63.2 cm |
| 120 cm B | 81.92–90.67 | 88 | 55.7% | 107.9 cm | 104.6–112.5 cm |
| 60 cm B | 105.03–114.08 | 91 | 54.9% | 87.2 cm | 79.9–136.8 cm |
| 120 cm C | 129.39–137.50 | 81 | 0% | — | — |
| Removed/wall | 145.91–154.62 | 88 | 0% | — | — |

The near holds differ in both raw range spectra and numeric outputs. The second
hold is not simply the first with a small calibration offset. Orientation,
reflecting surfaces, multipath, operator position, actual placement and wrong
reflector association are possible contributors; this capture does not identify
which dominates. Do not fit an offset or choose only the first successful hold.

The initial wall interval produces unwanted close-range outputs, whereas the
final wall interval does not. This reinforces scene sensitivity. It does not
establish that the wall itself caused the initial ~1 m readings.

Both nominal target endpoints fit the native live range mask (bins 1–4), unlike
the distant endpoint in live-001. The actual reflecting surface and nominal
bin-center mask boundaries still differ from surveyed target coordinates.

## Motion-sensitive phase, but no resolved native Doppler separation

For every valid frame in each middle-half window, the full-map peak at each of
range bins 1–8 remains at zero Doppler. This includes the four motion windows.
The native FFT spacing is 0.0625 cycles/chirp. No m/s conversion is justified.

The first approach has a negative phase excursion, and the first retreat has a
positive excursion across multiple range bins. For example, the first approach's
middle-window median at range bin 2 is approximately -0.00108 cycles/chirp,
versus +0.00040 for the first retreat. The full phase timeline also shows negative
and positive excursions near the second approach/retreat boundaries. These
excursions are small relative to the native grid and cannot establish physical
velocity, absolute sign, target identity or uniform timing.

**Middle windows are not guaranteed to contain the strongest actual motion.**
The second approach's strongest negative phase excursion is near the start of
its labeled interval, before its selected 96.42–99.15 s middle window. Positive
excursions during retreats also concentrate near their beginnings. Variable speed,
timing uncertainty and operator movement could each contribute. These are
exploratory observations from the complete timeline; primary windows were not
shifted or rescored to improve results. The phase-detail plot shades all selected
windows so this limitation is visible.

Mean removal attenuates the map strongly in both movement and holds. It does not
provide reliable obstacle or motion classification here. Retain the full map.

## Implication and next work

This is a useful repeat with clearer direction-dependent phase excursions. Uneven
speed does not invalidate a qualitative test and is not by itself a reason to
repeat the whole experiment. It prevents interpreting whole-phase travel distance
divided by duration as the instantaneous velocity of a middle-window frame.

The next engineering priority is to establish intra-burst timing and whether the
short retained record can resolve robot-scale motion. These two captures show
motion-sensitive phase without separated native Doppler peaks. Verify timing,
then decide whether a dedicated longer coherent burst/profile is required before
expecting 2D CFAR to isolate the moving target. Do not stitch restarted frames.

For a later capture, mark the radar-facing reference surface at both endpoints,
maintain target orientation and operator position, and video the motion with a
visible stopwatch. Include an operator-only motion control with target absent.
Matched stationary cart/target holds can help determine whether movement is
necessary for the changing spectrum. Constant speed is useful for physical
velocity validation, but the immediate issue is timing and target/scene ambiguity,
not hand-rolling perfection. Keep this difficult scene as development evidence.

## Reproduce

The maps output directory must be new for the first command:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/radar-mpl ./range-v1 range-doppler \
  recordings/gui-20261110-162410-575208/live-002 \
  --output evidence/rd-repeat-wall-20261110/maps

MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.review_rd_repeat
```

The report and map metadata preserve phase windows, raw/config/source hashes,
normalization and limitations. Rejected maps remain NaN; Doppler statistics use
valid maps, while numeric coverage includes every saved frame in each window.
