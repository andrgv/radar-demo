# Background-aware close-range detection

Use a matching empty recording to enable the background-aware detector:

```sh
python -m radar gui --replay recordings/close_near_1 --background recordings/close_empty_before
python -m radar gui --port YOUR_PORT --config configs/range-source-derived.json --background recordings/close_empty_before
```

For live operation, recapture the reference if the sensor, support or room changes.
The plotted profile remains the complex-subtracted spectrum. Detection additionally
requires raw power greater than four times the maximum baseline frame power in
at least two receivers at that bin. This rejects phase-only residuals and reduced
background returns. The factor is a conservative heuristic, not a false-alarm
probability. Weak targets overlapping strong clutter may be missed.

Bin 1 is accepted only with a measured background power envelope and a local
maximum. Its distance is the nominal bin center without fractional interpolation;
the readout identifies limited precision. Grid spacing is not an accuracy bound.
Other bins retain existing local-contrast and peak checks. No background means
the original detector remains active. This does not implement object tracking.

Snapshots now save the baseline envelope along with the complex reference. Old
snapshots still load and use reference power for the additional gate, but cannot
enable bin 1; refit from an empty recording to obtain variability measurements.

The five supplied close captures yielded 101/101 near detections in each repeat,
98/99 far detections, and 0/101 detections in independent empty-after data.
Empty-before was used to fit the reference and is not independent validation.
No threshold search was performed on these captures, but these are development
results, not general reliability estimates. Validate with fresh empty and target
captures. Run `PYTHONPATH=. python tools/compare_close_captures.py` to reproduce
the comparison report and plot in `artifacts/close-comparison`.
