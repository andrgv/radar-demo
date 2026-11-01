# Frozen cwm versus current GUI: common raw replay

Compared all 621 complete frames from the independent empty, stationary 30 cm,
and stationary 50 cm GUI captures. Labels follow the user's requested capture
order. These are nominal ruler labels, not externally synchronized ground truth.

Algorithms loaded directly from git commit a6d7a089d9a44814d4258b3593a28b9daffbd8ae
in the original repository into a separate Python module namespace. Original
repository files and branches were not edited. Source/raw hashes are in report.json.

## Results

Error is mean absolute error among reported frames; availability is reported/total.
No readings are filled through gaps. A jump means >20 cm between two adjacent
frames both reporting a distance; it excludes transitions across missing frames.

| Pipeline | Empty false frames /208 | 30 cm reports /207 | 30 cm MAE | 50 cm reports /206 | 50 cm MAE |
|---|---:|---:|---:|---:|---:|
| Actual cwm GUI observed coordinate | 1 | 169 | 4.76 cm | 198 | 15.65 cm |
| cwm internal smoothed coordinate | 1 | 169 | 4.76 cm | 198 | 14.25 cm |
| Disconnected StableRangeTracker default raw | 1 | 2 | 51.80 cm | 2 | 7.77 cm |
| Same tracker smoothed | 1 | 2 | 51.80 cm | 2 | 9.27 cm |
| Same tracker with empty-difference option, raw/smoothed | 2 | 1 | 40.67 cm | 1 | 7.52 cm |
| Current GUI fixed-waveform tone estimator | 1 | 133 | 12.10 cm | 141 | 16.94 cm |

cwm's 30 cm readings are all 34.7585 cm. Its 50 cm readings alternate between
34.7585 and 69.5171 cm, with median 34.7585 cm. Thus its availability is not an
accuracy rate. At 50 cm, cwm's smoothing reduces >20 cm jumps from 10 to zero,
but 183/198 reported smoothed readings still have error above 10 cm.
The actual cwm monitor displays observed_range_m, not this internal smoothed value.

The current GUI has 31 adjacent >20 cm jumps at 50 cm. It reports within 2 cm on
91/206 total frames; cwm observed does so on 0/206 and cwm smoothed on 1/206.
At 30 cm, current GUI reports within 2 cm on only 2/207 total frames; cwm on zero.
These methods fail differently. None establishes reliable centimetre accuracy.

## Exact comparison choices and limitations

- All background training uses the same first 30 frames of empty-001. Evaluation
  empty live-003 never contributes to fitting. State resets before each recording.
- All methods use recorded HPF350 profile, 5 MHz sample rate, 64 samples, 17 chirps,
  discard first chirp, recorded slope 33.69140625 THz/s, unity RX gains and no range
  scale/offset. Native nominal spacing is 0.347585 m; no physical calibration claimed.
- Actual cwm GUI decision path is ShortRangeAmplitudeTracker -> RangeTracker after
  empty capture. Its defaults are retained, including five-frame per-bin median,
  2 m search limit, 3 dB excess, 2 dB margin and tracker gate/persistence. The old
  broader Processor diagnostics do not drive this post-background monitor value.
- Disconnected StableRangeTracker has no existing live wiring to reproduce. This
  benchmark supplies mean FFT magnitude over retained chirps and three receivers,
  as its input contract requires, using its example's 4x padding (256-point FFT).
  Range axis uses sampled bandwidth slope*N/Fs, not full programmed ramp bandwidth.
  Zero padding does not improve physical resolution. This three-RX pooling is an
  explicit adapter choice, not proof of how a historical unrecorded run was wired.
- StableRangeTracker defaults remain unchanged: 0.15–1.5 m, prominence_sigma=4,
  history=5, lock gate=.25 m, alpha=.12/.65. Both documented stationary default
  (no background subtraction) and abs(magnitude-median-empty) option are shown.
  Its very low availability is a failure, not superior stability. Do not infer
  that every possible configuration of this tracker must fail.
- Current pipeline uses its original saved baseline and fixed-waveform estimator.
  Recomputed accepted ranges agree with live logs to 1e-8 m. All current captures
  had zero timing/transport rejection, so offline replay does not erase those misses.
- This is a counterfactual algorithm comparison on current qualification-firmware
  data, not a recreation of the user's October hardware/scene conditions.
- No parameters were selected using target labels. The different search limits,
  magnitude/power domains and gates are part of existing algorithms, not normalized
  away. This evaluates existing implementations, not an isolated smoothing ablation.

## Decision and next experiment

Do not switch the GUI to StableRangeTracker or claim cwm solves ranging. Keep all
raw evidence. The next offline diagnostic should locate competing per-RX spectral
components on the 30 cm failures and 50 cm jumps, and test whether a consistent
component corresponding to the target exists before developing another estimator.
No additional physical captures or flashing needed for this diagnosis.

## Reproduce

From wavvy-range-v1, with NumPy and SciPy installed (system python3 used here;
original radar virtualenv lacks SciPy):

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python3 -m tools.compare_cwm_gui
```

report.json contains aggregate metrics; frames.jsonl retains per-frame raw and
smoothed results including misses. No GUI, hardware connection or firmware action.
