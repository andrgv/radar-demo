# BGT60CUTR13AIP physical antenna geometry

The generic half-wavelength coordinates in the original host configs were a prototype assumption, not an established geometry for this board. Use the physical array model for hardware work.

## Documented reference

Sources:

- [BGT60CUTR13AIP datasheet V1.10, table 28](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60cutr13aip-datasheet-en.pdf): nominal RX center spacing is **2.35 mm** along each of the two orthogonal array directions.
- [AN163617, figure 4](https://www.infineon.com/assets/row/public/documents/24/42/infineon-an163617-pcb-design-guidelines-for-xensiv-60ghz-radar-mmics-with-aip-applicationnote-en.pdf): portrait orientation uses RX1-RX3 in the E-plane for azimuth and RX1-RX2 in the H-plane for elevation. Landscape orientation swaps these axes.
- [KIT_CSK user guide figures 29/30](https://www.infineon.com/assets/row/public/documents/24/44/infineon-ug113247-kit-csk-bgt60cutr13-xensiv-connected-sensor-kit-usermanual-en.pdf): its characterized orientation uses RX3-RX1 for azimuth and RX2-RX1 for elevation.

`configs/range-csk-portrait.json` specifies the portrait antenna-face drawing, viewed toward the exposed antenna package: RX1 at the lower right, RX2 above RX1, RX3 left of RX1, and TX1 at the upper left. Relative right/up coordinates in millimeters, in FIFO RX1/RX2/RX3 order, are `[[0,0],[0,2.35],[-2.35,0]]`. This reference is tied to antenna positions, not an unverified assumption about which edge of a USB board is down.

The file preserves the empirical plate **range** calibration. It does not reuse the rejected weak iPad phase fit: relative channel corrections are unity and RX phase remains uncalibrated. This is an antenna geometry preset, not a validated 3D calibration.

## Mounting rotation

`mount_roll_deg` rotates the reference array counterclockwise in its antenna-face drawing, without changing FIFO channel order. `--mount-roll` can override it for GUI/live or replay processing:

```powershell
python -m radar gui --port COM3 --config configs/range-csk-portrait.json --mount-roll -90 --phase-probe 1.3
```

The command is an example for a **clockwise 90-degree rotation from the defined reference**, not an automatic determination of the user's mount. Use `+90` for the opposite side, `180` for an upside-down reference, or `0` for the reference. At -90, RX2 is right of RX1 and RX3 is above RX1; at +90 those baseline signs reverse. The UI banner shows which geometry and roll are in use. Off-center measurements must establish physical axis signs and FFT phase convention before trusting angles.

The corrected geometry is used consistently by angle solving, beamforming, phase calibration and synthetic generation. Physical millimeters convert to wavelengths with the configured carrier frequency. That carrier remains unverified in the current RF template, so the model does not imply verified angle scaling. The original generic wavelength coordinates remain supported for old recordings and explicit synthetic arrays; `geometry_mm`, when present, takes precedence.

## Tabletop setup

The user clarified that the antenna face looks across the table and the evaluation board rests on its side. This does **not** mean the antenna looks upward; the remaining mounting issue is roll about boresight. A nearby tabletop and background objects may contribute reflections, but no recorded experiment has isolated their contribution. Keep the antenna face unobstructed and, for a controlled check, raise both it and the target off the tabletop using available nonmetallic supports. Do not infer that plastic is RF-invisible or that tabletop multipath has been proven to cause the problem.

No hardware purchase, firmware change or reflash is required for the geometry model. A fresh sufficiently isolated phase-reference measurement and known left/right/up target positions are still required; changing pairing cannot cure a weak/mixed range cell by itself.

## Current user setup and next capture

The user reports the USB connector is **left when viewed from the iPad toward the antenna face**, with the antenna looking across the table. This has been recorded as setup information; it is not used to guess an extra +/-90-degree rotation of the antenna reference. The earlier claim that a board described as "on its side" necessarily swaps this reference's baselines was too strong: portrait/landscape here describes the antenna array, not the long side of the baseboard.

Confirm the antenna PCB's **E-plane marking runs horizontally** before interpreting the portrait configuration's world azimuth/elevation axes, as directed by [Infineon's official example hardware setup](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-people-tracking). If it is vertical, the array reference needs an appropriate +/-90-degree roll and an off-center check of signs. A USB edge alone is not independent confirmation of the mounted antenna geometry or FIFO order.

For a target centered on boresight, expected geometric phase difference is zero regardless of array roll. Consequently, changing roll cannot remove a nonzero centered estimate caused by channel offsets or coherent background. The existing weak centered iPad recording is not sufficient for the revised calibration acceptance check.

Prepare a new centered recording with the physical-geometry config, using the same target/setup that produced a strong return in the earlier plate range recordings where possible. Keep both faces at the same height and move them away from the tabletop with existing nonmetallic supports if practical. That controls the experiment; it is not a claim that table reflections have been established as the cause.

```powershell
python -m radar record recordings/phase_center_usb_left --port COM3 --config configs/range-csk-portrait.json --metadata configs/measurement.json --seconds 10
```

This saves raw data with neutral channel gains and the established range correction. It does not apply a new phase calibration or certify angles. Inspect the selected cell's contrast, channel coherence and stability before saving any new phase correction. Then validate left/right/up positions independently. The existing `range-phase-pilot.json` remains preserved as historical output, not the recommended live angle config.
