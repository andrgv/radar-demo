# First replay 2D CFAR prototype

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Source: `recordings/avg16-motion-01`, all 605 saved frames valid. This is
development evidence using the existing video labels, including the corrected
23.27–24.64 s first retreat. No recording or firmware was changed.

[Candidate timeline](candidate-timeline.png) ·
[Threshold midpoint maps](threshold-midpoints.png) ·
[Numeric comparison](summary.json) · [Replay metadata](replay/metadata.json)

## Implemented behavior

`radar_min.cfar_2d.CaCfar2D` applies a rectangular training ring to the full
linear-power map, retaining zero Doppler. Default settings were chosen as an
empirical starting point and kept fixed for this first review: range/Doppler
guards 1/1, training widths 3/2, minimum 16 references, factor 4, Doppler wrap.
Range never wraps, and range DC/Nyquist are excluded. The 16 × 33 grid has
496 testable cells, with 29–54 unique references per cell. No empty capture,
background subtraction, mean removal or zero-Doppler notch is used by CFAR.

The prototype exports noise, threshold, reference counts, accepted cells,
eight-connected candidate groups and their local maxima. Multiple maxima are
kept inside a merged group. It supplies no target identity, held target,
tracking, calibrated velocity or fine-distance estimate. See
[algorithm and CLI documentation](../../docs/CFAR_2D.md).

## Video-labeled motion output

These windows trim 0.2 s per side, without fitting the video offset. The path
bins 2–4 are exploratory analysis probes inherited from the motion review;
they do not restrict CFAR, which tests every usable range bin.

| Phase | Frames | Nonzero accepted local maximum in bins 2–4 | Sign of those maxima | Group touching zero and also having a nonzero local maximum, any range |
|---|---:|---:|---|---:|
| Approach 1 | 11 | 6 | Negative | 4 |
| Retreat 1 | 10 | 10 | Positive | 10 |
| Approach 2 | 9 | 6 | Negative | 5 |
| Retreat 2 | 10 | 8 | Positive | 6 |

No opposite-sign local maxima occur in bins 2–4 in these windows. These are
candidate-output counts on development data, not target-detection rates.
The short windows and video offset uncertainty remain. Snapshot frames are
chosen at window midpoints rather than the strongest detector response, so
some snapshots still have their strongest local maximum at zero Doppler.

The mixed-group column demonstrates why a connected group cannot yet be
treated as one object: moving and stationary accepted cells frequently bridge.
The exported local maxima preserve the signed response inside those groups.

## Stationary output and unresolved cases

Every one of the 347 buffered stationary frames has accepted zero-Doppler local
maxima somewhere in the map. In the five holds, zero-Doppler maxima in bins 2–4
occur in 74/74, 65/65, 81/81, **9/53**, and 74/74 frames respectively. In the
remaining 44 frames of the second near hold, the nearby maximum is at bin 1.
The target's identity and repeatable distance remain unresolved; shifting the
ROI after observing this result would hide that limitation.

There are no nonzero accepted local maxima in bins 2–4 during the buffered
holds. Across **all** usable ranges, however, 86/347 hold frames have nonzero
local maxima, mostly in weak/far returns. The full-range timeline retains these
outputs. They require scene/control validation and candidate quality or
association work before motion/obstacle classification. Do not interpret a
nonzero candidate anywhere as a confirmed moving object, or these counts as a
calibrated false-alarm probability.

## Comparison with existing pipelines

The existing 1D CA-CFAR is replayed with the user's earlier settings: guard 1,
training 4, minimum 4, factor 2, current range bins 1–4 and confirmation logic.
The original `radar.processing.Processor` is invoked with matching acquisition
dimensions, no background, and its default 12 dB median threshold. Its moving
path removes the slow-time mean, notches zero Doppler ±1, then applies a median
range threshold to the maximum over Doppler. This is not the 2D ring test.
Angles, identity and calibrated velocity are not scored.

| Phase | Frames | New 2D nonzero local maximum in bins 2–4 | Existing 1D confirmed scalar output | Original median moving output in bins 2–4 |
|---|---:|---:|---:|---:|
| Approach 1 | 11 | 6 | 6 | 11 |
| Retreat 1 | 10 | 10 | 10 | 10 |
| Approach 2 | 9 | 6 | 5 | 9 |
| Retreat 2 | 10 | 8 | 10 | 10 |
| 120 cm A hold | 74 | 0 | 2 | 9 |
| 60 cm A hold | 65 | 0 | 65 | 3 |
| 120 cm B hold | 81 | 0 | 35 | 3 |
| 60 cm B hold | 53 | 0 | 53 | 1 |
| 120 cm C hold | 74 | 0 | 74 | 1 |

The columns describe different outputs and thresholds. They do not establish
equal false-output operating points, intended-target association or accuracy
superiority. The new path's useful addition is explicit cell-level thresholds,
signed local maxima and multiple candidates while preserving stationary data.

## Verification and next work

Focused tests cover exact training-ring means/counts, DC/Nyquist exclusion,
range clipping, minimum reference counts, strict thresholds, Doppler wrapping
and truncation, stationary/signed/near-zero synthetic returns through Hann
processing, merged maxima, plateaus, invalid inputs, export/replay and clearing
candidates on invalid frames. The existing 1D CFAR and range–Doppler tests also
pass. The 605-frame replay has a median CFAR computation time of about 0.22 ms
and a 95th percentile about 0.37 ms on this machine; this is not an end-to-end
live latency measurement.

The next engineering work is candidate quality and association, including
handling connected static/moving responses, stopped targets, ambiguity and
weak intermittent candidates. Keep these settings as the documented initial
operating point. Independent target/wall and operator-only controls should
follow a concrete frozen prototype; do not tune a range blacklist or distance
offset to this recording. No new sample or firmware flash is needed before
reviewing/implementing that candidate logic.

## Reproduce

The replay output directory must be new:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl-radar ./range-v1 range-doppler \
  recordings/avg16-motion-01 --detector cfar2d \
  --output evidence/rd-cfar2d-20261110/replay
MPLCONFIGDIR=/private/tmp/mpl-radar .venv/bin/python -m tools.review_cfar_2d
```

Use the interactive command without `--output` to inspect candidates without
overwriting the saved evidence. Settings and input/source hashes are exported
in metadata and the numeric summary.
