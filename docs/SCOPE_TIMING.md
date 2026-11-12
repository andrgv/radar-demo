# Sensor-derived timing output for clip-ended BNC leads

Prepared and built locally on macOS on November 10, 2026. The user subsequently
flashed it and recorded `recordings/scope-timing-01`; no electrical waveform was
measured. The built HEX is at
`build/scope-timing/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex` (SHA-256
`a48ed6f40e42b627c037c10321baab1c89ef53d96ed4ca0e5649399847b3a5d5`).
This is a separate build. The November 10 captures report HPF350 qualification
profile `0x33514802`, whose code leaves DIO4 as IRQ. On November 10, the connected
board's flash was compared read-only over KitProg3 SWD with the archived HPF350
HEX: OpenOCD verified all 47,100 programmed image bytes. Attaching to that image
would show IRQ events, not the intended chirp marker. The readback is documented
in the [timing checkpoint](../evidence/rd-timing-feasibility-20261110/README.md).

## Which image to program

For the **scope timing measurement**, program the HEX above (profile
`0x33515301`) and use `configs/qualification-scope.json` for raw recording.
It routes CHIRP_ACTIVE to the buffered DIO4/IRQ header pin and disables the MCU
GPIO10 rising-edge interrupt. The firmware continues to poll FIFO and error
status over SPI. HPF remains 350 kHz; raw sequencer words, 17 acquired chirps,
64 samples, three RX, frame scheduling and UART baud are retained from the
HPF350 qualification variant. No Doppler velocity calibration is claimed.

After the timing measurement, to resume the **previous HPF350 CFAR setup**,
restore `artifacts/hpf-pair-2/hpf350/glass-radar-3rx.hex` (profile `0x33514802`,
SHA-256 `a68e0646857d76d1511be8a5ec9ba2c8130a7d3ff897966afd6e391073163897`)
and use `artifacts/hpf-pair-2/hpf350/range-config.json`. The archive's
November 1 return-to-350 flash record verifies that exact HEX at that time;
the November 10 readback independently confirms it still matches the board's
programmed application bytes before the scope experiment. The comparison covers
the HEX image's programmed addresses, not the entire 2 MB flash.

The original general `firmware/main.c` has profile `0x33525801` and is a
different build. Do not use `build/last_config/glass-radar-3rx.hex` as an assumed
HPF350 restore image. Source and provenance details are in
`artifacts/hpf-pair-2/manifest.json` and the November 10
[timing checkpoint](../evidence/rd-timing-feasibility-20261110/README.md).

To flash the scope image from this Mac, close the radar GUI/serial readers,
keep only the intended KitProg3 board connected, and run from the repository root:

```sh
make program -j4 \
  CY_TOOLS_DIR=/Applications/ModusToolbox/tools_3.9 \
  CY_BUILD_LOCATION=build/scope-timing \
  RADAR_QUALIFICATION=1 RADAR_HPF_KHZ=350 RADAR_SCOPE_OUTPUT=1
```

This runs the ModusToolbox program target for the built scope variant; it **will
replace** the board's current HPF350 application. Check the program command's
success and then record with `configs/qualification-scope.json` (profile
`0x33515301`). The scope marker requires the new image; merely opening the
serial port or connecting the scope to the old image does not enable it.

To return to the verified previous application, use the archived HPF350 HEX
above in ModusToolbox Programmer's image selector, or run this OpenOCD command
from the repository root. The `program` command writes flash, verifies it and
resets the target; this restore command has not been executed in this study.

```sh
/Applications/ModusToolboxProgtools-2.0/openocd/bin/openocd \
  -s /Applications/ModusToolboxProgtools-2.0/openocd/scripts \
  -f interface/kitprog3.cfg -c 'transport select swd' \
  -c 'set ENABLE_ACQUIRE 0' -f target/infineon/cy8cxxa.cfg \
  -c 'program artifacts/hpf-pair-2/hpf350/glass-radar-3rx.hex verify reset exit'
```

Then use the archived HPF350 range config again. Do not rebuild the general
`firmware/main.c` as a substitute for that archive.

The scope variant uses HPF350 and the same raw acquisition sequence. After the
driver has completed initialization/calibration, it disables the MCU GPIO10
rising-edge interrupt, selects CHIRP_ACTIVE on radar DMUX0, and routes DMUX0 to
DIO4 with no pulse stretching. It reads both registers back to verify values.
The FIFO and overflow checks still poll sensor status over SPI. No DIO0/DIO1 SPI
data pin is repurposed. Normal and HPF A/B builds compile out this routing.

Source-backed intended route:

- Radar IO_CTRL (0x0100): change DMUX0_SEL bits4:0 to 15 (CHIRP_ACTIVE), preserve all other fields.
- Radar IO_DIO4 (0x0120): MAP=6 (DMUX0), output enabled, strong drive, pulse length=NONE.
- Wing IRQ/DIO4 connection reaches SPI_DIO4_Feather: GPIO10/P9_3, header J1 pin7.
- Board ground is header J2 pin4.
- The header is on the level-shifted MCU side. Do not substitute a bare 1.8 V radar test pad.

The board mapping is from Infineon's UG113247 revision1.10, Table8 (pages26--27).
Use the GPIO10/IRQ and GND markings to identify the actual pins; do not infer pin
numbering from an arbitrary viewing direction. Keep the wing's normal routing
switch configuration. A different board revision or changed routing switch
needs confirmation before using these locations.

For MSOX4024G analog CH1 and a BNC-to-clips cable, intended connection after
confirmation/flashing is signal clip to GPIO10/IRQ, ground clip to GND. Attach
with board power off, ensuring clips cannot bridge adjacent pins, then power
the USB board. Set CH1 to DC coupling, **1 megohm**, and **1x** attenuation for
a direct cable. Start at 1 V/div, 500 us/div, rising-edge trigger around 1.5 V,
Normal mode. The header signal should be logic-level, nominally 3.3 V; the
scope measurement must confirm that expectation. The signal/ground clips must
be known from cable markings or continuity; never assume clip colors.

Direct coax has more capacitance than a 10x probe. This connection is intended
for the buffered header marker, not the radar oscillator, RF path or SPI clock.
Do not select 50-ohm termination. A cable that distorts/misses pulses is not a
valid timing measurement; borrow a compensated 10x probe if necessary.

After programming the scope image, start streaming with the matching profile.
For a raw capture usable by the range–Doppler replay code, use a new recording
directory and your actual port:

```sh
./range-v1 capture recordings/scope-timing-01 \
  --config configs/qualification-scope.json \
  --port /dev/cu.usbmodemACTUAL --seconds 20
```

The older broad-pipeline GUI can also start streaming using:

```powershell
python -m radar gui --port COM3 --config configs/qualification-scope.json
```

## Capturing rising-edge times on the MSOX4024G

You do **not** need to hand-enter each edge. Save the analog CH1 waveform as a
CSV with time and voltage samples; the edge times can be extracted afterward.
The `burst_id,time_us` format mentioned below is a *derived edge list*, not the
format the oscilloscope itself must export.

1. With the board powered off, connect the signal clip to the buffered
   GPIO10/IRQ header pin and its ground clip to board GND as described above.
   Power the board, then set CH1 to DC, 1 MΩ, 1x for a direct cable, around
   1 V/div. Do not use the scope's 50 Ω termination.
2. Set Trigger to **Edge**, source CH1, rising, around 1.5 V, **Normal** mode.
   Set approximately **500 µs/div** and position the trigger near the left side
   of the display so the roughly 3.5 ms acquisition fits in the 5 ms screen.
   Increase to 1 ms/div if pulses are clipped. Check that CH1 shows clean pulses
   rising from near 0 V to logic level, rather than IRQ spikes or noise.
3. Arm **Single** on the scope, then start a new raw capture, for example
   `recordings/scope-timing-02` with the matching scope config. The scope should
   stop on one burst. Count its pulses and ensure the first and last pulses are
   both visible. Save that acquisition before pressing Single again. Capture at
   least three separate bursts; a later burst in the 20-second run is useful.
4. Insert a USB stick in the scope. Press **Save/Recall → Save**, select **CSV
   data** (or **ASCII XY data**) as the format, choose the USB location, set the
   available **Length** to preserve enough samples, then **Press to Save**.
   Save each burst under a distinct name. Also save a PNG screen image showing
   the waveform, horizontal scale and pulse count. Do not save only a screenshot:
   its pixels are less precise than waveform samples.

Copy the scope CSV files and images into the workspace beside the new raw
recording. Keep the scope's original units and metadata; there is no need to
manually convert them into microseconds. If CSV export is unavailable, use the
scope's X1 and X2 time cursors on adjacent rising edges to record several
rise-to-rise intervals, plus the first-to-last rise interval and pulse count;
waveform CSV is preferable because it preserves all intervals.

More than 17 pulses are possible because firmware stops after FIFO readout
rather than after an exact hardware chirp count. CHIRP_ACTIVE marks sensor chirp
activity, not necessarily ADC start. It measures the radar's chirp schedule;
further checks must associate saved raw blocks with pulses and establish
same-waveform sampling. Once an edge list has been extracted, the optional
`tools/analyze_chirp_edges.py` accepts a derived `burst_id,time_us` CSV and
reports each burst separately. Independent bursts must not be stitched together.

The [feasibility audit](../evidence/rd-timing-feasibility-20261110/README.md)
uses recent capture-path durations to give a conditional upper bound on uniform
chirp spacing. It is not a substitute for this electrical measurement.

This build does not automatically mark velocity calibration verified. It must
not be used as one side of an HPF A/B run; both sides of that comparison need
identical diagnostic routing.

Build command (no programming):

```powershell
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -Variant scope
```

Output: `build/scope-timing/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex`.
New profile ID: 0x33515301. Firmware flashing requires separate confirmation.

Sources:
- Installed official register HAL: IO_CTRL_DMUX0_SEL_CHIRP_ACTIVE and IO_DIO4_MAP_DMUX0.
- [Infineon CSK wing guide](https://www.infineon.com/assets/row/public/documents/24/44/infineon-ug113247-kit-csk-bgt60cutr13-xensiv-connected-sensor-kit-usermanual-en.pdf), level shifting and header mapping.
- [Keysight probe-loading guidance](https://www.keysight.com/zz/en/lib/resources/selection-guides/oscilloscope-probes.html).
