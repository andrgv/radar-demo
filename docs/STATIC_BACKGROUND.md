# Experimental static background subtraction

## Evidence from the matched bottle control

The user recorded `bottle_only_03` and `target_with_bottle_03` without moving the radar/support between the pair. Each has 101 complete frames, matching configurations and no stored sequence gaps or device error/drop increases. At selected bin 4, adding the target changes RX1/RX2/RX3 mean power by **+5.35/+5.04/+5.12 dB**. Whole-session relative coherences are 0.945 and 0.989. The target therefore produces a consistent change across all receivers in this pair, unlike the previous target-plus-support versus empty comparison.

The raw selected-cell contrast remains about 6.7 dB, below the existing 12 dB detector threshold. That local contrast compares neighboring range cells; it is not a direct measurement of thermal noise. Persistent scene reflections affect it.

A fixed complex background spectrum was fitted using only the **first 50 bottle-only frames**. The remaining **51 bottle-only frames** were held out. Subtracting that reference before detection produced:

| Data | Frames | Frames with a detection within 0.35 m of 1.3 m |
|---|---:|---:|
| Bottle-only held out, raw | 51 | 0 |
| Bottle-only held out, subtracted | 51 | 0 |
| Target + bottle, raw | 101 | 0 |
| Target + bottle, subtracted | 101 | 96 |

The subtracted target cell's per-frame local contrast p05/median/p95 was approximately 12.04/16.09/18.48 dB. Only **6/101** subtracted target frames passed the full phase-probe checks, including the assumed forward-direction unit disk. The physical-geometry config still has neutral RX gains. Do not interpret this range-detection improvement as working 3D tracking or a validated phase reference. Whole-session residual RX2 coherence also remains below the calibration criterion, so no phase correction has been generated from this subtraction experiment.

These counts describe one matched static tabletop pair. They are not general detection/false-alarm rates, and adjacent frames are not independent experimental trials. The baseline includes the bottle; adding the target can change target–support interactions. It is not proof of isolated target RCS or material classification.

## Reproduce on saved data first

The processing now supports an explicit `--background` argument:

```powershell
python -m radar gui --replay recordings/target_with_bottle_03 --config configs/range-csk-portrait.json --background recordings/bottle_only_03 --phase-probe 1.3
```

This viewer command fits the reference using the **entire supplied bottle-only session**, not the first-half-only model used for the held-out check. It is useful for inspecting the subtraction effect without touching hardware. The banner and status identify background subtraction as experimental. Angle rejection remains active.

For a live check, the reference is relevant only if the radar, bottle, room and acquisition configuration still match it. Do not reuse this old reference after moving the setup; recapture a baseline for the new scene. The live syntax, when a matching reference is available, is:

```powershell
python -m radar gui --port COM3 --config configs/range-csk-portrait.json --background recordings/bottle_only_03 --phase-probe 1.3
```

## Implementation and limitations

`SpectralBackground` fits one complex mean range-FFT coefficient per bin and RX, averaging the supplied background frames/chirps. It stores coefficients before channel-gain calibration. Runtime subtraction applies the current complex gains consistently to both frame and reference. Acquisition dimensions, profile and timing/RF metadata must match. This is fixed-reference subtraction: no online adaptation, target association, smoothing or missed-point persistence is introduced.

When recording with background subtraction, metadata identifies the method/source and a `spectral-background.npz` snapshot is saved inside the session. Raw ADC remains unchanged. GUI replay and headless `analyze` automatically load a stored snapshot when present; an explicit GUI `--background` overrides it. Snapshot values are numeric plus JSON and load with `allow_pickle=False`. Reprocessing under another range offset/scale, gain calibration or mounting roll is supported, since raw spectral coefficients precede those choices.

Static complex subtraction assumes enough phase/amplitude repeatability between reference and measurement. Sensor motion, phase drift, changing background, target shadows, coherent multipath or including the desired object in the baseline can invalidate it. Do not use background-subtracted power as absolute reflectivity. Evaluate held-out empty-scene data and target presence independently; passing channel coherence does not establish object identity.

The original detector threshold, physical geometry, range correction and calibration acceptance checks are unchanged. No firmware was changed or flashed. Data products: `artifacts/bottle-control-03/comparison.png`, `report.json`, and `background-validation.json`. The paired mean-spectrum plot is reproducible with:

```powershell
$env:PYTHONPATH='.'
python tools/compare_background_capture.py recordings/bottle_only_03 recordings/target_with_bottle_03 --distance 1.3 --output artifacts/bottle-control-03
```
