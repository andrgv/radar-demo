# Archived bulk evidence

The 75 artifacts listed below total **461.87 MiB**.
They were added in original commit `95690be9937724e955e4e2fd787b34dff91728f2` and are now excluded from the Git index.
The files remain on the local filesystem, and the user has separately backed up
the complete `evidence/` folder. Reports, metrics, images and source code remain tracked.

## Locate and restore

The archive is the user-maintained external copy of `evidence/`; a permanent
archive path/download URL has not been supplied. The backup must be retained
alongside the raw recordings if complete reproduction is required.

To restore an artifact, copy its path below relative to `evidence/` from that
backup into the same path under this checkout. For example, restore
`avg16-cfar-qualification-20261111/readings.jsonl` into
`evidence/avg16-cfar-qualification-20261111/readings.jsonl`. Restored bulk files
remain ignored by Git. Older already-tracked bulk files are retained unchanged.

The [manifest](archive-manifest.json) records all paths, sizes, complete SHA-256
hashes and related reports. Verify either the current local files or a backup:

```sh
.venv/bin/python -m tools.verify_archived_evidence --evidence-root evidence
.venv/bin/python -m tools.verify_archived_evidence --evidence-root /path/to/backup/evidence
```

## Regenerate

Follow the reproduction commands in each related report, retaining the original
raw recordings, scene manifests, configuration and processing-source version.
Many commands require a **fresh output directory**; generate there rather than
overwriting a historical report. Some reviewers consume a preceding replay
audit, so preserve the documented command order. The excluded files are outputs,
not substitutes for raw recordings or scene annotations.

Original source/input hashes remain unchanged in historical JSON reports.
Per-frame output can include processing times and compression metadata; a new
run need not have an identical file hash even when scientific results agree.
Use the archive hashes to verify exact saved originals and the existing parity
checks to verify regenerated measurements. A clean clone does not contain these
bulk files until they are restored or regenerated.

## Git history

Untracking files in the index does not remove them from existing commits.
This cleanup is prepared for an amendment of the most recent commit; committing
it as a separate deletion commit would leave the original bulk in history.
This cleanup itself does not amend commits or push the branch.

## Archived files

| Path relative to evidence/ | MiB | Related report |
|---|---:|---|
| `avg16-cfar-qualification-20261111/readings.jsonl` | 9.552 | [avg16-cfar-qualification-20261111/README.md](avg16-cfar-qualification-20261111/README.md) |
| `avg16-motion-20261111/readings.jsonl` | 3.771 | [avg16-motion-20261111/README.md](avg16-motion-20261111/README.md) · [avg16-motion-20261111/REVIEW.md](avg16-motion-20261111/REVIEW.md) |
| `avg16-motion-rd-20261111/candidates.jsonl` | 1.828 | Use adjacent retained metadata and source tool. |
| `avg16-motion-rd-20261111/cfar.npz` | 5.497 | Use adjacent retained metadata and source tool. |
| `avg16-motion-rd-20261111/diagnostics.jsonl` | 2.014 | Use adjacent retained metadata and source tool. |
| `avg16-motion-rd-20261111/maps.npz` | 5.745 | Use adjacent retained metadata and source tool. |
| `avg16-motion-rd-20261111/tracks.jsonl` | 2.661 | Use adjacent retained metadata and source tool. |
| `avg16-operator-abab-20261111/readings.jsonl` | 4.851 | [avg16-operator-abab-20261111/README.md](avg16-operator-abab-20261111/README.md) · [avg16-operator-abab-20261111/REVIEW.md](avg16-operator-abab-20261111/REVIEW.md) |
| `avg16-operator-empty-abab-20261111/readings.jsonl` | 4.033 | [avg16-operator-empty-abab-20261111/README.md](avg16-operator-empty-abab-20261111/README.md) · [avg16-operator-empty-abab-20261111/REVIEW.md](avg16-operator-empty-abab-20261111/REVIEW.md) |
| `avg16-operator-empty-rd-20261111/candidates.jsonl` | 2.424 | Use adjacent retained metadata and source tool. |
| `avg16-operator-empty-rd-20261111/cfar.npz` | 6.284 | Use adjacent retained metadata and source tool. |
| `avg16-operator-empty-rd-20261111/diagnostics.jsonl` | 2.301 | Use adjacent retained metadata and source tool. |
| `avg16-operator-empty-rd-20261111/maps.npz` | 6.578 | Use adjacent retained metadata and source tool. |
| `avg16-operator-empty-rd-20261111/tracks.jsonl` | 4.689 | Use adjacent retained metadata and source tool. |
| `avg16-placements-20261111/readings.jsonl` | 8.456 | [avg16-placements-20261111/README.md](avg16-placements-20261111/README.md) · [avg16-placements-20261111/REVIEW.md](avg16-placements-20261111/REVIEW.md) |
| `avg16-repeat50-20261111/readings.jsonl` | 10.673 | [avg16-repeat50-20261111/README.md](avg16-repeat50-20261111/README.md) · [avg16-repeat50-20261111/REVIEW.md](avg16-repeat50-20261111/REVIEW.md) |
| `bare-box-b-20261111/phase/frames.jsonl.gz` | 0.069 | [phase/README.md](bare-box-b-20261111/phase/README.md) |
| `bare-box-b-20261111/results.jsonl.gz` | 8.175 | [bare-box-b-20261111/README.md](bare-box-b-20261111/README.md) |
| `clutter-reference-20261111/readings.jsonl.gz` | 17.691 | [clutter-reference-20261111/README.md](clutter-reference-20261111/README.md) · [clutter-reference-20261111/REVIEW.md](clutter-reference-20261111/REVIEW.md) |
| `empty-trained-tone-20261111/background.npz` | 0.555 | [empty-trained-tone-20261111/README.md](empty-trained-tone-20261111/README.md) |
| `empty-trained-tone-20261111/foil-first/background.npz` | 0.555 | [empty-trained-tone-20261111/README.md](empty-trained-tone-20261111/README.md) |
| `empty-trained-tone-20261111/foil-first/frames.jsonl.gz` | 0.084 | [empty-trained-tone-20261111/README.md](empty-trained-tone-20261111/README.md) |
| `empty-trained-tone-20261111/foil-repeat/background.npz` | 0.548 | [empty-trained-tone-20261111/README.md](empty-trained-tone-20261111/README.md) |
| `empty-trained-tone-20261111/foil-repeat/frames.jsonl.gz` | 0.113 | [empty-trained-tone-20261111/README.md](empty-trained-tone-20261111/README.md) |
| `empty-trained-tone-20261111/frames.jsonl.gz` | 0.119 | [empty-trained-tone-20261111/README.md](empty-trained-tone-20261111/README.md) |
| `foil-box-live-20261111/results.jsonl.gz` | 4.583 | [foil-box-live-20261111/README.md](foil-box-live-20261111/README.md) |
| `foil-box-repeat-20261111/phase/frames.jsonl.gz` | 0.147 | [phase/README.md](foil-box-repeat-20261111/phase/README.md) |
| `foil-box-repeat-20261111/results.jsonl.gz` | 5.608 | [foil-box-repeat-20261111/README.md](foil-box-repeat-20261111/README.md) |
| `joint-results-20261111/results.jsonl.gz` | 11.472 | [joint-results-20261111/README.md](joint-results-20261111/README.md) |
| `joint-stationary-80cm-20261111/results.jsonl.gz` | 1.597 | [joint-stationary-80cm-20261111/README.md](joint-stationary-80cm-20261111/README.md) |
| `matched-background-20261111/background.npz` | 0.485 | [matched-background-20261111/README.md](matched-background-20261111/README.md) |
| `matched-background-20261111/frames.jsonl.gz` | 0.119 | [matched-background-20261111/README.md](matched-background-20261111/README.md) |
| `material-control-20261112-background/background.npz` | 0.356 | Use adjacent retained metadata and source tool. |
| `material-control-20261112-background/frames.jsonl.gz` | 0.101 | Use adjacent retained metadata and source tool. |
| `material-control-20261112-phase/frames.jsonl.gz` | 0.142 | [material-control-20261112-phase/README.md](material-control-20261112-phase/README.md) |
| `material-control-20261112-tone/background.npz` | 0.556 | Use adjacent retained metadata and source tool. |
| `material-control-20261112-tone/frames.jsonl.gz` | 0.100 | Use adjacent retained metadata and source tool. |
| `material-control-20261112/results.jsonl.gz` | 7.746 | [material-control-20261112/README.md](material-control-20261112/README.md) |
| `motion-aware-joint-20261111/results.jsonl.gz` | 11.526 | [motion-aware-joint-20261111/README.md](motion-aware-joint-20261111/README.md) |
| `motion-aware-live-20261111/results.jsonl.gz` | 1.641 | [motion-aware-live-20261111/README.md](motion-aware-live-20261111/README.md) |
| `phase-range-20261111/frames.jsonl.gz` | 0.681 | [phase-range-20261111/README.md](phase-range-20261111/README.md) · [phase-range-20261111/REVIEW.md](phase-range-20261111/REVIEW.md) |
| `phase-residuals-20261111/frames.jsonl.gz` | 0.179 | [phase-residuals-20261111/README.md](phase-residuals-20261111/README.md) |
| `rd-association-20261110/first/candidates.jsonl` | 1.573 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/first/cfar.npz` | 4.387 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/first/diagnostics.jsonl` | 1.595 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/first/maps.npz` | 4.591 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/first/tracks.jsonl` | 2.487 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/followup/candidates.jsonl` | 2.725 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/followup/cfar.npz` | 8.334 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/followup/diagnostics.jsonl` | 3.048 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/followup/maps.npz` | 8.716 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-association-20261110/followup/tracks.jsonl` | 4.024 | [rd-association-20261110/README.md](rd-association-20261110/README.md) |
| `rd-avg16-motion-20261110/timelines.npz` | 2.719 | [rd-avg16-motion-20261110/README.md](rd-avg16-motion-20261110/README.md) |
| `rd-cfar2d-20261110/replay/candidates.jsonl` | 1.573 | [rd-cfar2d-20261110/README.md](rd-cfar2d-20261110/README.md) |
| `rd-cfar2d-20261110/replay/cfar.npz` | 4.387 | [rd-cfar2d-20261110/README.md](rd-cfar2d-20261110/README.md) |
| `rd-cfar2d-20261110/replay/diagnostics.jsonl` | 1.493 | [rd-cfar2d-20261110/README.md](rd-cfar2d-20261110/README.md) |
| `rd-cfar2d-20261110/replay/maps.npz` | 4.591 | [rd-cfar2d-20261110/README.md](rd-cfar2d-20261110/README.md) |
| `rd-cfar2d-followup-20261110/replay/candidates.jsonl` | 2.725 | [rd-cfar2d-followup-20261110/README.md](rd-cfar2d-followup-20261110/README.md) |
| `rd-cfar2d-followup-20261110/replay/cfar.npz` | 8.334 | [rd-cfar2d-followup-20261110/README.md](rd-cfar2d-followup-20261110/README.md) |
| `rd-cfar2d-followup-20261110/replay/diagnostics.jsonl` | 2.853 | [rd-cfar2d-followup-20261110/README.md](rd-cfar2d-followup-20261110/README.md) |
| `rd-cfar2d-followup-20261110/replay/maps.npz` | 8.716 | [rd-cfar2d-followup-20261110/README.md](rd-cfar2d-followup-20261110/README.md) |
| `rd-fixed-wall-20261110/maps/diagnostics.jsonl` | 3.975 | [rd-fixed-wall-20261110/README.md](rd-fixed-wall-20261110/README.md) |
| `rd-fixed-wall-20261110/maps/maps.npz` | 12.514 | [rd-fixed-wall-20261110/README.md](rd-fixed-wall-20261110/README.md) |
| `rd-fixed-wall-20261110/review-timelines.npz` | 1.194 | [rd-fixed-wall-20261110/README.md](rd-fixed-wall-20261110/README.md) |
| `rd-repeat-wall-20261110/maps/diagnostics.jsonl` | 3.777 | [rd-repeat-wall-20261110/README.md](rd-repeat-wall-20261110/README.md) |
| `rd-repeat-wall-20261110/maps/maps.npz` | 11.959 | [rd-repeat-wall-20261110/README.md](rd-repeat-wall-20261110/README.md) |
| `rd-repeat-wall-20261110/review-timelines.npz` | 1.144 | [rd-repeat-wall-20261110/README.md](rd-repeat-wall-20261110/README.md) |
| `rx-diagnostics-20261111/results.jsonl.gz` | 34.304 | [rx-diagnostics-20261111/README.md](rx-diagnostics-20261111/README.md) |
| `stopped-support-20261111/results.jsonl.gz` | 9.722 | [stopped-support-20261111/README.md](stopped-support-20261111/README.md) |
| `weak-candidates-20261111/frames.jsonl.gz` | 0.995 | [weak-candidates-20261111/README.md](weak-candidates-20261111/README.md) |
| `weak-candidates-live-20261111/results.jsonl.gz` | 48.642 | [weak-candidates-live-20261111/README.md](weak-candidates-live-20261111/README.md) |
| `weak-features-20261111/frames.jsonl.gz` | 0.379 | [weak-features-20261111/README.md](weak-features-20261111/README.md) |
| `weak-features-live-20261111/results.jsonl.gz` | 48.993 | [weak-features-live-20261111/README.md](weak-features-live-20261111/README.md) |
| `weak-motion-20261111/frames.jsonl.gz` | 0.338 | [weak-motion-20261111/README.md](weak-motion-20261111/README.md) |
| `weak-motion-live-20261111/results.jsonl.gz` | 48.755 | [weak-motion-live-20261111/README.md](weak-motion-live-20261111/README.md) |
