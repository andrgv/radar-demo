# Sensor-derived timing output for clip-ended BNC leads

Prepared, not yet flashed or electrically measured. This is a separate build;
the currently running HPF350 qualification image leaves DIO4 as IRQ. Attaching
to that existing image would show IRQ events, not the intended chirp marker.

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

Start streaming using:

```powershell
python -m radar gui --port COM3 --config configs/qualification-scope.json
```

Trigger on a burst, then zoom in until consecutive pulses can be measured.
Record rise-to-rise interval, pulse width, number of pulses per acquisition and
burst-to-burst interval. Observe whether the initial pulse differs or intervals
change. More than 17 pulses are possible because firmware stops after FIFO
readout rather than after an exact hardware chirp count. Do not assume that a
CHIRP_ACTIVE edge aligns exactly with ADC start. It measures the sensor's chirp
activity schedule; further checks are needed to associate each saved raw block
with one pulse and establish uniform same-waveform sample timing.

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
