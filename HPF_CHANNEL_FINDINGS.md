# Receiver and empty-reference diagnosis

Completed the analysis without changing live processing, thresholds, firmware or
recordings. The board remains on HPF350 qualification firmware. No target label
was used to select a receiver, reference or estimator. This is retrospective
diagnosis; results are not new prospective validation.

## What was compared

Use the frozen joint sinusoid/DC fitter and fixed nominal 0.15–1.50 m search.
Fit all three receivers together and each receiver separately, keeping all 16
retained chirps. RX0/1/2 denote wire-array indices, not independently verified
physical antenna locations. Inspect all 12 target recordings from 350-a, 100-a,
350-b, without removing poor or ambiguous frames.

For each run compare four equal-size empty waveform means:

- first30: empty-before frames [0,30), the original reference;
- next30: frames [30,60);
- third30: frames [60,90);
- after30: empty-after frames [0,30), a retrospective reference unavailable before
  the targets were recorded. It is NOT a causal live method.

Common empty evaluation data exclude all reference frames: 11 remaining
empty-before frames and 71 empty-after frames per run, 246 total. These new
comparisons consume some formerly held-out frames for retrospective development.
The historical native-detector 0/516 result is not reused as a new independent
validation claim. No new detection gate is fitted or evaluated here.

## Receiver disagreement is real; no single bad receiver explains it

With the original 100 kHz empty reference:

| Measured position | RX0 median | RX1 median | RX2 median | Combined median |
|---|---:|---:|---:|---:|
| 30 cm | 31.1 | 29.7 | 28.7 | 30.2 |
| 50 cm | 48.6 | 50.8 | 48.3 | 49.5 |
| 40 cm | 35.7 | 34.9 | 47.1 | 41.3 |
| 40 cm untouched repeat | 37.0 | 36.4 | 46.4 | 41.5 |

Table values are cm. At 40 cm the median per-frame spread between RX estimates
is 13.8 cm, versus 3.5/3.4 cm at 30/50 cm. All channels contribute appreciable
centered energy. At 40 cm their median shares are about 32/34/34%; this is not
one overwhelmingly strong receiver controlling the combined objective.

The combined estimate optimizes shared frequency; it is not a simple average of
RX ranges. Its closeness to the label does not prove that the receivers agree
on one target. For 100 kHz at 40 cm, RX2 has the lowest median residual fraction
(0.37 versus 0.46/0.57) yet estimates roughly 47 cm. A better single-tone fit is
not automatically a better box distance. We have not demonstrated faulty RX
hardware; clutter, differing mixtures and model mismatch remain hypotheses.

| Run, original reference | Combined MAE | RX0 MAE | RX1 MAE | RX2 MAE |
|---|---:|---:|---:|---:|
| 350-a | 4.60 | 8.37 | 8.39 | 4.30 |
| 100-a | **1.83** | 3.08 | 4.74 | 4.34 |
| 350-b | **2.26** | 2.57 | 3.44 | 5.19 |

MAEs in cm give all four target recordings equal weight, including the 40 cm
repeat. A fixed receiver switch does not improve every run; choosing per-distance
winners from these labels would be an invalid deployment strategy.

## Reference sensitivity contributes, but does not explain everything

| Reference | Combined MAE, 350-a | Combined MAE, 100-a | Combined MAE, 350-b |
|---|---:|---:|---:|
| first30 (original) | 4.60 | 1.83 | 2.26 |
| next30 | 4.40 | 2.27 | 1.68 |
| third30 | 4.41 | 1.75 | 1.87 |
| after30 (retrospective) | 4.53 | 2.15 | 3.23 |

These are sensitivity comparisons, not a reference-selection contest. Do not
replace the reference with whichever row minimizes known-target errors.

On 100-a at 40 cm, swapping first30 for next30 shifts estimates by a median
absolute 1.44 cm; third30 by 0.62 cm; after30 by 3.14 cm. For its untouched
repeat, shifts are 1.36 / 0.66 / 2.98 cm. At 30/50 cm, after30 shifts are only
0.29/0.31 cm. Sensitivity therefore depends on the actual signal condition.
The final 350-a empty reference also changes individual-RX performance strongly
while barely changing combined MAE, showing why aggregate error alone can hide
instability. In 350-b at 30 cm, after30 shifts estimates by 3.52 cm.

The tool records centered waveform RMS differences as ADC units, not calibrated
RF gain/phase drift. Different reference waveforms demonstrate sensitivity to
background choice; they do not identify whether room changes, oscillator phase,
temperature or any specific physical mechanism caused it. We have not measured
a physical phase-alignment error or proven that a different subtraction method
will fix it.

## Empty scenes and limits

Every common unused empty frame still yields numeric fit estimates. With the
original reference, empty-record median fits are approximately 1.02–1.17 m;
median residual fractions overlap target values. Nothing here makes the fitter
a presence detector. No new false-positive rate is claimed for any alternate
reference or channel, and original native presence misses remain unresolved.

There are only three sequential setups and one 100 kHz run. Adjacent frames and
untouched repeats are correlated. The new plots show frame 5th–95th percentiles,
not confidence intervals or instrument-certified accuracy bounds. The original
12 combined fits reproduced their previously reported MAEs before comparison.

## Decision and next actionable experiment

Do not switch to one receiver or smooth away disagreement. Keep all channels and
the current live pipeline unchanged. The evidence now supports testing a
different treatment of background in the physical estimator: model background
as a nuisance component fitted alongside the target rather than assuming a fixed
waveform can be subtracted exactly. This is a candidate experiment, not a fix.

First require simulated recovery with varying background amplitude/phase and
known targets, checking whether background flexibility absorbs the target or
makes frequency unidentifiable. Then replay the saved target AND common unused
empty frames, reporting all receivers, fit ambiguity, error and numeric empty
outputs; do not choose parameters using each target's known distance. Preserve
these fixed-subtraction results as the benchmark. No new hardware capture or
flash is needed for that offline experiment.

## Files and reproduction

Tool: tools/diagnose_hpf_channels.py. Summary evidence and channel plot:
evidence/hpf-channel-diagnosis-1/report.json and channels.png. Every per-frame
fit remains in artifacts/hpf-channel-diagnosis-1/frames.jsonl. Inputs are hashed
and each reference's frame interval is recorded. No raw input was overwritten.

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.diagnose_hpf_channels artifacts/new-channel-diagnosis
```

Use a new output directory. The command needs saved recordings but no board.
