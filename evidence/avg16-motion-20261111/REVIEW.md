# Manual 120↔50 cm motion with operator at A

**Bulk artifacts archived:** per-frame exports and/or numerical arrays for this
report are kept in the external evidence backup and ignored in Git. Local copies
may still exist. See [archive paths, hashes, restoration and regeneration notes](../ARCHIVED_ARTIFACTS.md).

The movement gives useful signed RD evidence, but neither 1D range consistency
nor RD physical-target identity is accepted. Frozen 2D processing retains more
features, including a persistent close feature in the target-absent control.
Do not implement unconditional OR/nearest-feature fusion from these results.

## Timing and integrity

Labels are absolute host seconds from the first saved frame: first 120 cm hold
ends at 11.27; 11.27–11.46 is unscored; approach 11.46–about 13; 50 cm hold
13–26.62; retreat 26.62–28.05; 120 cm hold 28.05–42.57; slower approach
42.57–45.15; 50 cm hold 45.15–59.09; slower retreat 59.09–61.76; final 120 cm
hold 61.76–75.174. The first stop time is approximate. Holds trim two seconds
per side (one-second summaries also exported); motions trim 0.2 seconds per
side. No video offset was fitted. Manual rolling means arm/hand/operator
contributions cannot be excluded, even with the operator nominally at A.

All 757 recomputed 1D decisions, fine ranges and reasons match saved live
results. Capture reports zero rejected frames, CRC/sequence errors or device
errors/drops. There are 2,587 partial bytes at capture stop; complete saved
frames remain valid. All 757 frames are valid in RD replay. This does not
independently verify absolute frame age or physical chirp timing/carrier.

## Stationary 1D baseline

| Hold | Numeric / frames | Median cm | 5th–95th cm |
|---|---:|---:|---:|
| First 120 cm | 73/73 | 125.8 | 124.6–126.8 |
| First 50 cm | 25/97 | 35.4 | 34.0–39.7 |
| Middle 120 cm | 8/105 | 130.7 | 128.4–133.2 |
| Second 50 cm | 100/100 | 60.9 | 59.2–62.3 |
| Final 120 cm | 94/94 | 131.2 | 128.2–134.5 |

Both near and far holds can fail after replacement despite the unchanged
reported operator position. The first 50 cm hold has 42 candidate frames, of
which 25 confirm. The middle 120 cm hold has 24 candidate frames, of which
eight confirm, and a longest numeric gap of 6.5 seconds. Failures occur at
threshold/confirmation, not unresolved fine estimation. No constant correction
can reconcile the two 50 cm medians. Conditional numeric statistics do not
establish reflector identity.

## Signed motion evidence from frozen RD

| Motion | Frames | 1D numeric frames | Confirmed expected-sign RD feature frames, bins 1–4 |
|---|---:|---:|---:|
| Faster approach | 11 | 0 | 10 |
| Faster retreat | 11 | 5 | 9 |
| Slower approach | 22 | 11 | 18 |
| Slower retreat | 23 | 13 | 17 |

Both approaches produce negative phase progression and retreats positive,
consistent with earlier motion recordings. No opposite-sign local maximum
occurs in these trimmed path windows. Counts are motion-sensitive features,
not verified object-detection rates or calibrated velocities. Physical speed
remains unverified; the manually rolled object and operator are not separable
ground-truth identities.

RD also retains a confirmed zero-Doppler endpoint-region feature on every
trimmed stationary frame. The near holds peak in native bin 1 and then bin 2;
the far holds peak in bin 4. Native bins are not fine-distance replacements.
Additional close stationary features can coexist with the far return.

## Necessary target-absent comparison

The same RD CFAR/association settings and source were replayed on live-005
without a target. All four trimmed A/B quiet intervals retain a confirmed
zero-Doppler bin-1 feature: 122/122, 128/128, 126/126, 122/122, or 498/498 total.
There are no confirmed nonzero features in those quiet path intervals. The
1D baseline had zero outputs there. This need not be a false physical obstacle
(the scene contains real reflectors), but it cannot identify the added target.

Consequently, RD's higher stationary feature coverage cannot be counted as
target-recovery accuracy. The first near hold's bin-1 feature is particularly
unsafe to interpret as independent recovery of the 50 cm object. Keep source,
support, association and range validity explicit in the combined result bank;
do not automatically turn every RD-only feature into the primary distance.

These recordings are enough to proceed with the unified result/diagnostic
implementation without another repeat. Keep independent acceptance captures
for after that implementation/settings are frozen. Existing data can evaluate
motion-conditioned refinement and expose nuisance features without tuning to
make this scene pass.

[1D/RD timeline](rd-comparison.png) · [Metrics, settings and control](rd-comparison.json) ·
[1D window metrics](report.json) · [1D threshold diagnostics](diagnostics.json)

Reproduction inputs are `configs/avg16-motion-20261111.json`, the original
live-006 recording and the live-005 target-absent recording. Use
`tools.qualify_avg16_cfar` for the 1D export and `radar_min range-doppler
RECORDING --detector cfar2d --associate --output NEW-DIRECTORY` with
`MPLBACKEND=Agg` for RD. The fixed-path `tools.review_avg16_motion_20261111`
checks frame alignment, saved-live 1D parity and RD control source/settings
parity before generating the comparative report/plot. All detector settings
remain unchanged.
