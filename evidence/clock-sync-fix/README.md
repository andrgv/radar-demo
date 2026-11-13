# Bounded startup clock mapping: validation

The live capture path now learns a relative clock rate during startup and freezes it. No scene baseline, threshold tuning, firmware change or edits to original recordings.

| Capture | Frames | Old timing rejections | New clock rejections | Final state | Maximum error after freeze |
|---|---:|---:|---:|---|---:|
| live-001 | 276 | 0 | 0 | frozen | 5.0 ms |
| live-002 | 423 | 0 | 0 | frozen | 25.8 ms |
| live-003 | 1469 | 741 | 0 | frozen | 43.8 ms |
| live-004 | 119 | 0 | 0 | collecting | not yet fitted |
| live-005 | 244 | 0 | 0 | frozen | 5.6 ms |
| live-006 | 490 | 0 | 0 | frozen | 52.8 ms |
| live-007 | 194 | 0 | 0 | collecting | not yet fitted |

## Live policy

- Fit an affine host-time/device-time mapping after at least 20 device seconds and 100 eligible samples. Short captures retain the original nominal-rate check.
- Only valid, continuous, single-frame, non-backlogged arrivals can train it. Require rate within ±2% of nominal, startup maximum residual ≤100 ms and 95th-percentile residual ≤50 ms.
- Freeze once fitted. No ongoing rate adaptation, reanchoring, persisted machine-specific constant or latency forgiveness. The progress-error threshold remains 0.5 s.
- An invalid mapping, a duplicate/restarted device timestamp, impossible rate, unstable fit, unavailable fit after 30 device seconds, backwards host time or excessive corrected progress error invalidates timing until a new capture is explicitly started.
- Existing frame continuity, ADC validation, serial-backlog rejection, one-second timeout and raw recording remain active. A rejected reading clears presence and both coarse/fine coordinates.
- Logs retain the raw elapsed difference plus corrected error, mapping state, rate and fit count. Metadata records policy. No old readings are rewritten.

## Tests and limitations

- Synthetic tests cover one-hour positive/negative 0.7% rate differences, a 0.6 s late delivery step, a growing delay after freeze, out-of-bound rate, unstable startup, timestamp wrap, restart/duplicate, backwards host time and ineligible fit samples.
- Real-stream integration tests exercise 1,500 recorded frames with skew, plus an injected delay that clears the fine readout while retaining raw bytes and closing serial. A queued burst remains rejected and does not train the fit. Existing timeout/corruption/continuity tests also run.
- Saved-capture replay uses frame wall-clock arrivals as a proxy for reader monotonic time; it cannot reconstruct every original read chunk. Actual queue flags are retained. This validates relative timing behavior, not restored historical live correctness or absolute sensor age.
- During startup, a sufficiently smooth latency ramp can be indistinguishable from clock skew within the allowed rate range. A constant initial backlog is also unobservable from relative timing. Absolute freshness still needs firmware identity/start acknowledgment and clock verification.
- A frozen estimate deliberately rejects later rate changes large enough to exceed the progress limit; it does not continually learn away stalls. New live hardware validation remains to be performed after restarting the app.

[Timing plot](clock-fix.png) · [Report/policy/source hashes](report.json) · [Per-frame gate decisions](timelines.jsonl)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.validate_clock_sync --root recordings/gui-20261109-224819-094246 --output evidence/new-clock-sync-validation
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests_min -v
```
