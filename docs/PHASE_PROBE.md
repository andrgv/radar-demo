# Checking phase when the target is below the detection threshold

The saved `recordings/phase_center` iPad session contains 101 complete frames. Reprocessing with `configs/range-phase-pilot.json` finds the selected return at bin 4 is above its neighbors in 86 frames and has estimated local signal/background ratio p05/median/p95 of 4.04/4.95/6.16 dB. It exceeds the configured 12 dB detection threshold in **zero** frames. Its relative phase still produces a valid direction in all 101 frames when inspected at that bin. This explains why a phase calibration can pass while the normal 3D detection display has no stable iPad point. This is evidence from the saved centered session, not a recording of the subsequent live movement.

The normal viewer has no object association, track IDs or missed-detection persistence. Each refresh clears and redraws the current frame's detections. A point can disappear because its range peak fails the detection threshold, its coherent/static or moving gate fails, or its two phases imply an invalid direction. The status now reports both total detections and valid 3D detections. No temporal smoothing or point-holding has been added.

An explicit diagnostic phase probe inspects the chosen range cell without globally lowering the detector threshold. Following review of the noisy live behavior, a direction marker now requires both high coherence and signal/background above the configured detection threshold, plus a local range peak. Otherwise the display reports why direction was rejected and plots **raw RX phase**, not an azimuth/elevation estimate:

```powershell
python -m radar gui --port COM3 --config configs/range-phase-pilot.json --phase-probe 1.3
```

For the saved session:

```powershell
python -m radar gui --replay recordings/phase_center --config configs/range-phase-pilot.json --phase-probe 1.3
```

The probe selects the FFT bin nearest the requested range (bin 4 for 1.3 m). It calculates inter-RX phase from chirp-averaged cross products with RX1, cancelling common chirp phase, and reports channel coherence, local signal/background ratio, the ordinary detection threshold, and whether the selected bin is a local peak. A direction marker requires a physically valid direction, minimum coherence at least 0.90, a local range peak and signal/background at least the configured threshold. Its radial coordinate is the selected bin center, not a new range measurement. The probe does not select the scene's strongest return or follow a target to other bins.

Keep the radar fixed and the iPad near its calibration range, then move the iPad left/right/up in small measured steps. The probe should respond to changes in the selected cell's phase. It can reflect background or unresolved multipath in that cell, even with high coherence; coherence alone does not identify the iPad. A broadside calibration on the same session is not an independent verification of antenna ordering, geometry or angle accuracy. The marker is explicitly **not a detection or track**, and no glass decision uses it.

The original 12 dB detector and saved calibration are unchanged. Lowering the global threshold could increase false detections and is not established as a fix by this one recording. A useful object tracker will require reliable detections, association and measured miss/false-positive behavior, not merely holding this diagnostic marker on screen.

The probe now opens a dedicated **Phase movement check** tab: a large azimuth/elevation crosshair, a close-up 3D marker and the last 100 displayed raw angle updates. The angle view defaults to +/-30 degrees and can be changed with the control above the plots. Left/right motion should change azimuth; up/down motion should change elevation. Invalid phases leave gaps in history and remove the current marker rather than holding an old point. This display introduces no smoothing or object tracking. The original six plots remain under **Radar overview**. Restart the application with the same command to load the updated view.

The prior `configs/range-phase-pilot.json` was generated under the earlier coherence-only calibration check. Reassessment rejects its centered iPad source recording at about **5.2 dB** mean-spectrum signal/background versus the configured **12 dB** requirement. Preserve that config and recording as historical data, but do not treat that fit as validated angle calibration. The new calibration guard prevents repeating the same acceptance error. The threshold is an operating criterion, not a universal proof of calibration quality; high-coherence multipath can still pass it.

The generic geometry in the existing config assigns RX2 to horizontal and RX3 to vertical. [Infineon's KIT_CSK guide, figures 29/30](https://www.infineon.com/assets/row/public/documents/24/44/infineon-ug113247-kit-csk-bgt60cutr13-xensiv-connected-sensor-kit-usermanual-en.pdf) instead uses RX3-RX1 for azimuth and RX2-RX1 for elevation in its documented orientation. [The chip datasheet, table 28](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60cutr13aip-datasheet-en.pdf) gives a nominal RX spacing of 2.35 mm. A centered fit cannot establish which baseline is horizontal, its sign, or the board's mounting rotation. Do not blindly swap axes without establishing physical orientation and testing known off-center positions. Neither an axis swap nor a marker quality gate has been demonstrated to cure the live instability.
