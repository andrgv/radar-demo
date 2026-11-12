# Data collection setup and evaluation catalog

As of November 11, 2026: **165 raw recordings**, plus 5 configuration-only parent directories. 25 captures have curated physical-setup notes below. Every saved configuration is indexed in the inventory; missing setup facts are explicitly unknown.

This is a setup/annotation index, not a detector acceptance report. User-reported placement, saved acquisition configuration, and analyst-selected scoring windows are kept separate. Do not infer target material or operator position in an earlier recording from a later one. “Empty” means the added target is absent; walls, people and other reflectors may remain.

## How to evaluate a capture

1. Use the exact full recording path; `live-001`/`live-002` alone are not unique. Load its saved `config.json`, raw `frames.grd`, `metadata.json`, and, when available, `arrivals.jsonl`, `readings.jsonl`, `capture-summary.json` and original `serial-wire.bin`.
2. Choose the scene manifest linked below. User durations start at the first saved frame unless explicitly noted. Use half-open intervals in host seconds, derived from `(host_unix_ns − first_host_unix_ns) / 1e9`; do not fit an offset to detector output. Exclude handling/ignored intervals and preserve unlabeled tails. Two-second trims are primary where provided; one-second trims are sensitivity checks, not additional independent data.
3. Read timing/transport and label caveats in the linked review. A valid packet or clock does not certify range accuracy. Do not pool overlapping windows, use the display as ground truth, or compare historical firmware profiles as an isolated firmware A/B test.
4. Keep detector/configuration settings frozen, score numeric coverage and empty outputs alongside conditional placement differences, and preserve misses/rejections. The phase fit requires an existing candidate; its empty silence can be inherited from that detector. Physical target identity and calibrated speed remain unverified.

The AVG16 working profile is `0x33515403` (64 samples, 17 saved blocks, discard first, 3 RX; vendor averaging 16). Earlier profiles differ. **A profile ID is not a firmware hash.** Firmware identity is often explicitly unknown in saved metadata; consult [timing/firmware provenance](AVG16_TIMING_TEST.md), [older timing images](MCU_EDGE_TIMING.md), and each capture’s metadata before replay.

## Detailed known collections

Tables distinguish original user hold intervals from scored interiors. Where a manifest only preserves a scored window, no original boundary is invented. Full manifests retain alternate trims and any approximate operator splits.

### `recordings/gui-20261111-093723-246315/live-001`

User-labeled empty / 50 / empty / 80 / empty / 120 / empty stepped placements. Target material, dimensions, operator position and wall geometry were not supplied for this run. Do not retroactively assume the later cardboard/foil setup. Consecutive stopwatch durations; transitions explicitly excluded.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261111-093723-246315/live-001/config.json) · [Metadata](../recordings/gui-20261111-093723-246315/live-001/metadata.json)

Capture summary: 1747 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-placements-20261111.json](../configs/avg16-placements-20261111.json).

User-supplied consecutive durations in seconds, starting at first saved frame. No fitted video offset. Half-open windows, 1s and 2s trims. Reflector identity unverified.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| initial empty (trim 2s) | 0.00–18.36 s | 2.00–16.36 s | — |
| 50 cm (trim 2s) | 22.74–44.20 s | 24.74–42.20 s | 50 cm |
| empty after 50 cm (trim 2s) | 49.39–65.08 s | 51.39–63.08 s | — |
| 80 cm (trim 2s) | 79.57–103.28 s | 81.57–101.28 s | 80 cm |
| empty after 80 cm (trim 2s) | 106.51–122.27 s | 108.51–120.27 s | — |
| 120 cm (trim 2s) | 128.86–150.97 s | 130.86–148.97 s | 120 cm |
| final empty (trim 2s) | 156.03–173.14 s | 158.03–171.14 s | — |

Sources / reviews: [evidence/avg16-placements-20261111/README.md](../evidence/avg16-placements-20261111/README.md) · [evidence/avg16-placements-20261111/REVIEW.md](../evidence/avg16-placements-20261111/REVIEW.md) · [evidence/clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md)

### `recordings/gui-20261111-093723-246315/live-003`

Repeated nominal 50 cm placements. Ignore 28.67–48.68 s as requested. Final 50 cm hold: first approximately half with operator beside sensor, potentially in range; second half in prior out-of-range position. Split time is approximate. Target material/dimensions unspecified. Operator concern is scene sensitivity, not proof of algorithmic overfitting.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261111-093723-246315/live-003/config.json) · [Metadata](../recordings/gui-20261111-093723-246315/live-003/metadata.json)

Capture summary: 2194 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-repeat50-20261111.json](../configs/avg16-repeat50-20261111.json).

Consecutive user durations from first saved frame. Ignore 28.67–48.68 s. Final-hold midpoint is an approximate operator-position split, not a measured transition; exclude 2 s around it. One- and two-second quiet-interior trims. No offset fitting.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| initial empty (trim 2s) | 0.00–15.73 s | 2.00–13.73 s | — |
| 50 cm A (trim 2s) | 48.68–79.44 s | 50.68–77.44 s | 50 cm |
| empty after A (trim 2s) | 82.30–97.63 s | 84.30–95.63 s | — |
| 50 cm B (trim 2s) | 107.86–133.45 s | 109.86–131.45 s | 50 cm |
| empty after B (trim 2s) | 147.91–158.67 s | 149.91–156.67 s | — |
| 50 cm C (trim 2s) | 166.98–192.21 s | 168.98–190.21 s | 50 cm |
| final empty (trim 2s) | 200.70–211.64 s | 202.70–209.64 s | — |

Sources / reviews: [evidence/avg16-repeat50-20261111/README.md](../evidence/avg16-repeat50-20261111/README.md) · [evidence/avg16-repeat50-20261111/REVIEW.md](../evidence/avg16-repeat50-20261111/REVIEW.md) · [evidence/clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/phase-residuals-20261111/README.md](../evidence/phase-residuals-20261111/README.md)

### `recordings/gui-20261111-093723-246315/live-004`

Target stationary at nominal 50 cm throughout. Operator A/B/A/B: A beside sensor, described as in range; B described as out of range. These are user position labels, not measured angular/range boundaries. Target material unspecified.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261111-093723-246315/live-004/config.json) · [Metadata](../recordings/gui-20261111-093723-246315/live-004/metadata.json)

Capture summary: 946 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-operator-abab-20261111.json](../configs/avg16-operator-abab-20261111.json).

User supplied consecutive durations from first saved frame. Target stationary throughout at nominal 50 cm. A beside sensor, described as in range; B described as out of range, not independently verified. Exclude transitions and trim 1 or 2 s per side. No fitted offset.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| A1 (trim 2s) | 0.00–17.01 s | 2.00–15.01 s | 50 cm |
| B1 (trim 2s) | 21.85–38.69 s | 23.85–36.69 s | 50 cm |
| A2 (trim 2s) | 45.85–62.36 s | 47.85–60.36 s | 50 cm |
| B2 (trim 2s) | 67.27–83.91 s | 69.27–81.91 s | 50 cm |

Sources / reviews: [docs/RX_DIAGNOSTICS.md](../docs/RX_DIAGNOSTICS.md) · [evidence/avg16-operator-abab-20261111/README.md](../evidence/avg16-operator-abab-20261111/README.md) · [evidence/avg16-operator-abab-20261111/REVIEW.md](../evidence/avg16-operator-abab-20261111/REVIEW.md) · [evidence/clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/phase-residuals-20261111/README.md](../evidence/phase-residuals-20261111/README.md) · [evidence/rx-diagnostics-20261111/README.md](../evidence/rx-diagnostics-20261111/README.md)

### `recordings/gui-20261111-093723-246315/live-005`

Matched no-added-target operator A/B/A/B control for live-004. Same position definitions; walls and other scene reflectors remain present.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261111-093723-246315/live-005/config.json) · [Metadata](../recordings/gui-20261111-093723-246315/live-005/metadata.json)

Capture summary: 867 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-operator-empty-abab-20261111.json](../configs/avg16-operator-empty-abab-20261111.json).

User supplied consecutive durations from first saved frame. No target. A beside sensor described as in range; B described as out of range, not independently verified. Exclude transitions, trim 1 or 2 s per side, no fitted offset.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| A1 (trim 2s) | 0.00–16.23 s | 2.00–14.23 s | — |
| B1 (trim 2s) | 20.77–37.48 s | 22.77–35.48 s | — |
| A2 (trim 2s) | 43.41–59.94 s | 45.41–57.94 s | — |
| B2 (trim 2s) | 63.78–79.94 s | 65.78–77.94 s | — |

Sources / reviews: [docs/CLUTTER_REFERENCE_EXPERIMENT.md](../docs/CLUTTER_REFERENCE_EXPERIMENT.md) · [evidence/avg16-operator-empty-abab-20261111/README.md](../evidence/avg16-operator-empty-abab-20261111/README.md) · [evidence/avg16-operator-empty-abab-20261111/REVIEW.md](../evidence/avg16-operator-empty-abab-20261111/REVIEW.md) · [evidence/clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/phase-residuals-20261111/README.md](../evidence/phase-residuals-20261111/README.md) · [evidence/stopped-support-20261111/README.md](../evidence/stopped-support-20261111/README.md)

### `recordings/gui-20261111-093723-246315/live-006`

Target manually rolled 120↔50 cm with operator at A throughout. Moves 11.46–about 13, 26.62–28.05, 42.57–45.15, 59.09–61.76 s. Initial hold reported through 11.27 s; 11.27–11.46 s excluded. Slower second cycle. Operator/hand returns can accompany target motion; material unspecified.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261111-093723-246315/live-006/config.json) · [Metadata](../recordings/gui-20261111-093723-246315/live-006/metadata.json)

Capture summary: 757 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-motion-20261111.json](../configs/avg16-motion-20261111.json).

Absolute supplied times from first saved frame, 1:01.76 = 61.76 s. First stop near 13 s is approximate. Exclude 11.27–11.46 s and all motion from hold metrics. Holds trim 1/2 s per side; motions trim 0.2 s. No fitted timing offset. Operator/arm/hand contributions are possible.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| 120 cm A (trim 2s) | 0.00–11.27 s | 2.00–9.27 s | 120 cm |
| 50 cm A (trim 2s) | 13.00–26.62 s | 15.00–24.62 s | 50 cm |
| 120 cm B (trim 2s) | 28.05–42.57 s | 30.05–40.57 s | 120 cm |
| 50 cm B (trim 2s) | 45.15–59.09 s | 47.15–57.09 s | 50 cm |
| 120 cm C (trim 2s) | 61.76–75.17 s | 63.76–73.17 s | 120 cm |
| faster approach | 11.46–13.00 s | 11.66–12.80 s | — |
| faster retreat | 26.62–28.05 s | 26.82–27.85 s | — |
| slower approach | 42.57–45.15 s | 42.77–44.95 s | — |
| slower retreat | 59.09–61.76 s | 59.29–61.56 s | — |

Sources / reviews: [docs/JOINT_RANGE_DOPPLER.md](../docs/JOINT_RANGE_DOPPLER.md) · [docs/MOTION_AWARE_RANGE.md](../docs/MOTION_AWARE_RANGE.md) · [evidence/avg16-motion-20261111/README.md](../evidence/avg16-motion-20261111/README.md) · [evidence/avg16-motion-20261111/REVIEW.md](../evidence/avg16-motion-20261111/REVIEW.md) · [evidence/clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/phase-residuals-20261111/README.md](../evidence/phase-residuals-20261111/README.md) · [evidence/stopped-support-20261111/README.md](../evidence/stopped-support-20261111/README.md)

### `recordings/rd-gui-20261111-132433-610820/live-001`

Joint-GUI exploratory trial; timing rejection stopped displayed measurements. No physical scene or distance ground truth supplied. Use for timing regression, not detection scoring.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-132433-610820/live-001/config.json) · [Metadata](../recordings/rd-gui-20261111-132433-610820/live-001/metadata.json)

Capture summary: 358 frames; 158 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Sources / reviews: [evidence/joint-gui-timing-20261111/README.md](../evidence/joint-gui-timing-20261111/README.md)

### `recordings/rd-gui-20261111-133435-428121/live-001`

Stationary scene described as an object at approximately 80 cm for about 60 seconds; recording is longer. Target type and operator position unspecified. Conservative offline scoring window 2–73 s was used; it is not a user-timed transition annotation.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-133435-428121/live-001/config.json) · [Metadata](../recordings/rd-gui-20261111-133435-428121/live-001/metadata.json)

Capture summary: 758 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Sources / reviews: [docs/CLUTTER_REFERENCE_EXPERIMENT.md](../docs/CLUTTER_REFERENCE_EXPERIMENT.md) · [docs/WEAK_CANDIDATE_EXPERIMENT.md](../docs/WEAK_CANDIDATE_EXPERIMENT.md) · [docs/WEAK_FEATURE_CONFIRMATION.md](../docs/WEAK_FEATURE_CONFIRMATION.md) · [docs/WEAK_MOTION_LINK.md](../docs/WEAK_MOTION_LINK.md) · [evidence/clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md) · [evidence/joint-stationary-80cm-20261111/README.md](../evidence/joint-stationary-80cm-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/phase-range-20261111/REVIEW.md](../evidence/phase-range-20261111/REVIEW.md) · [evidence/phase-residuals-20261111/README.md](../evidence/phase-residuals-20261111/README.md) · [evidence/weak-candidates-live-20261111/README.md](../evidence/weak-candidates-live-20261111/README.md) · [evidence/weak-features-live-20261111/README.md](../evidence/weak-features-live-20261111/README.md) · [evidence/weak-motion-live-20261111/README.md](../evidence/weak-motion-live-20261111/README.md)

### `recordings/rd-gui-20261111-135229-775366/live-001`

Paired empty / 80 cm / empty / 80 cm capture. Operator at B for each quiet hold, explicitly confirmed by user. Target material/dimensions not supplied for this capture. Durations end at 147.61 s; later tail unscored.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-135229-775366/live-001/config.json) · [Metadata](../recordings/rd-gui-20261111-135229-775366/live-001/metadata.json)

Capture summary: 1545 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/live-os-paired80-20261111.json](../configs/live-os-paired80-20261111.json).

User supplied consecutive durations from first saved frame. Operator B for quiet holds. Transitions excluded, 1s and 2s quiet-interior trims; no fitted offset. Labeled end 147.61s; later tail unscored.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| empty A (trim 2s) | 5.53–26.49 s | 7.53–24.49 s | — |
| 80 cm A (trim 2s) | 44.38–75.11 s | 46.38–73.11 s | 80 cm |
| empty B (trim 2s) | 84.05–104.64 s | 86.05–102.64 s | — |
| 80 cm B (trim 2s) | 116.80–147.61 s | 118.80–145.61 s | 80 cm |

Sources / reviews: [evidence/live-os-paired80-20261111/README.md](../evidence/live-os-paired80-20261111/README.md)

### `recordings/rd-gui-20261111-141606-847532/live-002`

Start at 120 cm; move to 50 cm 11.56–13.58 s, to 120 cm 25.06–27.02 s, to 50 cm 38.47–42.15 s, to 120 cm 53.30–56.61 s. Operator position, target construction and exact trajectory not supplied.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-141606-847532/live-002/config.json) · [Metadata](../recordings/rd-gui-20261111-141606-847532/live-002/metadata.json)

Capture summary: 682 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/motion-aware-live-20261111.json](../configs/motion-aware-live-20261111.json).

Absolute supplied times from first saved frame; holds trim 1/2 s and motion 0.2 s per side. No fitted timing offset. Operator position and precise ground-truth trajectory not supplied.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| 120 cm A (trim 2s) | 0.00–11.56 s | 2.00–9.56 s | 120 cm |
| 50 cm A (trim 2s) | 13.58–25.06 s | 15.58–23.06 s | 50 cm |
| 120 cm B (trim 2s) | 27.02–38.47 s | 29.02–36.47 s | 120 cm |
| 50 cm B (trim 2s) | 42.15–53.30 s | 44.15–51.30 s | 50 cm |
| 120 cm C (trim 2s) | 56.61–67.66 s | 58.61–65.66 s | 120 cm |
| approach 1 | 11.56–13.58 s | 11.76–13.38 s | — |
| retreat 1 | 25.06–27.02 s | 25.26–26.82 s | — |
| approach 2 | 38.47–42.15 s | 38.67–41.95 s | — |
| retreat 2 | 53.30–56.61 s | 53.50–56.41 s | — |

Sources / reviews: [docs/SUBBIN_ASSOCIATION.md](../docs/SUBBIN_ASSOCIATION.md) · [evidence/motion-aware-live-20261111/README.md](../evidence/motion-aware-live-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/stopped-support-20261111/README.md](../evidence/stopped-support-20261111/README.md)

### `recordings/rd-gui-20261111-143819-360020/live-003`

Large bare cardboard box; front face approximately 45×24 cm facing sensor. Distances antenna front face to box front surface, user estimates error no more than a few cm. Background wall a little over 2 m. Empty / 50 / empty / 50 / empty / 120 / remaining empty. Later user clarification (2026-11-11): operator at position A / within range during the 120 cm hold. Operator position in other holds is not separately confirmed. The ~32 cm feature is therefore operator-confounded; it is not established as a spurious obstacle or as the box return.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-143819-360020/live-003/config.json) · [Metadata](../recordings/rd-gui-20261111-143819-360020/live-003/metadata.json)

Capture summary: 1735 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/reflector-live-20261111.json](../configs/reflector-live-20261111.json).

Consecutive user durations from first saved frame; transitions excluded; final remaining interval labeled empty. No fitted offset.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| empty A (trim 2s) | 0.00–15.83 s | 2.00–13.83 s | — |
| 50 cm A (trim 2s) | 29.36–51.60 s | 31.36–49.60 s | 50 cm |
| empty B (trim 2s) | 57.79–69.94 s | 59.79–67.94 s | — |
| 50 cm B (trim 2s) | 77.41–99.04 s | 79.41–97.04 s | 50 cm |
| empty C (trim 2s) | 104.58–116.75 s | 106.58–114.75 s | — |
| 120 cm (trim 2s) | 126.57–148.26 s | 128.57–146.26 s | 120 cm |
| final empty (trim 2s) | 153.59–172.30 s | 155.59–170.30 s | — |

Sources / reviews: [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/phase-residuals-20261111/README.md](../evidence/phase-residuals-20261111/README.md) · [evidence/stopped-support-20261111/README.md](../evidence/stopped-support-20261111/README.md) · [evidence/weak-candidates-live-20261111/README.md](../evidence/weak-candidates-live-20261111/README.md) · [evidence/weak-features-live-20261111/README.md](../evidence/weak-features-live-20261111/README.md)

### `recordings/rd-gui-20261111-200448-409110/live-001`

Same cardboard box as prior run with front face covered in tin foil; nominal face 45×24 cm, front-face distance reference and wall geometry inherited from prior clarification. Empty / 50 / empty / 50 / empty / 120 / empty. Operator position not explicitly supplied. Tail beyond 185.14 s unlabeled.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-200448-409110/live-001/config.json) · [Metadata](../recordings/rd-gui-20261111-200448-409110/live-001/metadata.json)

Capture summary: 1937 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/foil-box-live-20261111.json](../configs/foil-box-live-20261111.json).

Consecutive user durations from first saved frame; transitions excluded; 1/2-second quiet trims, no fitted offset; final tail after 185.14 s unlabeled.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| empty A (trim 2s) | 0.00–15.54 s | 2.00–13.54 s | — |
| 50 cm A (trim 2s) | 32.95–54.11 s | 34.95–52.11 s | 50 cm |
| empty B (trim 2s) | 66.99–78.23 s | 68.99–76.23 s | — |
| 50 cm B (trim 2s) | 88.07–108.78 s | 90.07–106.78 s | 50 cm |
| empty C (trim 2s) | 116.49–127.38 s | 118.49–125.38 s | — |
| 120 cm (trim 2s) | 139.96–160.84 s | 141.96–158.84 s | 120 cm |
| final empty (trim 2s) | 169.58–185.14 s | 171.58–183.14 s | — |

Sources / reviews: [evidence/foil-box-live-20261111/README.md](../evidence/foil-box-live-20261111/README.md) · [evidence/phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [evidence/phase-range-20261111/REVIEW.md](../evidence/phase-range-20261111/REVIEW.md)

### `recordings/rd-gui-20261111-200448-409110/live-002`

Requested independent repeat: empty / 50 / empty / 50 / empty / 120 / empty. User confirmed same foil-covered 45×24 cm box, antenna-face distance reference, wall little over 2 m and operator B during every hold. User supplied all segment durations; total 230.62 s, later recording tail unlabeled.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-200448-409110/live-002/config.json) · [Metadata](../recordings/rd-gui-20261111-200448-409110/live-002/metadata.json)

Capture summary: 2366 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/foil-box-repeat-20261111.json](../configs/foil-box-repeat-20261111.json).

Consecutive user durations from first saved frame; transitions excluded, 1/2-second quiet trims, no fitted offset. Any recording tail beyond 230.62 s is unlabeled.

| Supplied segment | Original host interval | Duration |
|---|---:|---:|
| empty A | 0.00–15.69 s | 15.69 s |
| transition | 15.69–34.59 s | 18.90 s |
| 50 cm A | 34.59–60.33 s | 25.74 s |
| transition | 60.33–71.92 s | 11.59 s |
| empty B | 71.92–91.60 s | 19.68 s |
| transition | 91.60–110.33 s | 18.73 s |
| 50 cm B | 110.33–135.91 s | 25.58 s |
| transition | 135.91–148.99 s | 13.08 s |
| empty C | 148.99–165.47 s | 16.48 s |
| transition | 165.47–178.11 s | 12.64 s |
| 120 cm | 178.11–204.04 s | 25.93 s |
| transition | 204.04–214.83 s | 10.79 s |
| final empty | 214.83–230.62 s | 15.79 s |

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| empty A (trim 2s) | 0.00–15.69 s | 2.00–13.69 s | — |
| 50 cm A (trim 2s) | 34.59–60.33 s | 36.59–58.33 s | 50 cm |
| empty B (trim 2s) | 71.92–91.60 s | 73.92–89.60 s | — |
| 50 cm B (trim 2s) | 110.33–135.91 s | 112.33–133.91 s | 50 cm |
| empty C (trim 2s) | 148.99–165.47 s | 150.99–163.47 s | — |
| 120 cm (trim 2s) | 178.11–204.04 s | 180.11–202.04 s | 120 cm |
| final empty (trim 2s) | 214.83–230.62 s | 216.83–228.62 s | — |

Sources / reviews: [evidence/foil-box-repeat-20261111/README.md](../evidence/foil-box-repeat-20261111/README.md) · [evidence/foil-box-repeat-20261111/phase/README.md](../evidence/foil-box-repeat-20261111/phase/README.md)

### `recordings/avg16-timing-01`

Ordinary stationary-scene vendor AVG16 timing/edge test. No target-distance ground truth. CHIRP_ACTIVE edges captured in each wire-v4 frame; 272 edges in 17 groups of 16 reported.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `not recorded`. [Configuration](../recordings/avg16-timing-01/config.json) · [Metadata](../recordings/avg16-timing-01/metadata.json)

Capture summary: 201 frames; 1 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-cfar-qualification.json](../configs/avg16-cfar-qualification.json).

Inherited approximate video windows from evidence/rd-avg16-motion-20261110/report.json and evidence/rd-cfar2d-followup-20261110/report.json; no offset fitting. Holds trimmed 2 s/side, motion 0.2 s/side. Host seconds from first saved frame, half-open windows. Timing-only scene has no target-distance label.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| unspecified stationary scene | not separately preserved | 0.00–19.90 s | — |

Sources / reviews: [docs/AVG16_TIMING_TEST.md](../docs/AVG16_TIMING_TEST.md) · [evidence/avg16-cfar-qualification-20261111/README.md](../evidence/avg16-cfar-qualification-20261111/README.md) · [evidence/rd-avg16-20261110/README.md](../evidence/rd-avg16-20261110/README.md)

### `recordings/avg16-motion-01`

Controlled 120/60 cm wheeled-target motion. Capture protocol called for fixed radar, fixed target orientation, nearby wall retained and operator to the side; exact operator pose/orientation compliance was not separately recorded. Actual video moves 11.35–12.80, 23.27–24.64 (corrected), 36.64–37.93, 47.11–48.48 s. Qualitative signed motion, not independently measured speed.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `not recorded`. [Configuration](../recordings/avg16-motion-01/config.json) · [Metadata](../recordings/avg16-motion-01/metadata.json)

Capture summary: 605 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-cfar-qualification.json](../configs/avg16-cfar-qualification.json).

Inherited approximate video windows from evidence/rd-avg16-motion-20261110/report.json and evidence/rd-cfar2d-followup-20261110/report.json; no offset fitting. Holds trimmed 2 s/side, motion 0.2 s/side. Host seconds from first saved frame, half-open windows. Timing-only scene has no target-distance label.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| 120 cm A | not separately preserved | 2.00–9.35 s | 120 cm |
| 60 cm A | not separately preserved | 14.80–21.27 s | 60 cm |
| 120 cm B | not separately preserved | 26.64–34.64 s | 120 cm |
| 60 cm B | not separately preserved | 39.93–45.11 s | 60 cm |
| 120 cm C | not separately preserved | 50.48–57.86 s | 120 cm |
| approach 1 | not separately preserved | 11.55–12.60 s | — |
| retreat 1 | not separately preserved | 23.47–24.44 s | — |
| approach 2 | not separately preserved | 36.84–37.73 s | — |
| retreat 2 | not separately preserved | 47.31–48.28 s | — |

Sources / reviews: [docs/AVG16_TIMING_TEST.md](../docs/AVG16_TIMING_TEST.md) · [docs/CFAR_2D.md](../docs/CFAR_2D.md) · [docs/RANGE_DOPPLER_ASSOCIATION.md](../docs/RANGE_DOPPLER_ASSOCIATION.md) · [evidence/avg16-cfar-qualification-20261111/README.md](../evidence/avg16-cfar-qualification-20261111/README.md) · [evidence/rd-association-20261110/README.md](../evidence/rd-association-20261110/README.md) · [evidence/rd-avg16-motion-20261110/README.md](../evidence/rd-avg16-motion-20261110/README.md) · [evidence/rd-cfar2d-20261110/README.md](../evidence/rd-cfar2d-20261110/README.md)

### `recordings/gui-20261110-162410-575208/live-001`

Earlier fixed radar / manually moving target / nearby wall run, before AVG16 development capture. Initial far hold, approach, near approximately 30 cm, retreat, far hold, wall only. Consecutive durations 18.58/28.03/31.01/25.53/30.71/33.64 s total 167.50 s, exceeding recording span 165.73 s. Transitions approximate; far position close to wall, not a clean separation test.

Saved acquisition: profile `0x33514802`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261110-162410-575208/live-001/config.json) · [Metadata](../recordings/gui-20261110-162410-575208/live-001/metadata.json)

Capture summary: 1670 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Sources / reviews: [evidence/rd-fixed-wall-20261110/README.md](../evidence/rd-fixed-wall-20261110/README.md)

### `recordings/gui-20261110-162410-575208/live-002`

Earlier fixed-radar wheeled-target 120↔60 cm nearby-wall repeat; operator to side, hand-driven variable speed. Consecutive durations 20.48/5.86/17.29/9.63/18.24/6.04/17.51/5.46/18.09/6.74/16.21/17.43 s: wall/placement/far/approach/near/retreat/far/approach/near/retreat/far/removal+wall. Seven packet/sequence losses; final phase mixes removal and empty with unknown transition.

Saved acquisition: profile `0x33514802`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261110-162410-575208/live-002/config.json) · [Metadata](../recordings/gui-20261110-162410-575208/live-002/metadata.json)

Capture summary: 1603 frames; 7 rejected; serial counters `{"bad_crc": 7, "bad_headers": 0, "discarded_bytes": 43916, "gaps": 7, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Sources / reviews: [evidence/rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md) · [evidence/rd-repeat-wall-20261110/README.md](../evidence/rd-repeat-wall-20261110/README.md)

### `recordings/gui-20261110-221227-169414/live-001`

AVG16 empty then target 120↔30 cm; faster and slower cycles. Video moves 31.11–32.82, 48.78–50.63, 64.18–67.45, 81.14–84.70 s; 1:07:45 interpreted as 67.45 s. Placement handling conservatively 13.99–18.99, removal 95.39–100.39 s. User confirmed no operator movement before 106.62 s; later target-absent portion is operator-confounded.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261110-221227-169414/live-001/config.json) · [Metadata](../recordings/gui-20261110-221227-169414/live-001/metadata.json)

Capture summary: 1149 frames; 0 rejected; serial counters `{"bad_crc": 1, "bad_headers": 0, "discarded_bytes": 7508, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/avg16-cfar-qualification.json](../configs/avg16-cfar-qualification.json).

Inherited approximate video windows from evidence/rd-avg16-motion-20261110/report.json and evidence/rd-cfar2d-followup-20261110/report.json; no offset fitting. Holds trimmed 2 s/side, motion 0.2 s/side. Host seconds from first saved frame, half-open windows. Timing-only scene has no target-distance label.

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| 120 cm A | not separately preserved | 20.99–29.11 s | 120 cm |
| 30 cm A | not separately preserved | 34.82–46.78 s | 30 cm |
| 120 cm B | not separately preserved | 52.63–62.18 s | 120 cm |
| 30 cm B | not separately preserved | 69.45–79.14 s | 30 cm |
| 120 cm C | not separately preserved | 86.70–93.39 s | 120 cm |
| fast approach | not separately preserved | 31.31–32.62 s | — |
| fast retreat | not separately preserved | 48.98–50.43 s | — |
| slow approach | not separately preserved | 64.38–67.25 s | — |
| slow retreat | not separately preserved | 81.34–84.50 s | — |
| initial target absent | not separately preserved | 2.00–13.99 s | — |
| post-removal quiet | not separately preserved | 102.39–106.12 s | — |
| target absent, possible operator motion | not separately preserved | 106.62–113.81 s | — |

Sources / reviews: [docs/LIVE_RANGE_DOPPLER.md](../docs/LIVE_RANGE_DOPPLER.md) · [docs/RANGE_DOPPLER_ASSOCIATION.md](../docs/RANGE_DOPPLER_ASSOCIATION.md) · [evidence/avg16-cfar-qualification-20261111/README.md](../evidence/avg16-cfar-qualification-20261111/README.md) · [evidence/rd-association-20261110/README.md](../evidence/rd-association-20261110/README.md) · [evidence/rd-cfar2d-followup-20261110/README.md](../evidence/rd-cfar2d-followup-20261110/README.md) · [evidence/rd-live-gui-20261110/README.md](../evidence/rd-live-gui-20261110/README.md)

### `recordings/gui-20261109-235116-484020/live-001`

Fresh post-clock-fix CFAR run. Tentative recalled steps: initially empty, about 30 s→60 cm, 60 s→30 cm, 90 s→100 cm, 120 s→70 cm. User may have mixed distance/order; times estimated from GUI graph, not a stopwatch. Do not score as verified range accuracy.

Saved acquisition: profile `0x33514802`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261109-235116-484020/live-001/config.json) · [Metadata](../recordings/gui-20261109-235116-484020/live-001/metadata.json)

Capture summary: 1386 frames; 2 rejected; serial counters `{"bad_crc": 2, "bad_headers": 0, "discarded_bytes": 12759, "gaps": 2, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Sources / reviews: [docs/CFAR_RANGE_DOPPLER_PLAN.md](../docs/CFAR_RANGE_DOPPLER_PLAN.md) · [docs/RANGE_DOPPLER_DIAGNOSTIC.md](../docs/RANGE_DOPPLER_DIAGNOSTIC.md) · [evidence/cfar-stage1-review-235116/README.md](../evidence/cfar-stage1-review-235116/README.md)

### `recordings/gui-20261109-224819-094246/live-001`

Approximate six-second alternating empty/target states, starting and ending empty; target nominal 50 cm, five intervals. Fresh validation labels, physical setup details unspecified.

Saved acquisition: profile `0x33514802`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261109-224819-094246/live-001/config.json) · [Metadata](../recordings/gui-20261109-224819-094246/live-001/metadata.json)

Capture summary: 276 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/cfar-validation-20261109-224819.json](../configs/cfar-validation-20261109-224819.json).

User-reported fresh validation after v2 implementation; approximate six-second alternating empty/target states, starting and ending empty. No tuning.

Alternating-label rule: 5 intervals of 6 s; target nominal 0.5 m. See manifest/review for interpretation.

Sources / reviews: [evidence/cfar-validation-224819/README.md](../evidence/cfar-validation-224819/README.md)

### `recordings/gui-20261109-224819-094246/live-002`

Approximate six-second alternating empty/target states, starting and ending empty; target nominal 80 cm, seven intervals. Physical setup details unspecified.

Saved acquisition: profile `0x33514802`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `range-ca-cfar-v2`. [Configuration](../recordings/gui-20261109-224819-094246/live-002/config.json) · [Metadata](../recordings/gui-20261109-224819-094246/live-002/metadata.json)

Capture summary: 423 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/cfar-validation-20261109-224819.json](../configs/cfar-validation-20261109-224819.json).

User-reported fresh validation after v2 implementation; approximate six-second alternating empty/target states, starting and ending empty. No tuning.

Alternating-label rule: 7 intervals of 6 s; target nominal 0.8 m. See manifest/review for interpretation.

Sources / reviews: [evidence/cfar-validation-224819/README.md](../evidence/cfar-validation-224819/README.md)

### `recordings/scope-timing-01`

Timing instrumentation experiment; physical target setup not established here. Use saved configuration and the timing review, not the directory name, to choose matching parser/firmware.

Saved acquisition: profile `0x33515301`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `not recorded`. [Configuration](../recordings/scope-timing-01/config.json) · [Metadata](../recordings/scope-timing-01/metadata.json)

Capture summary: 201 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Sources / reviews: [docs/MCU_EDGE_TIMING.md](../docs/MCU_EDGE_TIMING.md) · [docs/SCOPE_TIMING.md](../docs/SCOPE_TIMING.md) · [evidence/rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md) · [evidence/rd-timing-feasibility-20261110/README.md](../evidence/rd-timing-feasibility-20261110/README.md)

### `recordings/edge-timing-01`

Timing instrumentation experiment; physical target setup not established here. Use saved configuration and the timing review, not the directory name, to choose matching parser/firmware.

Saved acquisition: profile `0x33515401`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `not recorded`. [Configuration](../recordings/edge-timing-01/config.json) · [Metadata](../recordings/edge-timing-01/metadata.json)

Sources / reviews: [docs/MCU_EDGE_TIMING.md](../docs/MCU_EDGE_TIMING.md) · [docs/SCOPE_TIMING.md](../docs/SCOPE_TIMING.md) · [evidence/rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md)

### `recordings/edge-timing-02`

Timing instrumentation experiment; physical target setup not established here. Use saved configuration and the timing review, not the directory name, to choose matching parser/firmware.

Saved acquisition: profile `0x33515401`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `not recorded`. [Configuration](../recordings/edge-timing-02/config.json) · [Metadata](../recordings/edge-timing-02/metadata.json)

Capture summary: 201 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Sources / reviews: [docs/MCU_EDGE_TIMING.md](../docs/MCU_EDGE_TIMING.md) · [docs/SCOPE_TIMING.md](../docs/SCOPE_TIMING.md) · [evidence/rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md)

### `recordings/rd-gui-20261111-223730-634059/live-001`

Bare cardboard box; operator explicitly stationary at position B (described as away from sensor range) during all quiet holds. User supplied initial handling / empty / 50 cm / empty / repeated 50 cm / empty / 120 cm / empty with all handling durations. Same established bare-box protocol; prior front dimensions approximately 45×24 cm and antenna-face to box-face reference are inherited, not remeasured in this message. Operator-B protocol is explicitly confirmed for this run, unlike the earlier bare-box 120 cm hold at A. Labeled end 261.83 s; later tail unscored. Command includes --experimental-weak; saved metadata confirms native association metric.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261111-223730-634059/live-001/config.json) · [Metadata](../recordings/rd-gui-20261111-223730-634059/live-001/metadata.json)

Capture summary: 2691 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/bare-box-b-20261111.json](../configs/bare-box-b-20261111.json).

Consecutive user durations from first saved frame; transitions excluded; primary 2s trims with 1s sensitivity. No fitted offset. Labeled end 261.83s; later tail unlabeled.

| Supplied segment | Original host interval | Duration |
|---|---:|---:|
| transition | 0.00–10.18 s | 10.18 s |
| empty A | 10.18–25.66 s | 15.48 s |
| transition | 25.66–46.30 s | 20.64 s |
| 50 cm A | 46.30–76.96 s | 30.66 s |
| transition | 76.96–89.75 s | 12.79 s |
| empty B | 89.75–105.71 s | 15.96 s |
| transition | 105.71–126.37 s | 20.66 s |
| 50 cm B | 126.37–157.46 s | 31.09 s |
| transition | 157.46–169.77 s | 12.31 s |
| empty C | 169.77–185.75 s | 15.98 s |
| transition | 185.75–203.93 s | 18.18 s |
| 120 cm | 203.93–235.59 s | 31.66 s |
| transition | 235.59–245.85 s | 10.26 s |
| final empty | 245.85–261.83 s | 15.98 s |

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| empty A (trim 2s) | 10.18–25.66 s | 12.18–23.66 s | — |
| 50 cm A (trim 2s) | 46.30–76.96 s | 48.30–74.96 s | 50 cm |
| empty B (trim 2s) | 89.75–105.71 s | 91.75–103.71 s | — |
| 50 cm B (trim 2s) | 126.37–157.46 s | 128.37–155.46 s | 50 cm |
| empty C (trim 2s) | 169.77–185.75 s | 171.77–183.75 s | — |
| 120 cm (trim 2s) | 203.93–235.59 s | 205.93–233.59 s | 120 cm |
| final empty (trim 2s) | 245.85–261.83 s | 247.85–259.83 s | — |

Sources / reviews: [evidence/bare-box-b-20261111/README.md](../evidence/bare-box-b-20261111/README.md) · [evidence/bare-box-b-20261111/phase/README.md](../evidence/bare-box-b-20261111/phase/README.md)

### `recordings/rd-gui-20261112-094114-038104/live-001`

User-timed empty / bare / foil / bare / empty, all target holds nominal 50 cm. Operator explicitly B during quiet holds. User explicitly confirms box footprint and orientation stayed fixed while only foil was added/removed. Earlier box dimensions about 45 x 24 cm and antenna/front-face convention are inherited context, not remeasured. Wall distance not remeasured. Labels end 243.71 s; later tail unscored. Foil gives baseline ~46.1 cm and raw-tone ~51 cm; bare return after removal gives confirmed weak ~29.1 cm despite main distance withheld, so scene-feature confirmation is not box identity.

Saved acquisition: profile `0x33515403`; samples=64, saved chirps/blocks=17, discard=1, frame interval=0.1 s. Detector: `joint-range-cfar-rd-v1`. [Configuration](../recordings/rd-gui-20261112-094114-038104/live-001/config.json) · [Metadata](../recordings/rd-gui-20261112-094114-038104/live-001/metadata.json)

Capture summary: 2532 frames; 0 rejected; serial counters `{"bad_crc": 0, "bad_headers": 0, "discarded_bytes": 0, "gaps": 0, "restarts": 0}`. These are saved capture counters, not a fresh replay audit.

Scene annotation: [configs/material-control-20261112.json](../configs/material-control-20261112.json).

Consecutive user durations from first saved frame; handling excluded; primary 2s trims and 1s sensitivity. No fitted offset. Labels end 243.71s; any later tail unscored.

| Supplied segment | Original host interval | Duration |
|---|---:|---:|
| transition | 0.00–6.66 s | 6.66 s |
| empty A | 6.66–24.12 s | 17.46 s |
| transition | 24.12–50.36 s | 26.24 s |
| bare A 50 cm | 50.36–85.10 s | 34.74 s |
| transition | 85.10–115.66 s | 30.56 s |
| foil 50 cm | 115.66–147.49 s | 31.83 s |
| transition | 147.49–179.20 s | 31.71 s |
| bare B 50 cm | 179.20–210.38 s | 31.18 s |
| transition | 210.38–226.29 s | 15.91 s |
| final empty | 226.29–243.71 s | 17.42 s |

| State / label | Original interval if preserved | Scored host interval | Nominal placement |
|---|---:|---:|---:|
| empty A (trim 2s) | 6.66–24.12 s | 8.66–22.12 s | — |
| bare A 50 cm (trim 2s) | 50.36–85.10 s | 52.36–83.10 s | 50 cm |
| foil 50 cm (trim 2s) | 115.66–147.49 s | 117.66–145.49 s | 50 cm |
| bare B 50 cm (trim 2s) | 179.20–210.38 s | 181.20–208.38 s | 50 cm |
| final empty (trim 2s) | 226.29–243.71 s | 228.29–241.71 s | — |

Sources / reviews: [docs/EMPTY_TRAINED_BACKGROUND.md](../docs/EMPTY_TRAINED_BACKGROUND.md) · [evidence/material-control-20261112-phase/README.md](../evidence/material-control-20261112-phase/README.md) · [evidence/material-control-20261112/README.md](../evidence/material-control-20261112/README.md)

## Complete saved-configuration inventory

Each row links the actual recording directory/configuration. “Unspecified” means physical setup is not established here, even if a filename suggests a range. Saved metadata labels and distances below are provenance, not independently verified truth. Consult the detailed sections above or linked reviews before scoring. Configuration-only parents are not extra captures. The machine-readable catalog retains complete saved configs/metadata and all discovered exact-path review references.

| Recording | Raw | Profile | Saved label / distance | Setup / evidence |
|---|---|---|---|---|
| [1ft](../recordings/1ft/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [2ft](../recordings/2ft/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [3ft](../recordings/3ft/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [agh_empty](../recordings/agh_empty/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [avg16-motion-01](../recordings/avg16-motion-01/config.json) | yes | `0x33515403` | capture | Detailed above; [configs/avg16-cfar-qualification.json](../configs/avg16-cfar-qualification.json) · [docs/AVG16_TIMING_TEST.md](../docs/AVG16_TIMING_TEST.md) · [docs/CFAR_2D.md](../docs/CFAR_2D.md) · [docs/RANGE_DOPPLER_ASSOCIATION.md](../docs/RANGE_DOPPLER_ASSOCIATION.md); more in JSON |
| [avg16-timing-01](../recordings/avg16-timing-01/config.json) | yes | `0x33515403` | capture | Detailed above; [configs/avg16-cfar-qualification.json](../configs/avg16-cfar-qualification.json) · [docs/AVG16_TIMING_TEST.md](../docs/AVG16_TIMING_TEST.md) · [avg16-cfar-qualification-20261111/README.md](../evidence/avg16-cfar-qualification-20261111/README.md) · [rd-avg16-20261110/README.md](../evidence/rd-avg16-20261110/README.md) |
| [close_empty_after](../recordings/close_empty_after/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [close_empty_before](../recordings/close_empty_before/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [close_far](../recordings/close_far/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [close_near_1](../recordings/close_near_1/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [close_near_2](../recordings/close_near_2/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [connection-check-20261101](../recordings/connection-check-20261101/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here |
| [connection-check-20261101-authorized](../recordings/connection-check-20261101-authorized/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here |
| [distance-sweep-1-30cm](../recordings/distance-sweep-1-30cm/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-1-40cm](../recordings/distance-sweep-1-40cm/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-1-40cm-repeat](../recordings/distance-sweep-1-40cm-repeat/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-1-40cm-repeat-2](../recordings/distance-sweep-1-40cm-repeat-2/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here |
| [distance-sweep-1-40cm-untouched-1](../recordings/distance-sweep-1-40cm-untouched-1/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here |
| [distance-sweep-1-50cm](../recordings/distance-sweep-1-50cm/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-1-empty-after](../recordings/distance-sweep-1-empty-after/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-1-empty-before](../recordings/distance-sweep-1-empty-before/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-2-30cm](../recordings/distance-sweep-2-30cm/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-2-40cm](../recordings/distance-sweep-2-40cm/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-2-40cm-repeat](../recordings/distance-sweep-2-40cm-repeat/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-2-50cm](../recordings/distance-sweep-2-50cm/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-2-empty-after](../recordings/distance-sweep-2-empty-after/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [distance-sweep-2-empty-before](../recordings/distance-sweep-2-empty-before/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [door03/closed-01](../recordings/door03/closed-01/config.json) | yes | `0x33514802` | unknown; scene door03 | Physical setup unspecified here |
| [door03/closed-02](../recordings/door03/closed-02/config.json) | yes | `0x33514802` | unknown; scene door03 | Physical setup unspecified here |
| [door03/closed-03](../recordings/door03/closed-03/config.json) | yes | `0x33514802` | unknown; scene door03 | Physical setup unspecified here |
| [door03](../recordings/door03/config.json) | configuration only | `0x33514802` | unspecified | Physical setup unspecified here |
| [door03/open-01](../recordings/door03/open-01/config.json) | yes | `0x33514802` | unknown; scene door03 | Physical setup unspecified here |
| [door03/open-02](../recordings/door03/open-02/config.json) | yes | `0x33514802` | unknown; scene door03 | Physical setup unspecified here |
| [door03/open-03](../recordings/door03/open-03/config.json) | yes | `0x33514802` | unknown; scene door03 | Physical setup unspecified here |
| [door03/stream](../recordings/door03/stream/config.json) | yes | `0x33514802` | unknown | Physical setup unspecified here |
| [door04/closed-01](../recordings/door04/closed-01/config.json) | yes | `0x33514802` | unknown; scene door04 | Physical setup unspecified here |
| [door04/closed-02](../recordings/door04/closed-02/config.json) | yes | `0x33514802` | unknown; scene door04 | Physical setup unspecified here |
| [door04/closed-03](../recordings/door04/closed-03/config.json) | yes | `0x33514802` | unknown; scene door04 | Physical setup unspecified here |
| [door04](../recordings/door04/config.json) | configuration only | `0x33514802` | unspecified | Physical setup unspecified here |
| [door04/open-01](../recordings/door04/open-01/config.json) | yes | `0x33514802` | unknown; scene door04 | Physical setup unspecified here |
| [door04/open-02](../recordings/door04/open-02/config.json) | yes | `0x33514802` | unknown; scene door04 | Physical setup unspecified here |
| [door04/open-03](../recordings/door04/open-03/config.json) | yes | `0x33514802` | unknown; scene door04 | Physical setup unspecified here |
| [door04/stream](../recordings/door04/stream/config.json) | yes | `0x33514802` | unknown | Physical setup unspecified here |
| [door05](../recordings/door05/config.json) | configuration only | `0x33514802` | unspecified | Physical setup unspecified here |
| [door06](../recordings/door06/config.json) | configuration only | `0x33514802` | unspecified | Physical setup unspecified here |
| [door07/closed-01](../recordings/door07/closed-01/config.json) | yes | `0x33514802` | unknown; scene door07 | Physical setup unspecified here |
| [door07/closed-02](../recordings/door07/closed-02/config.json) | yes | `0x33514802` | unknown; scene door07 | Physical setup unspecified here |
| [door07/closed-03](../recordings/door07/closed-03/config.json) | yes | `0x33514802` | unknown; scene door07 | Physical setup unspecified here |
| [door07](../recordings/door07/config.json) | configuration only | `0x33514802` | unspecified | Physical setup unspecified here |
| [door07/open-01](../recordings/door07/open-01/config.json) | yes | `0x33514802` | unknown; scene door07 | Physical setup unspecified here |
| [door07/open-02](../recordings/door07/open-02/config.json) | yes | `0x33514802` | unknown; scene door07 | Physical setup unspecified here |
| [door07/open-03](../recordings/door07/open-03/config.json) | yes | `0x33514802` | unknown; scene door07 | Physical setup unspecified here |
| [door07/stream](../recordings/door07/stream/config.json) | yes | `0x33514802` | unknown | Physical setup unspecified here |
| [edge-timing-01](../recordings/edge-timing-01/config.json) | yes | `0x33515401` | capture | Detailed above; [docs/MCU_EDGE_TIMING.md](../docs/MCU_EDGE_TIMING.md) · [docs/SCOPE_TIMING.md](../docs/SCOPE_TIMING.md) · [rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md) |
| [edge-timing-02](../recordings/edge-timing-02/config.json) | yes | `0x33515401` | capture | Detailed above; [docs/MCU_EDGE_TIMING.md](../docs/MCU_EDGE_TIMING.md) · [docs/SCOPE_TIMING.md](../docs/SCOPE_TIMING.md) · [rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md) |
| [edge-timing-03](../recordings/edge-timing-03/config.json) | yes | `0x33515402` | capture | Physical setup unspecified here; [docs/MCU_EDGE_TIMING.md](../docs/MCU_EDGE_TIMING.md) · [rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md) |
| [empty-50cm-1](../recordings/empty-50cm-1/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here |
| [empty-50cm-v2-1](../recordings/empty-50cm-v2-1/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here |
| [empty-after-1m-session-1](../recordings/empty-after-1m-session-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [empty-after-35cm-v2-1](../recordings/empty-after-35cm-v2-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [empty-after-50cm-1](../recordings/empty-after-50cm-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [empty-after-50cm-v2-1](../recordings/empty-after-50cm-v2-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [empty-session-1](../recordings/empty-session-1/config.json) | yes | `0x33525801` | capture | Physical setup unspecified here |
| [empty_check](../recordings/empty_check/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |
| [gui-20261101-144515-340260/empty-001](../recordings/gui-20261101-144515-340260/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [associated-fit-3/README.md](../evidence/associated-fit-3/README.md) |
| [gui-20261101-144515-340260/live-002](../recordings/gui-20261101-144515-340260/live-002/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-144515-340260/live-003](../recordings/gui-20261101-144515-340260/live-003/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-144515-340260/live-004](../recordings/gui-20261101-144515-340260/live-004/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-144515-340260/live-005](../recordings/gui-20261101-144515-340260/live-005/config.json) | yes | `0x33514802` | live | Physical setup unspecified here; [associated-fit-3/README.md](../evidence/associated-fit-3/README.md) |
| [gui-20261101-153315-782345/empty-001](../recordings/gui-20261101-153315-782345/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261101-153315-782345/empty-002](../recordings/gui-20261101-153315-782345/empty-002/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261101-153315-782345/empty-004](../recordings/gui-20261101-153315-782345/empty-004/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261101-153614-515628/empty-001](../recordings/gui-20261101-153614-515628/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261101-153614-515628/live-002](../recordings/gui-20261101-153614-515628/live-002/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-153737-539230/empty-001](../recordings/gui-20261101-153737-539230/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261101-153737-539230/live-002](../recordings/gui-20261101-153737-539230/live-002/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-153737-539230/live-003](../recordings/gui-20261101-153737-539230/live-003/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-153737-539230/live-004](../recordings/gui-20261101-153737-539230/live-004/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-153737-539230/live-005](../recordings/gui-20261101-153737-539230/live-005/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-153737-539230/live-006](../recordings/gui-20261101-153737-539230/live-006/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/empty-001](../recordings/gui-20261101-155623-972019/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-002](../recordings/gui-20261101-155623-972019/live-002/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-003](../recordings/gui-20261101-155623-972019/live-003/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-004](../recordings/gui-20261101-155623-972019/live-004/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-005](../recordings/gui-20261101-155623-972019/live-005/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-006](../recordings/gui-20261101-155623-972019/live-006/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-007](../recordings/gui-20261101-155623-972019/live-007/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-008](../recordings/gui-20261101-155623-972019/live-008/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-155623-972019/live-009](../recordings/gui-20261101-155623-972019/live-009/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-163602-348990/empty-001](../recordings/gui-20261101-163602-348990/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261101-163602-348990/live-002](../recordings/gui-20261101-163602-348990/live-002/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-163602-348990/live-003](../recordings/gui-20261101-163602-348990/live-003/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-163602-348990/live-004](../recordings/gui-20261101-163602-348990/live-004/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-163602-348990/live-005](../recordings/gui-20261101-163602-348990/live-005/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261101-163602-348990/live-006](../recordings/gui-20261101-163602-348990/live-006/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261109-202256-780060/empty-001](../recordings/gui-20261109-202256-780060/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261109-202556-804613/empty-001](../recordings/gui-20261109-202556-804613/empty-001/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [gui-20261109-202556-804613/live-002](../recordings/gui-20261109-202556-804613/live-002/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261109-215257-942086/live-001](../recordings/gui-20261109-215257-942086/live-001/config.json) | yes | `0x33514802` | live | Physical setup unspecified here; [cfar-fresh-session-20261109/README.md](../evidence/cfar-fresh-session-20261109/README.md) |
| [gui-20261109-215257-942086/live-002](../recordings/gui-20261109-215257-942086/live-002/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261109-215257-942086/live-003](../recordings/gui-20261109-215257-942086/live-003/config.json) | yes | `0x33514802` | live | Physical setup unspecified here; [docs/CFAR_RANGE.md](../docs/CFAR_RANGE.md) · [cfar-toggle-live-003/README.md](../evidence/cfar-toggle-live-003/README.md) |
| [gui-20261109-224819-094246/live-001](../recordings/gui-20261109-224819-094246/live-001/config.json) | yes | `0x33514802` | live | Detailed above; [configs/cfar-validation-20261109-224819.json](../configs/cfar-validation-20261109-224819.json) · [cfar-validation-224819/README.md](../evidence/cfar-validation-224819/README.md) |
| [gui-20261109-224819-094246/live-002](../recordings/gui-20261109-224819-094246/live-002/config.json) | yes | `0x33514802` | live | Detailed above; [configs/cfar-validation-20261109-224819.json](../configs/cfar-validation-20261109-224819.json) · [cfar-validation-224819/README.md](../evidence/cfar-validation-224819/README.md) |
| [gui-20261109-224819-094246/live-003](../recordings/gui-20261109-224819-094246/live-003/config.json) | yes | `0x33514802` | live | Physical setup unspecified here; [cfar-long-hold-224819-live003/README.md](../evidence/cfar-long-hold-224819-live003/README.md) |
| [gui-20261109-224819-094246/live-004](../recordings/gui-20261109-224819-094246/live-004/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261109-224819-094246/live-005](../recordings/gui-20261109-224819-094246/live-005/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261109-224819-094246/live-006](../recordings/gui-20261109-224819-094246/live-006/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261109-224819-094246/live-007](../recordings/gui-20261109-224819-094246/live-007/config.json) | yes | `0x33514802` | live | Physical setup unspecified here |
| [gui-20261109-235116-484020/live-001](../recordings/gui-20261109-235116-484020/live-001/config.json) | yes | `0x33514802` | live | Detailed above; [docs/CFAR_RANGE_DOPPLER_PLAN.md](../docs/CFAR_RANGE_DOPPLER_PLAN.md) · [docs/RANGE_DOPPLER_DIAGNOSTIC.md](../docs/RANGE_DOPPLER_DIAGNOSTIC.md) · [cfar-stage1-review-235116/README.md](../evidence/cfar-stage1-review-235116/README.md) |
| [gui-20261110-162410-575208/live-001](../recordings/gui-20261110-162410-575208/live-001/config.json) | yes | `0x33514802` | live | Detailed above; [rd-fixed-wall-20261110/README.md](../evidence/rd-fixed-wall-20261110/README.md) |
| [gui-20261110-162410-575208/live-002](../recordings/gui-20261110-162410-575208/live-002/config.json) | yes | `0x33514802` | live | Detailed above; [rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md) · [rd-repeat-wall-20261110/README.md](../evidence/rd-repeat-wall-20261110/README.md) |
| [gui-20261110-221227-169414/live-001](../recordings/gui-20261110-221227-169414/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [configs/avg16-cfar-qualification.json](../configs/avg16-cfar-qualification.json) · [docs/LIVE_RANGE_DOPPLER.md](../docs/LIVE_RANGE_DOPPLER.md) · [docs/RANGE_DOPPLER_ASSOCIATION.md](../docs/RANGE_DOPPLER_ASSOCIATION.md) · [avg16-cfar-qualification-20261111/README.md](../evidence/avg16-cfar-qualification-20261111/README.md); more in JSON |
| [gui-20261111-093636-901489/live-001](../recordings/gui-20261111-093636-901489/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [gui-20261111-093723-246315/live-001](../recordings/gui-20261111-093723-246315/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [configs/avg16-placements-20261111.json](../configs/avg16-placements-20261111.json) · [avg16-placements-20261111/README.md](../evidence/avg16-placements-20261111/README.md) · [avg16-placements-20261111/REVIEW.md](../evidence/avg16-placements-20261111/REVIEW.md) · [clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md); more in JSON |
| [gui-20261111-093723-246315/live-002](../recordings/gui-20261111-093723-246315/live-002/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [gui-20261111-093723-246315/live-003](../recordings/gui-20261111-093723-246315/live-003/config.json) | yes | `0x33515403` | live | Detailed above; [configs/avg16-repeat50-20261111.json](../configs/avg16-repeat50-20261111.json) · [avg16-repeat50-20261111/README.md](../evidence/avg16-repeat50-20261111/README.md) · [avg16-repeat50-20261111/REVIEW.md](../evidence/avg16-repeat50-20261111/REVIEW.md) · [clutter-reference-20261111/README.md](../evidence/clutter-reference-20261111/README.md); more in JSON |
| [gui-20261111-093723-246315/live-004](../recordings/gui-20261111-093723-246315/live-004/config.json) | yes | `0x33515403` | live | Detailed above; [configs/avg16-operator-abab-20261111.json](../configs/avg16-operator-abab-20261111.json) · [docs/RX_DIAGNOSTICS.md](../docs/RX_DIAGNOSTICS.md) · [avg16-operator-abab-20261111/README.md](../evidence/avg16-operator-abab-20261111/README.md) · [avg16-operator-abab-20261111/REVIEW.md](../evidence/avg16-operator-abab-20261111/REVIEW.md); more in JSON |
| [gui-20261111-093723-246315/live-005](../recordings/gui-20261111-093723-246315/live-005/config.json) | yes | `0x33515403` | live | Detailed above; [configs/avg16-operator-empty-abab-20261111.json](../configs/avg16-operator-empty-abab-20261111.json) · [docs/CLUTTER_REFERENCE_EXPERIMENT.md](../docs/CLUTTER_REFERENCE_EXPERIMENT.md) · [avg16-operator-empty-abab-20261111/README.md](../evidence/avg16-operator-empty-abab-20261111/README.md) · [avg16-operator-empty-abab-20261111/REVIEW.md](../evidence/avg16-operator-empty-abab-20261111/REVIEW.md); more in JSON |
| [gui-20261111-093723-246315/live-006](../recordings/gui-20261111-093723-246315/live-006/config.json) | yes | `0x33515403` | live | Detailed above; [configs/avg16-motion-20261111.json](../configs/avg16-motion-20261111.json) · [docs/JOINT_RANGE_DOPPLER.md](../docs/JOINT_RANGE_DOPPLER.md) · [docs/MOTION_AWARE_RANGE.md](../docs/MOTION_AWARE_RANGE.md) · [avg16-motion-20261111/README.md](../evidence/avg16-motion-20261111/README.md); more in JSON |
| [hpf100-a-30cm](../recordings/hpf100-a-30cm/config.json) | yes | `0x33514801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf100-a-40cm](../recordings/hpf100-a-40cm/config.json) | yes | `0x33514801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf100-a-40cm-repeat](../recordings/hpf100-a-40cm-repeat/config.json) | yes | `0x33514801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf100-a-50cm](../recordings/hpf100-a-50cm/config.json) | yes | `0x33514801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf100-a-empty-after](../recordings/hpf100-a-empty-after/config.json) | yes | `0x33514801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf100-a-empty-before](../recordings/hpf100-a-empty-before/config.json) | yes | `0x33514801` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf100-a-startup-check](../recordings/hpf100-a-startup-check/config.json) | yes | `0x33514801` | capture | Physical setup unspecified here |
| [hpf350-a-30cm](../recordings/hpf350-a-30cm/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-a-40cm](../recordings/hpf350-a-40cm/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-a-40cm-repeat](../recordings/hpf350-a-40cm-repeat/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-a-50cm](../recordings/hpf350-a-50cm/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-a-empty-after](../recordings/hpf350-a-empty-after/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-a-empty-before](../recordings/hpf350-a-empty-before/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-a-startup-check](../recordings/hpf350-a-startup-check/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [hpf350-a-startup-check-2](../recordings/hpf350-a-startup-check-2/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [hpf350-b-30cm](../recordings/hpf350-b-30cm/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-b-40cm](../recordings/hpf350-b-40cm/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [docs/CFAR_RANGE.md](../docs/CFAR_RANGE.md) · [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-b-40cm-repeat](../recordings/hpf350-b-40cm-repeat/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-b-50cm](../recordings/hpf350-b-50cm/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-b-empty-after](../recordings/hpf350-b-empty-after/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-b-empty-before](../recordings/hpf350-b-empty-before/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here; [cfar-sweep-1/README.md](../evidence/cfar-sweep-1/README.md) |
| [hpf350-b-startup-check](../recordings/hpf350-b-startup-check/config.json) | yes | `0x33514802` | capture | Physical setup unspecified here |
| [rd-gui-20261110-234545-061442/live-001](../recordings/rd-gui-20261110-234545-061442/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261111-132415-538511/live-001](../recordings/rd-gui-20261111-132415-538511/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261111-132433-610820/live-001](../recordings/rd-gui-20261111-132433-610820/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [joint-gui-timing-20261111/README.md](../evidence/joint-gui-timing-20261111/README.md) |
| [rd-gui-20261111-133435-428121/live-001](../recordings/rd-gui-20261111-133435-428121/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [docs/CLUTTER_REFERENCE_EXPERIMENT.md](../docs/CLUTTER_REFERENCE_EXPERIMENT.md) · [docs/WEAK_CANDIDATE_EXPERIMENT.md](../docs/WEAK_CANDIDATE_EXPERIMENT.md) · [docs/WEAK_FEATURE_CONFIRMATION.md](../docs/WEAK_FEATURE_CONFIRMATION.md) · [docs/WEAK_MOTION_LINK.md](../docs/WEAK_MOTION_LINK.md); more in JSON |
| [rd-gui-20261111-135229-775366/live-001](../recordings/rd-gui-20261111-135229-775366/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [configs/live-os-paired80-20261111.json](../configs/live-os-paired80-20261111.json) · [live-os-paired80-20261111/README.md](../evidence/live-os-paired80-20261111/README.md) |
| [rd-gui-20261111-135229-775366/live-002](../recordings/rd-gui-20261111-135229-775366/live-002/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261111-141606-847532/live-001](../recordings/rd-gui-20261111-141606-847532/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261111-141606-847532/live-002](../recordings/rd-gui-20261111-141606-847532/live-002/config.json) | yes | `0x33515403` | live | Detailed above; [configs/motion-aware-live-20261111.json](../configs/motion-aware-live-20261111.json) · [docs/SUBBIN_ASSOCIATION.md](../docs/SUBBIN_ASSOCIATION.md) · [motion-aware-live-20261111/README.md](../evidence/motion-aware-live-20261111/README.md) · [phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md); more in JSON |
| [rd-gui-20261111-143819-360020/live-001](../recordings/rd-gui-20261111-143819-360020/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261111-143819-360020/live-002](../recordings/rd-gui-20261111-143819-360020/live-002/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261111-143819-360020/live-003](../recordings/rd-gui-20261111-143819-360020/live-003/config.json) | yes | `0x33515403` | live | Detailed above; [configs/reflector-live-20261111.json](../configs/reflector-live-20261111.json) · [phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [phase-residuals-20261111/README.md](../evidence/phase-residuals-20261111/README.md) · [stopped-support-20261111/README.md](../evidence/stopped-support-20261111/README.md); more in JSON |
| [rd-gui-20261111-200448-409110/live-001](../recordings/rd-gui-20261111-200448-409110/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [configs/foil-box-live-20261111.json](../configs/foil-box-live-20261111.json) · [foil-box-live-20261111/README.md](../evidence/foil-box-live-20261111/README.md) · [phase-range-20261111/README.md](../evidence/phase-range-20261111/README.md) · [phase-range-20261111/REVIEW.md](../evidence/phase-range-20261111/REVIEW.md) |
| [rd-gui-20261111-200448-409110/live-002](../recordings/rd-gui-20261111-200448-409110/live-002/config.json) | yes | `0x33515403` | live | Detailed above; [configs/foil-box-repeat-20261111.json](../configs/foil-box-repeat-20261111.json) · [foil-box-repeat-20261111/README.md](../evidence/foil-box-repeat-20261111/README.md) · [phase/README.md](../evidence/foil-box-repeat-20261111/phase/README.md) |
| [rd-gui-20261111-223730-634059/live-001](../recordings/rd-gui-20261111-223730-634059/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [configs/bare-box-b-20261111.json](../configs/bare-box-b-20261111.json) · [bare-box-b-20261111/README.md](../evidence/bare-box-b-20261111/README.md) · [phase/README.md](../evidence/bare-box-b-20261111/phase/README.md) |
| [rd-gui-20261112-093251-196918/live-001](../recordings/rd-gui-20261112-093251-196918/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261112-093251-196918/live-002](../recordings/rd-gui-20261112-093251-196918/live-002/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261112-093940-910559/live-001](../recordings/rd-gui-20261112-093940-910559/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261112-093957-844351/live-001](../recordings/rd-gui-20261112-093957-844351/live-001/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261112-093957-844351/live-002](../recordings/rd-gui-20261112-093957-844351/live-002/config.json) | yes | `0x33515403` | live | Physical setup unspecified here |
| [rd-gui-20261112-094114-038104/live-001](../recordings/rd-gui-20261112-094114-038104/live-001/config.json) | yes | `0x33515403` | live | Detailed above; [configs/material-control-20261112.json](../configs/material-control-20261112.json) · [docs/EMPTY_TRAINED_BACKGROUND.md](../docs/EMPTY_TRAINED_BACKGROUND.md) · [material-control-20261112-phase/README.md](../evidence/material-control-20261112-phase/README.md) · [material-control-20261112/README.md](../evidence/material-control-20261112/README.md) |
| [scope-timing-01](../recordings/scope-timing-01/config.json) | yes | `0x33515301` | capture | Detailed above; [docs/MCU_EDGE_TIMING.md](../docs/MCU_EDGE_TIMING.md) · [docs/SCOPE_TIMING.md](../docs/SCOPE_TIMING.md) · [rd-mcu-edge-20261110/README.md](../evidence/rd-mcu-edge-20261110/README.md) · [rd-timing-feasibility-20261110/README.md](../evidence/rd-timing-feasibility-20261110/README.md) |
| [target-1m-repeat-1](../recordings/target-1m-repeat-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [target-1m-session-1](../recordings/target-1m-session-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [target-35cm-v2-1](../recordings/target-35cm-v2-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [target-50cm-1](../recordings/target-50cm-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [target-50cm-v2-1](../recordings/target-50cm-v2-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [target-50cm-v2-repeat-1](../recordings/target-50cm-v2-repeat-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [target-session-1](../recordings/target-session-1/config.json) | yes | `0x33525801` | live | Physical setup unspecified here |
| [temp_empty](../recordings/temp_empty/config.json) | yes | `0x33525801` | unknown | Physical setup unspecified here |

## Keeping this catalog current

Add physical setup facts and their provenance to [capture-setups.json](../configs/capture-setups.json), and write explicit timing labels in a separate scene manifest under `configs/`. Preserve raw data and original metadata. Record target dimensions/material/orientation/support, antenna-to-front-surface distance and uncertainty, sensor height/motion, background geometry, operator position/motion, firmware hash/profile, timing origin and ignored intervals. Distinguish reported facts from intended setup and inference.

Regenerate both this document and [the machine-readable catalog](../configs/capture-catalog.json):

```sh
.venv/bin/python -m tools.build_capture_catalog
```

Replay a newly labeled joint capture with [the joint audit](JOINT_RANGE_DOPPLER.md), and compare phase fits without changing live output:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_phase_range \
  --manifest configs/foil-box-repeat-20261111.json --output evidence/NEW-PHASE-REVIEW
```
