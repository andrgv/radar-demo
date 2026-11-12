# Replay association of range–Doppler candidates

`--associate` adds persistent radar feature IDs to full-map 2D CFAR replay.
The association layer uses no empty reference, background subtraction, range
blacklist or calibrated velocity model. It retains stationary features from
startup and can associate an isolated moving peak as it returns to zero Doppler.
These are feature hypotheses, not certified physical-object identities.

## Run

```sh
./range-v1 range-doppler \
  recordings/gui-20261110-221227-169414/live-001 \
  --detector cfar2d --associate
```

For an export, use a **new** directory; add `--show` to also open the slider:

```sh
./range-v1 range-doppler recordings/avg16-motion-01 \
  --detector cfar2d --associate --output evidence/my-association-review --show
```

The `range-doppler` command is replay-only and requires `--detector cfar2d` for
association. The new [live `rd-gui` mode](LIVE_RANGE_DOPPLER.md) runs the same
algorithms during raw capture; the original `gui` remains the 1D display.
Keep the current AVG16 image and matching capture config; no firmware flash is
needed.

## States and measurements

| State | Current confirmed measurement | Meaning |
|---|---|---|
| `tentative` | No | Current local peak exists but has not passed confirmation |
| `measured` | Yes | Unique current accepted local maximum, confirmed feature |
| `ambiguous` | No | Competing association or current accepted cells without an isolated peak |
| `missed` | No | No current support within the association gates |
| `lost` | No | Hypothesis expired, confirmation failed, or continuity/validity reset it |

Only `measured` has `measurement_valid=true` and a non-null `measurement`.
Every such point is a current-frame accepted CFAR local maximum. It contains
native range/Doppler bins, cycles per saved block, power, threshold, margin and
current cluster ID. No point is extrapolated, smoothed or held across a miss.
No calibrated meter or m/s estimate is added.

`current_peak` retains a raw observation for tentative/measured features and
some failed-confirmation events; it is distinct from a confirmed measurement.
An ambiguous feature exports actual `current_support_cells`, not its previous
position as a new observation. `last_peak_sequence` and `frames_since_peak`
identify history explicitly. Lost features appear once in `ended_tracks`.

`doppler_evidence` describes the current measured FFT bin as `zero_doppler`
or `nonzero_doppler`; it does not classify world motion. Static obstacles and
walls may both have nonzero Doppler on a moving robot. History of a nonzero
peak is exported but does not establish target identity.

## Association and quality rules

An optional [sub-bin cost experiment](SUBBIN_ASSOCIATION.md) is available with
`--track-range-metric quadratic`; the default remains `native`. It refines only
assignment cost and leaves native gates and measurement validity unchanged.

Accepted local maxima are the observation pool, including multiple maxima in
one connected CFAR component. Tracks and observations are gated in native
range and Doppler bins. Doppler distance follows the CFAR wrap/truncate policy;
range never wraps. Inside the gate, cost is normalized range displacement plus
normalized Doppler displacement. No prediction is used.

A match requires a reciprocal unique best observation/track pair, with the
configured cost separation from the second choice. Competing matches are
withheld rather than resolved by an arbitrary greedy assignment. This rule is
conservative and can leave a feasible multi-feature assignment unresolved.

New tracks require extra headroom above the CFAR threshold and consecutive
quality peaks. Weak/transient observations remain in the exported observation
pool with rejection reasons. A confirmed feature may continue on any accepted
unique peak, including one with less birth headroom. Distinct peaks can seed
beside a successfully measured track; unresolved track gates block duplicate
hypotheses.

Accepted-cell support alone cannot seed, confirm or move a track's anchor. A
confirmed feature may remain ambiguous briefly when a ridge merges or peaks
compete. Support does not renew its age since the last isolated peak, so a
stationary ridge cannot keep an unsupported identity alive indefinitely.
An initially unresolved shoulder cannot become an independently measured
object through association alone.

## Initial settings

| CLI option | Default | Meaning |
|---|---:|---|
| `--track-confirmation` | 3 | Consecutive quality peaks to confirm |
| `--track-birth-margin` | 3 | dB above CFAR threshold to seed/confirm |
| `--track-range-gate` | 1 | Maximum native range-bin displacement per update |
| `--track-doppler-gate` | 2 | Maximum native Doppler-bin displacement per update |
| `--track-max-missed` | 2 | Maximum frames since a peak when current support is absent |
| `--track-max-ambiguous` | 5 | Maximum frames since a peak when current support/competition exists |
| `--track-ambiguity-gap` | 0.25 | Required strict normalized cost separation from second choice |

These empirical defaults were selected before replaying the recordings with
association and kept identical across both runs. They are not a calibrated
false-alarm operating point. Tentative tracks lose confirmation immediately
when quality or uniqueness is interrupted. Confirmed tracks retain their ID
through short gaps but publish no measurement in those frames. The age limits
are measured from the last unique peak, not separate clocks that reset when
switching between missed and ambiguous states.

Device sequence/timestamp discontinuities, counter changes and invalid input
frames clear all hypotheses. IDs increase monotonically within a replay and
are not recycled after a reset. Association does not certify original host
freshness or live serial latency.

## Exports and viewer

`tracks.jsonl` contains one report per frame: validity/reason, active `tracks`,
`ended_tracks`, and the observation pool with association/birth dispositions.
Track confirmation, age, support, history and current measurement are explicit.
All existing CFAR files remain available, including rejected low-quality
observations as original accepted CFAR peaks. `metadata.json` records settings,
source hashes and measurement/identity limits. `diagnostics.jsonl` adds
association time and measured/ambiguous track counts.

The replay viewer marks measured features with cyan circles and IDs. Orange
diamonds show current ambiguous accepted-cell support. Missed/lost positions
are not plotted; tentative peaks remain visible in the raw CFAR layer. The
header counts each state separately, and invalid frames clear overlays.

## Evidence and remaining work

The [fixed-settings review](../evidence/rd-association-20261110/README.md)
compares both AVG16 motion recordings against their unchanged CFAR outputs.
It checks that every published measurement is a confirmed current local maximum
and that ambiguous/missed/lost features publish no point. It includes persistent
clutter tracks, ID fragmentation and lost slow-motion coverage.

Association suppresses short weak candidates but does not establish which
feature belongs to the intended target. Persistent clutter can confirm, nearby
features can swap physical identity without a uniquely observable crossing,
and weak/merged stationary targets can remain unresolved. The next acceptance
work needs independent scene/operator controls and an agreed output policy for
ambiguous support. No previous distance should be promoted to a fresh obstacle
measurement during such ambiguity.
