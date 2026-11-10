# Live range viewer

Long captures now use a bounded startup host/device clock mapping. Restart an
already open GUI to load it; no new flags or empty capture are needed for clock
estimation. See [clock policy and validation](docs/CFAR_RANGE.md#long-run-hostdevice-clock-handling).

For the new **baseline-free CA-CFAR mode**, use `--detector cfar`; see
[setup, commands, settings and initial results](docs/CFAR_RANGE.md). The existing
empty-reference mode below remains the default.

The board currently runs HPF350 qualification firmware. From wavvy-range-v1:

```sh
./range-v1 gui --config artifacts/hpf-pair-2/hpf350/range-config.json --port /dev/cu.usbmodem103
```

1. Close other radar/serial readers. Leave sensor fixed and remove the box.
2. Click **Box removed: capture empty (10 s)**. There is a five-second delay to
   step away, then ten seconds of raw recording. The first 30 frames fit the
   background; the unused-frame detection count is displayed and saved. This is
   a within-recording check, not a replacement for a separate empty holdout.
3. Put the supported box in position, then click **Start live + record**. Stop
   when finished. A live run is limited to one hour. Each start creates a new
   recording folder; no previous recording is overwritten.

The large number is the frozen fixed-empty-waveform joint-tone estimate only
when the existing presence detector accepts the frame. It is **experimental and
uncalibrated**, not a validated object distance. When the detector rejects it,
the large number clears; any numeric fit is separately labeled **candidate only**.
The plot keeps gaps for rejected frames, even if UI redraws skip frames. There
is no smoothing, held-last-reading behavior or new confidence percentage.

**Signal change (dB)** is `10 log10(current native-bin power / fitted empty-bin
power)` at the detector's candidate bin. That coarse bin need not coincide with
the fine fitted frequency. It is not dBm, absolute RF power or calibrated SNR.
The left plot shows the same background-relative spectrum. Values can be negative.

The right plot shows accepted experimental estimates versus time. All raw frames
and original serial bytes are recorded regardless of detector decisions. During
live capture, readings.jsonl includes experimental_range_m and fit residual
alongside unchanged native-detector fields; range_m remains null/calibrated=false.
The new fitted-background model is NOT used in the GUI.

Raw files are saved under `recordings/gui-<timestamp>/empty-001`, `live-002`, etc.
The empty subfolder contains baseline.json and empty-holdout.json. The recording
location appears in the window. USB timeout/stale data clears the readout; errors
stop the worker, close serial and retain partial recordings. Stop/window close
sends the existing stop command and finishes recording. No flash operation exists
in the GUI. A frame-validity failure is never treated as a fresh accepted range.

An existing reference can be reused only if the sensor and scene truly match:

```sh
./range-v1 gui --config artifacts/hpf-pair-2/hpf350/range-config.json --baseline artifacts/hpf350-b-baseline.json
```

The empty recording's saved hash/configuration must match. Prefer a fresh empty
capture after changes. The program will not silently mix HPF100/HPF350 profiles.

Replay without the board:

```sh
./range-v1 gui --config artifacts/hpf-pair-2/hpf350/range-config.json --baseline artifacts/hpf350-b-baseline.json --replay recordings/hpf350-b-40cm
```

Click Start replay. Replay does not record or connect to serial. The UI identifies
REPLAY explicitly. An offscreen replay snapshot was rendered and inspected;
tests cover stale/rejected readouts, stop preserving raw data and enhanced logs,
and timeout clearing/port closure. Existing acquisition tests still pass.
Fresh hardware GUI calibration/live use awaits the user's setup/button clicks;
no unlabelled scene is automatically treated as empty.

Search-limit correction: fits at the configured 15 cm / 150 cm endpoints now
show **distance unresolved** and leave a gap in the main range history, even
when presence is detected. The candidate remains visible and recorded; this is
not proof of a physical sensor minimum/maximum range. Saved readings also include
fit_boundary and fit_near_optimal_width_m; the latter is not a confidence interval.
This correction does not resolve wrong estimates away from the search limits.
Restart an already open GUI to load code changes.

Experimental associated-peak option: append `--estimator associated` to live or
replay commands. It restricts fine-fit local maxima to the connected qualified
spectral-bin group and rejects unresolved endpoints. It improves the saved 50 cm
jumping capture, but 30 cm failures and an empty false detection remain. Default
is still `fixed`; no smoothing is enabled. See evidence/associated-fit-3/README.md
for before/after metrics and limitations. Neither mode is calibrated ranging.
