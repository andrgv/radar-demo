# Sub-bin association experiment and range-bias investigation

The retreat review found native-grid association ties: tracks one bin on either
side of a current peak can have identical integer range cost. The optional
`--track-range-metric quadratic` uses a three-point log-power peak coordinate
to rank current observations inside the existing native range/Doppler gates.
No prediction, smoothing, new threshold or gate expansion is added.

```sh
./range-v1 rd-gui \
  --replay recordings/rd-gui-20261111-141606-847532/live-002 \
  --motion-aware --track-range-metric quadratic --view-range-bins 8
```

For live use, add the same flag to the existing AVG16 `rd-gui --config ...
--port ... --motion-aware` command. The default metric remains `native` for
controlled comparison; this option is still experimental.

## What changes

Each usable interior RD local maximum gets a fractional `range_coordinate`
in **native-bin units**, from the log powers immediately beside its peak at
the same Doppler bin. The coordinate is clipped within half a native bin.
The first and last usable bins retain native centers because their neighbors
would include excluded DC/Nyquist cells.

The previous measured coordinate and current observed coordinate replace the
integer range displacement in assignment cost. Native-bin and Doppler gates,
ambiguity gap, reciprocal uniqueness, birth confirmation and bounded loss rules
remain unchanged. Support-only/ambiguous frames do not update the coordinate.
A true remaining tie is still withheld. Every published point still requires
a current accepted local maximum and the existing dense fine estimator.

This coordinate only informs assignment. It is not calibrated distance and does
not replace the displayed fine estimator. Motion-aware policy fields and source
labels continue to distinguish current RD measurements from the frozen baseline.

## Remaining errors

The first retreat also contains a jump from the moving feature to a closer
stationary return, after which the real motion peak lies outside the old gate.
Sub-bin costs cannot recover an observation outside that gate, and widening it
could increase identity errors. During stopping, unresolved peaks can still
merge with stationary clutter. More numeric output does not establish identity.

The range-bias investigation compares median raw spectra in a declared near-range
diagnostic band, including each RX separately. A stable spectral peak at the
wrong nominal distance is not an interpolation or GUI redraw problem. Its
physical source cannot be determined solely from approximate endpoint labels.

[Comparison and spectra](../evidence/subbin-association-20261111/README.md)
include both the latest live run and earlier target-present/absent controls.
No fitted range offset, blacklist or change to the frozen 1D baseline is made.

## Helpful targeted capture

Use one rigid flat reflector, such as a foil-covered board, supported on the
beam centerline and facing the radar. Mark the antenna-face origin and measure
to the reflector's front surface. Keep radar pose, height, target orientation
and operator position B fixed. Record target dimensions/material and a sketch
or photo showing sensor, reflector, supports and background wall distances.

Record one sequence, logging actual handling and quiet-hold times separately:

1. 15 s empty.
2. Reflector at measured 50 cm, supported and untouched for 20 s.
3. Remove it; 10 s empty.
4. Replace at identical 50 cm marks/orientation; 20 s untouched.
5. Remove it; 10 s empty.
6. Place the same reflector at measured 120 cm; 20 s untouched.
7. Remove it; finish with 15 s empty.

Use the same firmware and settings, and keep failures. This is a source/geometry
diagnostic, not an offset-fitting dataset. A simpler reflector helps distinguish
complex target/multipath selection from systematic range-scale/model error.
The repeated 50 cm placement isolates replacement sensitivity. No broad moving
sweep is needed to reproduce the existing retreat failure.

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.investigate_motion_association \
  --output evidence/NEW-ASSOCIATION-REVIEW
```
