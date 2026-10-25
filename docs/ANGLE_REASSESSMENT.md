# Angle calibration reassessment

The initial centered iPad recording passes a relative-channel coherence test but is not sufficiently isolated from the measured background to support the earlier confidence in its 3D point. This is a correction to the previous acceptance decision, not a new claim of working angle tracking.

Measured from `recordings/phase_center`:

- 101 complete frames, no sequence gaps in the stored stream or device error/drop counter increases.
- Relative channel coherences approximately 0.985 and 0.992 over the session.
- At target bin 4, per-frame local signal/background p05/median/p95 approximately 4.04/4.95/6.16 dB using the phase-corrected config.
- The revised calibration check uses the uncorrected mean spectrum and obtains approximately 5.2 dB, below the existing 12 dB threshold.
- A zero-direction fit to the same centered data is not independent validation of angle accuracy. Coherent background reflections can have stable phase and still be the wrong source.

Corrections made:

1. `calibrate_channels` now checks range-cell signal/background as well as channel coherence. It rejects this iPad session instead of issuing another apparently usable phase calibration.
2. Probe rendering now rejects weak/nonlocal-peak/low-coherence/invalid direction estimates and explicitly reports the reason. It exposes raw RX2-RX1 and RX3-RX1 phase for diagnosis instead of turning weak phase into a 3D marker. It retains no old point and adds no temporal smoothing.
3. Geometry is still unverified. The existing generic half-wavelength layout does not match the KIT_CSK guide's azimuth/elevation channel pairing in its depicted orientation. Board mounting orientation and actual FIFO order must be established before selecting the physical geometry.

No current live-motion raw recording exists in this workspace, so the report cannot identify the exact cause of the reported long settling or wrong live direction. The existing software has no deliberate phase-estimate settling filter. Target/background mixing, flat-panel tilt and cell selection remain possible causes; wrong geometry can affect direction mapping independently.

References: [Infineon KIT_CSK_BGT60CUTR13 user guide, figures 29/30](https://www.infineon.com/assets/row/public/documents/24/44/infineon-ug113247-kit-csk-bgt60cutr13-xensiv-connected-sensor-kit-usermanual-en.pdf), [BGT60CUTR13AIP datasheet table 28, nominal 2.35 mm RX spacing](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60cutr13aip-datasheet-en.pdf), and [AIP PCB design guidelines, figure 4, orientation-dependent axes](https://www.infineon.com/assets/row/public/documents/24/42/infineon-an163617-pcb-design-guidelines-for-xensiv-60ghz-radar-mmics-with-aip-applicationnote-en.pdf).

The empirical plate range correction is separate and has not been changed. No firmware changes or flashing were performed for this reassessment.
