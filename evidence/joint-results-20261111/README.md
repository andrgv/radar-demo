# Joint 1D/RD result-layer regression

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The shared adapter was audited on all 4,764 frames of live-003 through live-006
with frozen settings. Every 1D decision, reason and fine distance matches both
the saved live result and an independent scalar detector. Every 2D accepted-cell
mask and feature-association report matches the independent standalone RD path.
No firmware programming or physical live capture was performed.

| Recording | Frames | Automatic primary distance frames | Frames with an RD fine inspection estimate |
|---|---:|---:|---:|
| live-003: repeated 50 cm / operator change | 2,194 | 895 | 2,173 |
| live-004: fixed target / A-B-A-B | 946 | 944 | 944 |
| live-005: target absent / A-B-A-B | 867 | **0** | 865 |
| live-006: manual 120↔50 cm motion | 757 | 468 | 754 |

Counts are whole-recording algorithm outputs, not labeled target-detection
accuracy. In particular, the target-absent recording's RD refinements remain
inspectable scene features and never create a primary distance. Returning a
number for an RD feature does not establish a physical object or correct range.

Median processing time per session is approximately 5.0–6.8 ms; 95th percentile
is approximately 7.0–8.5 ms on this machine. These measurements exclude serial,
JSON export, GUI redraw and sensor-to-screen latency. Outliers reach 41.2 ms.

Synthetic tests additionally check independent Doppler-conditioned ranging of
a weaker moving reflector beside a stronger wall in the same native range bin,
multiple maxima without arbitrary deduplication, nearby competing Doppler peaks
withheld from refinement, independent confirmation of multiple 1D groups,
RD-only primary exclusion, and rejection/reconfirmation. Existing numerical,
stream-recording, timing, timeout, and GUI clearing tests remain applicable.

[Settings, hashes, counts and timings](report.json) ·
[Per-frame results (gzip JSONL) (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) ·
[Target-present UI](../joint-results-ui-20261111/measured-return.png) ·
[Empty-control UI](../joint-results-ui-20261111/empty-control.png)

Usage and schema: [JOINT_RANGE_DOPPLER.md](../../docs/JOINT_RANGE_DOPPLER.md).

Reproduce into a new directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --output evidence/NEW-JOINT-REVIEW
```

The original standalone modes and detector settings remain unchanged. This is
an inspectable experimental result layer, not independent physical detection
acceptance or a new automatic nearest-RD-feature policy.
