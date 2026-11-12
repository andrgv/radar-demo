# Empty-trained background: result and next capture

**Requested material capture completed:** the [fixed-position review](../evidence/material-control-20261112/README.md)
confirms a foil model range near 51 cm, but no model-qualified bare-box ranges.
The second bare hold produces confirmed weak inspection near 29 cm despite
fixed 50 cm geometry and operator B. No immediate repeat is needed. Next improve
the GUI's model-quality/qualified-range diagnostics while preserving the main
distance. The collection protocol below is retained for reference.

The [offline one-tone/RX experiment](../evidence/empty-trained-tone-20261111/README.md)
allows current background phase/amplitude to vary while keeping empty-trained
frequencies fixed. It produces plausible inspection ranges in all 1,168 scored
foil-target frames and no inspection outputs in 1,197 held-out empty frames.
It recovers **zero of 821 bare-box target frames**. It also underfits the bare
empty scene and hits a nuisance-search boundary on one receiver in the foil
repeat. No live detector, distance or GUI policy changes are justified.

This is a model comparison on development recordings, not independent physical
accuracy acceptance. The foil results argue against applying a universal range
offset to fix the bare-box failure. They do not isolate material from placement.

## Next useful capture: change material without moving the box

Start with the **same 50 cm position**, box height, orientation, background and
operator B used for the latest bare-box run. Mark the footprint and measure
antenna face to front surface. Record an approximate photo/sketch of the
sensor, target, nearby furniture and wall, including lateral offsets. Keep the
sensor fixed. Use the same approximately 45 × 24 cm front face if available;
report actual dimensions rather than assuming the old values.

Use the current firmware and command:

```sh
./range-v1 rd-gui --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodem2103 --experimental-weak --view-range-bins 8
```

Start live recording. Suggested quiet-hold durations are:

1. **20 s empty**, operator B.
2. Insert the bare box at the marked 50 cm position; return to B; **30 s bare**.
3. Cover only the front with a removable flat foil-faced sheet, keeping the box
   footprint/orientation unchanged; return to B; **30 s foil**.
4. Remove the foil sheet without moving the box; return to B; **30 s bare again**.
5. Remove the box and foil assembly entirely from the scene; return to B;
   **20 s empty**.

Leave enough extra time for handling; record each actual transition start/end
and hold start/end relative to the first saved frame. These are suggested hold
durations, not timestamps to paste into an annotation manifest. Do not score
handling as a quiet target hold. Preserve misses and blank readouts; do not
adjust thresholds or target pose in response to the display during a hold.

Keep the foil sheet supported independently or fastened so it can be added and
removed without shifting the box; log any shift and the sheet's thickness,
size and tilt. It is a controlled change of reflector assembly, not a perfect
material-only intervention. Avoid touching or flexing the front during holds.
Recheck the front distance after each modification and record measurement
uncertainty. Keep the removed sheet and operator away from the beam.

One such run at 50 cm is the priority. If practical, repeat the full sequence
at **120 cm as a separate recording**. A cleaner scene with the wall farther
away is useful later as a distinct setup; do not move the wall/sensor while
performing this first paired comparison. There is no need to flash other
firmware for this test.

## How this will be evaluated

Use the initial empty only to fit references, freeze model complexity and
quality rules, then evaluate all quiet holds plus the final empty. Inspect raw
per-RX spectra, conditional fits, residual/width/conditioning, receiver agreement
and changes to the farther background, together with baseline/weak coverage.
The bare → foil → bare sequence checks whether the response returns when the
same physical footprint is restored. A foil success alone will not establish
bare-box detection or justify copying a probe into the displayed primary.

The immediate goal is to distinguish a weak/mixed target return from placement
or scene changes. If neither material gives consistent correspondence with
fixed geometry, investigate acquisition/range-transfer behavior before adding
more tracking or fitting components. An independent session is still needed
before promoting any model developed from these captures.
