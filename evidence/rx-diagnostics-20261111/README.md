# Live GUI receiver diagnostics: regression review

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The joint GUI now exposes per-RX current range peaks/unresolved states, their
spread and a single-tone residual at the existing pooled FFT range. Confirmed
1D support defines the scope. Colored peak markers supplement the existing
range profile, and candidate selection changes inspection immediately. The
default and motion-aware distance policies, detection, thresholds and firmware
are unchanged. See [usage and interpretation](../../docs/RX_DIAGNOSTICS.md).

## Regression and limits

All 13,989 frames across ten preserved recordings pass the joint replay audit:
the primary exactly matches the saved/independently computed frozen baseline;
RD masks and association match their standalone algorithms. All previously
saved joint result banks also compare exactly, with the comparison count
preserved per recording. Historical v1/v2 motion-policy differences remain the
previously documented differences; this change does not modify either policy.

The new diagnostics are separate from `results` and never feed a selector.
The review verifies current sequence and confirmed-group support. Focused
tests cover receiver disagreement, background/model mismatch, zero-energy RX,
unresolved pooled range, confirmation, rejection/recovery, saved readings and
GUI selection/staleness clearing. The complete 172-test suite passes.

| Quiet case | RX inspection result |
|---|---|
| Fixed 50 cm operator A/B control | All 513 frames have a waveform-mismatch note; 482 also have RX peak disagreement |
| Repeated-50 first hold reading near 59 cm | RX disagreement in all 270 frames |
| Manually rolled run's second 50 cm hold reading near 64 cm | RX disagreement in 99/100 frames |
| Bare cardboard first 50 cm hold | Both RX disagreement and waveform mismatch in all 184 frames |
| Latest foil repeat: first 50 cm / repeated 50 cm / 120 cm | No notes in 219/219, 216/217 and 221/221 frames; one unresolved RX in the remaining near frame |
| Dedicated no-target A/B control | No confirmed 1D group and no inspection peaks in the quiet intervals |
| Approximately 80 cm stationary detection failure | No confirmed 1D group; no invented receiver distance |

These are diagnostic-note counts, not validated error-classification rates.
For example, the original foil run's first 50 cm hold has disagreement notes
in all 173 frames despite a pooled median near 51 cm. Notes must not be used
as an unvalidated detector gate. The GUI explicitly labels inspection-only
status, and absence of a note does not certify accuracy.

The residual here is evaluated at the current FFT range; it is intentionally
different from the optimized single-tone residual in the earlier offline
investigation. It can expose FFT peak bias as well as background mixtures.
It does not distinguish those physical causes, select a Doppler component or
produce a calibrated confidence interval.

## Display review and processing cost

[Fixed-target screenshot](fixed-target-gui.png) shows a numeric baseline beside
an unresolved RX, divergent other peaks and a mixed-waveform note.
[Foil screenshot](foil-gui.png) shows the existing motion-aware/baseline readout,
three resolved RX markers and no current diagnostic note. Layout and labels
were inspected on replay; no hardware capture was required or performed.

The existing dense FFT is reused. In isolated 200-iteration per-group checks,
diagnostic p50/p95 times were approximately 0.21/0.42 ms for the fixed-target
example and 0.28/0.44 ms for the foil example. These exclude the existing FFT
and UI, and are observations on this machine rather than live timing acceptance.
The offline nuisance search is not part of the live path. Startup clock,
freshness and 4 Hz expensive redraw limits remain unchanged.

[Joint audit and processing measurements](report.json) ·
[Window diagnostic counts and parity checks](receiver-review.json) ·
[Per-frame results (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) · [Isolated diagnostic timing](diagnostic-timing.json)

## Reproduce

Run `tools.evaluate_joint_results` with the recording paths listed in
`report.json` and a fresh `--output` directory, then summarize that directory:

```sh
.venv/bin/python -m tools.review_rx_diagnostics --output evidence/NEW-RX-REVIEW
```

For a replay screenshot:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl QT_QPA_PLATFORM=offscreen ./range-v1 rd-gui \
  --replay recordings/gui-20261111-093723-246315/live-004 --view-range-bins 8 \
  --snapshot evidence/NEW-RX-REVIEW/fixed-target-gui.png --snapshot-frame 90
```

Next investigate weak-target candidate support and selection against the matched
empty/operator controls. Keep these new inspection notes separate from any
proposed acceptance gate until that gate has its own replay and independent
validation. Another identical foil hold capture is not needed first.
