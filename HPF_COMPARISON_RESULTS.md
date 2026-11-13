# Completed 350 → 100 → 350 kHz comparison

The 100 kHz run improved the frozen joint signal fit on average, but did not
establish consistent centimeter accuracy or reliable live detection. The returned
350 kHz control improved substantially relative to the first control and beat
100 kHz at 40 cm. Hardware filter setting alone does not explain all variation.

## What was actually tested

User explicitly authorized all three flashes. Each frozen image was hash-checked,
programmed and verified on KitProg3 170D0E8300023400 / CY8C624AFNI-S2D43. Startup
streams matched profile IDs/flags. The board currently runs the **350 kHz
qualification image**, SHA256 a68e0646857d76d1511be8a5ec9ba2c8130a7d3ff897966afd6e391073163897.
This is not a return to the original October 28 binary; that image remains backed
up under artifacts/hpf-pair-2/restore-oct28. No further flash is needed to analyze
these data. No programmer-firmware update was performed.

Each run has six 101-frame recordings: empty-before, 30 cm, 50 cm, 40 cm, an
untouched 40 cm repeat and empty-after. The first 30 empty-before frames fit that
run's reference; 71 unused frames and all 101 empty-after frames are evaluated.
Totals: 1,212 target frames, 516 unused empty frames, 90 training empty frames.
All 18 experimental recordings have zero reported sequence gaps, CRC/header
errors, device errors, rejected frames or ADC container rails. Each has a retained
one-byte incomplete serial tail at stop; this is not an accepted-frame CRC error.
Container-rail checks cannot exclude analog overload or every internal ADC issue.

The sensor was fixed, target supported, distances measured antenna-face to box
front, and orientation held consistent according to the user. There are no photos,
automated pose measurements or instrument-certified ground-truth uncertainties.
No new arbitrary distance offset, scaling correction, smoothing, gate change or
target-label training was introduced during this experiment.

## Main results

MAE is mean absolute error over ALL target frames, including those rejected by
the detector. Four target recordings have equal lengths/weight; 40 cm appears
twice because of the untouched repeat. The joint fit uses empty-waveform
subtraction and a single common frequency with independent chirp/RX phase,
amplitude and DC. All meter values retain the nominal source-derived scale.

| Run | Joint-fit MAE | Fine FFT-peak MAE | Native detector acceptance | Empty false detections |
|---|---:|---:|---:|---:|
| 350-a | 4.60 cm | 5.95 cm | 120/404 (29.7%) | 0/172 |
| 100-a | **1.83 cm** | 10.56 cm | 116/404 (28.7%) | 0/172 |
| 350-b | 2.26 cm | 6.86 cm | 207/404 (51.2%) | 0/172 |

Giving each distinct distance equal weight instead yields joint MAEs of
4.22 / 1.53 / 2.54 cm respectively. Neither weighting establishes generalization
outside this small experiment. Only 41.6% of 100 kHz joint estimates are within
1 cm; a 1.83 cm mean error is NOT a ±1.83 cm bound.

| Actual placement | Joint MAE, 350-a | Joint MAE, 100-a | Joint MAE, 350-b |
|---|---:|---:|---:|
| 30 cm | 3.86 | **1.07** | 2.16 |
| 50 cm | 3.07 | **0.80** | 4.01 |
| 40 cm | 5.69 | 2.78 | **1.71** |
| 40 cm untouched repeat | 5.79 | 2.67 | **1.18** |

Errors in this table are cm. The original fine FFT peak is sometimes accurate
but not consistent: at 100 kHz its medians at 30/50/40 cm are 34.2/48.3/25.5 cm.
The joint fit's medians are 30.2/49.5/41.3 cm, but individual-frame variability
remains. At 100 kHz, the 40 cm fit's middle 90% spans 35.4–45.2 cm, and the
repeat spans 36.9–46.7 cm. Those are empirical percentiles, not confidence bounds.

## Interpretation and limitations

- The 100 kHz joint-fit errors at 30 and 50 cm beat BOTH 350 controls. The
  single-tone residual is also smaller in those captures. This supports the
  lower-filter hypothesis for those conditions, without proving causation.
- At 40 cm the final 350 control is better. Repositioning, background/reference
  variation, phase alignment, multipath, temperature/time or combinations could
  contribute. These causes were not separately measured and must not be asserted.
- Untouched 40 cm repeats have median changes of approximately -0.22 / +0.16 /
  -0.57 cm for 350-a / 100-a / 350-b. Short-term repeatability can coexist with
  substantial placement/session bias. The first and last 350 runs are not equal.
- There is one 100 kHz run, a fixed sequential order and correlated frames. No
  statistical confidence claim or universal minimum measurable distance follows.
  Only 30–50 cm was tested here; 12–15 cm remains unvalidated.
- Native detection misses remain significant: 769/1,212 target frames withheld.
  Reasons are 363 checking-persistence and 406 competing-separated-peak cases;
  none of these target rejections is a no-candidate-above-noise outcome. This
  identifies software rejection mechanisms, not certified target identity.
- The zero empty count belongs to the unchanged native detector. A sinusoid fit
  still returns numbers for empty scenes, so its apparent accuracy on target
  recordings does not make it a safe standalone live output. Do not discard the
  gate or treat a low fit residual as calibrated confidence. Earlier mismatched-
  background false alarms remain separate unresolved evidence.

## Concrete next work

No further captures or flashes are required immediately. Use the saved 18 raw
recordings to inspect the three RX channels separately and test the sensitivity
of waveform subtraction to the empty reference. This can determine whether the
40 cm variability is shared across receivers or dominated by one channel and
whether background phase sensitivity is a plausible source of bias. Report all
channels; do not select a winning receiver using its known distance label.
Keep both estimators frozen as benchmarks and count discarded/ambiguous cases.

Only after that diagnosis should a revised estimator/gate be frozen for new
independent validation. If 100 kHz is chosen for a later deployment experiment,
switching back requires authorization beyond the now-completed three-flash
sequence. Live processing remains the existing conservative, uncalibrated path.

## Evidence and reproduction

Per-record reports, raw hashes, build and flash logs, comparison.json and
comparison.png are in evidence/hpf-pair-2. Raw recordings and fitted references
remain intact under recordings/ and artifacts/. The board's final profile is
0x33514802, so future captures require the HPF350 config rather than the old
default profile. No firmware or algorithm was changed after observing outcomes.

From the isolated repository, choose a new output directory:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.replay_hpf_series artifacts/new-hpf-replay
```

This recomputes all 18 recordings from raw data with training-only empty
references, stores every estimate/rejection in frames.jsonl, and checks that
target MAEs and accepted counts reproduce the original reports. It does not
access hardware. The complete replay was run successfully into
artifacts/hpf-series-replay-1; all 12 target comparisons matched.
