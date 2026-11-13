# Glass-specific transfer test: phase does not resolve the current failure

The primary objective is recognition of glass as an obstacle across setups.
Generic reflector points, unresolved warnings and 3D rendering do not satisfy
that objective. No replacement glass model was deployed from this experiment.

## Protocol

This test uses 27 recordings: complete door03/door04/door07 pairs, the six
corrected archived window/drywall views, and three later user-labeled controls.
Door03 and door04 are grouped as one physical door. The second door and archived
window study are separate evaluation groups; physical novelty across studies
is not independently verified. The later controls never enter fitting.

Train/test partitions exclude an entire group. ADC frame hashes are checked
for train/test overlap and raw files are unique. Whole recordings have equal
training weight; ten-frame nonoverlapping medians follow ten warm-up frames.
Scores are uncalibrated, with fixed .35/.65 control/glass-blocking margins.
Model settings are the existing pilot's fixed 100 depth-two XGBoost rounds.

Two representations are tested without per-fold tuning:

- Full-spectrum relative power, preserving all three receivers, bins 1..31.
- The same features plus real/imaginary normalized cross-RX covariance, encoding
  relative phase/coherence without assigning 3D positions.

No XYZ, selected pane range, manually selected receiver or scene baseline enters
these features. All captures have one nominal profile ID. The labels identify
closed glass in the intended beam versus open-door or drywall-facing controls,
not certified glass-free scenes or independently attributed scattering centers.
This is exploratory evaluation of previously inspected data, not blind validation.

## Results with phase included

Counts below are **recordings**, not independent material specimens:

| Held-out group | Glass-blocking recordings recognized | Controls correctly rejected |
|---|---|---|
| First physical door (door03 + door04) | 0/6 | 5/6; one uncertain |
| Second door (door07) | 2/3; one uncertain | 1/3; two falsely positive |
| Archived window study | 3/3 | 0/3; all falsely positive |

Relative-power-only results also fail, and all per-recording/window scores are
retained in `report.json`. Adding phase to this model does not give reliable
transfer. Correctly recognizing all positive window captures is meaningless if
the same model also declares every drywall view glass-blocking.

These findings reject these candidates for integration. They do not prove no
radar-only solution exists. More fitting to the same handful of scenes cannot
serve as independent validation of whichever candidate eventually looks good.
The unresolved issues remain glass-return attribution, scene/distance dependence,
coverage over incidence angles/backgrounds, and independent physical specimens.
3D calibration is a separate issue and cannot be presented as the glass fix.

## Reproduce in the persistent project environment

```
python -m venv .venv
.venv/bin/python -m pip install -e '.[material-cpu]'
python tools/restore_material_recordings.py --destination /tmp/glass-material-analysis-20261109
.venv/bin/python -m tools.audit_glass_transfer --archive-recordings /tmp/glass-material-analysis-20261109/recordings --output artifacts/glass-transfer-reproduced/report.json
```

The archive destination and report path must be fresh; if the archive is already
restored, use its existing `recordings` root. Run from the repository root. The
saved report was generated using NumPy 2.5.4 and xgboost-cpu 3.4.1. A subsequent
run of the checked-in script verifies reproducibility before accepting its report.
