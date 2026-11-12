# Clutter-reference decision

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Implemented and evaluated one fixed OS reference preset, with a conservative
inspection candidate selector. It is useful for exposing reference masking,
but fails the target-absent control and is not promoted to the primary readout.

## Scope

All 7,269 frames in six recordings were replayed. The frozen CA detector matches
saved decisions, reasons and fine ranges on every frame. OS uses the same
guard/training/minimum/factor (1/4/4/2), search mask, group confirmation and
fine estimator. Only the reference changes to the kth smallest power,
`k=ceil(0.5*actual reference count)`. No rank/multiplier sweep or distance fit
was performed. All data are development cases, not independent validation.

The candidate selector adds: a single current OS group, confirmed presence,
resolved current fine range and a unique current raw RD maximum inside group
support. It withholds missing/multiple RD support and multiple OS groups. This
rule does not treat shared ADC evidence as independent confirmation or certify
target identity. All selected values are marked inspection-only.

## Key results

| Scored case | Frozen CA numeric frames | OS numeric frames | OS + unique RD support |
|---|---:|---:|---:|
| New ~80 cm stationary, 714 interior frames | 0 | 578 | 332 |
| live-003 second 50 cm placement, 218 frames | 0 | 218 | 218 |
| live-005 no target, A/B/A/B, 498 frames | 0 | 403 | **402** |

In the 80 cm case, raw OS numeric values have median 91.0 cm; selected values
have median 87.9 cm. Neither figure is calibrated error conditional on verified
identity. In the second 50 cm placement, median OS output is 54.7 cm, but other
50 cm placements retain their differing ranges. More output is not enough to
establish correct reflector selection or accurate distance.

The target-absent OS feature is near 30 cm and often has unique stationary RD
support. Persistence and source agreement cannot distinguish it from an added
stationary object. Some extra empty outputs elsewhere are withheld by the
selection rule; that does not fix this main failure. The no-target scene may
contain legitimate reflectors, so these counts are added-target specificity
failures, not a calibrated false-obstacle probability.

## Implementation decision

The primary remains frozen CA and no default mode changes. The optional GUI
flag `--experimental-os` adds a labeled comparison readout and dashed threshold
profile, and records reference and candidate-disposition diagnostics. It is
disabled by default. No region blacklist, empty-reference learning, physical
speed/bearing claim, firmware change or timing-gate relaxation was added.

151 tests pass, including contaminated edge references, DC/guard exclusion,
actual-count rank selection, scale behavior, multiple-candidate withholding,
unchanged primary/RD association, optional GUI display and immediate clearing
on faults. Replay auditing covers all six captures; physical live verification
of the optional OS branch is not claimed.

The remaining problem requires additional validated scene/measurement evidence
or a concrete scene model to distinguish stationary nuisance returns. Preserve
this failed control rather than tuning or blacklisting it away. No additional
repeat of the existing scene is needed to establish this prototype's limitation.

[Full window comparison](README.md) · [Metrics and source/input hashes](report.json) ·
[All six timelines](comparison.png) ·
[Usage and algorithm details](../../docs/CLUTTER_REFERENCE_EXPERIMENT.md)
