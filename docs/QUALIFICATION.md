# Timing, channel convention and controlled HPF qualification

Status: two separate firmware variants have been compiled. Neither was flashed,
no HPF hardware experiment was run, and no known-position capture was fabricated.
The working `firmware/main.c` remains byte-for-byte unchanged. Normal builds keep
that firmware; experimental builds use an isolated generated source and output
directory. The original 1-RX project is untouched.

## Independent validity of range, phase and velocity

Incorrect chirp spacing invalidates a Doppler velocity scale. It does **not** by
itself invalidate the fast-time range FFT or inter-RX phase. Those require their
own waveform, synchronization and calibration checks. Tests now vary the assumed
chirp interval while holding ADC data fixed and verify identical range/phase
processing. The host returns `velocity_mps: null` and labels Doppler in normalized
cycles/chirp unless **both** `chirp_timing_verified` and
`carrier_frequency_verified` are explicitly true. Normalized Doppler itself
assumes uniform slots; it is not proof of physical uniformity. Old hardware configs
default to unverified. The synthetic example explicitly marks its known timing.

## Timing trace and remaining gap

```powershell
python tools/timing_trace.py
```

The result in `artifacts/qualification/timing-trace.json` preserves the SH/ADC/
SEQ/averaging/clock register trace, all 42 sequencer words, frame cadence from
device timestamps and an independent host arrival timebase comparison.

- Nominal 80 MHz radar clock, ADC divider16/DF1: 5 MHz sampling.
- 64 samples: a 12.8 us acquisition window; 12.6 us first-to-last sample span.
- MCU source frame scheduling: 100000 timer ticks, with timer requested at 1 MHz.
- The detkin device timestamps are approximately 99999--100001 ticks per frame.
- Long-separated host/device timestamp slopes imply about **99.02--99.05 ms**
  host elapsed time for the nominal 100 ms schedule in those six sessions.
  This is a repeatable timebase discrepancy worth checking, not a calibrated
  oscillator measurement. USB/OS/processing latency and host wall-clock changes
  can bias the comparison. Do not use it to rescale radar sampling or range.
- Actual chirp start spacing and full burst duration remain unknown. The
  public register HAL names trigger-delay fields but supplies no sequencer ISA
  decoder establishing how the encoded program loops and waits. Inferring a
  period from ramp duration alone or importing the 1 ms placeholder is invalid.
- Runtime factor1 averaging plus the 17-block truncation changes the original
  factor16 profile semantics. The original generated metadata cannot certify
  the resulting raw chirp schedule.

The qualification variants add a common MCU elapsed-time measurement in the
existing reserved header word10. Header flag bit1 declares it valid. It measures
from before the trigger SPI write through FIFO polling/reads, FSM stop and IRQ
checks. It bounds the host-visible acquisition path, not precise RF active time.
Dividing it by 17 does **not** produce a verified chirp period. The field is
preserved in raw recording/replay, arrivals JSON and the GUI status. Old frames
continue to decode with no elapsed-time field.

True independent verification needs a supported sequencer trace/configuration
description or a measured RF/ADC timing marker. A logic-analyzer check must
observe a sensor-derived chirp/ADC event, not merely the MCU start command or
UART packet. Routing such an event to a pin requires verifying the board pin
and output-mux mapping first; no unverified GPIO routing was installed here.
An MCU envelope marker can corroborate capture duration, but alone cannot
establish each chirp's start time.

## Reference H/E matrices and known positions

```powershell
python tools/channel_reference.py
```

All **12 loaded H/E register words exactly match** the installed official driver
reset tables. The current combined matrix exactly matches the candidate decoding
of those loaded words. Infineon's release-v1.1.0 README documents the default
coefficients for the plain CSK wing and the separate 2x3 H/E mapping. This is
coefficient provenance, not certification of stream order, complex packing,
positive angle signs, mounting or the combined 3D steering assumption.

The next known-position series should record actual target coordinates in a
sensor-relative frame: +x radar-right, +y boresight-forward, +z up, all defined
when standing behind the radar looking forward. Record TX-corner orientation,
radar height/roll/tilt, target coordinates, target normal, operator position,
and how coordinates were measured. A plate rotated in place tests reflectivity
versus incidence; it does not provide different target position angles.

Use the same firmware/profile for the entire channel test. Include a center
reference and measured horizontal and vertical offsets at a known range, plus
repeat center at the end. Evaluate all fixed channel permutations and signs on
some positions, then check withheld positions; report errors and spread instead
of forcing every capture to center. A different person/arm return remains a
legitimate scene object, but must not automatically be identified as the known
target. Empty control matching and target association must be explicit. No new
capture is needed merely to rerun the existing numerical audit; actual channel
convention validation does require independent positional information.

## HPF1 A/B experiment, prepared but not executed

The two variants share the SAME register list, sequence words, averaging
override, FIFO configuration/read loop, frame schedule and serial baud. Both
have identical duration telemetry and initialization readback. Only the RX bank0
HPF1 selection bits, identifying profile ID and HPF-identification header flag
differ. Each register is read, mask-modified, written and checked against its
expected value before any acquisition. The sequencer's use of bank0 must still
be established as part of timing/config verification.

| Register | 350 kHz | 100 kHz | Changed bits |
|---|---|---|---|
| CS_IDX0_RX1, 0x1010 | 0x000a1161 | 0x000a1061 | bit8 |
| CS_IDX0_RX2, 0x1014 | 0x000a1161 | 0x000a1061 | bit8 |
| CS_IDX0_RX3, 0x1018 | 0x000a1161 | 0x000a1061 | bit8 |

The allowed HPF1 mask is 0x300; the actual difference is 0x100. Gain, AAF, HPF2,
phase controls and RX enable bits are preserved. The nominal HPF1 range-corner
equivalents are 1.557 m and 0.445 m, respectively, not hard cutoffs.

Build only:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -Variant hpf350
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -Variant hpf100
```

Images are under `build/qualification-350/APP_CYSBSYSKIT-DEV-01/Release/` and
`build/qualification-100/APP_CYSBSYSKIT-DEV-01/Release/`. Use
`configs/qualification-hpf350.json` and `configs/qualification-hpf100.json`
with the corresponding images. Distinct profile IDs cause mismatched host
configurations to be rejected. The no-variant build command retains the working
firmware. Firmware flashing remains explicitly gated by `-ConfirmFlash`; no
program command was executed.

Before a hardware A/B run, freeze sensor/target/operator poses and incidence,
keep the same power/USB setup, and obtain an empty and target condition at each
HPF setting. Repeat 350→100→350 to detect drift. Compare raw per-RX power,
clipping, range peaks, relative phase/coherence, near-zero leakage, bin23 and
transport/capture duration statistics. Lowering the HPF may increase leakage or
table clutter; increased brightness alone is not a validated localization gain.
Do not change averaging, chirp count, gain or thresholds between the A/B captures.

## Objective decision

The prepared qualification supports either downstream objective. It does not
quietly replace dense mapping with sparse tracking. Dense geometry needs
additional constraints such as independent known-pose observations or validated
surface/scene priors. Radar-only glass localization can instead be evaluated
with associated detections/tracks and labeled material data, but glass reliability
cannot be claimed from these iPad measurements. Decide between those objectives
after the measurement model is qualified, rather than changing scope to make
current plots appear successful.

Reference: [official CSK H/E calibration documentation](https://github.com/Infineon/sensor-xensiv-bgt60cutrxx/tree/release-v1.1.0#calibration-matrix-update).
