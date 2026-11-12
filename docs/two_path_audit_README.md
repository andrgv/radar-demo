# Ground-bounce hypothesis audit (offline; not a calibration)

This experiment fits the original 5 training poses only and compares:

- **direct**: geometric single-target direct signal;
- **direct+floor**: direct signal plus one receive-side floor bounce using a mirror-target ray.

Common nuisance parameters across *all training poses*: two RX phase offsets. The bounce model also fits one complex reflection coefficient with an approximate amplitude ≤1. It **does not** fit per-pose RX phase corrections, room signatures, or target height labels for the checks. For each pose it eliminates a nuisance overall complex amplitude by fitting the normalized cross-spectral covariance across FFT bins 4–8.

The forward model assumes a single point reflector, flat floor, co-located TX/RX, 60 GHz carrier, the device-specific 3-RX array, a +90 degree orientation, and the same reflection coefficient across poses. It models range beat frequency and carrier interference. Its one-bounce geometry is deliberately narrower than a full four-ray model.

## Install

Copy `two_path_geometry_audit.py` into repository `tools/` and `test_two_path_geometry_audit.py` into `tests/`, or use `git apply radar-two-path-audit.patch` at project root.

No SciPy installation required; NumPy and Matplotlib are already in project dependencies.

## Run

```bash
.venv/bin/python tools/two_path_geometry_audit.py --self-test
.venv/bin/python -m unittest discover -s tests -p 'test_two_path_geometry_audit.py' -v
.venv/bin/python tools/two_path_geometry_audit.py recordings/box-angle-01 \
    --config configs/qualification-hpf350.json \
    --output artifacts/two-path-audit-01
```

It uses **original** qualification-hpf350 configuration and neutral RX gains; it does **not** use the exploratory gains calibrated from the held-out center-repeat. It fixes roll=+90° based on prior development work. This is still not a fully independent experiment, since the geometry was explored on the same dataset.

## Outputs

- `summary.json`: train-only fit, modeled receiver gains and floor coefficient, scores, held-out heights, and ambiguity margins.
- `comparison.png`: model comparison and the height score profiles for check_up/check_down.

### Crucial restrictions

- Training positions: `center`, `left`, `right`, `up`, `down` (four were below the original quality gate).
- Held-out development checks: `check_right`, `check_left`, `check_up`, `check_down`, `center_repeat`.
- **The inversion receives known fixture X and Y** for each held-out pose, solely to give the height model the best possible chance. **It does not receive true height**. This is an *optimistic constrained-Z experiment*, **not a robot-ready 3D estimator**.
- It never writes an updated calibration JSON and does not relax the original quality gate.
- An excellent score alone is insufficient: the model can have several equally likely heights, even for perfectly generated synthetic input. Compare `score_gap_nonlocal` and the entire `plausible_z_span_m`.
- Direct box returns are removed by saved complex background subtraction. Bottle-box and bottle-floor multipath remain possible.
- A failed one-bounce fit does not rule out higher-order paths, scattering from different points of the tall bottle, incorrect array model, or the transmitter-side floor bounce.

The 60 GHz wavelength is about 5 mm. At this geometry, a ground-reflected receive path differs from direct path by a few to ~15 cm, *smaller than the ~35 cm range-bin spacing*. Both paths can contribute to a single range cell while accumulating large carrier-phase differences.

## Scientific decision rule

Only retain a floor-bounce hypothesis if it improves held-out height prediction *and* explains the measured complex spectrum, without ambiguous height solutions. Even success here remains same-room development evidence and cannot certify cross-room or moving-robot elevation accuracy.
