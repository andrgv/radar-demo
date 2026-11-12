# Fresh bare-box / operator-B validation

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Recording: `recordings/rd-gui-20261111-223730-634059/live-001`.
The user explicitly reports a bare cardboard box and operator stationary at B
(described as away from sensor range) throughout quiet holds. The command
enables `--experimental-weak`, using the AVG16 config and native association
metric. This run tests two nominal **50 cm** placements and one **120 cm**
placement. Prior box dimensions/front-face measurement convention are retained
as setup context, not a new measurement. No detector settings were changed.

**The capture is healthy, but the bare-box distance result fails:** baseline,
motion policy and confirmed weak-feature ranges are blank in all 821 scored
target frames. The second 50 cm hold has sustained confirmed CFAR presence,
but no resolved distance. Empty silence does not compensate for target misses.
This fresh result limits the earlier weak-feature development success; no
primary fallback or relaxed gate is justified by this capture.

## Quiet interiors

Times are cumulative from the first saved frame with no fitted offset.
All handling is excluded, then two additional seconds are trimmed per side.
One-second variants are preserved as sensitivity checks, not independent data.
The labels 50 cm A/B identify repeated placements; the operator remains at B.

| Scene | Scored host interval | CA confirmed presence | Baseline distance | Confirmed weak distance |
|---|---:|---:|---:|---:|
| Empty A | 12.18–23.66 s | 0/116 | 0/116 | 0/116 |
| First 50 cm | 48.30–74.96 s | 0/268 | 0/268 | 0/268 |
| Empty B | 91.75–103.71 s | 0/120 | 0/120 | 0/120 |
| Repeated 50 cm | 128.37–155.46 s | **274/274** | 0/274 | 0/274 |
| Empty C | 171.77–183.75 s | 0/121 | 0/121 | 0/121 |
| 120 cm | 205.93–233.59 s | 0/279 | 0/279 | 0/279 |
| Final empty | 247.85–259.83 s | 0/120 | 0/120 | 0/120 |

All 477 scored empty frames have no numeric output in these paths. All scored
target holds also have no numeric weak-candidate selection; increasing temporal
confirmation cannot create a missing or unresolved input measurement.

## Where it fails

**First 50 cm:** CA has no qualifying candidate throughout the 268-frame
interior. Median CA margins in bins 1–3 are approximately −6.5/−7.9/−6.8 dB.
The box changes the raw signal substantially: median bin-2 power is about
14 dB above the preceding empty interval, but stronger farther returns and
the current reference still mask it. Raw OS confirms presence on 45 frames;
23 have a fine inspection value near **86.0 cm**, while 22 are at a fine-support
boundary. The raw-tone optimum is boundary-pinned on all 45, so the weak
selector withholds them. Those OS numbers are not established 50 cm box ranges.

**Repeated 50 cm:** CA and OS presence are confirmed for all 274 frames; native
bins 1–2 have median margins about +1.2/+1.3 dB. Every pooled fine estimate is
withheld as `multiple_fine_peaks`. Fixed every-fifth-frame sampling finds two
comparable maxima around **37 and 83 cm** in all 55 sampled frames. They are
spectral maxima, not demonstrated separate objects. The independent unchanged
raw phase estimator also rejects all 274 current fits as
`poor_single_tone_model`, so it does not provide a validated replacement.

The repeated placement is not a repeat of the first raw scene response:
near-bin power and the stronger farther returns change materially. RX responses
also differ. This is already present in the ADC-derived spectra; it is not
introduced by GUI redraws, feature confirmation or distance history. A constant
offset or smoothing does not resolve the two-peak ambiguity.
In the near-midpoint GUI snapshot, the separate RD fine inspection reads about
82.5 cm, while RX peaks are about 23.1/62.1 cm with the third unresolved.
Copying that RD value into the primary would not establish the reported 50 cm
box range.

**120 cm:** neither CA nor OS supplies a qualifying candidate in any of the
279 frames. Median CA margins in native bins 3–4 are about −15.1/−8.4 dB.
The full RD map chiefly confirms stronger farther scene features; their
existence does not identify the box. The earlier ~32 cm weak return does not
recur with B, but this is a sequential scene comparison, not proof that
operator position alone caused the earlier return. Physical box recovery at
120 cm remains unresolved.

The four empty profiles are comparatively repeatable within this recording.
That makes this a useful matched dataset for investigating background/foreground
signal separation and range modeling, including a held-out empty check. It
does not by itself validate coherent waveform subtraction, which would require
checking phase alignment/stability. Do not lower thresholds or select one of
the two fine peaks just to produce a number.

## Timing and replay audit

There are 2,691 saved frames spanning 266.801 host seconds, all accepted, with
no CRC/header errors, sequence gaps, restarts or recorded timing rejects. One
partial trailing byte is preserved separately. Clock fitting collects 200
frames, then remains frozen for 2,491. Startup p95/max residuals are
2.27/15.03 ms. Post-freeze p95/max relative errors are 140.41/153.09 ms, within
the separate unchanged 500 ms progress bound. Startup fit limits are not
per-frame post-freeze limits.

Supplied durations end at 261.83 s; the additional 4.971 s is unlabeled and
unscored. The [scene manifest](../../configs/bare-box-b-20261111.json) preserves
all original segments and both trim variants. The capture catalog now records
the confirmed B setup; no raw data or saved readings were rewritten.

Replay reproduces the saved baseline, result bank, full association, RX
diagnostics, motion/weak-motion results, original OS selector, phase-fit
inspection, weak selector and weak-feature confirmation. The joint audit also
checks frozen CA and RD against independent standalone processing. Parameters
and processing source are unchanged from collection. This is a fresh
fixed-settings check, not a tuning result or physical accuracy acceptance.

No immediate repeat is needed. Next investigate the raw range/background
model using this matched empty/target sequence; the limiting stages here are
thresholding and unresolved spectral structure, upstream of tracking. First
establish whether separable target-range evidence is present. A model or
tracking change cannot guarantee recovery of a physically weak/mixed return.

[Timeline and CA margins](comparison.png) · [Per-RX raw spectra](spectra.png) ·
[GUI near the repeated-50 midpoint](ambiguous50-gui.png) ·
[Window/timing/parity metrics](capture-review.json) · [Standalone replay audit](report.json) ·
[Unchanged phase comparison](phase/README.md) · [Capture catalog](../../docs/CAPTURE_CATALOG.md)

## Reproduce

Use a fresh output directory:

```sh
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_joint_results \
  --experimental-weak --recordings recordings/rd-gui-20261111-223730-634059/live-001 \
  --output evidence/NEW-BARE-B-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.review_weak_capture \
  --manifest configs/bare-box-b-20261111.json --output evidence/NEW-BARE-B-REVIEW
MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_phase_range \
  --manifest configs/bare-box-b-20261111.json --output evidence/NEW-BARE-B-REVIEW/phase
```
