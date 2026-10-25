# Empirical plate range check

User-surveyed plate recordings at 0.6 m, 1.3 m and 2.0 m were analyzed without changing their raw files. The first two sessions fit an affine range correction. The third session was excluded from fitting and used as a check.

| Surveyed distance | Frames | Dominant FFT bin | Mean-spectrum interpolated bin | Corrected estimate |
|---|---:|---:|---:|---:|
| 0.6 m | 100 | 2 | 1.7055 | 0.600 m (fit) |
| 1.3 m | 101 | 4 | 3.7218 | 1.300 m (fit) |
| 2.0 m | 101 | 6 | 5.8044 | 2.023 m (held out) |

All RX channels track the dominant bin. The 2 m main return is detected in 101/101 frames, with no sequence gaps or device error/drop counter increases in that recording. The 0.6 m recording has one sequence gap. Saved recordings contain validated frames; their clean CRCs cannot prove no corrupt bytes were discarded at acquisition.

The held-out error is +0.023 m for the interpolated **mean spectrum** in this session. This is one measured scene/reflector, not a general accuracy guarantee. Survey error, orientation, temperature, other targets and larger/smaller distances have not been characterized.

`configs/range-plate-pilot.json` uses `range_scale=4.4469550451027695` and `range_offset_m=0.007889536386001317`, retaining the original illustrative RF/timing parameters and `verified=false`. It makes an empirical correction without pretending to have established sample rate or chirp slope. Original configs and recordings are unchanged. No firmware change or reflash is required.

The processor now estimates each detected peak's fractional bin with a bounded three-point log-power parabola before converting to range. This reduces integer-bin stepping; it does not increase physical resolving power or distinguish unresolved objects. Angle and Doppler estimates remain unverified. Values outside the checked 0.6–2 m interval are extrapolations; the larger numerical endpoint in the heatmap is not a verified hardware range limit.

Close the existing viewer and launch:

```powershell
python -m radar gui --port COM3 --config configs/range-plate-pilot.json
```

To inspect the existing held-out session with the same correction:

```powershell
python -m radar gui --replay recordings/plate_2m --config configs/range-plate-pilot.json
```

The viewer continues to mark these estimates provisional. The full comparison and plot are in `artifacts/plate-comparison/report.json` and `spectra.png`. Reproduce using `$env:PYTHONPATH='.'; python tools/compare_plate_captures.py` from the project root. This tool uses only the first two sessions for the fit and reports the third prediction separately.
