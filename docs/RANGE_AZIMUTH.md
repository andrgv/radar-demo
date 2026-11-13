# Simultaneous range and azimuth

`radar.range_azimuth` reads live USB frames or replays a recording. It measures
range and RX2–RX1 azimuth from the same return, using the physical steering
model in `radar.angle_lab`. The terminal prints both measurements; `--plot`
adds a live range profile and a top-down position display. Close the plot or
press Ctrl-C to stop. `--seconds` sets an optional time limit.

Try the existing right-hand check:

```bash
.venv/bin/python -m radar.range_azimuth \
  --replay recordings/box-angle-01/check_right \
  --reference recordings/box-angle-01/center_repeat \
  --reference-xyz 0 2 -0.1125 \
  --min-range 1.5 --max-range 2.5 --plot
```

For live USB, replace `--replay ...` with `--port /dev/ttyACM0` (use the actual
serial device). Add `--jsonl artifacts/range-azimuth-live.jsonl` to save
measurements. The output must be a new file. USB acquisition sends the existing
firmware start/stop commands and closes the serial connection on exit.

The reference is a recording of a target at a measured sensor-relative X,Y,Z
position, in meters: right, forward, up. It must contain at least ten raw
frames with matching acquisition settings and pass contrast, coherence and
local-peak checks. The existing reference provides a starting point for the
same radar mounting and channel response; changed mounting or phase response
requires a new reference. Reference XYZ describes that recording, not the
current target position.

The program searches the specified range interval and selects its strongest
local peak. Narrow the interval to the intended target. It cannot distinguish
the target from a stronger object or clutter in that interval. Five frames
are averaged by default (roughly half a second); `--window 1` responds faster.
Sequence discontinuities reset averaging.

`CANDIDATE` means the selected return passed the configured contrast threshold,
RX2 coherence >= 0.90, and the azimuth model bounds. `WEAK` and `NO_TARGET`
suppress angle and position output. These gates do not certify target identity
or reject all multipath. The azimuth search is limited to +/-25 degrees.

Height is assumed equal to reference Z, or supplied with `--target-z`. It is
shown in the display and JSONL and is used to convert slant range into X,Y.
There is no elevation measurement. The existing measurements support local
azimuth performance near 2 m at a fixed height; they do not validate range
accuracy, other heights/ranges, moving-platform performance or new scenes.
On the full saved check captures, range/azimuth are approximately
2.067 m / -4.40 degrees and 2.120 m / +4.10 degrees (surveyed forward distance
2 m, bearings +/-4.29 degrees). No range-scale adjustment is fitted here.

Replay automatically uses its own saved `spectral-background.npz` if present.
Live acquisition uses no background by default. `--background` explicitly
loads a matching empty recording or NPZ; this requires an unchanged static
scene and is unsuitable for subtraction after the robot moves.
