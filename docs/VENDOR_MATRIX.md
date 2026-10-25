# Host angle-matrix implementation

`configs/range-vendor-matrix-experimental.json` enables a candidate reconstruction
of the loaded firmware's factory calibration. Existing configs keep identity
mixing. No firmware update is needed.

The implementation uses signed Q0.15, upper half real and lower half imaginary.
It assembles rows H[0], H[1], E[1] (H[0] equals E[0] in this profile). These
correspond to reference, RX2 vertical and RX3 horizontal virtual channels under
the nominal portrait geometry. Each complex snapshot is mixed before covariance
or beamforming. Moving detections mix their complex Doppler-bin vector.
Range power and detection thresholds remain in the original RX domain, so a
matrix cannot manufacture additional range detections. Do not combine this
config with an old diagonal phase calibration: its gains intentionally are unity.

Replay comparison of all 908 frames is saved in
`artifacts/vendor-matrix-replay.json`. Plate 1.3 m and 2 m each change from zero
mathematically valid directions out of 101 detections to 101/101. Median angles
are respectively (-10.46, -0.12) and (-8.91, 0.33) degrees. The 0.6 m record
changes from 22/155 to 155/155 valid directions, with median (-0.98, 2.38).
These counts include all range detections, not just a surveyed target gate.

This is a measurable removal of the invalid-direction failure, not proof of
angular accuracy. Packing, raw-FFT sign convention, physical channel identity,
mounting rotation and applicability of these factory coefficients remain
unverified on hardware. The recordings lack surveyed angular ground truth.
Weak iPad sessions still fail the range threshold; this correction does not
solve low contrast or multipath. Carrier and chirp interval remain provisional.

```powershell
python -m radar gui --replay recordings/plate_1_3m --config configs/range-vendor-matrix-experimental.json --phase-probe 1.3
python -m radar gui --port COM3 --config configs/range-vendor-matrix-experimental.json --phase-probe 1.3
```

Factory matrix provenance: the exact loaded
`firmware/vendor/presence_detection_tracking.h`, addresses 0x1e00 through 0x1e68.
The installed official driver README section "Calibration matrix update"
documents the 2x3 mixing operation. A synthetic inverse-mixing test checks
known-angle recovery; it does not independently validate register packing.
