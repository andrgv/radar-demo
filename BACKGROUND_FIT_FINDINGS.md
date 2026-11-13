# Fitted-background trial: not suitable for live use

Implemented an offline alternative: a target sinusoid plus two per-receiver
background nuisance modes and DC, with independent coefficients per chirp/RX.
The nuisance modes are the first 30 empty frames' chirp-averaged waveform and its
finite-record Hilbert quadrature. The target frequency is shared across receivers,
searched over the same fixed nominal 0.15–1.50 m interval. No labels were fitted,
no thresholds changed, and no best-reference or best-channel selection performed.

This particular nuisance basis is a hypothesis. Averaging chirps can cancel
background components, and the finite-window Hilbert transform is not a measured
RF phase model. It does not span every physically phase-shifted background.

## Simulation findings

- Positive control: background generated exactly in the nuisance span plus a
  distinct target recovers 30/40/50 cm across 12 phases to numerical precision.
  This checks solver mathematics, not physical adequacy.
- A target coincident with the reference tone can be absorbed completely into
  background; remaining energy is essentially zero and the result is no estimate.
  This is an identifiability problem, not a successful target disappearance test.
- Stronger test: independently phase-shift a true 90 cm sinusoid background and
  vary amplitude while keeping a weaker target. The finite-window basis fails:
  average errors are 24.62 / 13.30 / 15.68 cm at actual 30/40/50 cm. Maximum
  errors are approximately 59.86 / 49.55 / 40.31 cm. These failures rule out
  claiming the method handles general background phase variation.

## Hardware replay, retained as diagnostic evidence

| Run | Frozen fixed-subtraction MAE | Fitted-background MAE |
|---|---:|---:|
| 350-a | 4.60 cm | 8.19 cm |
| 100-a | 1.83 cm | 3.34 cm |
| 350-b | 2.26 cm | 1.92 cm |

All four target recordings per run are equally weighted, including both 40 cm
captures. This changes both background treatment and nuisance representation;
it does not isolate one physical cause. Its one-run improvement does not offset
the synthetic failure and worse other runs. No live deployment is justified.

The same common unused empty frames from the receiver study (11 empty-before,
71 empty-after per run, 246 total) remain outside reference fitting. They still
receive numeric fits. For example, the first 350-a empty-after median estimate
is about 19 cm despite no box. Adding nuisance flexibility does not supply an
empty-scene detector; low residual is not calibrated confidence. No new gate,
false-alarm guarantee, calibrated range or accuracy claim is introduced.

The GUI therefore uses the earlier fixed-subtraction estimator only, explicitly
experimental, with the unchanged native presence gate. That preserves visible
misses and exposes rejected candidates rather than hiding them.

## Reproduce

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.test_background_fit artifacts/new-background-fit
```

Summary evidence: evidence/background-fit-2/report.json. Per-frame results:
artifacts/background-fit-2/frames.jsonl. Run 2 adds the physically phase-shifted
simulation to the original run without changing the model or hardware results.
The original run is also preserved. This is one failed candidate, not proof that
every joint-background model is impossible. A next estimator should first pass
these synthetic phase/overlap challenges before requesting more physical data.
