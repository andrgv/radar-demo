# MCU chirp-edge timing capture

This is a no-oscilloscope diagnostic for the current HPF350 raw acquisition.
The first 64-slot image, profile `0x33515401`, was flashed and captured in
`recordings/edge-timing-02`. Its 201 frames all reported 112 edges and
overflowed. See the [capture review](../evidence/rd-mcu-edge-20261110/README.md).
The revised **128-slot** image is
`build/edge-timing-full/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex`
(SHA-256 `8fe4339f3ab28231c0f08fcd489c052774fa391bafbccba7708f3c6650a399a7`).
The user flashed it and recorded `recordings/edge-timing-03`; see the
[complete capture review](../evidence/rd-mcu-edge-20261110/README.md#complete-capture-edge-timing-03).

The image routes sensor CHIRP_ACTIVE through DIO4 to MCU GPIO10, timestamps
rising edges with the MCU's nominal 1 MHz timer, and sends them in the same
CRC-protected packet as the 17 raw blocks. Profile `0x33515402` and protocol
version 3 distinguish the revised image from the first timing capture and
scope profile `0x33515301`. Each packet contains the edge count, an overflow
flag, and up to 128 offsets from the frame's timer start. The 16 retained raw
blocks after the usual first-block discard remain available as a diagnostic,
although their physical timing is not yet
verified. The MCU timer and GPIO interrupt have not been independently
calibrated for absolute time or latency. Edge spacing does not by itself prove
raw sample timing or phase coherence.

## Reproduce the flash and capture

Close the radar GUI and other serial readers. Keep only the intended KitProg3
board connected. From the repository root, flash the **built** image:

```sh
/Applications/ModusToolboxProgtools-2.0/openocd/bin/openocd \
  -s /Applications/ModusToolboxProgtools-2.0/openocd/scripts \
  -f interface/kitprog3.cfg -c 'transport select swd' \
  -c 'set ENABLE_ACQUIRE 0' -f target/infineon/cy8cxxa.cfg \
  -c 'program build/edge-timing-full/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex verify reset exit'
```

Use a new directory and your actual serial port. A stationary, ordinary scene
is enough for the first timing check; no moving target is needed.

```sh
./range-v1 capture recordings/edge-timing-03 \
  --config configs/qualification-edge-timing-full.json \
  --port /dev/cu.usbmodemACTUAL --seconds 20
```

Capture stores the raw ADC and edge times together in `frames.grd`, and writes
readable copies of the edge times to `arrivals.jsonl`. For a first summary and
CSV compatible with the existing edge analyzer:

```sh
.venv/bin/python -m tools.analyze_mcu_edges recordings/edge-timing-03 \
  --csv recordings/edge-timing-03/chirp-edges.csv
.venv/bin/python -m tools.analyze_chirp_edges \
  recordings/edge-timing-03/chirp-edges.csv \
  --output recordings/edge-timing-03/chirp-edge-report.json
```

Share the full recording directory. We will check edge count per burst,
within-burst spacing, missing/extra edges, packet integrity, and whether the
raw phase behaves consistently. An empty or irregular edge log requires
investigation before using its interval for a physical velocity axis.

To resume the previous CFAR setup afterward, restore the archived HPF350 image
and config using [SCOPE_TIMING.md](SCOPE_TIMING.md#which-image-to-program).
