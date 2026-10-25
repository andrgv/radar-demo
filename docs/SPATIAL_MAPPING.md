# Spatial reflectivity and reconstruction limits

Run the new per-frame view without the phase probe:

```powershell
python -m radar gui --port COM3 --config configs/range-vendor-matrix-experimental.json --spatial-map
```

Or replace `--port COM3` with `--replay recordings/plate_1_3m`.
The first tab shows range/azimuth and range/elevation projections, angular
spread at the strongest range cell, and 3D reflectivity cells. Display dynamic
range and maximum viewing range are adjustable. No local peak, 12 dB detection,
phase-coherence or valid-direction gate removes cells from the volume. There
is no temporal smoothing or history accumulation. The display cutoff is
relative brightness, not a detection confidence or probability of occupancy.
The projections maximize over the omitted angular coordinate; they are not
slices or independent measurements. At most 2500 uniformly subsampled cells
are rendered as 3D markers; full numeric data are retained by offline export.

The method forms a three-channel sample covariance for each range cell. A joint
azimuth/elevation steering grid predicts raw RX signatures by inverting the
configured calibration matrix. Each signature is normalized in the raw-channel
domain before matched filtering. This avoids directional noise gain from
non-unitary matrix mixing, assuming equal independent noise in the input RX
domain. The 5 degree grid samples the response; it is not 5 degree resolution.
All post-discard chirps contribute to covariance, retaining static and moving
energy without slow-time mean subtraction. The first two range bins and
Nyquist are excluded as in the existing detection path. No zero-padding or
interpolated grid is presented as independent range measurements.

The nominal 64 sample profile has 0.3476 m FFT spacing. Previously reported
10 cm bins do not describe this profile. Interpolation of an isolated peak
does not make two objects resolvable at the interpolation precision.

Offline mean-power exports (no coherent combination between frames):

```powershell
python -m radar.spatial recordings/plate_1_3m --config configs/range-vendor-matrix-experimental.json --output artifacts/spatial/plate_1_3m
```

This saves a PNG (default viewing range 4 m) and an NPZ containing the full
range/elevation/azimuth power array, axes, frame count and config provenance.
The export is a session average; the live view uses each individual frame.

On the existing 1.3 m plate recording, the session-mean response peaks near
(-10, 0) degrees at bin 4. Its -3 dB region spans azimuth approximately
[-55, 30] and elevation [-45, 35] degrees within the sampled field of view.
The target-with-bottle recording is less localized. These are response widths
of the data plus the assumed model, not measured antenna resolution or target
extent. They demonstrate why filling a wall surface with all bright cells
would create an unjustified geometry claim. Angular bias remains unresolved.

Only three RX complex observations are available at each range/slow-time
sample. Many extended reflectivity distributions can explain the same data.
The model cannot uniquely distinguish multiple coherent scatterers at one
range, multipath and a biased array response. A dense angular grid adds no
independent aperture information. The factory coefficient convention, exact
carrier, physical RX mapping and board pose still need validation. This view
deliberately exposes the ambiguity instead of installing another center offset.

This is sensor-relative reflectivity, not a persistent world map. Accumulating
frames while the board moves requires estimated or measured position and
orientation, registration, uncertainty and multipath handling. No such pose
estimate exists in this project yet; blindly accumulating would smear or
duplicate the scene. The storage/pipeline can later accept poses from radar
odometry or another source without requiring a camera or ROS2. No claim of
validated world reconstruction is made.
