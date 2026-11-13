# Open/closed glass-door experiment

This tests repeatable door-state differences. It does not identify glass as a
material: moving the door also moves its frame/handle and alters multipath.
No firmware changes or flashing are needed. Use the configuration matching the
firmware already on your board; this workflow cannot verify that match physically.

Fix the radar facing the middle of the closed pane, approximately perpendicular
to it. Measure antenna-face-to-glass distance. Keep the handle/frame away from
the beam center where practical. Keep the background unchanged and people out
of the scene. When open, move the door fully clear of the beam if possible.
Record the door type, coating/thickness if known, incidence angle, and background
in notes. Distance is a measured label, not a calibrated radar coordinate.

From the glass-radar directory in PowerShell (replace COM7 and distance):

```powershell
.\.venv\Scripts\python.exe -m radar door-check recordings\door01 --port COM7 --config configs\qualification-hpf350.json --distance-inches 48 --seconds 30 --repeats 3 --notes "Glass door; perpendicular; fixed background"
```

Use `--distance-inches` for your tape measurement (decimals allowed), or
`--distance` for meters. Supply exactly one. Inches are converted to meters in
the saved measurement fields using 1 inch = 0.0254 meters.

The example config matches the HPF350 profile `0x33514802`. Startup checks the
reported device profile and frame dimensions before the first door prompt;
choose a different matching config if your board reports a different profile.

Close other serial readers first. Use a fresh output directory. The command
prompts open → closed three times, allows five seconds to step away after each
prompt, and captures 30 seconds per state. `--settle` changes that delay (minimum
three seconds). The serial reader remains active through prompts and transitions.
Ctrl-C stops capture and preserves partial raw data; an incomplete experiment
cannot produce an analysis report. Repeat it in a new directory.

Outputs:

- `open-01`, `closed-01`, etc.: raw `frames.grd`, config, metadata, arrival times.
- `stream/serial-wire.bin` and `stream/transport.jsonl`: entire original serial
  stream including transitions and rejected packets. `stream/frames.grd` is unused;
  analyze the individual state directories.
- `door-check.json`: protocol, measured distance, notes, progress/completion.
- `door-check-report.json`: full profiles, variability, training selection and
  held-out result.
- `door-profiles.csv`: every bin's signed change, threshold and held-out change.
- `door-profiles.png`: repeated profiles and signed open/closed differences.

Reanalyze without hardware:

```powershell
.\.venv\Scripts\python.exe -m radar door-check-analyze recordings\door01
```

Processing preserves stationary energy: remove each chirp/RX sample mean, apply
Hann, unpadded real FFT, average power across retained chirps/RX, convert to dB.
Discard chirps according to the saved config. Each recording contributes one
median profile; adjacent frames are not independent evaluation samples.

The final open/closed pair is held out from bin selection and thresholds. Earlier
pairs must each show the same direction of change exceeding the per-bin threshold:
the maximum of 3 dB, twice the open-recording median spread, and six times the
largest within-open-recording MAD. These are exploratory engineering thresholds,
not significance levels. Among qualifying bins, select the largest absolute
median change, excluding DC and Nyquist. Both increases and decreases qualify.
Evaluate each held-out state against the training open median using the frozen
direction and threshold. A null selected bin means no repeatable training change.

Analysis rejects short (<20 frames), corrupted/truncated, discontinuous,
configuration-mismatched, container-rail and sensor/host timing-mismatched
recordings. Live capture also rejects transport-counter changes. Relative timing
cannot prove absolute freshness; there is no firmware identity/start acknowledgment.

Inspect the full profiles alongside the held-out false detection/missed detection.
Changes behind the measured door distance can be attenuation or multipath; they
do not locate the pane. Plot coordinates remain config-derived and unvalidated.
One held-out pair from one door is not an accuracy estimate or a glass classifier.
Repeat at additional distances/angles and with independent doors and non-glass
controls before drawing broader conclusions. Keep held-out recordings out of
threshold tuning; after tuning, collect a new evaluation experiment.
