# Replay range–Doppler CA-CFAR

The optional `cfar2d` mode tests the full linear-power range–Doppler map and
exports accepted cells, candidate groups and local maxima. Zero Doppler is
included. It uses no empty reference, background subtraction or central-bin
notch. The default mode does not associate candidates with objects, track them,
interpolate distance or output calibrated velocity. Optional
[feature association](RANGE_DOPPLER_ASSOCIATION.md) with `--associate` adds
confirmation, persistent feature IDs, current-cell ambiguity and loss states;
physical-object identity remains unverified.
The [live range–Doppler GUI](LIVE_RANGE_DOPPLER.md) now runs this full-map
processing and association during raw capture with the current AVG16 firmware.

## Run

Inspect the AVG16 motion recording with an interactive frame slider:

```sh
./range-v1 range-doppler recordings/avg16-motion-01 --detector cfar2d
```

Export maps and candidates to a **new** directory, optionally showing the slider:

```sh
./range-v1 range-doppler recordings/avg16-motion-01 \
  --detector cfar2d --output evidence/my-rd-cfar-review --show
```

For a file-only run, omit `--show` and set `MPLBACKEND=Agg` if needed.
The existing `range-doppler` command without `--detector cfar2d` retains the
full/mean-removed diagnostic. CFAR always uses the full map. The mean-removed
map is still exported as a diagnostic and is not its input.

## Settings and edge policies

| CLI option | Default | Meaning |
|---|---:|---|
| `--rd-guard-range` | 1 | Range guard cells per side |
| `--rd-guard-doppler` | 1 | Doppler guard cells per side |
| `--rd-training-range` | 3 | Range training width beyond the guards, per side |
| `--rd-training-doppler` | 2 | Doppler training width beyond the guards, per side |
| `--rd-min-training` | 16 | Minimum references required to test a cell |
| `--rd-factor` | 4 | Empirical multiplier on mean reference power |
| `--rd-doppler-edge` | `wrap` | `wrap` or `truncate` at the Doppler boundary |

Defaults form a 7 × 9 outer rectangle in Doppler × range, with the inner 3 × 3
guard/CUT rectangle excluded. There are 54 references in the interior and 29
at the first/last usable range bin under Doppler wrapping. The threshold is
`factor × mean(reference powers)`, with a numerical noise floor of `1e-12`.
A cell is accepted only when its power is strictly greater than the threshold.
The factor is not a calibrated probability of false alarm: Hann windowing and
RX integration correlate neighboring cells.

Range DC and Nyquist are excluded from tests and training. Every other range
bin is tested, including ranges outside the old 1D detector's bins 1–4. Range
windows are truncated and never wrap; references are not replaced with more
distant cells. Tests with too few references have NaN noise/threshold values.

Doppler wrapping follows the periodic FFT axis, including the Nyquist seam.
Window geometry that would reuse a Doppler row is rejected. `truncate` clips
Doppler training windows and clustering at that boundary instead. Zero Doppler
is tested under either policy.

## Candidate groups and viewer

Eight-connected accepted cells form a candidate group using the configured
Doppler edge policy. Each group exports all cells, its strongest accepted cell,
and all local power maxima. Equal neighboring maxima on a plateau have one
deterministic representative. Frequencies are cycles per saved block. Native
range bins are exported without fine-distance calibration.

A connected group can bridge stationary and moving returns, so one group is
not necessarily one object. `touches_zero_doppler`, `crosses_doppler_seam`, and
the group's multiple local maxima make those cases visible. A component's
strongest accepted cell is retained even if training contamination prevents
the true neighboring local maximum from passing its own threshold.

The viewer shows full power on the left, with accepted cells outlined and
local maxima marked ×. The right shows power relative to each cell's empirical
threshold; values above 0 dB pass. The slider changes frames and clears overlays
on invalid frames. No candidate is held across a missing or invalid frame.

## Exports

- `maps.npz`: full and diagnostic mean-removed linear powers, native frequency
  and nominal range axes, and frame validity. `cycles_per_saved_block` is the
  frequency axis; the old `cycles_per_chirp` key is a compatibility alias.
- `cfar.npz`: per-frame `noise_power`, `threshold_power`, `accepted`, and `valid`;
  fixed geometry arrays `reference_count` and `testable`. Invalid frames have
  NaN thresholds/noise and no accepted cells.
- `candidates.jsonl`: sequence, device timestamp, validity/reason and groups for
  every frame. Peak dictionaries include range/Doppler bins, frequency, power,
  noise, threshold and dB margin. Invalid frames have an empty group list.
- `diagnostics.jsonl`: existing map diagnostics plus CFAR time, accepted-cell
  count and group count.
- `metadata.json`: input/config/source hashes, settings, edge policy,
  normalization and verification limits.
- `preview.png`: first frame with threshold/candidate overlays.

The [first development replay](../evidence/rd-cfar2d-20261110/README.md) includes
the full 605-frame AVG16 motion run, time-labeled candidate summaries and
comparisons against the existing 1D and original local-median pipelines.
The [frozen follow-up](../evidence/rd-cfar2d-followup-20261110/README.md) adds
target-absent controls and faster/slower 120↔30 cm motion with the same source
and settings. It confirms signed motion response while exposing inconsistent
far stationary candidates, merged ridges and operator-confounded outputs.
These data are development evidence. Independent scenes and operator-only
controls are required before claiming detection or false-output accuracy.
