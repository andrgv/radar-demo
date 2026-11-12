# Live range–Doppler GUI verification

[Measured feature view](measured.png) · [Ambiguous support view](ambiguous.png) ·
[Missing/unconfirmed view](missing.png) · [Parity audit](summary.json) ·
[Usage](../../docs/LIVE_RANGE_DOPPLER.md)

The new `rd-gui` command runs the existing full-map 2D CFAR and association
algorithms in a capture worker and renders only the latest result in Qt. It
records raw frames, original serial bytes, feature diagnostics, settings and
processing hashes through the shared capture path. The old `gui` command
continues to provide 1D CFAR/fine-range display.

## Meaning of the outputs

The two maps show full return power and power relative to the empirical CFAR
threshold, retaining zero Doppler. Confirmed current peaks get cyan IDs and
table rows with native bins and approximate nominal bin-center ranges. The
table does not present a 1D fine fit or calibrated object distance.
Ambiguous, missing and confirming rows have blank point-distance fields.
Ambiguous support is drawn from actual current accepted cells in orange.

Plot zoom affects presentation only. The table includes features beyond the
visible plot range; the ambiguous screenshot intentionally demonstrates that
with a measured feature at native bin 14 outside the displayed bins 1–8.
No single nearest-distance/object-present alarm is inferred from this table.

The snapshots are selected to exercise GUI states, not to score detection
performance. All use the latest 120↔30 cm recording:

- Frame index 502: the closest fast-retreat midpoint frame with a confirmed
  nonzero path-region feature. It shows a native bin-2 nominal range around
  0.70 m and +0.125 cycles/block, with a separate ambiguous feature.
- Frame index 664: a slow-approach frame with ambiguous accepted-cell support
  and blank distance for that feature; other current peaks remain visible.
- Frame index 501: the preceding time-midpoint frame, with no confirmed current
  point even though return power is bright. Confirming/ambiguous/missing states
  are visible with blank distances.

Feature IDs and Doppler bins are radar observations, not certified object
identity, physical velocity or world-motion classification.

## Verification

The live processing adapter was run over all 605 frames of `avg16-motion-01`
and all 1,149 saved frames of the follow-up. Its association reports match the
prior replay reports exactly. Full powers, CFAR thresholds and accepted masks
also match exactly. Every fresh table distance corresponds to a confirmed
current measurement; there are zero table-freshness invariant violations.
The parity audit uses saved data and does not apply original host-arrival
gates as if replay were a fresh sensor stream.

72 focused tests pass, covering the new adapter/Qt interface and existing
association, CFAR, stream, clock, 1D GUI and protocol paths. New checks include:

- Independent live adapter versus replay algorithm equivalence and immutable,
  sequence-tagged view snapshots.
- Quality-gate rejection on serial backlog, host clock failure and invalid
  frame flags while retaining every raw frame and clearing active features.
- Stream timeout, stop and stale/mismatched views clearing maps and point rows.
- Ambiguous/missing rows refusing to display an old point, even in a malformed
  presentation input.
- Replay using no serial access or live recording; plot zoom retaining all
  table features; real worker start/stop wiring to the shared stream function.
- Snapshot mode rejecting implicit live access.
- Size-aware backlog calculation for all packet versions, including the
  7,868-byte AVG16 timing packet. The two-frame backlog rule and clock thresholds
  are preserved; the old hard-coded 6,580-byte assumption is removed.

The GUI was rendered offscreen and visually inspected in all three states.
Adapter computation is sub-millisecond on typical frames in this check, but
the report's timings exclude Qt redraw, serial transfer and sensor latency.
The GUI can skip redraws while the worker still processes/records every frame.

**No physical serial device was opened for this verification.** No USB modem
port was visible, so a real board capture with the new GUI remains to be
checked. The current AVG16 firmware is retained; no reflash is required.
The existing clock/freshness gates may clear a real display if host timing is
unstable, while raw recording continues for diagnosis. Detection accuracy and
physical-object identity are unchanged from the replay prototype's limits.

## Reproduce

```sh
.venv/bin/python -m tools.review_rd_live
QT_QPA_PLATFORM=offscreen MPLCONFIGDIR=/private/tmp/mpl-radar ./range-v1 rd-gui \
  --replay recordings/gui-20261110-221227-169414/live-001 \
  --snapshot-frame 502 --view-range-bins 8 \
  --snapshot evidence/rd-live-gui-20261110/measured.png
```

Use indices 664 and 501 for the ambiguous and missing cases. Snapshot generation
opens no serial port and saves no new live recording.
