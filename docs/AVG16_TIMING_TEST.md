# Vendor AVG16 timing test

The complete [AVG1 edge capture review](../evidence/rd-mcu-edge-20261110/README.md)
found 112 CHIRP_ACTIVE edges in seven groups of 16 while the MCU saved 17 ADC
blocks. An earlier moving-target recording shows an enlarged phase step at the
saved-block boundary matching the first group gap. This supports, but does not
directly prove, the conclusion that AVG1 and early FIFO truncation leave an
uneven slow-time sequence.

This **separate experimental image** preserves the vendor-generated AVG16
setting (`AVG_CTRL_SEQ0=4`) and checks its register readback. It keeps HPF350,
the same sequencer words, three RX, 64 samples, 17 saved blocks, FIFO drain,
frame scheduling and UART baud. It logs up to 320 CHIRP_ACTIVE rising edges in
each CRC-protected frame. The profile is `0x33515403`, wire version 4, with
matching `configs/qualification-avg16-timing.json`. The built HEX is
`build/avg16-timing/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex`
(SHA-256 `d0977802717651271a0acd25d236104a57fbe466e9a214c278cee0d86917f4d6`).
The user flashed it and recorded `recordings/avg16-timing-01`. All 201 frames
have 272 edges in 17 groups of 16, with no overflow or device errors. The
stationary saved-block phase is consistent. See the
[capture review](../evidence/rd-avg16-20261110/README.md). It remains an
experiment, not a calibrated velocity detector.

## First capture

Close the radar GUI and serial readers, and keep only the intended KitProg3
board connected. From the repository root:

```sh
/Applications/ModusToolboxProgtools-2.0/openocd/bin/openocd \
  -s /Applications/ModusToolboxProgtools-2.0/openocd/scripts \
  -f interface/kitprog3.cfg -c 'transport select swd' \
  -c 'set ENABLE_ACQUIRE 0' -f target/infineon/cy8cxxa.cfg \
  -c 'program build/avg16-timing/APP_CYSBSYSKIT-DEV-01/Release/glass-radar-3rx.hex verify reset exit'
```

Start with an ordinary stationary scene. Use a fresh directory and the actual
serial port:

```sh
./range-v1 capture recordings/avg16-timing-01 \
  --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL --seconds 20
```

The first review will check packet integrity, whether the edge count approaches
the expected 17 × 16, the inter-group schedule, overflow, acquisition time,
and phase consistency across saved blocks. Only then should we collect a
controlled approach/hold/retreat sample with this image to test useful Doppler
response. The MCU GPIO interrupt can delay individual edge timestamps, and
AVG16 coherence and block correspondence remain unverified until measured.

To return to the earlier HPF350 CFAR setup, use the restore image and config in
[SCOPE_TIMING.md](SCOPE_TIMING.md#which-image-to-program).

## Next capture: controlled motion

The first controlled run is now recorded in `recordings/avg16-motion-01`.
It shows repeatable direction-dependent phase and nonzero full-map peaks;
see the [motion review](../evidence/rd-avg16-motion-20261110/README.md).
The next work is a replay 2D CFAR prototype. The protocol below documents that
development capture; another run is not required before software work.

Keep this firmware and `configs/qualification-avg16-timing.json`. No reflash is
needed. Use the wheeled target with the radar fixed, and keep the target's
orientation consistent. The existing 120 cm and 60 cm endpoints are suitable
for this first qualitative test. Keep the wall if space requires it and keep
the operator to the side as before.

```sh
./range-v1 capture recordings/avg16-motion-01 \
  --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL --seconds 60
```

Aim for these approximate phases:

| Approximate time | Action |
|---|---|
| 0–10 s | Hold target at 120 cm |
| 10–12 s | Roll toward 60 cm, taking about 1–2 seconds |
| 12–22 s | Hold at 60 cm |
| 22–24 s | Roll back to 120 cm, taking about 1–2 seconds |
| 24–34 s | Hold at 120 cm |
| 34–36 s | Repeat approach |
| 36–46 s | Hold at 60 cm |
| 46–48 s | Repeat retreat |
| 48–60 s | Hold at 120 cm |

Record the actual start/stop times or take a video with a visible stopwatch.
Smooth motion is helpful; constant speed is not required to check direction
and stopped intervals. A 60 cm trip over 1–2 seconds should provide a clearer
first test than the earlier very slow rolls. We will test slower motion after
confirming a response. Do not use the GUI's distance estimate as ground truth.

The raw capture continues saving frames if a host `clock_fit_unstable` quality
message appears. Keep that evidence with the recording; it will be reviewed
separately from onboard timing and phase. No empty-reference training or
background subtraction is needed.
