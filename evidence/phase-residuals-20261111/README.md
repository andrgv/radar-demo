# Background-component and RX disagreement investigation

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The investigation finds a real limitation of the global single-tone quality
check: stronger farther returns consume substantial raw waveform energy. But
fitting a separate farther component does **not** consistently recover the
reported physical range. It can sharply lower residuals while retaining biased
or support-boundary estimates. The live baseline and phase quality gates remain
unchanged. No accepted-distance policy was added.

## Protocol and implementation

Ten recordings / 13,989 saved frames were replayed. Frozen CA presence,
selected bin, fine range and reason match saved readings on every frame.
Detailed raw-model work uses 796 samples: every tenth frame in each existing
primary quiet interior, anchored at the window start. These counts must not
be read as new full-frame detection coverage. Motion/handling intervals and
approximate operator subwindows are excluded.

The diagnostic fits a shared candidate frequency plus an independently chosen
farther frequency per RX, with separate DC/cos/sin amplitudes per chirp/RX.
Candidate bounds are the unchanged current CA/OS group half-bin support.
Nuisance bounds come from support plus a one-bin separation through half a bin
below Nyquist, not the labeled wall. The fixed grids are 64 candidate and 16
nuisance steps per native bin, with at most four alternating grid updates and
candidate refinement. This remains a limited two-component hypothesis with
coarse nuisance quantization, not a validated model of the scene or receiver.

CA and OS are modeled only with their own confirmed group. A separately marked
fixed-mask probe also runs with no detection, allowing empty and missed-target
failure checks. It is not a presence detector or a new candidate selector.
No label was fitted, search support expanded, window moved, threshold loosened,
or background waveform learned. Extra parameters improve in-sample fit by
construction; a lower residual is not independent validation.

## Findings

| Case / nominal hold | Diagnostic samples with CA support | Single residual median | Two-component residual median | Result |
|---|---:|---:|---:|---|
| `093723/live-004`, 50 cm A1 | 14 | 69.9% | 39.2% | 12 support-boundary optima; RX span about 34.8 cm |
| Same, B1 | 13 | 66.6% | 38.6% | 13 boundary optima |
| Same, A2 | 13 | 68.1% | 41.4% | 9 boundary optima |
| Same, B2 | 13 | 66.8% | 39.3% | 13 boundary optima |
| `093723/live-003`, first 50 cm hold | 27 | 30.3% | 20.9% | Fitted median remains 59.5 cm |
| `093723/live-006`, second 50 cm hold | 10 | 37.4% | 30.6% | Fitted median remains 64.2 cm |
| Bare box `143819/live-003`, first 50 cm | 19 | 58.5% | 27.3% | Fitted median moves to 63.1 cm, not the supplied 50 cm |
| Bare box, repeated 50 cm | 13 | 71.1% | 39.0% | Large RX disagreement and unstable near fit remain |
| `093723/live-005`, target absent, fixed-mask probe | 52 probes; no CA support | 68.6–74.3%* | 28.9–30.3%* | All 52 probe optima at artificial lower boundary |
| `133435/live-001`, approximately 80 cm, fixed-mask probe | 72 probes; no CA support | 85.4% | 23.9% | 31 boundary optima; 9 competing-optimum cases; RX span median 55.7 cm |

*Range of the four operator-window medians, rather than a pooled percentile.

Full recording paths and every window's metrics are retained in
[report.json](report.json) and [the capture catalog](../../docs/CAPTURE_CATALOG.md).
The corresponding original recordings include
`recordings/gui-20261111-093723-246315/live-003`,
`recordings/gui-20261111-093723-246315/live-004`,
`recordings/gui-20261111-093723-246315/live-005`,
`recordings/gui-20261111-093723-246315/live-006`,
`recordings/rd-gui-20261111-143819-360020/live-003`, and
`recordings/rd-gui-20261111-133435-428121/live-001`.

The fixed-target A/B run illustrates two distinct effects. Its fitted nuisance
components cluster near 2.2–2.3 m and account for much of the original residual.
Yet after that adjustment, typical conditional receiver optima remain near
52 cm, 41–43 cm, and the 17.4 cm lower support boundary. All 53 sampled fits
have at least one RX at a support boundary, and 47/53 shared candidate optima
also reach a boundary. The 17.4/52.1 cm endpoints are imposed search boundaries,
not new measured objects. Broad/mixed spectra remain after removing two tones.

The target-absent control has a lower two-component residual than the real
fixed-target control, despite no qualifying CA detection. It is a direct
counterexample to treating the improved global residual as presence or range
accuracy. The approximately 80 cm probe similarly spans 17.4–81.9 cm at its
5th–95th percentiles; reporting its occasional near-80 optimum as target
recovery would hide failures.

Both foil-box recordings change relatively little. Sampled two-component hold
medians are approximately 50.4 / 46.3 / 123.1 cm in `200448/live-001`, and
51.2 / 48.6 / 122.1 cm in `200448/live-002`. These are provisional diagnostic
fits, not promoted replacements for either the existing estimator or the
unchanged accepted single-tone comparison. The added background component
does not explain away the older 59–64 cm bias.

Receiver differences establish model/scene inconsistency, not a defective RX,
a proven RF calibration error, verified multipath, or known reflector identity.
No Doppler component was selected by this model, so its values must not be
copied into individual feature tracks.

## Decision and next step

Keep live distances and frozen quality policies unchanged. The concrete new
diagnostics preserve unique candidate versus nuisance energy, per-RX optima,
boundaries, competing optima and grid convergence rather than classifying a
fit as trustworthy solely because it explains more total energy.

Next expose those measurement limitations alongside the existing GUI results,
using bounded-cost current-frame RX diagnostics rather than running this
expensive exploratory model in the live loop. Then investigate candidate
support for weak target returns with the existing matched empty controls.
Another identical foil-box hold capture is unnecessary for this step.

## Artifacts and reproduction

[RX residual example](fixed-target-rx-residuals.png) ·
[All 54 fixed-midpoint RX snapshots](rx-residual-snapshots.pdf) ·
[Window metrics / hashes](report.json) · [Sample decisions (archived)](../ARCHIVED_ARTIFACTS.md#archived-files) ·
[Method and limits](../../docs/PHASE_RESIDUAL_INVESTIGATION.md)

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.investigate_phase_residuals \
  --output evidence/NEW-PHASE-RESIDUALS
```

Use a fresh output directory. Synthetic tests recover a weak candidate in the
presence of a strong separated tone and demonstrate that a low global residual
can coexist with a false interior candidate optimum when both real tones lie
outside its support. The model intentionally has no accepted `range_m` output.
