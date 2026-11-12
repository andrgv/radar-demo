# Weak-candidate selection experiment

The next stage, [weak-feature confirmation](WEAK_FEATURE_CONFIRMATION.md), is
now available in this same mode, with separate IDs and current measured history.
Later setup clarification places the operator at A / within range during the
bare-box 120 cm hold; its ~32 cm feature is therefore not proven spurious or
proven to be the box. The capture catalog preserves this clarification.

`--experimental-weak` adds an inspection branch combining OS/RD support and
raw-frequency peak geometry. It filters the known empty controls and retains
some previously missed ~80 cm candidates. A roughly 32 cm scene return during
a 120 cm box hold with the operator in range still lacks established object
correspondence, so **it is not a primary-distance fallback or validated object selector**.

## Use

Restart the GUI. No firmware change is needed; the mode is disabled by default
and implies the original OS comparison:

```sh
./range-v1 rd-gui --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL --view-range-bins 8 --experimental-weak
```

For replay:

```sh
./range-v1 rd-gui --replay recordings/rd-gui-20261111-133435-428121/live-001 \
  --view-range-bins 8 --experimental-weak
```

It can accompany `--motion-aware --track-range-metric quadratic`, but never
feeds that readout. Read **Weak scene candidate (inspection only)** separately
from the main distance. Its value is the existing OS FFT peak, not an accepted
phase estimate. The label preserves the raw model's accepted/withheld state.
Frequency-peak support can survive background energy without accepting the
complete waveform model or establishing which physical object produced it.

## Fixed hypothesis

CA, OS, RD, association, phase-estimator settings and motion policy are unchanged.
OS retains guard/training/minimum/factor 1/4/4/2, lower-median reference, the saved
range mask and three-frame confirmation. The new selector requires:

1. One confirmed OS group with resolved fine range and exactly one current RD
   local maximum in its support, as in the original OS selector.
2. A current raw real-tone/DC optimum strictly inside that group's half-bin
   boundaries, with one comparable optimum and near-optimal span at most half
   a native bin.
3. At least two RX frequency optima inside support and within a quarter native
   bin of the shared optimum.

The geometry settings are inherited from the phase experiment; there was no
threshold/rank sweep, label fit, support expansion, distance blacklist, empty
reference, smoothing or prediction. Original phase residuals and accepted
`range_m` rejection remain unchanged. All weak outputs are inspection-only and
ineligible for the primary. RD and RX evidence share ADC data and are not
independent confirmation. These geometry checks are not calibrated confidence.

Rejection, timeout, reset and missing/multiple/unconfirmed support clear the
current comparison; recovery must reconfirm. New readings record
`clutter_comparison.weak_selection` and `weak_phase_fit`; metadata records the
method, original phase settings and source hashes. Without the flag no extra
OS/phase work runs. The original `--experimental-os` behavior is preserved.

## Outcome and next step

Across 15,534 frames in eleven recordings, the new selector emits zero values
in 3,045 scored target-absent frames, versus 774 for old OS+RD inspection. The
~80 cm stationary failure gains 297/714 candidate values, median 87.7 cm,
fragmented into 20 episodes (longest 16.4 s). These are current scene candidates,
not demonstrated continuous tracking or verified target-identity accuracy.

The bare-cardboard 120 cm hold gains 19/178 values near 32.1 cm, with the raw
range model still rejected. The repeated 50 cm miss gains only 4/218 values,
and other biased holds remain biased. Empty-control improvement alone therefore
does not justify promotion. The hypothetical CA-first fallback in the report
is only an offline comparison. No primary or motion-aware policy was changed.

The [motion-seeded continuation investigation](WEAK_MOTION_LINK.md) is now
implemented as recorded inspection status in this mode. It adds only three
isolated points and no settled-hold coverage. The weak ~80 cm candidates mostly
fail the RD birth-margin guard, as do the operator-confounded ~32 cm candidates.
Separate [weak-feature confirmation](WEAK_FEATURE_CONFIRMATION.md) is now
implemented without changing the original birth margin. Physical object
correspondence remains open. A clean bare-box/operator-B control, rather than
another foil repeat, is the useful next validation before promotion.

[Selection metrics and failures](../evidence/weak-candidates-20261111/README.md) ·
[Live-adapter parity and GUI review](../evidence/weak-candidates-live-20261111/README.md)
