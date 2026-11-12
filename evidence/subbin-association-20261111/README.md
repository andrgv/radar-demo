# Retreat association and biased hold investigation

The investigation separates association fragmentation from range-estimator
bias. It compares native and optional sub-bin assignment costs over 5,446 frames
from five recordings, including motion, repeated placements and empty controls.
All frozen 1D results match saved outputs and every RD accepted-cell mask is
identical across branches. No firmware, CFAR threshold or native gate changed.

## Association findings and implemented improvement

The first retreat in the new live recording briefly associates feature 13 with
a closer zero-Doppler bin-1 peak after outgoing bin-2/3 observations. The next
moving peak is at bin 3, outside the resulting one-bin gate, and ID continuity
breaks. This is a wrong-peak/identity problem; expanding gates could admit more
wrong reflectors, so that was not used as a remedy.

The second retreat also has observations at bin 4 that are equally distant from
tracks anchored at bins 3 and 5 on the integer grid. The optional
`--track-range-metric quadratic` computes a bounded three-point log-power range
coordinate for current RD peaks and uses it in assignment cost, inside the same
native gates. True remaining ambiguity is still withheld; no predicted range
or held point is published. The default remains native.

| New live motion window | Native readout frames | Sub-bin readout frames |
|---|---:|---:|
| First approach | 15/16 | 15/16 |
| First retreat | 8/15 | 8/15 |
| Second approach | 21/33 | 21/33 |
| Second retreat | 19/29 | 21/29 |

The change recovers two current zero-Doppler transition measurements in the
second retreat. It does not preserve the ID to the final far hold or fix the
first retreat's larger wrong-peak jump. Scored-window coverage on earlier
live-003 through live-006 is unchanged, including zero output in all scored
empty interiors and the entire live-005 operator-only capture. IDs may differ
between algorithms and are not verified physical identities.

159 tests pass. New tests demonstrate an integer-cost tie resolved by actual
current peak shape, an exact refined tie remaining ambiguous, and unchanged
native gate exclusion. The existing continuity, timeout, no-held-range,
stationary-control, motion/stop and GUI clearing tests remain.

## Biased hold spectra

Raw dense spectra were sampled at a fixed every-fifth-frame cadence in each
two-second-trimmed hold. No strongest-frame selection or label fit was used.
The declared diagnostic search band is 0.15–1.7 m. Values below describe raw
spectral peaks in that band, not independently identified reflectors.

| Hold | Averaged-RX raw peak | Individual RX raw peaks |
|---|---:|---:|
| First nominal 50 cm | 64.6 cm | 73.3 / 57.0 / 68.4 cm |
| Second nominal 50 cm | 35.3 cm | 164.6 / 33.7 / 39.6 cm |
| Middle nominal 120 cm | 128.2 cm | 132.5 / 170.0 / 124.4 cm |
| Final nominal 120 cm | 147.2 cm | 144.5 / 165.1 / 139.0 cm |

The biased ranges are already in the acquired spectra, before association,
motion-aware selection or display history. A fixed offset or smoothing is not
an adequate correction. Channel-dependent peaks also undermine the assumption
of one isolated reflector shared by all RX. Target geometry, multipath,
operator/support returns and analog/profile effects are plausible contributors;
these recordings do not isolate their physical causes. A channel's global
near-band maximum need not be the intended target.

## Helpful new capture

Use a rigid flat reflector, e.g. a foil-covered board, supported on the beam
centerline and facing the radar. Measure antenna face to the reflector's front
surface. Keep height, orientation, radar/support/cable pose and operator B
position fixed. Note dimensions/material and background-wall distances, and
include a sketch/photo of the geometry if possible.

One recording: 15 s empty → 20 s at measured 50 cm → 10 s empty → replace at
the same 50 cm marks for 20 s → 10 s empty → 20 s at measured 120 cm → 15 s
empty. Log actual handling and quiet-hold times separately. No rolling during
holds. Keep firmware and detector settings unchanged and preserve failed holds.
This tests a simpler known reflector and replacement repeatability; it is not
an offset-fitting or independent acceptance dataset.

[Raw hold spectra](hold-spectra.png) · [Full results and source/input hashes](report.json) ·
[Algorithm, optional flag and protocol](../../docs/SUBBIN_ASSOCIATION.md)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.investigate_motion_association \
  --output evidence/NEW-ASSOCIATION-REVIEW
```
