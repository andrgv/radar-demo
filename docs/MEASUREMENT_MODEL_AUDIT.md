# Measurement-model audit: findings and consequences

This audit uses **2119 frames in all 15 saved sessions**, including complete
detkin scenes with body and arm returns. No capture is discarded for containing
more than the iPad. It does not change firmware, live settings, old configurations
or recordings. It fits no per-capture offsets and installs no winning model.

```powershell
python -m radar.model_audit recordings --config configs/range-vendor-matrix-experimental.json --output artifacts/model-audit
```

Outputs: `report.json` (every hypothesis, range-cell score, raw-file hash and
chirp-slot statistic), `report.md` (summary), and `diagnostics.png`. The default
register definitions come from the installed official release-v1.1.0 driver;
`--hal` can override that path.

## 1. Raw packing is supported, physical RX labels are not certified

Six interpretations are compared: current unsigned sample-interleaved data,
signed containers, byte-swapped containers, adjacent 16-bit halfword swapping,
RX-major within a chirp and RX-major within a frame. Every raw sample is retained
for these tests. In the strong plate records:

| Recording | Current normalized roughness | Adjacent-halfword swap roughness |
|---|---:|---:|
| 0.6 m | 0.321 | 1.639 |
| 1.3 m | 0.487 | 1.694 |
| 2.0 m | 0.590 | 1.683 |

The halfword-swap interpretation creates dominant bins 30, 28, 26 instead of
2, 4, 6. This is evidence against that correction, not support for changing the
live decoder. Smoothness and plausible beat frequencies cannot identify which
of three receive streams physically belongs to RX1, RX2 or RX3.

Source inspection of the driver shows 16-bit SPI transfers into uint16 buffers,
and two ADC containers per FIFO word. Firmware reads FIFO levels in ADC samples
and converts them to FIFO-word counts consistently with the driver API. This
inspection finds no demonstrated unit-conversion or halfword-swap bug. It is
not a physical certification of every SPI transaction.

## 2. The analog and waveform configuration limits the measurement

Register fields decoded using official HAL masks show all three selected RX
channels enabled, with 42 dB gain, HPF1 at **350 kHz**, HPF2 bypass disabled and
AAF selection **2 MHz**. These are source settings, not measured readbacks.

The nominal sampling/slope model is 5 MHz / 33.69140625 THz/s. It implies:

- 0.347585 m FFT grid spacing for 64 samples;
- about 424.5 MHz frequency span over the N-1 sampled intervals;
- HPF1's 350 kHz corner equivalent to about 1.557 m range;
- the 1.3 m target's nominal beat frequency about 292 kHz, below that corner.

Filter corners are **not hard cutoffs**. Signals below the HPF corner can still
be detected, as the recordings demonstrate, but will be attenuated. Source
settings do not specify the entire measured analog response here. It would be
incorrect to blindly invert an assumed filter or claim that lowering this
corner alone fixes angular accuracy. No firmware changes were made.

The nominal range model is independently corroborated by Infineon's generated
localization header, preserved with its copyright in
`artifacts/model-audit/reference-localization.h`. Two published range-resolution
values match the ramp scaling; see RECORDING_AUDIT.md. That corroboration does
not establish exact carrier or absolute chirp timing for this different profile.
The sensor's advertised maximum bandwidth is not the bandwidth of this loaded
64-sample configuration.

## 3. Slow-time timing was never established

The loaded profile describes factor-16 averaging. Firmware explicitly writes
factor1 to AVG_CTRL_SEQ0, reads 17 blocks of 64x3 containers, then resets the FSM.
Thus the generated profile's original acquisition schedule cannot simply be
used as metadata for these truncated raw captures.

The audit retains all 17 chirps and checks per-slot amplitude, inter-channel
phase and adjacent-slot coherence. Strong detkin/plate returns are extremely
consistent through the stored slots: typically around 0.99--1.00 coherence and
sub-degree slot-dependent mean inter-channel phase changes. There is no obvious
gross alternating-channel or first-block failure in those returns. This does
not determine the physical spacing of those slots or establish the raw firmware's
sequence semantics. Scene motion can be small during a short burst.

The 100 ms device timestamps are frame trigger times; they cannot substitute
for intra-frame chirp timestamps. No sequencer instruction decoder is included
in the installed register HAL or this audit. Encoded sequence words are
preserved in the JSON without pretending their timing has been decoded. The
current host's 1 ms chirp interval and 60 GHz carrier remain placeholders.
Numeric velocity and the Doppler resolution promised by that timing are
therefore unsupported. Normalized cycles/chirp also assume uniformly spaced
slots; they do not independently validate that assumption.

## 4. Matrix and sign search does not identify a calibrated angle model

The audit evaluates **84 fixed hypotheses**: six receive permutations, both
FFT conjugation conventions, and seven correction-matrix interpretations:
identity, loaded rows, conjugated rows, transpose, adjoint, inverse and
conjugated inverse. The candidate matrix is derived from the exact loaded
register profile. No coefficients are optimized on the recordings.

The score is the squared projection of a range cell's dominant covariance
eigenvector onto the assumed raw array manifold. A symmetric direction-cosine
disk avoids privileging a guessed azimuth/elevation orientation. Every usable
cell within 20 dB of the session maximum is audited; a predominantly rank-one
subset is also reported to separate point-source model checks from mixed-scene
measurements. This distinction is about testing model assumptions, not excluding
people or valid objects from the scene.

Three plate sessions and six detkin sessions are scored as separate groups,
averaging sessions equally. The highest plate-ranked hypothesis has scores
0.96989 (plate) / 0.90003 (detkin). The current hypothesis scores 0.96005 /
0.90583. Identity with the current channel order scores 0.88044 / 0.82688.
The scores support a channel response correction, but do not single out its
physical interpretation. Transposing a factory matrix solely because it scores
higher would repeat the original mistake.

These scores also assume a particular relation between virtual-channel
amplitudes and directions. The documented on-chip 2x3 per-plane phase correction
does not independently certify the combined 3x3 equal-amplitude manifold that
the prototype beamformer inverted. Infineon's off-chip PDT documentation uses
separate 3x3 H/E matrices and different example coefficients. Those paths must
not be silently treated as interchangeable.

Conjugating a manifold and reflecting its directions gives exactly the same
fit. Unknown array rotations/reflections can likewise be absorbed into unknown
scene coordinates. These ambiguities are tested numerically. No unsigned or
signed folder label is used as certified pose or angular ground truth. The
model cannot certify the observed -21 degree bias without that reference or
an independently established hardware convention.

## 5. Raw observations do not uniquely specify arbitrary dense scenes

The audit includes two explicit counterexamples using the configured array:

1. Two different nonnegative distributions of incoherent scattering power
   over nine angular positions produce the same three-RX spatial covariance
   to machine precision. The covariance design has rank 7 in this ideal model.
2. Three coherent scatterers at distinct directions and one at another
   direction produce the same raw complex three-channel vector. Multiplying
   both by the same range/Doppler waveform leaves every raw chirp identical
   under the model, not merely the plotted covariance.

The directions, powers, complex amplitudes and numerical errors are saved in
the JSON. These are identifiability examples, not claims about the actual room.
They show that even perfect matrix calibration cannot guarantee a unique dense
reconstruction of arbitrary overlapping returns from one fixed aperture.

Sparse-target assumptions, surface/scene priors or independent observations
from known sensor poses can add constraints. Their performance needs validation;
they cannot be replaced by filling a broad beam lobe with points and calling
it a measured surface. This is not a statement that all radar point clouds or
all reconstruction methods are impossible. The prototype's current information
and unverified model do not support the requested accurate volumetric map.

## What this audit establishes, and what remains

The digital layout has strong supporting evidence. The analog configuration
attenuates near returns and the waveform has coarse range sampling. Absolute
slow-time timing remains unsupported. A matrix correction improves an assumed
point-source fit, but channel/phase/coordinate interpretations remain ambiguous.
The full-scene inverse problem is not uniquely determined by these observations.
Those are specific measurement-model findings, not excuses to reject the scenes.

The next hardware-dependent verification, if pursued, must establish the exact
raw sequence timing and physical channel/angle convention: supported sequencer
metadata or measurement/readback, exact board orientation, and an independent
angular reference. Register readbacks alone cannot establish angular calibration.
No additional recordings are requested by this audit and no new capture routine
is proposed here. Further model changes should wait for evidence resolving those
specific unknowns, rather than fitting a new center offset.

## Primary source provenance

- Loaded `firmware/vendor/presence_detection_tracking.h`, `firmware/main.c`,
  installed release-v1.1.0 register HAL and driver FIFO/SPI implementation.
- [Infineon driver calibration documentation](https://github.com/Infineon/sensor-xensiv-bgt60cutrxx/tree/release-v1.1.0#calibration-matrix-update).
- [Official localization configuration at pinned commit](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-clutter-clustering/blob/07becc7e36686e3d181ddd058df387287f09a504/radar_config/presence_detection_localization.h).
- [Official PDT example calibration description](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-people-tracking#calibration-matrix-update).
- [PDT library wrapper documentation](https://github.com/Infineon/xensiv-cmos-radar-sensing/blob/abfb4e2cd780ba2f78841541b9678dbb4e1d2ed3/docs/algo/wrapper.html).
