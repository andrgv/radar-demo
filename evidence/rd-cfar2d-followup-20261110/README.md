# Frozen 2D CFAR follow-up: empty scene and 120↔30 cm

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

Source: `recordings/gui-20261110-221227-169414/live-001`.

[Timeline](timeline.png) · [Motion midpoint maps](motion-midpoints.png) ·
[Stationary spectra and threshold margins](stationary-spectra.png) ·
[Numeric report](report.json) · [Frozen replay metadata](replay/metadata.json)

## Main result

The motion response repeats with the initial 2D CFAR settings unchanged. Both
approaches have negative accepted Doppler maxima, both retreats positive, and
slower trips shift mainly one native Doppler bin versus mainly two on the faster
trips. The two 30 cm holds produce strong stationary close returns. The 120 cm
holds are inconsistent as isolated candidates, and target-absent intervals
demonstrate why an arbitrary accepted candidate cannot identify the added object.
This supports candidate association work, not a claim of reliable obstacle
identity or calibrated distance.

The replay asserts that both detector source hash and settings match the first
AVG16 development replay: guards 1/1, training 3/2 in range/Doppler, minimum 16,
factor 4, Doppler wrap. CFAR uses the full map, including zero Doppler; no empty
reference or background subtraction is used. Every usable range bin is tested.

## Labels and integrity

Video times are used as supplied, without fitting an offset. `1:07:45` is
interpreted as 67.45 s. Movement windows are 31.11–32.82, 48.78–50.63,
64.18–67.45, and 81.14–84.70 s. Primary movement windows trim 0.2 s per side;
stationary target holds trim 2 s per side. Offset sensitivity shifts each
movement interior by -0.5, -0.25, 0, +0.25, +0.5 s without selecting a winner.

Placement is excluded from 13.99 to 18.99 s (five seconds leading up to the
reported placement). Removal is excluded from 95.39 to 100.39 s. Initial
target-absent analysis uses 2–13.99 s. The user confirmed no operator movement
before 106.62 s, so conservative quiet post-removal analysis uses 102.39–106.12 s.
The interval after 106.62 s has the target absent but possible operator motion;
its actual onset is unknown. It is not a matched operator-only control.

There are 1,149 saved frames spanning 113.815 host seconds, sequences 2–1150,
all valid in replay. Every frame logs 272 edges without overflow, and device
error/drop counters remain zero. There are no saved sequence gaps or host
quality rejects. The original wire log has one damaged startup packet at
sequence 1, short by 360 bytes before the first accepted header. It also has
one trailing byte at stop. Neither is hidden by the clean saved-frame audit.

## Motion: signed response at both speeds

The analysis path bins are 1–4, chosen from the supplied 30–120 cm endpoints
and nominal 35 cm range grid. This wider close-range probe is declared for
this recording because the target reaches 30 cm; it does not change CFAR's
search region or thresholds. These counts describe candidate outputs rather
than confirmed target-detection rates.

| Movement | Buffered host window | Frames | Expected-sign nonzero local maximum, bins 1–4 | Opposite sign | Nonzero peak bin offsets |
|---|---|---:|---:|---:|---|
| Fast approach | 31.31–32.62 s | 13 | 9 | 0 | -2 in 6 frames, -1 in 3 |
| Fast retreat | 48.98–50.43 s | 15 | 11 | 0 | +2 in 6 frames, +1 in 5 |
| Slow approach | 64.38–67.25 s | 29 | 13 | 0 | -1 in 13 frames |
| Slow retreat | 81.34–84.50 s | 32 | 19 | 0 | +1 in 19 frames |

All five timing-offset checks retain the expected sign and have no opposite-sign
local maxima in these path bins. Candidate coverage changes with the offset.
The nominal travel averages from 90 cm divided by video duration are about
0.53, 0.49, 0.28, and 0.25 m/s, respectively; they are not instantaneous
radar-velocity ground truth. The smaller slow-motion Doppler shift is useful
qualitative evidence. Operator/body contributions and multipath remain possible.
Slower peaks lie closer to zero, where stationary leakage and the short Hann
record make separation harder. No m/s axis or calibrated speed error is claimed.

## Stationary targets and recorded GUI output

For each nominal endpoint, the diagnostic endpoint bins are the floor/ceiling
of nominal range divided by range-bin spacing, clipped to usable bins. This
gives bin 1 for 30 cm and bins 3–4 for 120 cm. Passing a cell or finding a local
maximum in those bins is still not proof of target identity.

| Hold | Frames | Recorded 1D numeric-distance frames | Conditional median 1D distance | 2D zero-Doppler accepted cell in endpoint bins | 2D zero-Doppler local maximum in endpoint bins |
|---|---:|---:|---:|---:|---:|
| 120 cm A | 82 | 0 | — | 19 | 19 |
| 30 cm A | 120 | 120 | 35.1 cm | 120 | 120 |
| 120 cm B | 97 | 3 | 105.8 cm | 88 | 60 |
| 30 cm B | 98 | 98 | 37.8 cm | 98 | 98 |
| 120 cm C | 67 | 0 | — | 67 | 12 |

The final far hold is particularly informative: nominal-range cells pass CFAR
throughout the window, but most are not local maxima because they form part of
a broader stationary ridge. Local-maximum grouping therefore discards a possible
target shoulder. In contrast, the first far hold is weak even at the cell-test
stage. The raw spectra differ between far holds; association alone cannot
create a missing, separable measurement. Geometry, target reflectivity, operator
position and multipath are possible causes, not established explanations.

The 30 cm result is a useful near-range detection signal, but the GUI's
35.1/37.8 cm medians are not calibrated 30 cm readings. The native grid is about
35 cm, DC is excluded, and the first-bin/HPF response limits interpretation.
Do not fit a distance offset while reflector identity at other ranges remains
unresolved. The report separates confirmed-presence flags from numeric output:
some GUI frames have presence without a valid fine-distance estimate.

## Target-absent intervals and operator motion

| Interval | Frames | Recorded 1D numeric outputs | 2D zero-Doppler local maximum in path bins 1–4 | 2D nonzero local maximum in path bins 1–4 |
|---|---:|---:|---:|---:|
| Initial target absent | 121 | 6 | 28 | 2 |
| Quiet after removal | 38 | 0 | 0 | 0 |
| Target absent, operator motion possible | 73 | 17 | 40 | 3 |

The initial 1D numeric outputs have a conditional median of 116.2 cm even though
the added target is absent. The quiet post-removal window has no path-bin
outputs in either method. Later outputs occur in the operator-confounded
interval, with 1D conditional median about 48.9 cm. These are not reliable
added-target presence decisions. Fixed walls and scene reflectors can be
legitimate radar obstacles, so the table must not be read as a generic
false-obstacle probability. Full-range weak candidates remain visible in the
timeline; the path-bin summary does not suppress them.

## Consequence for the next software step

Keep the current AVG16 firmware. Use this recording alongside the earlier run
for candidate quality and association, including motion-to-stop transitions and
ambiguous static ridges. Association should consume cell/group support as well
as local maxima, make loss/ambiguity explicit, and avoid displaying a held or
predicted distance as a fresh measurement. A stationary target versus stationary
clutter can require additional range/angle/scene information when the raw return
is not separable. Fine-distance calibration remains deferred.

The new data are sufficient for that engineering step. A later matched
operator-only control and repeatable 120 cm target placement would help resolve
reflector identity, after a concrete association/quality prototype is frozen.
No threshold sweep, range blacklist, distance fit or firmware change was made
to improve this follow-up result.

## Reproduce

Use a new replay output directory:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/mpl-radar ./range-v1 range-doppler \
  recordings/gui-20261110-221227-169414/live-001 --detector cfar2d \
  --output evidence/rd-cfar2d-followup-20261110/replay
MPLCONFIGDIR=/private/tmp/mpl-radar .venv/bin/python -m tools.review_cfar_2d_followup
```
