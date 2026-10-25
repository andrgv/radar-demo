# Audit of existing ADC recordings

This audit deliberately uses the nine existing recordings, without new hardware captures, sweeps, smoothing, background subtraction, gain fitting or live configuration changes. Its independent raw plots and machine-readable findings are in `artifacts/recording-audit/`.

## Scope and reproduction

```powershell
python -m radar audit recordings --output artifacts/recording-audit
```

The report covers **908 complete packets and 2,963,712 stored uint16 ADC containers**. It hashes each raw file and retains every stored chirp, including chirp 0. The command saves one four-panel raw diagnostic image per session, `audit.json` and `audit.md`. It reads but does not modify raw recordings, firmware or existing host configurations. The live serial device is never opened.

## 1. Data structure and transport

All recorded packets have the expected 17 x 64 x 3 shape and matching profile ID. No saved packet CRC/header failures or incomplete tails were found. Eight sessions have no sequence gaps; `plate_0_6m` has one. Device error/drop counter increases are zero in all sessions. A clean re-encoded recording cannot prove that no corrupt serial bytes were discarded before recording.

Trigger timestamps are approximately 100,000 microseconds apart, with a 200,000-microsecond interval at the one sequence gap. They establish the nominal 10 Hz frame schedule. They do **not** establish intra-frame chirp spacing. The wire packet has no per-chirp timestamps, sampling clock readback, carrier frequency or boot ID.

No values hit the 0/65535 container rails. This says nothing definitive about the ADC's effective bit-depth or internal analog clipping thresholds. Bit occupancy, extrema, channel equality fractions and format comparisons are retained in the JSON rather than assuming effective ADC resolution from the 16-bit container size.

## 2. Packing and chirp repeatability

On the three strong plate sessions, the current little-endian unsigned, sample-interleaved interpretation yields dominant bins 2, 4 and 6. Adjacent-chirp waveform correlations have medians **0.99938, 0.99904 and 0.99926**. Chirp amplitudes are nearly uniform across all 17 slots; there is no obvious gross first-chirp corruption in these static datasets. This does not prove that chirp 0 is always usable or that the sequencer's timing is uniform.

Counterfactual interpretations were tested: signed 16-bit values, byte-swapped values, and receiver-major packing within a chirp or frame. In these plate sessions, byte swapping gives much rougher waveforms and about 9.6% energy near its dominant three FFT bins versus 84–91% under the current interpretation. Receiver-major interpretation instead creates a strong high-bin artifact (bins 21, 20 and 19), while current sample interleaving gives smooth waveforms and the expected outward-moving low-range peak.

This is evidence supporting the current packing assumption and against a gross byte-order/layout error. It is not physical certification of RX1/RX2/RX3 labels. Reordering the three unnamed receive channels preserves many of these statistics; a reference pattern or known directional response is still needed to establish physical mapping.

## 3. The range scale can be justified from source

The loaded profile specifies `SYSTEM_CLOCK_HZ=80,000,000`, `ADC_IDX0_CTRL=0x00100000`, `SH_IDX0_RAMP=0x2b2` and `SH_IDX0_SAMPLE=64`. The installed register definitions identify SR_DIV=16, decimation DF1 and ramp step 690.

The nominal model is:

```
sample_rate = system_clock / SR_DIV / decimation = 5,000,000 Hz
slope = ramp_step * system_clock**2 / 2**17 = 33,691,406,250,000 Hz/s
FFT bin spacing = c * sample_rate / (2 * slope * N) = 0.347585459 m
```

The 5 MHz sampling rate is also stated in Infineon's [clutter/clustering example](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-clutter-clustering). The slope scaling is corroborated by two independent generated sequence metadata sets in that example's [configuration header](https://github.com/Infineon/mtb-example-psoc6-cmos-radar-clutter-clustering/blob/07becc7e36686e3d181ddd058df387287f09a504/radar_config/presence_detection_localization.h), blob SHA `62007b3b453f6555902779c36aa89efadb5abb35`:

| Published sequence | Ramp step | Samples | Sample rate | Published resolution | Reproduced resolution |
|---|---:|---:|---:|---:|---:|
| RD, SH_IDX5 | 667 | 64 | 5 MHz | 0.36527864281192735 m | 0.36527864281192735 m |
| ULP, SH_IDX6 | 770 | 256 | 5 MHz | 0.07817353628520499 m | 0.07817353628520499 m |

Those generated resolution values use the sampled **N−1** interval span: `c*sample_rate/(2*slope*(N-1))`. The actual N-point FFT frequency grid uses **N**. Confusing these produces a separate small scale error. The nominal formula also appears in the pre-existing sibling demo's `python_scripts/rt_viz.py`; that file was read as corroborating local context, not modified or treated as an independent authoritative specification.

Applying the nominal 5 MHz/33.69140625 THz/s model to the uncorrected plate FFT peaks, without fitting any range scale or offset to them, gives:

| Surveyed plate position | Estimated range | Error |
|---|---:|---:|
| 0.6 m | 0.5928 m | −0.0072 m |
| 1.3 m | 1.2936 m | −0.0064 m |
| 2.0 m | 2.0175 m | +0.0175 m |

Peak interpolation here uses all recorded chirps and a local log-power parabola; it is an estimator, not improved physical resolving power. Survey uncertainty, panel orientation and room multipath remain uncharacterized. The numbers support the nominal source-derived range model on these three static records; they are not a general accuracy guarantee.

The original host metadata's 1 MHz/30 THz/s values were placeholders. Their empirical multiplier near 4.45 is largely explained by the actual profile's nominal ratio: `5 * 30 / 33.69140625 = 4.452173913`. Existing empirical configs and recording metadata were preserved rather than silently rewritten. Actual oscillator accuracy and sequencer behavior have not been measured on pins.

## 4. An important omitted angle-processing stage

The same loaded header includes the Infineon `MD_CAL_MAT_H` and `MD_CAL_MAT_E` coefficients. The [official driver documentation](https://github.com/Infineon/sensor-xensiv-bgt60cutrxx/tree/release-v1.1.0#calibration-matrix-update) describes hardware-specific **2x3 complex mixing matrices** that precede angle calculation. They include cross-channel terms, not just an independent scalar gain/phase per RX. The host's current angle estimator instead uses the uncorrected channels or a one-point diagonal correction; it has not applied these matrices.

Downloading matrix registers to the sensor does not make a host raw-FIFO FFT automatically matrix-calibrated. The matrices belong to the angle-processing path, while this firmware reads raw FIFO data with on-chip motion/FFT processing disabled in its chosen profile.

The audit extracts both matrices and reports their candidate effect on phase for every session. It uses signed Q0.15 coefficients with the upper/A half as real and lower/B half as imaginary. That packing and its hardware applicability must be verified before use as a live correction. These are **offline comparisons**, not newly certified angles or an installed calibration. Matrix values were taken from the exact loaded profile, not borrowed from a different board's latest defaults.

This omission is a specific software-model gap to investigate with the existing data. It means the prior generic raw-phase display was not equivalent to Infineon's calibrated angle pipeline. It does not prove that factory coefficients alone will solve all tabletop angle instability, since the existing records do not contain surveyed off-center target angles.

## 5. Averaging and timing remain separate uncertainties

The vendor profile describes 17 output chirps with an averaging factor of 16. The new firmware overrides `AVG_CTRL_SEQ0` to zero, lowers FIFO threshold to 191 and truncates acquisition after 17 raw-sized chirp blocks before resetting the FSM. The recordings show repeatable 64-sample block structure, but have no sensor register readback or per-chirp timing/header evidence to prove every aspect of this runtime modification. Firmware writes are not hardware measurement logs.

The current host's 1 ms chirp interval and 60 GHz carrier remain unverified. The audit leaves both unknown rather than estimating speed or angle scale from arbitrary values. A static target and a 100 ms frame timestamp cannot recover Doppler sampling time. Decoding the relevant sequencer timing or obtaining supported configuration metadata is the next source-level work; it should not be replaced by another arbitrary center calibration.

## Conclusion

Existing recordings are sufficient to establish a supported range model, strongly test format hypotheses, quantify repeatability, and identify an omitted vendor angle-calibration stage. They are insufficient to prove physical RX identity, absolute chirp timing or angular accuracy. No additional recordings or hardware purchases were needed to reach these findings. Live firmware/configuration behavior was frozen throughout this audit.
