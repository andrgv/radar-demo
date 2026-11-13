# Full response replay still does not reconstruct room geometry

The current output has not demonstrated a recognizable reconstruction of the
space in front of the radar. Centimetre-scale single-target range estimates,
stable candidate points, and successfully rendering a three-dimensional figure
are insufficient evidence of that result.

The existing full-volume processor was rerun on **all 303 raw frames** of each
`door03/closed-01`, `door04/closed-01` and `door07/closed-01` recording, using each
recording's configuration. This bypasses the point extraction step and retains
the broad angular responses. No thresholds, angle offsets, mounting guesses,
surface fitting, smoothing or furniture priors were added.

## What the images mean

The range/angle response shows broad lobes and radial bands/shells. It does not
show independently reconstructed wall, floor or furniture surfaces. The 3D
scatterplot samples the same response field and adds no new measurements.
An illuminated cell is a direction/range hypothesis compatible with the receiver
data, not evidence that a small object occupies that voxel. Adjacent angular
cells are strongly dependent because the same three RX observations generate
the entire angular search for a range bin.

The current point extractor instead selects a range/Doppler peak and places
one point at its strongest fitted direction. This discards ambiguity and can
make an uncertain response look like a precisely located reflection. Displaying
all hypotheses produces a broad cloud, but does not establish the physical shape
of the scene either.

The repository already identifies unverified angular calibration and mixed
coherent returns as unresolved. These replays do not isolate those causes from
limited aperture, scene multipath or processing/model mismatch. The images
cannot prove that every possible reconstruction algorithm fails on the hardware.

## Actual replays

- [door03 response](door03-response.png)
- [door04 response](door04-response.png)
- [door07 response](door07-response.png)

Each figure shows azimuth/range and elevation/range projections, a rendered
subset of response cells, and the full angular slice at the strongest displayed
range. Defaults show at most 4 m and a 30 dB display span; bin zero, bin one and
Nyquist are excluded by this existing processing path. The saved NPZ files retain
the full processed range axis. Configuration-derived coordinates remain
unverified for this scene. No surveyed room geometry is available to score a
reconstruction quantitatively.

[report.json](report.json) retains input/source hashes and measured half-power
response spans. Those spans are **not angular errors or physical surface widths**.
The numerical volume and original figures are under
`artifacts/volume-inspection-20261111/`.

Reproduce from the repository root, using a fresh output prefix:

```bash
MPLCONFIGDIR=/tmp/radar-volume-mpl .venv/bin/python -m radar.spatial \
  recordings/door07/closed-01 \
  --config recordings/door07/closed-01/config.json \
  --output artifacts/volume-inspection-new/door07-closed01
```

Repeat for door03/door04 with their own recorded configs. No hardware or firmware
changes are involved.

## Acceptance criterion

The next spatial-processing result should demonstrate repeatable scene structure
from the measured data and distinguish supported geometry from ambiguity. More
points, a smoother cloud or a SLAM/SAR label is not that demonstration. A useful
map additionally needs verified geometry and motion estimation. No successful
room reconstruction or moving map is claimed by these diagnostic outputs.
