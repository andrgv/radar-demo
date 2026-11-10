# Fresh CFAR session: coarse ranging and unstable bin selection

Source: `recordings/gui-20261109-215257-942086/live-001` and `live-002`.
Both recordings used guard 1, training 4, minimum total 4, factor 2, with no
empty baseline. The user reports moving an object during live-001, and an empty
scene → object near 50 cm → brief empty scene sequence during live-002. Exact
transition times were not supplied, so no scene-specific detection or false-alarm
rates are assigned here. These recordings are new evaluation evidence, not added
to the previous parameter tuning set.

| Recording | Frames | Duration from first to last frame | Accepted outputs | Accepted bins |
|---|---:|---:|---:|---|
| live-001 | 726 | 72.5 s | 408 | 1: 83, 2: 262, 3: 57, 4: 6 |
| live-002 | 290 | 29.0 s | 186 | 1: 54, 2: 132 |

The output coordinates are exactly bin × 0.34758545855 m: approximately 34.8,
69.5, 104.3 and 139.0 cm. There is no fine distance estimator or smoothing in
CFAR mode. The previous baseline mode subtracts an empty waveform and runs a
continuous-frequency tone fit. The CFAR implementation deliberately bypasses that
fit because it requires an empty reference. It therefore gives coarser estimates
than the previous UI, even when the correct physical reflector is detected.

In live-002 there were 47 changes between different non-null candidate bins
across consecutive recorded frames. Many bin changes clear persistence and leave
gaps. Acceptance at bin 1 or 2 does not establish that either reflection is the
50 cm target. The threshold plot shows power crossing the thresholds in both
neighboring bins. Their strongest local peak and group membership can change as
the received spectrum changes. The recording alone does not isolate whether the
change comes from motion, placement, clutter, multipath or another mechanism.

Live-001 has no reported CRC errors, gaps or rejected acquisition frames.
Live-002 has one reported CRC error and one sequence gap, with one rejected frame.
This accounts for a continuity reset but does not explain the repeated 35/70 cm
switching. The original serial bytes are preserved in each recording.

The previous sweep optimized target expected-bin coverage and empty-scene output
rates. At this waveform's nominal scale all 30/40/50 cm labels round to bin 1.
That objective cannot demonstrate continuous range accuracy or distinguish those
placements. Improved sweep coverage must not be described as improved physical
ranging accuracy.

Next work should evaluate a fine, baseline-free range estimator separately from
CFAR gating, include physical distance error and missing-output coverage, and test
selection stability and empty-scene rejection on fresh labeled intervals. Merely
averaging the 35/70 cm readouts could produce an apparently plausible middle value
without identifying the target. Fine estimation also cannot restore missing
physical resolution or automatically remove interfering static reflections.

- [Range and threshold plot](range-and-thresholds.png)
- [Counts, raw hashes and transport details](report.json)

## Approximate timing follow-up

The user estimates placement around 5 seconds and removal a couple seconds before
the end (roughly 27 seconds). These are approximate boundaries, not exact labels.
The user clarified that **70 cm was the UI readout during the empty scene**,
with no actual object there and the closest actual object at least 140 cm away.
The original approximately 50 cm target placement remains unchanged. No exact
scene-specific physical-error score is assigned because transition times are approximate.

| Window | Frames | Accepted at bin 1 (~35 cm) | Accepted at bin 2 (~70 cm) | No output |
|---|---:|---:|---:|---:|
| Initial 0–3 s | 29 | 0 | 24 | 5 |
| Initial 0–5 s | 49 | 0 | 39 | 10 |
| Central 8–24 s | 160 | 51 | 32 | 77 |
| Ending from 27 s | 21 | 0 | 21 | 0 |

The windows suggest a persistent ~70 cm return exists without the intended
object, and changes in the middle alter peak selection. This is evidence of
unwanted scene returns under the approximate labels, not proof of which physical
surface produced each return. The new session does not establish target identity.

## Confirmed empty-scene mismatch

The ~70 cm empty-scene readout has no matching physical object according to the
user. It is an unwanted detection and a misleading range output, rather than
just coarse rounding of a known 70 cm target. Its cause is not established by
this recording: leakage, spectral artifacts, multipath and scene reflections
remain hypotheses requiring raw-spectrum analysis. It must not be asserted to
be the 140 cm object, an alias, or a particular multipath path without evidence.
A fine fit or display smoothing alone cannot establish target identity or remove
this failure. Preserve this session as evaluation evidence when changing the gate
or estimator.
