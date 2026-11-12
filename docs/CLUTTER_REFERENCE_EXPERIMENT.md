# Clutter-resistant reference experiment

The [fixed-position bare/foil/bare control](../evidence/material-control-20261112/README.md)
now confirms foil recovery (~51 cm raw-model range) with no bare-box model
recovery. Operator B and unchanged footprint do not prevent a temporally
confirmed weak scene peak near 29 cm after foil removal. It is inconsistent
with the 50 cm box front and must not become the primary. Next make raw model
quality and model-qualified inspection explicit in the display; no immediate
repeat capture is needed.

The [matched background check](../evidence/matched-background-20261111/README.md)
uses only the first half of the first empty hold to fit fixed waveform/power
references. All 821 target frames show scene changes, but blind residual peaks
miss nominal range; the waveform change probe also flags all later empty frames.
Simple subtraction is not promoted. The subsequent
[empty-trained one-tone/RX test](../evidence/empty-trained-tone-20261111/README.md)
permits variable phase/amplitude, but still recovers no bare-box ranges.
It passes the foil target holds and empty controls; this limits the conclusion
to the mixed/weak scene rather than supporting a global range correction.
Next use the [same-position material control](EMPTY_TRAINED_BACKGROUND.md).

The [fresh bare-box/operator-B check](../evidence/bare-box-b-20261111/README.md)
now supplies a failing frozen-settings case: no numeric target-hold ranges,
with both reference masking and multiple fine-spectrum peaks. Existing OS,
phase and weak-feature checks are not a validated replacement; preserve this
case before further changes rather than requesting an immediate repeat.

The latest [weak-feature confirmation stage](WEAK_FEATURE_CONFIRMATION.md)
adds consecutive confirmation, separate IDs and current inspection history
under `--experimental-weak`. It preserves the original OS experiment and
strong/main policies. Operator A is now confirmed for the bare-box 120 cm
near-return case, so that case needs clean correspondence validation at B.

A subsequent [weak-candidate experiment](WEAK_CANDIDATE_EXPERIMENT.md) adds
`--experimental-weak` inspection using OS/RD support plus raw-frequency peak
geometry. It filters the known empty controls but still selects a wrong-range
scene return in one target hold. The original `--experimental-os` comparison
and default primary remain unchanged.

Known capture setups, timing labels, firmware/configuration references and
uncertainties are indexed in [the capture catalog](CAPTURE_CATALOG.md). The
latest unchanged-setting foil repeat is reviewed
[here](../evidence/foil-box-repeat-20261111/README.md); it does not promote OS.

The subsequent [residual/RX investigation](PHASE_RESIDUAL_INVESTIGATION.md) also
shows why explaining a strong background is insufficient for selecting a
target: lower residuals coexist with receiver disagreement and empty-scene
probe fits. Detector and live distance policies remain unchanged.

The frozen CA baseline averages surrounding reference powers. The stationary
80 cm failure showed that two farther bins contributed 86–92% of the reference
power around the expected target region. This experiment compares an ordered
statistic reference without changing the baseline, firmware or timing policy.

## Fixed prototype and candidate policy

The experimental detector sorts the same reference cells and selects
`k = ceil(0.5 * actual_reference_count)`, the lower median for even counts.
It keeps guard 1, training/minimum 4, multiplier 2, the saved detection mask,
confirmation and conservative fine estimator. No rank/factor sweep was used.
The algorithm follows the standard kth-smallest OS construction described in
[MathWorks CFAR documentation](https://www.mathworks.com/help/phased/ref/phased.cfardetector-system-object.html).
The chosen rank/multiplier is an empirical development preset, with no
calibrated false-alarm probability or equivalence to the CA multiplier.

The candidate selector requires one current OS group, confirmed presence,
resolved current fine range, and exactly one current raw RD maximum within the
group's accepted range bins. Multiple groups or RD maxima and missing RD
support produce explicit withholding reasons. Raw RD support is not independent
confirmation, physical-object identity, or necessarily a confirmed RD track.
The selected OS result is always inspection-only and never primary-eligible.

## Why this does not replace the current primary

The fixed reference reduces strong-training-return masking and recovers many
numeric estimates in the 80 cm capture. However, it also confirms a close
approximately 30 cm feature in the target-absent A/B control. Unique current RD
support cannot establish that a persistent stationary reflector is the added
target. Earlier 50 cm placements also retain different ranges despite better
coverage. These results fail added-target specificity and do not certify
accurate range recovery.

The primary remains the exact frozen 1D CA baseline. OS is disabled by default.
The comparison is useful for diagnosing the statistical reference failure,
not a validated fix for stationary target recognition. No range blacklist,
captured empty subtraction, fitted distance offset or automatic RD-only
promotion was added. Target-absent reflectors may be legitimate scene returns;
they cannot be silently relabeled as the added test object.

## Try the comparison without hardware

```sh
./range-v1 rd-gui \
  --replay recordings/rd-gui-20261111-133435-428121/live-001 \
  --experimental-os --view-range-bins 8
```

The results tab adds an **Experimental OS inspection** readout and a dashed
OS threshold on the 1D profile. It reports why a candidate was selected or
withheld. The CA primary and original candidate table remain unchanged. The
80 cm recording is not a standalone acceptance test; also replay the control:

```sh
./range-v1 rd-gui \
  --replay recordings/gui-20261111-093723-246315/live-005 \
  --experimental-os --view-range-bins 8
```

The flag can also be supplied to the existing live command using the matching
AVG16 config and serial port. It records `clutter_comparison.os` with native
power/reference/thresholds/counts, groups, confirmation and fine diagnostics,
and `clutter_comparison.selection` with the candidate disposition. Metadata
records the OS rank policy and source hashes. Rejected/stale frames clear
comparison values, and a rejection resets OS confirmation. Display throttling
and all acquisition/timing gates remain in effect. The optional branch has
replay/simulated verification; new physical live verification remains open.

## Reproduce and next decision

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_clutter_reference \
  --output evidence/NEW-CLUTTER-REVIEW
```

The tool evaluates six recordings: distance sweep, failed repeated placements,
target-present A/B, target-absent A/B, manual approach/stop/retreat, and the new
stationary 80 cm failure. It verifies CA parity with saved results, reports
coverage, conditional placement differences, empty-output episodes and unique
RD-support selection counts, and exports per-frame decisions with hashes.
All six recordings are development evidence, not independent validation.

[Comparison evidence](../evidence/clutter-reference-20261111/README.md) includes
both successful and failed intervals. Do not tune the rank until the empty
control passes and then call the same data independent validation. The remaining
problem is distinguishing close stationary scene/sensor returns and the desired
object, which the present range/Doppler evidence does not reliably resolve.
Use the preserved controls to compare a concrete additional scene/measurement
model before changing the default primary policy.

The subsequent [live paired 80 cm check](../evidence/live-os-paired80-20261111/README.md)
accepts all 1,545 frames with stable timing. Both target interiors have complete
CA/OS/selected coverage, with identical CA/OS medians of 81.53 and 82.84 cm;
both empty interiors have zero outputs. This verifies the optional branch live
in that scene, but does not demonstrate an OS advantage or negate the earlier
target-absent failure. The default primary remains unchanged.
