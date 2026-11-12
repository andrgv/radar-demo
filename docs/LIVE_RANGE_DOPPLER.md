# Live range–Doppler GUI

**Joint-results update:** `rd-gui` now also runs the frozen experimental 1D
comparison and a shared result/refinement layer. It opens the results/comparison
tab first; the native RD maps/table described below remain in the diagnostics
tab. See [combined display, policies and usage](JOINT_RANGE_DOPPLER.md).

The existing `./range-v1 gui --detector cfar` GUI runs 1D range CFAR and a fine
range estimate. The new `rd-gui` mode runs the full range–Doppler transform,
2D CFAR and conservative feature association while recording the raw stream.
It uses the same algorithms and initial settings as the association replay.

## Start live capture

Keep the current AVG16 firmware. Close the other radar GUI or serial reader,
connect the board and find its current port:

```sh
ls /dev/cu.usbmodem*
```

Replace the port below with that device:

```sh
./range-v1 rd-gui \
  --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL \
  --view-range-bins 8
```

Click **Start live + record**. Every run creates
`recordings/rd-gui-TIMESTAMP/live-NNN`, containing the same raw frames, wire
log, arrival log, config and capture summary used by the earlier GUI.
`readings.jsonl` additionally records CFAR candidates, feature states, current
measurements, ambiguity/support, ended tracks and transport quality. Metadata
preserves the CFAR/association settings and processing source hashes.

`--view-range-bins 8` zooms the plot to the nearby eight usable range bins;
it does not filter CFAR, association or the table. Omit it to show every usable
range bin, or change the plot-zoom control while running. The table always
includes all-range feature hypotheses.

## Results to show and how to read them

The display uses multiple feature rows because a single chosen distance can
hide walls, competing returns and unresolved associations.

| Display | Meaning |
|---|---|
| Full power map | Nominal range versus cycles per saved block, including zero Doppler |
| Threshold margin map | Power relative to the empirical 2D CFAR threshold; above 0 dB passes |
| White outlines / red × | Accepted cells / raw local maxima |
| Cyan circles and IDs | Confirmed current local-maximum measurements |
| Orange diamonds | Current accepted-cell support with unresolved association |
| Feature table | ID, state, nominal range, range bin, normalized Doppler, threshold margin, support and age since peak |

Only a fresh **Measured peak** row gets a range/frequency point. Nominal range
is simply `native bin × nominal bin spacing`, marked `~`; it is not the old
1D fine fit, calibrated distance or a verified object location. The native
spacing is approximately 0.35 m with the current profile. The display does not
claim centimeter accuracy.

Confirming, ambiguous and missing rows have **no distance measurement**.
Ambiguous support is shown in native range bins, not as a point at the old
distance. Ended IDs are reported without keeping their old position on screen.
IDs represent associated radar features; a wall, multipath return or operator
can also form a persistent feature.

Doppler remains **cycles per saved block**, not m/s. A zero bin is not proof
that an object is stationary in the world; a moving robot gives stationary
obstacles relative Doppler. No wall-versus-obstacle classifier or autonomous
collision decision is added.

The full-map color span follows each frame's maximum; the threshold-margin
color scale is fixed. The right map and table margins help distinguish weak
passing cells from strong ones without treating dB as calibrated SNR/dBm.

## Freshness and recording behavior

Processing and raw recording run in a worker; the GUI draws the latest result
and may skip redraws without skipping algorithm updates or raw recording.
Snapshots are immutable and tied to their frame sequence. Stale or mismatched
snapshots clear the maps and table.

Device discontinuities, invalid frames, host clock failures and serial backlog
clear active hypotheses and publish no current measurement. A stream stall
clears the display within one second and preserves the partial recording.
Stop clears point displays immediately while the worker closes the recording.
The backlog check uses actual packet size, including the AVG16 timing payload.
Existing clock thresholds are retained.

The status line shows frame sequence, display age, processing time, CRC/gap
counts and host clock state. Display age is time since the worker delivered
the frame; it does not certify absolute sensor-to-screen age. A timing rejection
may therefore clear the display even while raw packets continue to be saved.
Retain that recording for diagnosis instead of relaxing the gates.

## Replay and inspect without a board

```sh
./range-v1 rd-gui \
  --replay recordings/gui-20261110-221227-169414/live-001 \
  --view-range-bins 8
```

Replay uses the recording's saved config unless a matching `--config` is
supplied. It opens no serial port and creates no new live recording. Replay
checks device/map validity but does not certify original host freshness.

A deterministic screenshot can be generated from a replay frame:

```sh
./range-v1 rd-gui \
  --replay recordings/gui-20261110-221227-169414/live-001 \
  --snapshot-frame 502 --view-range-bins 8 --snapshot /private/tmp/rd-gui.png
```

Snapshot mode requires replay and never implicitly opens the board.

## Settings and verification

The `--rd-*` CFAR settings and `--track-*` association settings match the
[replay CFAR](CFAR_2D.md) and [association](RANGE_DOPPLER_ASSOCIATION.md)
defaults. Both are enabled automatically in `rd-gui`; no empty capture is
required. The scalar 1D GUI remains available as before.

The [GUI verification record](../evidence/rd-live-gui-20261110/README.md)
contains rendered measured/ambiguous/missing cases and exact parity checks
against both existing association replays. Simulated serial tests cover raw
recording, quality rejection and timeout clearing. A physical live capture
with this new GUI has not yet been tested; the board was not connected during
verification. Real detection accuracy, weak/slow motion and physical-object
identity remain open, as in the replay results.
