# Detection research and the carly implementation

Reviewed 2026-11-11, based on `main` commit
`33e03bfcca41e70e5f2a334127aed78386b23b88`. Scope: general object detection
with the current raw-data path. The implementation changes host processing;
hardware measurements and firmware qualification remain separate work.

The useful first improvement is to retain separate range–Doppler peaks, estimate
each peak's angle from its own channels, and report SNR against the gate that
actually admitted it. The larger hardware gains are likely to come from a
near-range filter setting and a waveform with more sampled bandwidth, after
verifying the raw sequencer timing and array calibration. This is an engineering
recommendation, not a measured hardware improvement.

## Sensor, acquisition and configuration

The board is CYSBSYSKIT-DEV-01 (PSOC 6) with the BGT60CUTR13AIP radar wing.
The radar is a 60 GHz FMCW device with one TX and three RX in an L-shaped
antenna-in-package array. The datasheet specifies 2.35 mm RX spacing in its two
array directions and up to 7 GHz bandwidth. That maximum is not the bandwidth
sampled by this application's loaded profile.
[Infineon datasheet, block diagram and table 28](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60cutr13aip-datasheet-en.pdf).

I re-ran `radar.model_audit.source_facts` against the checked-in register header
and the official release-v1.1.0 register HAL. These values describe source
configuration, not a live register readback:

| Setting | Current source/configuration | Detection consequence |
|---|---|---|
| Raw frame | 17 chirps × 64 samples × 3 RX, 16-bit containers | 6,528 payload bytes; 16 chirps retained after discarding the first |
| Scheduling / transport | Nominal 10 Hz, UART 2 Mbaud 8N1 | 6,580-byte packet takes 32.9 ms; acquisition and transfer have dead time |
| Averaging | Vendor profile factor 16; firmware overrides to factor 1 | Vendor averaged-chirp timing cannot be copied into raw-mode metadata |
| Sample rate / slope | 5 MHz / 33.69140625 THz/s, nominal source-derived | 0.347585 m range FFT grid spacing |
| Sampled frequency span | About 424.5 MHz across 63 sample intervals | About 0.3531 m rectangular-bandwidth range scale; Hann broadens target response |
| Analog RX settings | All three RX enabled, 42 dB gain, HPF1 350 kHz, HPF2 not bypassed, AAF 2 MHz | Near returns are attenuated; more gain also raises clutter/saturation risk |
| HPF1 corner mapped to range | About 1.557 m at the nominal slope | This is an attenuation corner, not a hard minimum detection distance |
| Array coordinates | Source-derived portrait model `[[0,0],[0,2.35],[-2.35,0]]` mm | Physical FIFO channel order, orientation, phase convention and correction still need independent validation |
| Chirp interval / carrier | Host 1 ms / 60 GHz placeholders | Physical velocity stays null unless both verification flags are true |

At 16 retained chirps, the normalized Doppler grid is 1/16 cycle/chirp.
Even that interpretation assumes uniform chirp spacing. Frame timestamps do
not establish intra-frame spacing. Firmware resets/truncates the sequencer after
the raw window, so a longer coherent burst needs a supported sequence and timing
verification before changing the FFT size.

Configuration files have different purposes:

- `configs/hardware-provisional.json` uses illustrative 1 MHz / 30 THz/s values.
  Its axes are not source-derived hardware measurements.
- `configs/range-source-derived.json` supplies the nominal 5 MHz / 33.6914 THz/s
  range scale and nominal physical geometry; timing and angles remain unverified.
- `configs/range-plate-pilot.json` and `range-csk-portrait.json` use empirical
  plate range corrections on the older scale. Do not combine those corrections
  with the source-derived scale: that would apply the range correction twice.
- `configs/range-vendor-matrix-experimental.json` tries a channel mixing matrix;
  the [measurement-model audit](MEASUREMENT_MODEL_AUDIT.md) does not certify its
  angular interpretation. Infineon's on-chip 2×3 H/E correction and off-chip
  PDT 3×3 H/E correction are distinct processing paths.
- `configs/qualification-*.json` belong to separate firmware variants/profile
  IDs, including the 100 kHz HPF experiment. A host JSON setting alone cannot
  reprogram the analog filter. See [qualification](QUALIFICATION.md).

The repository's older documents describe 2,119 captured frames in 15 sessions.
Those raw recordings are not in the inspected `main` tree (`recordings/` is
ignored). Their published findings informed this review, but I could not rerun
them or measure detection recall on them in this environment.

## Existing algorithms and concrete issues

`radar/processing.py` performs per-chirp DC removal, a Hann range FFT, channel
correction, a Hann Doppler FFT, a separate mean-subtracted moving path, local
median gates, phase-based azimuth/elevation and conventional beamforming.
The original main detector collapses moving power with `max(axis=0)` and then
uses `argmax` in Doppler, admitting at most one mover per selected range peak.
It can also lose a weak neighboring-range target at a different Doppler.

There is already a separate multi-peak extractor in `radar/pointcloud.py`, enabled
through `--point-cloud`. It uses per-row range gates and joint angle fitting.
The new work does not claim that range–Doppler peak detection was absent from
the entire repository, and it does not change that experimental extractor.

Two bugs in the main detector are fixed in both modes:

1. Moving detections used the total/static noise estimate for `snr_db`, although
   a different moving-path gate accepted them. SNR now uses the accepting gate.
2. Stationary angles used covariance from every slow-time component in that
   range cell. A co-range mover therefore biased the stationary angle. The
   stationary candidate now uses the same coherent zero-Doppler mean that
   supplies its power, then applies the configured channel matrix.

## Algorithm priorities from the research

| Priority | Approach | Fit to this repository and tradeoff |
|---|---|---|
| Now | Preserve range–Doppler candidates and apply local peak suppression | Implemented for the main detector as an opt-in mode. Separates resolvable movers without discarding the static path. |
| Next offline comparison | CA/GO/OS-CFAR and scene-conditioned thresholds | Compare at equal measured false detections per frame, not equal numeric thresholds. Median/order-statistic estimates tolerate some target contamination; clutter edges and crowded reference cells remain difficult. |
| Before reporting accurate 3D/speed | Establish raw timing and physical array calibration | Directly addresses the unresolved measurement model; software smoothing cannot establish these quantities. |
| Near-range hardware experiment | Existing 350 kHz versus 100 kHz HPF qualification | At the same nominal slope, 100 kHz maps to about 0.445 m. This could improve near-target sensitivity, but leakage and saturation must be measured. |
| Better range/motion separation | More sampled bandwidth and longer coherent bursts | Requires waveform/sequencer work and transport budgeting. Zero padding only samples the existing spectrum more finely. |
| Stable object output | Range/Doppler-aware grouping, then gated Kalman tracking and tentative/confirmed tracks | Can reduce flicker and associate scattering centers over time. Use measured uncertainty and reset on gaps; do not turn unmatched predictions into observed objects. Sparse three-RX detections may not support a useful DBSCAN density threshold. |
| Static-object work | Keep zero-Doppler detection; evaluate fixed background or a slowly updated clutter model separately | Background subtraction can remove objects already present in its reference. Adaptive updates need target protection and a measured phase-stability policy. |
| Later angular research | Loaded MVDR/Capon or MUSIC with a validated array/noise model | Three RX give only two independent phase baselines. These methods do not create missing aperture or uniquely recover arbitrary coherent scenes. |

The detection/peak-processing separation follows the vendor-described chain:
range/Doppler processing, threshold/local maxima, per-detection channel extraction
and angle estimation. [Infineon signal-processing overview](https://community.infineon.com/t5/Knowledge-Base-Articles/Understanding-radar-signal-processing-An-overview-for-Infineon-XENSIV-radar/ta-p/833659)
and [TI CFAR processing documentation](https://software-dl.ti.com/ra-processors/esd/MMWAVE-L-SDK/05_04_00_01/exports/api_guide_xwrL64xx/CFARPROC_PAGE.html).

CFAR threshold formulas have statistical assumptions. In particular, a
single-look exponential-power threshold is not automatically calibrated after
Hann windows, channel integration, mean subtraction and peak selection. The
current median gate and this implementation expose an empirical SNR factor,
not a false-alarm probability. CA, GOCA, SOCA and OS reference estimators are
useful candidates for a controlled comparison.
[MathWorks CFAR assumptions](https://www.mathworks.com/help/phased/ug/constant-false-alarm-rate-cfar-detection.html)
and [2D CFAR methods](https://www.mathworks.com/help/phased/ref/phased.cfardetector2d-system-object.html).

MUSIC requires a suitable covariance/source model; coherent sources can reduce
its rank, and spatial smoothing uses array structure/aperture. Applying it to
this unverified three-element array is an experiment, not a promise of dense
3D resolution. [MUSIC model and assumptions](https://www.mathworks.com/help/phased/ug/music-super-resolution-doa-estimation.html).
Infineon also explicitly requires hardware-specific phase correction before
angle calculation. [Official PDT calibration description](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-people-tracking#calibration-matrix-update).

For a production presence/tracking objective, the official Infineon
[clutter/localization example](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-clutter-clustering/tree/07becc7e36686e3d181ddd058df387287f09a504)
and [PDT example](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-people-tracking)
are useful alternative baselines with supported sequences. Their performance
claims do not transfer to this application's modified raw acquisition.

For glass, detecting a reflection and identifying the material are separate
tasks. GlassFormer uses radar with RGB-D fusion; it does not validate a radar-only
glass classifier for these three channels.
[GlassFormer paper](https://arxiv.org/abs/2609.36844). The repository's material
output should remain unknown without a separately validated classification task.

An example bandwidth budget: retaining 17 chirps but increasing to 256 samples
would produce 26,164-byte packets, or 261,640 bytes/s at 10 Hz. That exceeds the
2 Mbaud 8N1 limit of 200,000 bytes/s even before acquisition overhead. More
samples require a lower frame rate, faster link or on-device processing.

## Implemented experimental mode

`Config.moving_detector` defaults to `range_profile`, preserving old JSON
behavior. Set it to `range_doppler`, or override it from the CLI:

```sh
python -m radar gui --synthetic --moving-detector range_doppler
python -m radar gui --replay recordings/SESSION --moving-detector range_doppler
python -m radar analyze recordings/SESSION --moving-detector range_profile
python -m radar analyze recordings/SESSION --moving-detector range_doppler
```

`analyze` reports the selected mode and the final frame's detections; it is not
a labeled-session evaluator. `record` also accepts the option and saves the
selected mode in `config.json`. Replay overrides do not rewrite source recordings.
The option affects the main detection list, not the separate `--point-cloud`
extractor or the phase probe.

The new mode computes two separable median-reference gates and takes the larger:
the existing bounded range reference (offsets 3–10 where available, excluding
DC and Nyquist) at each Doppler row, and a circular Doppler reference at each
range. Doppler training excludes ±2 bins around the cell and the central three
bins. This is a CFAR-inspired empirical detector, not full 2D ring OS-CFAR.
Sparse bursts with no valid Doppler references are rejected conservatively.

Above-threshold candidates must be 3×3 local maxima. Doppler comparisons wrap
at Nyquist; range comparisons do not wrap. Adjacent equal maxima have a
deterministic index tie break. Peak comparisons retain the original values
inside the central exclusion zone, preventing an artificial peak at its edge.
Angles and range interpolation use the chosen Doppler row. Stationary candidates
retain their independent path. Both timing-verification flags remain required
before exposing velocity in m/s.

## Validation and measured limits

The complete Python suite passed: **93 tests**, including same-range movers,
adjacent ranges at different Dopplers, static/moving angle separation, independent
SNR gates, off-bin leakage, Nyquist wrap, noise, short bursts, configuration
roundtrip and unverified timing. Test dependencies included the official
`release-v1.1.0/register_hal/xensiv_bgt60cutrxxb_register_hal.h` at the sibling
`mtb_shared/sensor-xensiv-bgt60cutrxx/` path expected by existing audit tests.

An offscreen Qt run also processed and recorded 15 synthetic frames with the
new mode. CLI analysis replayed all 15 frames under both modes, the recording
retained its selected mode, and raw/config file hashes were unchanged by the
replay overrides. Python compilation and `git diff --check` passed.

Reproduce the synthetic comparison:

```sh
python -m unittest discover -s tests -q
python -m tools.detection_benchmark --frames 100 --output artifacts/detection-benchmark.json
```

Each scene has 100 frames, identical raw samples for both modes, seeds 0–99,
and white ADC noise with standard deviation 15. Matching requires range error
≤0.1 bin, circular Doppler error ≤0.51 bin, and azimuth/elevation errors ≤2°,
with one-to-one matches. Both modes below include the SNR and stationary-angle
bug fixes, so this comparison isolates the optional moving detector.

| Synthetic scene | Expected target instances | `range_profile` matched | `range_doppler` matched | Unmatched detections (old/new) |
|---|---:|---:|---:|---:|
| Two movers at the same range, second 6 dB down | 200 | 100 | 200 | 0 / 0 |
| Movers 0.6 range bin apart, different Dopplers | 200 | 100 | 200 | 0 / 0 |
| Stationary target and mover at the same range | 200 | 200 | 200 | 0 / 0 |
| Single off-bin mover | 100 | 100 | 100 | 0 / 0 |
| Near-Nyquist mover | 100 | 100 | 100 | 0 / 0 |
| Stationary target | 100 | 100 | 100 | 0 / 0 |
| Same-range mover 20 dB below the stronger one | 200 | 100 | 101 | 0 / 0 |
| Noise only | 0 | 0 | 0 | 0 / 0 |

On this cloud host, per-scene median processing time was approximately 2.4–3.0 ms
for `range_profile` and 10.2–12.3 ms for `range_doppler`; new-mode p95 was
45–48 ms. These timings cover host processing without GUI/serial acquisition,
not MCU performance or a real-time guarantee.

The 20 dB case is an explicit remaining failure: strong-target leakage/reference
contamination still masks nearly every weak return. The central ±1 Doppler-bin
blind zone also remains; the new mode does not solve slow-motion sensitivity.
Two targets in the same unresolved range–Doppler cell still cannot be reliably
separated by this detector. Synthetic inputs omit analog filters, multipath,
housing effects, phase drift and waveform timing errors. Zero unmatched
detections in this small simulation is not a hardware false-alarm-rate claim.

Before making the mode the default, evaluate paired empty/target recordings
across range, SNR, relative velocity, target count and near/far clutter. Compare
recall at the same false detections per frame, and report localization error,
dropouts and latency separately. Reserve held-out scenes for evaluation. The
software changes require no firmware rebuild; no firmware was flashed and no
hardware improvement has been asserted.
