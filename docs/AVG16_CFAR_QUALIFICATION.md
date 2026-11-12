# Qualifying 1D CFAR on the AVG16 acquisition profile

Use the current AVG16 image with `configs/qualification-avg16-timing.json`.
No firmware change is needed. Both processing paths can use the same saved
frames. The nominal range scale is unchanged, but hardware averaging changes
noise and motion response, so earlier AVG1 performance does not transfer.

## Frozen development replay

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.qualify_avg16_cfar \
  --manifest configs/avg16-cfar-qualification.json \
  --output evidence/my-avg16-cfar-qualification
```

The output directory must be new. The manifest fixes guard 1, training/minimum
4 and multiplier 2, with each recording's saved search mask and confirmation.
It includes the timing capture and both previously reviewed motion captures;
these are development data, not independent acceptance data. Reports preserve
source/input hashes, all recomputed frame decisions, scene-window coverage,
unresolved reasons, selected bins, numeric episodes and a timeline.

Recomputation uses ADC/device validity and continuity; it does not reconstruct
original host backlog/clock gates. Saved clock states and reading reasons are
reported separately. Conditional placement differences are calculated only on
numeric outputs and do not establish the identity of the measured reflector.
An added-target-absent scene can contain legitimate wall/operator returns.

The [initial replay report](../evidence/avg16-cfar-qualification-20261111/README.md)
covers 1,955 frames across three captures. It confirms processing compatibility,
but not accuracy acceptance: the two labeled 60 cm holds have medians of 85.0
and 48.7 cm despite complete numeric coverage. Several 120 cm holds have little
or no output. In the follow-up, the 30 cm holds have complete coverage with
35.1/37.8 cm medians, while the initial target-absent interval has 6/121 numeric
outputs. Repeatable placements and operator controls are needed to distinguish
reflector selection, placement effects and measurement bias. These results do
not isolate the effect of AVG16 versus AVG1.

## New data to collect

Keep the radar fixed on a support, with the antenna face as the distance origin.
Use the same target, height and orientation throughout. Mark its lateral position
and record the wall distance and scene geometry. Keep the operator out of the
beam during quiet holds. Film a stopwatch and the target, or write actual event
times relative to capture start. Include timing uncertainty; never infer labels
from the radar readout. Preserve every failed placement.

1. **Stationary placement and removal:** collect separate approximately 90-second
   runs at measured 50, 80 and 120 cm. In each run: 15 s target absent; insert and
   hold for 20 s; remove for 15 s; replace at the marked position for another
   20 s; remove and finish with 15 s quiet. Allow extra time for handling and log
   its actual start/end. The 120 cm repeat is especially useful given existing
   unresolved far returns. Add 30 cm as an optional near-range stress test.
2. **Stationary target at startup:** start a separate 30-second capture with the
   target already at 80 or 120 cm and leave it untouched. This checks detection
   without relying on insertion or previous motion.
3. **Motion, stop and hold:** start with 10 s at 120 cm, roll toward 50 cm over
   about 2 s, hold for 15 s, retreat over about 2 s, and hold for 15 s. Repeat
   with a slower 4–6 s trip. Log actual motion and stop times. This tests motion
   response and return-to-zero behavior; it does not supply precise speed truth.
4. **Operator-only control:** with the target absent, record 15 s quiet, move
   along the same operator path used for placement/motion, then remain out of
   the beam for 15 s. Log the movement interval and operator position.
5. **Long hold:** record at least 150 s with one supported target left untouched
   to exercise clock fitting, stability and dropouts beyond two minutes.

Repeat the stationary placements and motion run in a second session without
changing thresholds. A cleaner scene and the current wall/clutter scene are
useful separate cases. For initial development, the first stationary run and
motion run are enough to identify major issues; retain later sessions for
independent evaluation after combined processing is frozen.

Use the 1D GUI to see and record the frozen baseline while collecting:

```sh
./range-v1 gui --detector cfar \
  --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL \
  --cfar-guard 1 --cfar-training 4 --cfar-min-training 4 --cfar-factor 2
```

Click **Start live + record**. Record the generated directory for each run.
Preserve the entire directory, including raw frames, wire log, arrival log,
config, metadata and readings; attach scene notes and video/event times.
Only one serial reader can run at a time. The same recording can later feed
both 1D and RD processing; separate simultaneous GUIs are unnecessary.

For later replay, copy the qualification manifest and add cases with explicit
`window_host_s: [start, end]` relative to the **first saved frame**, using
half-open windows. Include `nominal_target_m` only for measured stationary holds;
exclude handling intervals and document any start/video offset. Do not reuse
old scene timestamps for new captures.

Assess numeric coverage together with unresolved/missing episodes and placement
differences, then inspect which reflector supplied the measurement. Report
target-absent outputs separately from verified false target associations. Agree
on practical coverage, error and response-time limits before acceptance; no
threshold tuning is performed by this tool. Proving the firmware change itself
improves performance would require matched AVG1/AVG16 scene captures, which are
not necessary to develop both algorithms on the current AVG16 image.
