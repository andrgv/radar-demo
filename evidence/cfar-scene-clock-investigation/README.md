# Sensor-position and clock investigation

Compared live-003 original-position empty interiors with the all-empty live-004 after the user moved the sensor approximately 20 cm sideways, farther from side clutter. Configuration and detector metadata match exactly. No live code, firmware, thresholds or recordings changed.

## Scene-dependent unwanted peak

- live-004: **0/119 detections** over 11.8 sensor seconds (11.71 host seconds), with clean transport.
- Around native bin 2 (~70 cm), median raw power falls from **67.47 dB** to **48.86 dB**: a **18.61 dB** decrease. Units are ADC power references, not dBm.
- The dominant raw spectral maximum over 0.15–3 m changes from 0.71 to 1.71 m. The latter is beyond the current detection mask (native bins 1–4, centers approximately 0.35–1.39 m). Zero detections means no accepted return inside that mask, not absence of room reflections. These maxima are not established physical object distances.
- This is strong evidence of position/scene dependence. It does not isolate the side clutter: translating the sensor also changes multipath phases, support/cable geometry and possibly orientation. A purely invariant electronics artifact is less consistent with the change, but electronics/near-field coupling is not excluded.
- The sensor datasheet specifies a broad 120° × 90° field of view. Off-axis objects can contribute even when outside the forward centerline; the FoV is not a hard cutoff or proof of a particular path.

## Timing findings

| Capture | Host span (s) | Sensor span (s) | Endpoint rate difference |
|---|---:|---:|---:|
| live-001 | 27.308 | 27.500 | 0.702% |
| live-002 | 41.908 | 42.200 | 0.696% |
| live-003 | 145.889 | 146.900 | 0.693% |
| live-004 | 11.713 | 11.800 | 0.741% |

A diagnostic clock mapping fitted using only 2–20 host seconds of live-003 gives sensor seconds = **1.007150585 × host seconds -0.005111**. On later data, maximum absolute mapped residual is **56.8 ms**. This is much smaller than the current unmapped elapsed discrepancy, which grows to about one second.

The checked-in acquisition gate compares elapsed host and device times one-to-one, taking absolute difference and rejecting above 0.5 s. It does not estimate rate difference. Sensor time runs ahead of host time here, which is not the signature expected from growing delivery delay alone.

Source audit: qualification firmware requests a 1 MHz HAL timer, writes the raw timer count as the frame timestamp, and schedules captures 100,000 counts apart. The BSP configures an IMO-derived FLL (nominal 100 MHz); HAL frequency setup accepts a 2% frequency tolerance and stores its computed clock rate internally. Success requesting 1 MHz does not prove an independently calibrated physical microsecond. Infineon documents that FLL output inherits reference-clock accuracy.

**Clock-scale mismatch is the leading explanation, not proven hardware calibration.** The running clock registers and timer frequency were not read back or measured. Divider/reference error, clock interpretation and timing instrumentation still need distinction. Host wall-clock arrivals support the same discrepancy seen by the live monotonic-time check.

A software remedy should represent a bounded host/device clock mapping and separately reject excess latency, stalled streams, queued frames, corruption and restarts. It must not simply increase the threshold or disable freshness checks. A fitted model cannot prove absolute age or distinguish every gradual backlog from clock drift. MCU timer scale also does not establish radar ADC/ramp calibration or explain the distance errors by itself.

## Additional captures that would help

1. Return the sensor to its original marked position, height and orientation; leave the target absent and record 15–20 seconds while stepped away. Recovery of the ~70 cm component would complete an A → B → A position control.
2. At the shifted position, keep the supported box at a measured 80 cm for 20–30 seconds with the operator out of the beam. A quiet empty scene alone does not establish that useful target detection/range accuracy is retained.
3. To isolate the side clutter specifically, if practical keep the sensor fixed and change only the suspected clutter, then restore it. A sensor translation alone cannot identify which object/path causes the component.

No further generic long captures are needed to demonstrate the timing failure. Actual timer/clock readback or an independent timing measurement would identify its physical source more directly than more scene sweeps. No hardware programming or configuration changes were performed.

[Plots](scene-and-clock.png) · [Full profiles, timing metrics and hashes](report.json)

Sources: [sensor datasheet](https://www.infineon.com/assets/row/public/documents/30/49/infineon-bgt60cutr13aip-datasheet-en.pdf), [Infineon FLL documentation](https://infineon.github.io/psoc6pdl/pdl_api_reference_manual/html/group__group__sysclk__fll.html).

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.investigate_cfar_scene_clock --root recordings/gui-20261109-224819-094246 --prior-labels evidence/cfar-long-hold-224819-live003/report.json --output evidence/new-scene-clock-investigation
```
