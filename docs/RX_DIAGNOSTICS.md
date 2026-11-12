# Current-frame receiver inspection in the joint GUI

The Results + comparison tab now shows receiver-level evidence beside the
existing distance. It addresses the disagreement and mixed-waveform behavior
found in [the residual investigation](PHASE_RESIDUAL_INVESTIGATION.md), without
turning an exploratory fit into an automatic distance or detection decision.

## Use

Restart the GUI to load the new code. No firmware change or additional flag
is needed. Replay the fixed-target/operator control:

```sh
./range-v1 rd-gui --replay recordings/gui-20261111-093723-246315/live-004 \
  --view-range-bins 8
```

Or use the existing AVG16 live configuration and actual serial port:

```sh
./range-v1 rd-gui --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL --view-range-bins 8 \
  --motion-aware --track-range-metric quadratic
```

The optional motion-aware readout still follows its existing policy. RX
inspection is explicitly about a separate **1D range group**, even when the
current large readout comes from an RD feature. No raw RX range is copied into
an individual Doppler feature's measurement.

## What to read

With no table selection, **1D RX inspection** describes the nearest current
confirmed baseline group, including a group whose pooled fine estimate remains
unresolved. Selecting a return with confirmed 1D support switches inspection
to that group. An RD-only, missing or unconfirmed selection shows no confirmed
1D support; it does not silently retain or substitute a previous group's data.

The row shows each RX's independently refined current Hann-spectrum peak within
the same group boundaries, or its unresolved reason. Matching colored markers
appear on the range profile. Boundary or competing-peak results remain blank.
Peak amplitudes use each RX's spectrum, whereas the main power curve averages
RX power, so marker heights need not equal the main curve.

**Spread** is the maximum minus minimum of resolved RX peaks. It is unavailable
with fewer than two resolved peaks; unresolved RX are not included as zero or
boundary distances. Read their explicit unresolved states alongside spread.
An amber disagreement note appears above one quarter native bin (about 8.7 cm
for the current profile). This is an engineering inspection threshold, not a
calibrated confidence interval, range-error tolerance or presence test.

**Single-tone unexplained** is the fraction of centered raw ADC energy not
explained by independent DC/cos/sin amplitudes per chirp/RX at the existing
pooled FFT range. It is a bounded linear fit, not a new frequency search or
the optimized offline phase estimator. A note appears above 50% unexplained
energy. Farther reflectors, other Doppler components and FFT peak bias can all
increase it; a high value alone does not establish a wrong distance. If the
pooled range is unresolved, no model frequency is forced and this metric is
unavailable. An RX peak being unresolved also produces an amber note.

No diagnostic note means only that these checks did not flag the current data.
Receiver agreement shares the same scene and is not independent confirmation,
physical target identity or calibrated accuracy. The original foil run's first
near hold is an example of useful distance output with RX disagreement. Thus
the notes do not filter distances, alter CFAR or enable RD-only promotion.

## Recording, freshness and cost

New joint readings record `receiver_diagnostics` with the current sequence,
confirmed group IDs/support, per-RX peaks/reasons, spread, residual and notes.
Recording metadata includes the method, inspection thresholds, limits and source
hash. Old captures gain diagnostics when replayed; original raw data and saved
readings are not rewritten. No target is inferred from a capture's scene label.

The computation reuses the result bank's existing dense spectrum, adds three
peak inspections per confirmed 1D group, and one small shared-frequency linear
model when the pooled FFT range is available. It does not run the expensive
alternating nuisance/phase search in the live loop. The isolated diagnostic
p95 was below 0.44 ms per group on this machine in two representative checks;
this is not a live timing qualification. Existing GUI redraw/freshness limits
and startup clock gates are unchanged.

Rejection, timeout, stream reset, unconfirmed recovery and loss of current
support clear the current inspection. Stale/mismatched GUI views clear labels
and markers with the other measurements. Selection updates labels and markers
immediately, including replay snapshots with no incoming frames.
Window shutdown cancels pending plot redraws before Qt destroys the canvases.

[Implementation/replay review](../evidence/rx-diagnostics-20261111/README.md) ·
[Capture setup catalog](CAPTURE_CATALOG.md)
