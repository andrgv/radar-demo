# Per-frame scattering-center point cloud

```powershell
python -m radar gui --port COM3 --config configs/range-vendor-matrix-experimental.json --point-cloud
```

This mode replaces the broad angular-cell scatterplot with extracted scattering
centers. The projection panels retain the full reflectivity response. The first
two range bins and Nyquist are excluded; default viewing range remains 4 m and
is adjustable. The forward angular search is +/-60 degrees in azimuth/elevation,
not a 360-degree view. The factory matrix, carrier and angle convention remain
provisional. This is not a claim that the previous angular bias is fixed.

The processor uses the range FFT then a Hann-window Doppler FFT, retaining DC
(stationary) energy. It finds local range/Doppler peaks, uses the existing
guarded median range-noise estimator in each Doppler row (8 dB contrast threshold),
and jointly matches the three raw receive channels against azimuth/elevation
steering signatures. A minimum matched energy fraction of 0.65 rejects poorly
fitting directions. These are heuristic selection criteria, not calibrated
confidence or a constant false-alarm-rate guarantee. No empirical angle offset
or per-session calibration is fitted. No empty-scene subtraction is required.

Different ranges and resolvable Doppler peaks at the same range are processed
independently. The algorithm currently estimates one direction per selected
range/Doppler peak. It does not claim to separate arbitrary coherent returns
sharing both range and Doppler using only three receive channels. More dense
points cannot be manufactured without imposing additional assumptions.
Reported half-power angular widths expose broad responses; they are not formal
confidence intervals and can include sidelobes and field-of-view boundaries.

All five detkin captures and detkin-empty were replayed (1211 frames). Median
point counts are 2--3 per frame, with typical extraction cost around 13 ms on
this machine. These are sparse scattering centers, not dense reconstructed
surfaces. Point counts, timing and range-bin counts are in
`artifacts/pointcloud/scene-replay.json`. This demonstrates processing and
retention of scene returns, not ground-truth geometric accuracy. Negative
captures are included in their entirety, with body/arm returns treated as scene
content. No persistent accumulation is done without sensor pose.

Record with countdown and automatic exit:

```powershell
python -m radar gui --port COM3 --config configs/range-vendor-matrix-experimental.json --point-cloud --record recordings/scene-cloud-01 --start-delay 15 --seconds 20
```

The new `pointcloud.jsonl` file saves per-frame XYZ, range bin, normalized Doppler
(cycles per chirp), power, local contrast/SNR, model fit and angular response width.
Original raw frames and serial wire logs are still saved. Numeric velocity is
deliberately not assigned to this cloud because chirp timing is unverified.

Existing data can be exported without a GUI or opening the serial port:

```powershell
python -m radar.pointcloud recordings/detkin-ipad0 --config configs/range-vendor-matrix-experimental.json --output artifacts/pointcloud/detkin-ipad0
```

Synthetic tests cover simultaneous stationary and moving returns, two opposite
Doppler returns sharing one range bin, recovery of their different directions,
a weaker return 20 dB below another at a different range, and empty data.
Qt replay checks the actual point-cloud rendering and automatic shutdown.
