# Controlled angular sweeps before point-cloud use

## What this test establishes

The next useful measurement is a **fixed-radar, known-target-position sweep**. It checks whether the two RX phase differences respond consistently to known horizontal/vertical displacements. This can expose swapped axes, sign/rotation mistakes, phase-offset drift, weak returns and target/background mixing. It is distinct from moving the radar around a room and combining points into a map.

Three RX channels give two receive baselines. The present processor emits sparse range/Doppler-cell direction estimates, not an RGB-D-like surface scan or person silhouette. Combining scans from a moving sensor would additionally require measured sensor poses and time alignment; neither is available in the current implementation. A stable room point cloud should not be promised by accumulating unverified phase points.

## One guided command

Use the **metal water bottle alone as the target**. This avoids attributing returns to an iPad and its metal support simultaneously. The bottle stands on its own; no reflector purchase is required. Its curved/extended surface is still a preliminary target, not a precision point reference. The report must be checked rather than assuming it will calibrate successfully.

Fix the radar facing across the scene, preferably away from immediate tabletop reflections with existing cardboard/books. Align the bottle's approximate reflecting center with the antenna height. Put ruler/tape marks at center, 30 cm left, 30 cm right, and 30 cm above center. Keep the **forward** distance 1.3 m; left/right/up positions are slightly farther in radial range, which the report accounts for.

Close the live viewer, then run from the project root:

```powershell
python -m radar sweep recordings/sweep_01 --port COM3 --config configs/range-csk-portrait.json --distance 1.3 --offset 0.3 --seconds 5
```

The output folder must be new. It prompts for:

1. **Empty baseline:** remove the bottle and iPad; keep radar and fixed scene unchanged.
2. **Center:** bottle directly ahead at the antenna center height.
3. **Left:** 0.30 m left of center, same forward distance and height.
4. **Right:** 0.30 m right of center, same forward distance and height.
5. **Up:** centered horizontally, 0.30 m above center, same forward distance.
6. **Check right:** 0.15 m right of center. This position is excluded from fitting.
7. **Center repeat:** return to the original center mark. This is also excluded from fitting.

Left/right mean **standing behind the radar looking toward the bottle**, not looking from the bottle back at the board. Each prompt is followed by a three-second countdown before recording, allowing the operator to step away. Hold each pose stationary for the five-second acquisition; this is a step sweep, not continuous hand motion. Use available stable nonmetallic supports for the raised position. If a 30 cm offset is impractical, choose a smaller accurately measured `--offset` (for example 0.15); the half-offset validation point changes accordingly. Smaller angular offsets make discrimination harder in noisy data.

At 1.3 m forward and 0.3 m offset, left/right/up directions are approximately 13 degrees from boresight; radial distance is approximately 1.334 m. Placement numbers are user-supplied labels, not automatically surveyed truth. Errors in target height, bottle scattering center or ruler marks limit what can be concluded.

## Analysis and acceptance

The command records raw frames at each pose and stores a background spectrum snapshot. Analysis uses the complex static baseline and neutral channel gains so it does not embed the rejected earlier iPad phase fit. It chooses the configured range bin nearest each pose's expected radial range. A pose must have at least ten frames, session channel coherence at least 0.90, local range contrast at least the configured threshold, and a local range peak. Rejected positions are reported; thresholds are not automatically reduced to obtain a fit.

If center plus all three training offsets pass, the report fits a two-dimensional phase response in direction-cosine coordinates. It reports the measured effective RX2/RX3 baseline vectors in wavelengths alongside the configured physical baselines. It does **not** install the fitted array as new physical geometry or silently swap axes. The check-right and repeated-center poses evaluate phase prediction and return-to-center drift independently of the fitted positions.

Outputs are `sweep-report.json`, `sweep-phase-check.png`, and individual raw recording folders. Blue plot markers pass reference quality checks; red markers fail. A successful least-squares fit is not itself independent accuracy validation. If held-out positions fail or are absent, do not treat the report as validated angular calibration. No new phase/gain config is saved automatically.

Reprocess without hardware:

```powershell
python -m radar sweep-analyze recordings/sweep_01
```

An interrupted acquisition preserves partial data; re-analysis reports missing poses rather than inventing them. A run with fewer than ten captured frames at a pose stops and leaves data available for debugging. Acquisition or recorder errors close the serial connection. No firmware changes or flashing are involved.

## Handheld option

If the target cannot be supported at each position, add `--handheld` to the same command. This changes the prompts and records the limitation in the manifest, pose metadata, analysis report and plot. Keep the radar fixed, pause the bottle near each mark for the capture and avoid deliberately waving it. Small unsteadiness is expected; do not try to force a perfectly still point by smoothing.

For the background, remove the bottle/iPad but keep your body near the holding-test position. During the target poses, keep your body off to the side and as stationary as practical. This does not perfectly subtract changing hand/body reflections. A handheld run can show whether phase generally responds to left/right/up movement, but cannot establish precise angle accuracy or physical baseline geometry. Any fitted vectors are apparent responses under those conditions; no calibration is installed automatically. Rejected positions remain useful diagnostics, not a reason to silently lower the quality thresholds.

## Current background evidence

The matched bottle-only/target-with-bottle recordings demonstrate why background handling matters: fixed-spectrum subtraction fitted to 50 background frames yields 96/101 near-target detections and zero near-target detections in 51 held-out background frames. Phase direction remains unreliable, so those figures are **not** point-cloud accuracy. See `STATIC_BACKGROUND.md` for method and limitations. The guided sweep takes a fresh empty baseline for its own fixed setup rather than reusing an old baseline after moving objects.
