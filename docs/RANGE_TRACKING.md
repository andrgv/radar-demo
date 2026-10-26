# Range tracking and detection diagnostics

Tracking is enabled by default, including for older JSON configurations. Use the
same live/replay commands and `--background` argument as before. `Processor` keeps
the original strong detections in `result.detections` and adds `result.tracks`
and `result.detection_diagnostics`.

## Track lifecycle

A strong detection starts a tentative track. Three strong hits within five
processed frames confirm it. Tentative tracks are hidden from the object display
and expire if they fail confirmation. Confirmed tracks can use weaker local peaks
within 3 dB of the original local power thresholds. These supporting measurements
cannot create or confirm tracks. Background support, local peaks, close-range
rules and the static-versus-moving power comparison still apply.

Association uses nearest range, one measurement per track per frame. Static and
moving detections within half a bin are merged when creating a track. Matching
tolerance is one range bin plus 0.5 m/s times time since the last measurement.
Range estimates use an exponential average with alpha 0.5. There is no velocity
prediction or angle smoothing. Objects at similar ranges or crossing in range
can be confused; IDs do not establish physical object identity.

After a miss, a confirmed track coasts at its last estimated range for up to
0.4 seconds using device timestamps. Confidence declines linearly during that
interval. It is a lifecycle score, not a calibrated probability. Supporting
measurements refresh the track, so persistent weak clutter can keep it alive.
Measure false-track duration when tuning hysteresis.

Sequence gaps and backwards timestamps reset tracks; normal 32-bit timestamp
wrap is supported. IDs increase within the processor's lifetime. Every accepted
frame is processed independently of GUI display skips.

## Display

The original per-frame detection readout remains. Confirmed tracks have green
range-profile lines and stable IDs. Solid lines and circles indicate current
measurements; dashed lines and fading crosses indicate retained estimates.
The track readout distinguishes strong, supporting and missing measurements and
reports time since measurement. A fresh measurement with invalid direction clears
the old direction while preserving range. While coasting, any displayed direction
comes from the last measurement and is labeled retained. Bin-1 tracks remain
labeled as unresolved close-range candidates. Calibration qualifications apply.

## Configuration

Add fields to your usual config JSON to override these defaults:

| Field | Default | Meaning |
| --- | --- | --- |
| `tracking_enabled` | `true` | Set false for the original per-frame 3D view |
| `track_confirm_hits` | `3` | Strong hits required for confirmation |
| `track_confirm_window` | `5` | Rolling confirmation window in frames |
| `track_hold_s` | `0.4` | Maximum time since a strong/supporting measurement |
| `track_match_bins` | `1.0` | Base matching tolerance in range bins |
| `track_max_speed_mps` | `0.5` | Additional matching tolerance per second |
| `track_smoothing` | `0.5` | Range averaging alpha; 1 disables averaging |
| `track_hysteresis_db` | `3.0` | Local threshold relaxation for confirmed tracks |

At 100 ms frame intervals, three uninterrupted hits confirm a track 200 ms after
its first observation. Hold time trades dropout tolerance for removal delay.

## Diagnostics and replay

Each usable range bin has residual power, background support and its margin,
local and coherent-power margins, moving power margin, local-peak status,
separate static/moving acceptance and rejection reasons, angle validity, and
whether only weaker support is available. Positive margins mean above threshold.
The background margin is the second strongest receiver's margin against four
times its maximum baseline power. Legacy backgrounds still reject bin 1 even
with a positive margin: inspect `background_supported` too. Bin 1 does not use
the local power threshold; that margin is informational there. Angle validity is
reported for evaluated candidates; `null` means no direction was evaluated.
An invalid angle does not reject range detection.

The GUI summarizes static checks near a coasting track, or at the strongest
residual bin when no track coasts. Static rejection alone does not imply that
the moving branch failed; inspect the separate moving diagnostics in the JSON.

New recordings include `tracking.jsonl`, one strict JSON record per processed
frame with sequence, timestamp, tracks and diagnostics. `measurement_kind` is
`strong`, `supporting`, or `none`. Raw ADC and feature files retain their formats.
Reprocess old recordings with:

```sh
python -m radar analyze recordings/SESSION --diagnostics-output /tmp/radar-diagnostics.jsonl
```

The output must be a new file. Analysis automatically loads a recording's
`spectral-background.npz` when present. For a separate background, use GUI replay
with the existing `--background` option.

Compare held-out empty scenes and stationary/moving object sessions. Measure raw
detection coverage, track coverage, longest dropout, appearance/removal delay,
range jitter and false tracks per minute. Synthetic tests verify lifecycle and
gate behavior; actual sensitivity and false alarms require hardware recordings.
Tracking improves continuity while preserving the strong detector thresholds
and fixed background statistics.
