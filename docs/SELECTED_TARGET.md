# Track one selected reflector

Use this mode to follow one return rather than accumulating multiple static
reflection regions. It uses the same CFAR and RX2 angle pipeline and preserves
the full raw recording. The persistent-map mode remains the default without
`--track-target`.

## Live whiteboard test

Close other radar readers. Keep the radar fixed and put the whiteboard face-on
at the measured **2 m starting position**. The reference below is the earlier
2 m whiteboard recording; keep that recording's original XYZ even when the
current board moves.

```sh
.venv/bin/python -m radar.cfar_map \
  --port /dev/cu.usbmodem103 \
  --config configs/exploratory-roll90-phase.json \
  --reference recordings/map-reference-whiteboard-01 --reference-xyz 0 2 0 \
  --min-range 1.5 --max-range 3.5 \
  --track-target --target-range 2 --target-bearing 0 --window 1 --plot
```

Use the current serial port, matching firmware/profile and unchanged radar
mounting. A new `recordings/target-track-...` directory is created automatically.

Wait for **TRACKING** and a green target near 2 m. Move the board slowly away
by a measured **20 cm**, keeping its orientation approximately unchanged. Compare
the measured distance with 2.2 m. Keep people out of the forward view for this
controlled check. Do not move the radar.

## What changes

- The start range/bearing select a return; they **do not calibrate, scale,
  clamp or overwrite the measured distance**.
- Three consecutive candidate observations near the starting position establish
  the lock. Multiple qualifying returns with similar association scores remain
  ambiguous rather than being chosen by power.
- Subsequent measurements must be close to the last return/predicted range and
  bearing. A different CFAR track ID alone does not change the selected target.
  All sensor-frame associations run in the acquisition worker, independent of
  GUI redraw speed.
- Default prediction tolerance is 0.25 m and 8 degrees, with a hard maximum
  0.35 m step from the last measurement, including after misses. The prediction
  is a bounded association aid; it is not displayed as a measured range or a
  verified Doppler velocity. `--track-range-gate` and `--track-max-step` expose
  the range bounds for controlled tests.
- **TRACKING:** one green target and its current measured range/bearing.
- **MISSING:** no current distance; only a gray last-observed marker and the
  dashed measured trail. Missing measurements are not filled in or held current.
- After fifteen consecutive misses (nominally 1.5 s), **LOST** is latched.
  `--track-max-misses` changes this tolerance; the current measurement is still
  blank from the first miss. Sensor/transport/timing
  faults also withdraw the lock. A distant return is never used to automatically
  reacquire the target after loss.
- Put the target back near the chosen start position and click **Re-lock near
  start** to request a new lock. To select a different starting range outside
  that window, restart with the new `--target-range`.

The raw power/CFAR profile still shows all reflections for diagnosis; only the
selected target is plotted as a current target on the right. Other returns stay
in `obstacles2d.jsonl`. `target_track.jsonl` logs every frame's selection state,
current/last measurement, rejections and trail. Stop records a terminal state
without a current measurement. This mode does not create `map.json`.

## What it does not fix

A switch from a 2.2 m return to a separate 3 m return is an association failure,
not proof of a 0.8 m range-scale error. The selected-target gates reject that
jump and report missing/lost instead. They cannot recover a genuine 2.2 m
measurement if CFAR does not resolve one.

The loaded waveform has about **0.348 m native FFT-bin spacing**, with a Hann
window. Dense FFT interpolation can locate an isolated peak between bins, but
does not add independent range resolution or establish centimeter accuracy.
Nearby reflections, target orientation and multipath can bias even an associated
return. Smooth movement through successive ghosts can still fool geometric
association. This is not verified physical-object identity, a human classifier,
or calibrated motion tracking. Keep measuring known positions to evaluate errors.

For an offline run replace `--port ...` with `--replay YOUR_RECORDING`; the same
tracker runs on every stored frame. Add `--output NEW_DIRECTORY` to retain its
results. `--snapshot IMAGE.png` saves the final view, including the stopped state.

```sh
MPLBACKEND=Agg .venv/bin/python -m unittest discover -s tests -p test_selected_target.py -v
```
