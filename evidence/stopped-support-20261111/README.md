# Cardboard-box capture and stopped-return handoff correction

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

New recording: `recordings/rd-gui-20261111-143819-360020/live-003`.
User clarification: cardboard box with approximately 45 × 24 cm front face;
wall a little over 2 m away; distance measured from antenna front face to box
front surface with uncertainty of a few centimetres. This was not a rigid
metal/foil reflector capture. The farther persistent return is consistent with
the described wall range, but its physical source was not independently tagged.

## Recorded live behavior before the correction

Durations are consecutive from the first saved frame. The first 50 cm hold is
29.36–51.60 s, second 77.41–99.04 s, and 120 cm hold 126.57–148.26 s. Handling
is excluded. Primary summaries trim two further seconds per quiet interval;
one-second labels are also preserved. The final remaining interval after
153.59 s is empty, as supplied. No video offset was fitted.

| Quiet interval | Frames | Recorded baseline outputs | Recorded motion outputs | Recorded motion median |
|---|---:|---:|---:|---:|
| Initial empty | 119 | 0 | 0 | — |
| First 50 cm | 184 | 184 | 184 | 58.75 cm |
| Empty after first removal | 82 | 0 | **82** | **30.82 cm** |
| Second 50 cm | 177 | 126 | 119 | 52.60 cm |
| Empty after second removal | 82 | 0 | **82** | **30.11 cm** |
| 120 cm | 178 | 0 | 0 | — |
| Final empty | 148 | 0 | 0 | — |

The selected feature ID 13 survives both removals and follows the close
stationary return. These are current measured RD peaks, not stale values;
nevertheless, presenting them as the tracked box's distance is incorrect.
This is a concrete failure of same-ID zero-Doppler continuation, not a successful
distance test. The baseline remains blank throughout every empty interior.

## Timing passes

All 1,735 saved frames are accepted over 172.301 host seconds, with no timing
rejections, CRC errors or sequence gaps. The clock collects for 200 frames and
freezes for the remaining 1,535. Startup fit p95/max errors are 3.22/34.69 ms;
post-freeze p95/max relative errors are 23.28/81.99 ms, within the unchanged
freshness policy. A 7,487-byte incomplete tail at stop is recorded separately.

## Implemented v2 stopped-output rule

Motion initiation and nonzero-Doppler measurements are unchanged. Before a
zero-Doppler RD measurement supplies the motion-aware readout, its native range
bin must also pass the **current** CA reference threshold and local-maximum
test. This checks the full usable profile, including outside the scalar mask.
No held baseline or new distance blacklist is involved. Failure yields
`unverified_stationary` / `stopped_rd_without_current_range_support`, with the
RD value retained as `inspection_range_m` and in the candidate diagnostics.
The same episode may resume if current evidence supports it again.

Replaying this capture removes all 164 unsupported numeric outputs in the two
post-removal interiors. All 431 scored empty frames are blank. First 50 cm
coverage remains 184/184; second changes from 119/177 to 110/177. The 120 cm
hold remains undetected. This corrects readout eligibility, not the underlying
scene feature or range bias.

The audit covers 4,041 frames across this capture, live-006, the live-005 empty
control and the previous live motion run. It reconstructs each saved policy
using its recorded version (or legacy v1 settings), verifies all saved baseline
outputs and current RD masks/association independently, then reports the v2
policy separately. No detector or association setting changed for this rule.

There is a coverage cost: in earlier live-006, the first near hold changes from
97/97 to 42/97 and the middle far hold from 105/105 to 24/105. Qualified weak
RD-only stopped returns are now inspection results, not automatic readout
points. Confirmed nonzero-Doppler measurements remain available; motion windows
can lose zero-Doppler transition points. This is a deliberate correctness versus
coverage tradeoff and not proof of general object recognition. 161 tests pass.

## Spectral diagnosis and useful next capture

Raw averaged-RX peaks for the two near holds are approximately 57.6 and 52.1 cm.
The first hold's individual RX peaks are 52.7/70.6/54.9 cm; the second's are
73.3/45.1/51.1 cm in the declared 0.15–1.7 m diagnostic band. The bias and
channel differences exist before display selection. The 120 cm interval has
no zero-Doppler accepted cells in endpoint bins 3–4; its near-band maximum is
at the search boundary, which is not an isolated 120 cm target estimate.

To distinguish the box response from a cleaner front-surface reflection, keep
the same box/geometry but cover its front face smoothly with foil and repeat
empty → 50 cm → empty → same 50 cm → empty → 120 cm → empty, with about 20 s
untouched holds. Keep firmware, CFAR settings, orientation, sensor/support and
operator B position fixed. Log actual handling times. This changes reflector
surface while retaining geometry; it is diagnostic data, not an offset fit.
No additional moving sweep is needed for the handoff failure.

[Recorded versus corrected timelines](motion-comparison.png) ·
[Window metrics and timing](motion-review.json) ·
[Independent parity audit](report.json) · [Raw hold spectra summary](hold-spectra.json)

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --recordings recordings/rd-gui-20261111-143819-360020/live-003 \
  recordings/gui-20261111-093723-246315/live-006 \
  recordings/gui-20261111-093723-246315/live-005 \
  recordings/rd-gui-20261111-141606-847532/live-002 \
  --output evidence/NEW-STOPPED-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_motion_range \
  --output evidence/NEW-STOPPED-REVIEW --hold-spectra \
  --manifest configs/reflector-live-20261111.json configs/avg16-motion-20261111.json \
  configs/avg16-operator-empty-abab-20261111.json configs/motion-aware-live-20261111.json
```
