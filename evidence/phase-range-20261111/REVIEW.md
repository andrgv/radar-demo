# Phase-aware range comparison review

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The candidate-constrained raw-tone fit improves the anomalous second foil-box
placement, but fails the broader coverage/accuracy check for live promotion.
This is a development comparison, not independent acceptance data. The default
GUI distance, CFAR thresholds, motion policy and firmware remain unchanged.

Nine recordings / 11,623 frames were replayed. Recomputed CA presence, selected
bin, fine range and decision reason match the saved baseline for every frame.
The fit uses only the current confirmed group's support, with no label fit,
baseline learning, threshold sweep, held value or prediction. All initial
quality settings were fixed before this comparison.

| Foil-box scored hold | Existing peak median | Phase-fit median | Phase numeric coverage |
|---|---:|---:|---:|
| First 50 cm | 51.38 cm | 50.74 cm | 173/173 |
| Repeated 50 cm | 38.05 cm | 46.74 cm | 168/168 |
| 120 cm | 122.66 cm | 122.94 cm | 170/170 |

On the repeated 50 cm hold, mean absolute difference from nominal placement
falls from 12.00 to 3.22 cm. The user estimates placement uncertainty of a few
cm, so this is not an established 3.22 cm instrument-accuracy claim. The far
hold changes little and its placement difference slightly increases. This
supports a phase-dependent near-DC FFT peak-location contribution, rather than
an across-the-board offset correction.

Generalization limits are material:

- Fixed-target operator A/B/A/B: existing peak is numeric in all 513 scored
  frames near 47 cm; the phase fit rejects all 513.
- Bare-cardboard 50 cm holds: all 310 current CA detections are rejected as
  `poor_single_tone_model`. The missing 120 cm target remains missing.
- The original repeated-50 run's first hold accepts 270/270 frames near 59.1 cm;
  the manually rolled run's second 50 cm hold accepts 100/100 near 64.1 cm.
  Passing a single-tone check therefore does not certify correct physical range.
- The original sweep's 50 cm hold accepts only 1/176 frames, near 76 cm.
  Sparse accepted values must be read together with coverage, not summarized
  as improved accuracy.
- The ~80 cm stationary failure still has no CA candidate and no phase output.
  This estimator cannot repair a detection-stage miss or select a weak target
  from a stronger scene return.

Across 2,187 scored target-absent frames, CA has zero outputs and therefore
supplies no fit candidates. That result is inherited from CA, not independent
empty-scene rejection by the estimator. OS has 637 peak outputs in those
interiors and zero accepted phase fits. In the dedicated no-target A/B control,
403 OS peak outputs are all rejected at the fit-support boundary. This is a
useful regression observation; it does not turn the fit into a validated
presence discriminator or justify promoting OS. Both target and empty failures
remain in the evidence rather than expanding support or loosening gates to fit
them.

The fit's measured per-session p95 time is at most 1.43 ms on this machine
(including early rejections and cache use); this is an offline timing observation,
not a new live timing qualification. Synthetic tests cover phase/chirp/RX
variation, competing tones, noise, support boundaries and insufficient RX
agreement. The estimate is not Doppler conditioned and must not be assigned
to separate RD feature IDs.

Keep this as an offline estimator comparison. The next useful new data is the
unchanged-setting foil-box repeat described in
[the experiment guide](../../docs/PHASE_RANGE_EXPERIMENT.md). Better modeling
must address the existing normal-target rejection and biased accepted returns
before replacing the live readout.

[Window metrics](README.md) · [Full report and hashes](report.json) ·
[Timeline comparison](comparison.png) · [Per-frame decisions (archived)](../ARCHIVED_ARTIFACTS.md#archived-files)
