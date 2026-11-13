# Trying glass versus drywall

This workflow reads the BGT60CUTR13AIP data already produced by your board. It
trains a small XGBoost model to compare glass-facing and drywall-facing readings.
It supports saved recordings and a live USB connection. It needs no new firmware.

The first model has been trained using your existing recordings. It correctly
classified the two recordings excluded from this fit: one view of your original
window and one view of your original drywall. There were only **two test
recordings of two known surfaces**. This does not establish an accuracy rate for
other windows or walls. Pair 3 was inspected during earlier door analysis, so this
is an exploratory repeat check, not a blind material-recognition study.

## What was adapted

The source project is [Povilas Dadelo's material-classification
repository](https://github.com/povilasDadelo/Material-classification), inspected
at commit `0455250483e5d4acee7d61347ca9af7d5c28e477`. Its
`dataset_building.ipynb` records three RX channels through the BGT60TR13C/MCU7
Radar SDK. Its `xgb1D.ipynb` flattens those readings and trains XGBoost. The
collection notebook's example classes are apple, coke, orange, tomato, kefir and
water; it does not supply a trained glass/drywall model.

This project independently implements that approach using the existing GRD3 USB
reader and recording format. No upstream source, SDK binaries, data or pretrained
weights are bundled. The upstream repository does not declare a license.

There are two input choices:

- `spectrum` (default): the strength of stationary echoes at fixed FFT bins,
  separately for each of the three receivers. This retains material reflection
  information while reducing sensitivity to the absolute waveform phase.
- `waveform`: three flattened, centered first-valid-chirp waveforms, matching the
  upstream input concept. It uses this board's 16-bit transport scale.

Both skip the configured startup chirp and the first ten recording frames, then
take medians over nonoverlapping groups of ten frames. Nothing removes the
stationary glass/wall echo. Raw receiver channels are preserved; unverified angle
calibration is not applied. XGBoost uses 100 trees with maximum depth 2, with
equal total weight per training recording. Parameters and decision margins are
fixed before evaluation. No test examples are used for fitting or early stopping.

The pilot uses bins **2, 3 and 4**, a fixed neighborhood around the provisional
1 m return (bin 3). These bins were chosen from the measured glass distance and
configured scale, not by searching the test outcomes. The scale is provisional,
and other objects can contribute within these coarse bins. The drywall distance
in the old experiment is unknown.

## Files already prepared

For a fresh checkout, restore the archived recordings first:

```bash
python3 tools/restore_material_recordings.py
```

The [recording archive](../data/material-study-2026-11-08/README.md) includes all
initial attempts, training recordings and later live tests. The trained model
and reports listed below are tracked directly, so they are available after pull.

- `experiments/materials/window-drywall-repeat.json`: labels and train/test split.
- `artifacts/material-glass-drywall-pilot/model.json`: feature settings and model
  provenance. Keep its sibling `booster.ubj` with it.
- `artifacts/material-glass-drywall-pilot/report.json`: predictions and limitations.

Your clarification supplies the labels: old `open-*` recordings faced drywall;
old `closed-*` recordings faced the window. The original notes about removing
glass were inaccurate. The manifest records that correction without changing
the original recordings. Pairs 1 and 2 train the model; pair 3 checks repeats.

## Try the current model live

Run commands from the `radar-demo` directory, with any other radar program stopped
so the USB port is available. For this Mac, the dependencies are installed in
`.venv`, including XGBoost and its required OpenMP runtime.

1. Put the radar on a stable support, facing straight toward the middle of the
   window. Keep it away from the metal frame, handle and heater grille.
2. Keep the window **closed** and raise the blinds. Measure **100 cm from the
   radar antenna face to the glass**, along the direction it faces.
3. Run this command. It gives you five seconds to step away, records for thirty
   seconds, and prints a comparison about once per second:

```bash
.venv/bin/python -m radar material-live recordings/material-live-window-01 --model artifacts/material-glass-drywall-pilot --port /dev/cu.usbmodem1103 --seconds 30
```

Output is `glass-like`, `drywall-like` or `uncertain`. A glass score of 0.8 means
the model favors its glass examples; it **does not mean an 80% chance of glass**.
Scores between 0.35 and 0.65 produce `uncertain`. These arbitrary margins do not
reliably reject unfamiliar materials. Plastic, metal or an empty scene can get
either material label because the model only learned two classes.

Try a wall at the same measured **100 cm**, height and straight-on angle. Keep
the radar still during each capture. Use a fresh output name such as
`recordings/material-live-wall-01` in the command. You can move the radar between
surfaces; record its new position and distance each time.

Raw frames and per-window predictions are saved. An interrupted/failed material
capture lacks a completion marker and is excluded from training and normal
replay. Repeat it in a fresh directory.

## The useful next test: a different window and wall

A different window tests whether the model learned a pattern that carries over
to another physical surface. Repeating the original view mainly tests whether
that view stays recognizable. You do not need a removable sheet of glass.

Record a **different physical window** at 100 cm with the window closed, blinds
raised and radar facing its center:

```bash
.venv/bin/python -m radar material-record recordings/material-window-02 --port /dev/cu.usbmodem1103 --config configs/qualification-hpf350.json --label glass --specimen window-02 --scene room01-new-setup --distance 1.0 --seconds 30
.venv/bin/python -m radar material-predict recordings/material-window-02 --model artifacts/material-glass-drywall-pilot --output artifacts/material-window-02-result
```

Then record a **different wall** at the same measured 100 cm, height and angle:

```bash
.venv/bin/python -m radar material-record recordings/material-wall-02 --port /dev/cu.usbmodem1103 --config configs/qualification-hpf350.json --label drywall --specimen wall-02 --scene room01-new-setup --distance 1.0 --seconds 30
.venv/bin/python -m radar material-predict recordings/material-wall-02 --model artifacts/material-glass-drywall-pilot --output artifacts/material-wall-02-result
```

Use the actual room/setup IDs. Use the same specimen ID whenever recording the
same physical window or wall again. Keep these new test recordings out of
training until after scoring them. Preserve misses and uncertain results too.
One successful new pair would be encouraging but still small evidence: window
coatings, frames, background, angle and room layout can all affect the echoes.

## Replay or rebuild the first model

Replay one of the test recordings:

```bash
.venv/bin/python -m radar material-predict recordings/glass-pane-100cm-01/closed-03 --model artifacts/material-glass-drywall-pilot
```

Rebuild the same fit in a new directory:

```bash
.venv/bin/python -m radar material-train experiments/materials/window-drywall-repeat.json artifacts/material-glass-drywall-rebuild --bins 2 3 4
```

For new datasets, copy the manifest and list explicit `path`, `label`,
`specimen_id`, `scene_id`, `distance_m` and `split` fields. Paths are relative to
the manifest. At least two training recordings per class and one test recording
per class are required as a software minimum, not a recommended study size.
Use `surface_holdout` evaluation when test surfaces **and** rooms/setups are
absent from training. It rejects overlapping specimen and scene IDs. The
`repeat_holdout` mode explicitly permits the weaker repeat comparison.

The workflow rejects duplicate/overlapping raw ADC frames, mismatched configs,
changed loss/error counters, gaps, corrupt/truncated data and suspect timing.
Replaying training data is flagged by `overlaps_training_frames: true`.
Results count whole recordings, rather than treating neighboring frame windows
as independent material tests. The saved booster includes only training data;
its feature definition, source hashes and XGBoost version are retained.

On another machine install the optional dependency with:

```bash
.venv/bin/python -m pip install -e '.[material]'
```

On macOS the XGBoost wheel may also require `brew install libomp`. The original
distance GUI still reports material as unknown; the experimental classifier
runs through the explicit `material-*` commands.
