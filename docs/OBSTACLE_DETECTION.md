# Calibrated obstacle presence

The obstacle prototype recognizes a clear-versus-blocked radar pattern in a fixed
scene. It does not classify material or estimate obstacle distance. It uses both
positive and negative range-power changes, so it can use a reflected return or a
repeatable change to the background when the glass door closes.

## Saved-data finding

The original one-bin, 3 dB-change rule falsely triggered on the last open recording
of door07. Combining repeatable bins and using clear/blocked templates separates
the final recording pairs of door03, door04 and door07 at the recording level.
At approximately one-second resolution, the final pairs produce:

| Setup | Open windows: clear / uncertain / obstacle | Closed windows: obstacle / uncertain / clear |
|---|---|---|
| door03, 44 inches | 30 / 0 / 0 | 30 / 0 / 0 |
| door04, 25 inches | 30 / 0 / 0 | 30 / 0 / 0 |
| door07, another door at 60 inches | 29 / 1 / 0 | 30 / 0 / 0 |

These are retrospective development results on recordings already inspected,
not independent validation or a 100% accuracy claim. Adjacent windows are
correlated. There are only two physical doors according to the user's labels.
The incomplete door05/door06 captures are excluded explicitly.

Leaving each pair out in turn reveals instability: when fitting door07 on pairs
1 and 3, only one bin passes the repeatability criterion. Calibration is refused
in that split. A successful final-pair result does not remove this limitation.
Cross-setup evaluation is exported separately; models are specific to a fixed
scene, not interchangeable between positions/doors. The code cannot reliably
infer whether the radar or background has changed from this template alone.

## Method

Fit using all pairs except the last, which is reserved from fitting. Each
recording contributes its median range-power profile; frames do not count as
independent calibration recordings. FFT processing matches the door experiment.

Keep bins whose change has the same sign and exceeds the threshold in every
training pair. Threshold = max(3 dB, twice the open-profile spread, six times
the largest within-open-recording MAD). Exclude DC and Nyquist and require at
least two qualifying bins. Adjacent selected bins are not independent evidence.

Let `b` be the median open profile and `d` the median closed-minus-open change,
zero outside selected bins. The similarity coordinate is
`score = dot(profile - b, d) / dot(d, d)`. Zero means near the clear reference;
one means near the obstacle example along this pattern. It is not a probability.
Scores <=0.25 report clear relative to calibration, >=0.75 report obstacle,
and intermediate scores report uncertain. Margins are fixed engineering choices,
not calibrated statistical confidence. RMS residual to the pattern is exported
as a diagnostic; it is not used as an out-of-scene rejection guarantee.

Replay/live decisions use median profiles of nonoverlapping approximately
one-second windows. Trailing incomplete windows are reported as discarded.
Gaps discard the current window; device restart invalidates the detector for
the remainder of the process. Invalid frames never produce a clear decision.
There is no learned material label, meter readout, smoothing that holds an old
detection, or automatic updating of the clear reference.

## Commands

From the glass-radar checkout, reproduce the study into a NEW directory:

```powershell
.\.venv\Scripts\python.exe -m tools.study_obstacles recordings artifacts\obstacle-study-02
```

The first run is saved at `artifacts/obstacle-study-01`: `study.json` includes
cross-setup results and leave-one-pair-out failures; `windows.csv` includes
every final-pair window; `scores.png` plots decisions; each setup has a model.
Raw recordings are never rewritten. Fitting refuses duplicate calibration raw
files; replay refuses any calibration file hash even if it was renamed/copied.

Fit a model and replay a recording (all output paths must be unused):

```powershell
.\.venv\Scripts\python.exe -m radar obstacle-fit recordings\door07 artifacts\door07-obstacle.json
.\.venv\Scripts\python.exe -m radar obstacle-replay recordings\door07\closed-03 --model artifacts\door07-obstacle.json --output artifacts\door07-closed-result.json
```

For live detection ONLY when the same radar pose, door, settings and background
as calibration are restored:

```powershell
.\.venv\Scripts\python.exe -m radar obstacle-live recordings\obstacle-live01 --port COM3 --model artifacts\door07-obstacle.json --seconds 60
```

The model supplies the matching config. Live prints JSON once per complete
window, saves raw frames and original serial transport, copies the model into
the recording, and writes `obstacle-decisions.jsonl`. It stops on transport
corruption, timeout or growing sensor/host timing mismatch. Ctrl-C preserves
raw data and reports uncertain. Live serial use has not been hardware-tested
in this implementation session. No firmware changes or flashing are involved.

For a changed setup, capture clear and blocked calibration again. A saved model
from today's setup should not be used later merely because the same door is
present. Without a valid reference, this prototype cannot establish a clear path.
New obstacles with different radar patterns can also be missed; this detects the
calibrated obstacle condition, not every possible object in the scene.
