# Material study recordings

This archive preserves all 111 files (about 879 MB uncompressed) from the
November 8 window/drywall work, including initial attempts, repeated recordings,
live classification tests, raw serial bytes and transport logs. Incomplete
attempts are retained as experiment history, not usable training examples.

Transport logs exceed GitHub's individual-file size limit, so the recordings
are compressed and divided into parts smaller than 50 MiB.
`manifest.json` lists every part's size and SHA-256 checksum. Keep both parts.

From the repository root, restore the original `recordings/` paths with Python
3.12 or later:

```bash
python3 tools/restore_material_recordings.py
```

The script verifies checksums and refuses to overwrite existing recording
folders. To verify without extracting, use:

```bash
python3 tools/restore_material_recordings.py --check
```

Alternatively restore into a separate clean directory using `--destination`.

The saved model and its reports are tracked directly under
`artifacts/material-glass-drywall-pilot/`. After installing `.[material]` and
restoring the recordings, reproduce the training with:

```bash
python3 -m radar material-train experiments/materials/window-drywall-repeat.json artifacts/material-reproduced --bins 2 3 4
```

The original OPEN/CLOSED notes were inaccurate: OPEN faced drywall and CLOSED
faced a closed window. The corrected labels are in the experiment manifest.
The original drywall training distance is unknown. Live test file names do not
independently establish that the physical surfaces differed from training.
During `new-wall-test-01`, the user adjusted the sensor; `new-wall-test-02` was
the stationary repeat. Retain all three later tests when reviewing results.

The November 8 progress-log snapshot is in
`docs/progress/Wavvy_Progress_Report_Log.docx`. Its push status describes the
state when the log was created, before this branch publication.
