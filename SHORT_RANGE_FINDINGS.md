# Short-range diagnosis and selection fix

The user's stationary 50 cm experiment contains a stable bin 1 change. The original
MVP's ranking order caused many of its missed readings. This is a software defect,
not evidence that the box reflection itself disappeared in those frames.

## Measured evidence and fix

Using the original fitted reference unchanged, bin 1 exceeds its 3 dB threshold
in **302/302 target frames**. Excess ranges from 4.478 to 5.562 dB (median 5.018).
Bin 2 varies more strongly: its reference-derived threshold is 11.697 dB and it
never passes that threshold. Yet it often has slightly greater raw excess than bin 1.
The old code ranked all bins first. An unqualified winner blocked a qualified bin
in 135 frames and reset the three-frame confirmation state.

The fix qualifies bins individually before ranking. No change to fitted background,
threshold, margin, mask, normalization or three-frame persistence. The separate-peak
margin still compares against all nonadjacent bins, including noisy ones: this
remaining conservative policy is visible rather than silently relaxed. Current
readings include `qualified_bins`, `strongest_excess_bin` and an algorithm identifier.
No historical readings or raw recordings were edited.

| Capture | Original accepted frames | Fixed selection | Total |
|---|---:|---:|---:|
| 50 cm reference holdout | 0 | 0 | 71 |
| 50 cm supported box | 104 | 246 | 302 |
| Empty after 50 cm box removal | 0 | 0 | 302 |
| Earlier reference holdout | 0 | 0 | 71 |
| Earlier 12 cm box | 15 | 17 | 302 |
| Earlier 1 m box | 90 | 95 | 302 |
| Earlier empty after 1 m | 0 | 0 | 302 |
| Earlier 1 m repeat | 59 | 72 | 302 |

All 246 fixed 50 cm detections are bin 1. Remaining rejection counts are 37
separate-peak ambiguity and 19 checking-persistence frames. A three-frame
confirmation requires two prior qualifying frames after every interruption.
The earlier 1 m trials were held by the operator according to the later user
clarification, so they do not isolate box response. These counts describe accepted
spectral changes, not certified object identities or calibrated ranges.

Historical October sessions retain their earlier outcomes: no accepted near/far
readings under the conservative MVP, zero within-session empty positives, and
35/61 false alarms for the known mismatched-background stress case. That background
transfer failure is not fixed by selection order.

This is retrospective development analysis, not a new independent validation set.
Both empty checks were excluded from fitting, but we have inspected their results.
New fixed-policy captures must test generalization, repeatability and false alarms.

## Temporal median: measured but not deployed

An offline causal five-frame median of excess, with current selected-bin evidence
required and the same threshold/margin/persistence, yields 259/302 at 50 cm vs
246/302 without the median. Both empty checks remain zero in this dataset.
It reduces detections in the operator-held 1 m records (95 -> 80, 72 -> 49).
That is not universal improvement. The median adds history/latency and cannot
recover filtered-out hardware information or calibrate a wrong distance.
The deployed fix does **not** add smoothing. No stale-range holding is used.

## There is no established hard minimum distance yet

Different mechanisms must not be conflated:

- The current software reports only bins1–4. Its smallest provisional output is
  **0.347585 m**, because bin0 is excluded. This is a display/selection floor,
  not proof that smaller physical targets are invisible. A 0.50 m reflector need
  not sit exactly at a bin center; broad windowed peaks and clutter can shift the
  winning bin. Never add an offset just to make bin1 read 0.50 m.
- Source RF settings select HPF1 350 kHz and active HPF2, nominally 40 kHz.
  The [official BGT60CUTR13AIP datasheet, §8](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60cutr13aip-datasheet-en.pdf)
  lists HPF1 settings 100/350/650/1000 kHz and a roughly 40 kHz second stage.
  These are 3 dB corners with tolerances, not brick-wall limits. We have not
  measured the board's analog response or independently read back its current
  RF settings. The firmware's matching constant profile ID is not such proof.
- At the source-derived slope, `fb=2*S*R/c`: 12 cm -> 26.97 kHz; 15 cm ->
  33.71 kHz; 25 cm -> 56.19 kHz; 50 cm -> 112.38 kHz. All are below the source
  HPF1 corner, and 12–15 cm are also below the nominal HPF2 corner.
- The equivalent beat coordinates of 350/100/40 kHz are 1.557/0.445/0.178 m.
  They are **not minimum measurable distances**. Attenuation, target reflectivity,
  leakage, SNR, multipath and calibration jointly determine practical performance.
- Mean removal, bin0 rejection and a Hann window also affect sub-bin returns.
  The 64 samples and nominal sampled bandwidth (~431.25 MHz) produce the coarse
  34.76 cm grid. Zero padding/interpolation does not increase physical bandwidth.

## Recommended next experiments, in order

1. **Software validation first.** The selection fix is now active in `range-v1`.
   Collect a fresh supported-box empty/50 cm/empty sequence without threshold tuning;
   repeat placements. No hand-held target. Reuse one reference only within a fixed
   scene. Score detection fraction and false-alarm fraction together; no meter
   accuracy claim from bin1. Preserve continuous insertion/removal evidence in a
   later recording to measure disappearance latency (separate captures do not).
2. **Controlled HPF A/B.** Existing `experiments/qualification/main.c` and
   `tools/prepare_qualification.py` already define isolated 350 and 100 kHz modes,
   RX register readback and distinct profile IDs. Inspection found changes limited
   to HPF1 selection plus common instrumentation. These sources were not newly
   built, flashed or asserted to be on the board in this task. Before an authorized
   flash, preserve the recoverable original image, establish source/build/board
   identity, compile/verify both variants, and review the exact register diff.
   Keep geometry, reflector, timing, gain and waveform fixed; capture fresh empty
   references per variant. Compare 25/40/50/70 cm as space permits, repeated in
   randomized order. Report raw spectra, rails/overload, false alarms and misses.
   A 100 kHz HPF should attenuate a 112 kHz beat less than 350 kHz, but the amount
   and net detection benefit require measurement. Increased leakage may worsen it.
3. **Only then evaluate the waveform.** If distance precision remains inadequate,
   design a supported wider sampled sweep with documented timing/slope, sample
   count, IF band and RF limits. Increasing sample count without a matching ramp
   or changing slope only in Python is invalid. A steeper ramp can move nearby
   target beats upward, but changes bandwidth/IF constraints and must be verified.
4. **Establish an empirical usable interval.** At supported known positions,
   repeat independent sessions and reserve calibration/validation data. Define
   acceptable detection rate, false alarms, bias and error for the project before
   declaring a minimum range. A single successful 12 cm or 50 cm frame is not a
   demonstrated measurement floor. Fit a common distance model only after stable
   target association; report misses alongside error statistics.

No flash was performed. Any hardware programming still requires the user's
explicit approval, as requested in the original task.

## Reproduce and files

```sh
./range-v1 test
MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.diagnose_short_range artifacts/new-diagnosis
```

The output directory must be new. `evidence/short-range-diagnosis/report.json`
contains gate counts, hashes, original/fixed/median comparisons;
`gate-diagnosis.png` shows the signal and accepted frames;
`historical-regression.json` preserves the older-session regression;
`tests.txt` records all 13 passing tests. Two new tests cover a stronger but
unqualified adjacent bin and preservation of separate-peak ambiguity rejection.
The analysis uses Git commit `4105345` for the exact pre-fix implementation.
