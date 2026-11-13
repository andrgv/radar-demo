# Glass/drywall classifier pilot — 2026-11-08

Implementation: `radar/material.py`; guide: `docs/MATERIAL_CLASSIFICATION.md`.
Inspected upstream project: `povilasDadelo/Material-classification` at
`0455250483e5d4acee7d61347ca9af7d5c28e477`. The implementation is independent;
no upstream SDK, source, data or weights are included.

## Experiment

The user clarified that OPEN recordings in `glass-pane-100cm-01` faced drywall
and CLOSED recordings faced the original window. The radar changed direction;
the background changed too. Glass was not removed. Drywall distance is unknown.
The source metadata is preserved, and the corrected interpretation is recorded
in `experiments/materials/window-drywall-repeat.json`.

Pairs 1/2 train; pair 3 is excluded from this fit. Pair 3 had already been viewed
in previous door analysis, so the result is exploratory rather than blind.
Features are per-RX stationary range power at fixed bins 2/3/4, with ten-frame
nonoverlapping median windows after ten skipped frames. These bins were chosen
around the nominal 1 m location before this fit. Hyperparameters and margins
are fixed in source; test rows do not affect training or early stopping.

| Recording excluded from fit | User's label | Prediction | Uncalibrated glass score |
|---|---|---|---|
| open-03 | drywall | drywall | 0.1705054 |
| closed-03 | glass | glass | 0.8814989 |

Both recordings were classified correctly; neither decision was uncertain.
This is two repeated views of two known surfaces, not evidence of 100% material
accuracy or recognition of a new window/wall. Different distance, angle,
background, frame and coating can explain the separation.

Local model: `artifacts/material-glass-drywall-pilot/{model.json,booster.ubj}`.
Local detailed report: `artifacts/material-glass-drywall-pilot/report.json`.
`report.json` in this evidence directory retains a portable snapshot of that
report, including raw hashes. The trained model is tracked at the paths above;
all session recordings are preserved in `data/material-study-2026-11-08/`.
Restore them with `python3 tools/restore_material_recordings.py` before replay.

Reproduce in a fresh output directory:

```bash
.venv/bin/python -m radar material-train experiments/materials/window-drywall-repeat.json artifacts/material-glass-drywall-rebuild --bins 2 3 4
```

## Verification

- All **13** material tests pass. Tests cover channel ordering, stationary echo
  retention, shared live/replay feature windows and predictions, held-out label
  independence, duplicate/subset-frame leakage, strict specimen/scene splits,
  profile and corruption rejection, capture interruption, and connection cleanup.
- CLI training and separate saved-replay commands succeed on both actual test
  recordings. Each contains 304 raw frames and yields 29 complete feature windows.
- The full `tests` suite ran **131** tests: **129 passed**, and two errored because
  an existing firmware dependency is absent at
  `../mtb_shared/sensor-xensiv-bgt60cutrxx/release-v1.1.0/register_hal/xensiv_bgt60cutrxxb_register_hal.h`.
  These are `test_register_profile_reveals_highpass_corner` and
  `test_scope_mux_preserves_spi_and_io_voltage_fields`, neither of which uses the
  new material code.
- A fake USB source verifies live capture/scoring against replay. No new physical
  board capture or new window/wall evaluation was performed during implementation.
- `git diff --check` passes. The existing edit to `radar/wavvy_range_filter.py`
  was preserved.

Dependencies installed for this Mac: XGBoost 3.4.1, SciPy 1.18.1, and Homebrew
OpenMP (`libomp` 23.1.5). XGBoost is an optional project dependency under
`.[material]`; ordinary range commands do not import it.
