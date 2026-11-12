# CFAR and range–Doppler: stage review and next steps

**Fixed-position material checkpoint (November 12):** bare → foil → bare at
50 cm with operator B and unchanged footprint/orientation. All 280 foil frames
have baseline ~46.1 cm and raw-model ~51 cm; neither bare hold has a main range.
The second bare hold nevertheless produces 257/274 confirmed weak values near
29.1 cm, rejected by both raw models. This limits scene-feature confirmation,
not just the original CFAR. No primary promotion or immediate capture repeat.
Next expose current model quality and a separate model-qualified experimental
range/status for diagnostic/demo use. See
[capture evaluation](../evidence/material-control-20261112/README.md).

**Empty-trained nuisance checkpoint (November 12):** exactly one frozen
background tone/RX, with variable current coefficients, gives no accepted
bare-box ranges in 821 target frames. The unchanged model gives plausible
ranges in all 1,168 foil target frames, with no inspection outputs in 1,197
held-out empty frames. Bare empty-scene underfit and one foil RX nuisance
boundary remain explicit. No primary/GUI promotion or global range correction.
Next collect a same-position bare/foil/bare sequence at 50 cm; see
[evidence](../evidence/empty-trained-tone-20261111/README.md) and
[capture protocol](EMPTY_TRAINED_BACKGROUND.md). Earlier checkpoints below
preserve the development sequence.

**Matched background checkpoint:** first-empty-trained fixed power/waveform
subtraction distinguishes substantial scene changes but recovers no blind
peak within half a native bin of the 821 scored nominal target frames. Later
empty holds fail the waveform-change control. No live fallback is added.
The follow-up empty-trained nuisance test is complete above; see
[fixed-reference experiment](../evidence/matched-background-20261111/README.md).

**Fresh bare-box/B checkpoint:** capture `223730/live-001` is valid for all
2,691 frames, but has zero numeric baseline/confirmed-weak distances in 821
scored target frames. Repeated 50 cm gives 274/274 confirmed CA-presence frames
with multiple fine peaks near 37/83 cm; first 50 cm and 120 cm fail thresholding.
All 477 scored empty frames stay blank. Independent replay reproduces every
saved stage without settings changes. Prior weak-feature confirmation does
not generalize into a reliable bare-box distance backend here. Next examine
background/foreground range modeling on this stable-empty dataset, including
held-out empty controls and phase-alignment checks before any waveform
subtraction. No further confirmation tuning or immediate capture repeat is
indicated. See [fresh review](../evidence/bare-box-b-20261111/README.md).

**Weak-feature confirmation checkpoint:** `--experimental-weak` now confirms
consecutive supported scene peaks into separate `weak:` IDs with a current
inspection range and gap-preserving history. It retains 267/714 frames in the
~80 cm stationary case, with zero points in 3,045 scored empty frames. It also
confirms 15 near-range samples during the bare-box 120 cm hold. The user has
now confirmed operator A / within range for that hold, so this is an
operator-confounded correspondence case, not established false-obstacle data.
The main distance and original strong/motion policies remain unchanged; all
188 tests pass. Next validate bare-box 80/120 cm with matched empty intervals
and the operator fixed at B. See [method/capture protocol](WEAK_FEATURE_CONFIRMATION.md)
and [metrics](../evidence/weak-features-20261111/README.md).

**Motion-link checkpoint:** a strict same-feature weak-stop link and recorded
inspection status are implemented under `--experimental-weak`. The fixed
15,534-frame replay adds only three isolated points and no scored stationary
hold coverage, so no main readout change is justified. In the weak ~80 cm
interior, 290/297 candidates are below the RD track-birth margin and seven lack
motion history; the 19 wrong-range candidates in the 120 cm hold are also
below that margin. Do not simply lower it or require motion for all stationary
detection. Next separate guarded weak-feature confirmation from physical
object correspondence, retaining both cases. All 183 tests pass. See
[method/status](WEAK_MOTION_LINK.md) and
[event/stage review](../evidence/weak-motion-20261111/README.md).

**Weak-candidate checkpoint:** a fixed OS/RD/raw-peak geometry selector and
optional `--experimental-weak` GUI comparison are implemented. In 15,534 replayed
frames across eleven captures, it reduces old OS+RD outputs from 774 to zero in
3,045 scored empty frames and retains 297 candidates in the previously blank
714-frame ~80 cm interior. But it selects ~32 cm on 19 frames during a 120 cm
bare-box hold. It remains inspection-only; no primary fallback is promoted.
All 177 tests pass. Next investigate motion-linked weak support and identity
through stopping/removal, retaining this failure rather than tuning it away.
See [method and usage](WEAK_CANDIDATE_EXPERIMENT.md) and
[comparison](../evidence/weak-candidates-20261111/README.md).

**RX display checkpoint:** current-frame per-RX peaks, unresolved states, spread
and pooled-FFT single-tone residual are now recorded and displayed in the joint
GUI. They reuse the dense spectrum and remain inspection-only. The 13,989-frame
regression preserves baseline, RD and existing joint results; all 172 tests pass.
The older biased holds visibly show RX disagreement, while useful foil returns
can also receive notes, so these are not a new detection gate. Next investigate
weak-target candidate support/selection with the matched empty controls. See
[usage](RX_DIAGNOSTICS.md) and [review](../evidence/rx-diagnostics-20261111/README.md).

**Residual/RX checkpoint:** the next investigation audits 13,989 frames in ten
recordings and applies a candidate-plus-background diagnostic to 796 fixed-stride
quiet samples. Fitting a farther component lowers global residuals but leaves
receiver disagreement, boundary optima and older 59–64 cm biased near holds.
Empty probes can have lower residuals than real targets. Keep live distances
unchanged; RX/model limitations are now exposed as quality evidence. Investigate
weak-target candidate support against the matched controls. See
[method and findings](PHASE_RESIDUAL_INVESTIGATION.md) and
[evidence](../evidence/phase-residuals-20261111/README.md).

**Phase-estimator checkpoint:** a candidate-constrained real-tone/DC estimator
and nine-recording comparison are now implemented (11,623 frames). The foil-box
hold medians move from 51.4 / 38.1 / 122.7 cm to 50.7 / 46.7 / 122.9 cm,
supporting the near-DC FFT peak-bias diagnosis. However, fixed model checks
reject all 513 scored fixed-target A/B frames and all current bare-cardboard
hold detections; other accepted holds still have substantial bias. Keep this
offline rather than replacing the live distance or loosening gates to force
coverage. No detector, firmware or GUI policy changed. See the
[experiment and independent repeat protocol](PHASE_RANGE_EXPERIMENT.md) and
[comparison review](../evidence/phase-range-20261111/REVIEW.md).

The independent foil repeat (`200448/live-002`) now gives complete scored
target coverage (657/657) and blank empty interiors (0/520). Phase medians are
51.4 / 48.6 / 122.1 cm versus baseline 48.0 / 49.2 / 124.2 cm; this is useful
foil-scene repeat evidence, not consistent improvement in every hold or a fix
for earlier model failures. Investigate residual scene/RX components next,
rather than requesting another identical capture. See the
[repeat review](../evidence/foil-box-repeat-20261111/README.md) and
[capture setup catalog](CAPTURE_CATALOG.md).

The retreat/hold investigation now includes an optional quadratic sub-bin
association cost, with native gates unchanged. It recovers two current frames
in the latest second retreat without scored-control coverage regressions, but
does not repair wrong-reflector jumps. Biased hold distances are already present
in raw, RX-dependent spectra. Those observations motivated the supported
flat-reflector captures at repeated 50 cm and 120 cm placements reviewed above;
no offset correction is justified. See
[investigation and capture protocol](SUBBIN_ASSOCIATION.md).

**Motion-readout milestone:** an opt-in measured-only `--motion-aware` policy
now exposes refined current RD distances after two same-feature/same-sign motion
measurements and continues that same ID through supported zero-Doppler stops.
It clears misses/ambiguity and retains the frozen baseline comparison. History
now records every processed frame independently of GUI redraws. Operator/removal
episodes can still attach to stationary clutter, so this is not a validated
object selector. See [motion-aware usage and evidence](MOTION_AWARE_RANGE.md).

## Product target and next implementation

The user wants one central GUI for useful detection results, with diagnostics
supporting those results. At minimum it must preserve the existing 1D CFAR
current-frame fine-distance output. The current live RD GUI is a feature-level
prototype: its nominal bin-center ranges do not yet replace that fine output,
and feature IDs do not certify distinct physical objects.

The next implementation should add a unified per-frame result layer before
adding more diagnostic views:

**First prerequisite: qualify the unchanged 1D baseline on AVG16.** Both paths
will consume the current AVG16 acquisition profile, rather than comparing a
new RD capture against historical AVG1 performance. Keep the experimental 1D
settings frozen (guard 1, training/minimum 4, factor 2) and preserve the saved
range mask/confirmation. The reproducible development replay and new-capture
protocol are in [AVG16_CFAR_QUALIFICATION.md](AVG16_CFAR_QUALIFICATION.md).
Hardware averaging preserves the nominal range grid but can change noise,
threshold behavior and motion sensitivity. Existing AVG16 captures can support
implementation; independent labeled captures are required for acceptance.
The [initial frozen replay](../evidence/avg16-cfar-qualification-20261111/README.md)
covers 1,955 frames and demonstrates compatibility, with inconsistent placement
distances and far-target coverage still open. No threshold or firmware change
was made for that qualification.

November 11 live controls now include repeated 50 cm placements with failures,
followed by a fixed-target operator A/B/A/B run and its target-absent control.
The fixed placement gives 513/513 numeric interior outputs near 47 cm; the
matched target-absent run gives 0/498 (and no outputs anywhere in its 867 saved
frames). Target removal reduces near-range power by approximately 7 dB.
Operator position still changes the reference threshold; successful controls
do not erase earlier placement sensitivity. See the
[matched review](../evidence/avg16-operator-empty-abab-20261111/REVIEW.md).
These data support proceeding with the unified result layer without more
repeats of this control or threshold retuning; physical accuracy and
independent combined-pipeline acceptance remain open.

The subsequent manually rolled 120↔50 cm run (`live-006`) has consistent signed
RD motion features and higher stationary feature coverage, but its 1D near-hold
medians differ (35.4 versus 60.9 cm). Crucially, unchanged RD processing on the
target-absent `live-005` confirms a zero-Doppler bin-1 feature throughout all
quiet interiors, where 1D has no output. RD-only feature persistence therefore
cannot establish recovery of the added target or automatically supply the
nearest primary distance. Preserve nuisance features and source/validity
distinctions in fusion; do not require both paths to pass for all observations,
and do not treat an unconditional union as validated target detection. See
[motion/control comparison](../evidence/avg16-motion-20261111/REVIEW.md).

1. Retain the existing confirmed 1D CFAR fine-range result and unresolved states
   in the central GUI. Associate that result with an RD feature only when their
   current range support has a unique match. An unassociated 1D return may still
   be shown as such; do not label it with an arbitrary object ID or suppress all
   stationary results for lack of nonzero Doppler.
2. Add range refinement for each resolved RD candidate using its own Doppler
   support. The existing 1D refiner integrates power across chirps; blindly
   copying its result into several track rows can assign the stronger wall's
   distance to a weaker moving return. Refuse fine estimates for unresolved
   shoulders, boundary optima and comparable competing peaks.
3. Merge duplicate current-frame 1D/RD observations into a candidate-return bank,
   preserving multiple separated returns and explicit ambiguity. These share
   the same ADC data and are not statistically independent confirmations.
4. Make `rd-gui` the results-oriented interface: a primary nearest valid measured
   return and a list of candidate returns with distance, relative radial-motion
   label, measurement quality and freshness. Keep full RD/threshold maps in a
   diagnostics tab. No held/predicted point is a fresh range result.
5. Add approaching/receding/no-resolved-radial-motion labels only for supported
   current associations. Zero Doppler does not prove a stationary world object.
   Physical radial speed requires verified timing/carrier and a per-candidate
   phase/velocity estimate. Bearing and sensor-relative XY positions require
   separate RX geometry/phase/angular validation.

Fine range interpolation can improve the location of an isolated peak, but does
not improve the approximately 35 cm native range-bin spacing or guarantee
separation of nearby objects. RD mainly helps choose/separate returns by radial
motion; accurate physical-object detection must still be validated, especially
for the unresolved 120 cm stationary target and operator/clutter controls.
Acceptance should score added-object association, missed/extra episodes,
start/stop response and range error conditional on correct identity, not just
candidate counts or smoother numbers. Both robot-stationary and robot-moving
scenarios remain part of the final goal.

The first unified result/refinement milestone is now implemented in `rd-gui`:
shared-frame frozen 1D/RD processing, supplementary confirmation of every 1D
group, conservative support-based deduplication, Doppler-conditioned fine
estimates, explicit disagreement/unresolved states, and results/diagnostic tabs.
The automatic primary remains the exact frozen 1D baseline; RD-only features
are inspectable without being silently promoted. This preserves the observed
target-absent nuisance as diagnostic evidence. See
[implementation and validation](JOINT_RANGE_DOPPLER.md). A new automatic primary
policy and independent physical accuracy acceptance remain future work; no
firmware or detector threshold change was made for this milestone.

The first joint GUI live trial failed the startup jitter gate; display workload
was reduced without changing timing limits. A subsequent stationary ~80 cm
capture accepts all 758 frames, freezes the clock near 20 s and stays valid for
75 host seconds. Its primary remains blank because 1D has no qualifying cell,
not because of timing. Farther bins 6–7 dominate the target-region reference
power; RD chiefly confirms a ~2.22 m scene feature with only brief near-range
support. Keep this as a reference-contamination/selection regression case for
the next detector investigation; automatic RD-only promotion would misrepresent
the requested target range. See the
[hardware retry and detection review](../evidence/joint-stationary-80cm-20261111/README.md).

A fixed lower-median OS reference and single-group/unique-current-RD-support
selector have now been implemented as an optional inspection experiment. The
same guard/training/multiplier and fine estimator recover more numeric outputs
under contaminated training, but also admit a persistent ~30 cm feature in the
target-absent control. The primary therefore remains unchanged; no rank/factor
sweep or range blacklist was used to force a pass. See
[experiment, usage and limits](CLUTTER_REFERENCE_EXPERIMENT.md). Additional
stationary-scene discrimination remains necessary before promoting this branch
as an improved object-distance detector.

## Earlier 1D stage decision

Freeze the current implementation as an **experimental baseline-free range-CFAR
stage**, suitable for controlled-scene research and comparison. This is not a
validated distance instrument or clutter-independent object detector. Preserve
current settings and evidence while developing Doppler as an explicit optional
backend. Do not keep tuning thresholds against every new validation recording.

The fresh capture `recordings/gui-20261109-235116-484020/live-001` validates the
long-run clock fix in hardware: approximately 138 host seconds, no timing-gate
rejections, frozen rate after startup, and less than 50 ms corrected error after
fitting. Two CRC/sequence-gap events were rejected with recovery. Tentative scene labels were later supplied, but the user may have mixed target
distances and estimated transitions from the UI. Conditional summaries show
possible placement-dependent bias and first-target dropouts; a clearly labeled
repeat is needed before physical accuracy acceptance. See the
[review follow-up](../evidence/cfar-stage1-review-235116/README.md#tentative-scene-label-follow-up).
Transport stability alone cannot establish range accuracy.

No additional software change was required to demonstrate completion of
the first algorithm-development stage. Before calling its physical performance
accepted, obtain a repeat with confirmed scene labels and agree on practical
miss/false-output/error limits. Keep unresolved clutter, placement bias and USB
corruptions visible in the baseline report.

## What stage one added

- Baseline-free linear-power range CA-CFAR with configurable guards, training
  cells, minimum reference count and empirical multiplier. Explicit DC/Nyquist
  exclusion and truncated-edge policy.
- Adjacent-bin grouping, nearest-group selection and three-frame confirmation
  associated by overlapping support and at most one-bin maximum motion.
- Fine current-frame spectral peak estimation within group support, independent
  of an empty waveform. Boundary and comparable-multiple-peak cases remain
  unresolved. No temporal smoothing or extrapolation across misses.
- Live/replay/terminal integration, raw power/reference/threshold/candidate plots,
  fine-distance history and recorded diagnostics. Original baseline mode remains.
- A bounded startup host/device clock mapping, frozen after fitting. Existing
  queue/continuity/timeout checks remain, and invalid timing clears readouts.
- Reproducible parameter sweeps, capture-validation tools and evidence, including
  false returns that change when sensor position/clutter changes.

## 1. Verify Doppler feasibility and metadata

November 10 timing checkpoint: the prepared HPF350 CHIRP_ACTIVE scope image
now builds locally. The existing capture-path duration gives a conditional
upper bound of 231.5 µs on uniformly spaced retained-chirp intervals and,
with an illustrative unverified 60 GHz carrier, a native velocity-grid spacing
of at least 0.675 m/s. This is a feasibility bound, not a measured chirp period.
The board/scope were not connected for an electrical measurement. See the
[reproducible checkpoint](../evidence/rd-timing-feasibility-20261110/README.md).
The next timing evidence can come from sensor CHIRP_ACTIVE edges measured with
an external scope/logic analyzer **or** a separate diagnostic firmware that
timestamps those edges at the MCU input. A matching raw capture is needed to
check edge/block correspondence and coherence. The public device limits and
the 1 ms host placeholder do not establish the current runtime chirp interval.
Replay processing and candidate diagnostics may continue in cycles/saved block while
physical timing remains unverified; do not label the axis in m/s.
The first MCU diagnostic capture found 112 CHIRP_ACTIVE edges per frame in
groups of 16, while only 17 raw blocks were saved. Its 64-slot edge log
overflowed in every frame. This makes edge/block correspondence a concrete
open issue; do not treat the 16 retained raw blocks as uniformly timed yet.
See the [capture review](../evidence/rd-mcu-edge-20261110/README.md). A revised
128-slot capture then confirmed seven groups of 16 edges per frame without
overflow. FIFO block-to-edge timing remains unverified. The next experiment
should either instrument FIFO block production or test a distinct vendor-AVG16
full-burst capture before adding physical velocity detection. The AVG16 test
capture now shows the expected 272 edges in 17 groups and consistent stationary
phase. The [capture review](../evidence/rd-avg16-20261110/README.md) supports
proceeding to controlled approach/hold/retreat with the same image; see the
[motion protocol](AVG16_TIMING_TEST.md#next-capture-controlled-motion).
The controlled AVG16 motion recording now shows repeated negative/positive
phase progression for approach/retreat and nonzero peaks in the full map,
with stationary holds centered at zero. See the
[motion review](../evidence/rd-avg16-motion-20261110/README.md). This is enough
qualitative feasibility evidence to start step 3 on replay data, keeping
physical velocity verification open. No further firmware change is needed for
that prototype.

Implementation update: a replay-only diagnostic is available via
`./range-v1 range-doppler RECORDING`, with full/mean-removed maps, an interactive
frame slider, optional artifact export, and phase-progression diagnostics.
See [usage, verification limits and new-sample protocol](RANGE_DOPPLER_DIAGNOSTIC.md).
Synthetic checks establish processing behavior, not hardware timing/coherence.
Timing verification remains open. Replay [2D CFAR candidate processing](CFAR_2D.md)
is now implemented. Conservative feature association and the
[live range–Doppler GUI](LIVE_RANGE_DOPPLER.md) are also available;
physical-object identity and acceptance testing remain open.
The intended use is obstacle detection from a stationary or moving robot. Preserve
stationary returns; robot motion can give walls and small stationary obstacles
the same radial speed. Check range-profile suitability alongside Doppler timing,
while deferring fine-distance calibration.

**Work:** Audit the actual chirp schedule, retained chirps, carrier frequency,
RX ordering and phase consistency. Distinguish the MCU frame timer from the radar
chirp clock. The newly fitted MCU/host rate is not a calibration of ADC rate,
ramp slope, carrier or chirp spacing.

The working AVG16 test profile saves 17 averaged blocks, 64 ADC samples and
three RX, with one block discarded. That leaves 16 slow-time samples. Existing broad-pipeline
configuration uses an unverified 1 ms chirp-interval placeholder. The current
AVG16 acquisition elapsed field is around 8.8 ms for the whole readout path
(the earlier AVG1 path was around 3.46 ms). These are whole-path durations,
not measured chirp intervals, and cannot validate the placeholder. Do not
infer chirp spacing simply by dividing acquisition duration by chirp count.

Derive/read back the programmed timing where possible and independently verify
uniform spacing and phase consistency. At verified carrier wavelength lambda and
chirp spacing T, nominal Doppler bin spacing is lambda/(2*N*T), and unambiguous
radial speed is approximately ±lambda/(4*T). Windowing broadens spectral peaks.
Calculate these before promising separation of slow hand/box motion from clutter.

**Deliverable:** Explicit timing/verification metadata and a short feasibility
report for the current burst. Until then, plots may show Doppler index or
cycles/saved block, clearly marked as timing-unverified diagnostics; do not publish m/s.

**Exit condition:** Uniform, coherent samples and meaningful achievable Doppler
resolution are demonstrated. If the current burst is too short, prepare a reviewed
longer-burst/profile proposal; firmware changes/flashing require separate explicit
authorization. Do not stitch independent restarted bursts as a coherent record.

## 2. Add a replay-first range–Doppler backend

**Work:** Reuse `radar_min.core.range_spectrum()` to retain complex values as
`[chirp, range, RX]`. Port the useful slow-time FFT/windowing structure from
`radar/processing.py`, with its limitations made explicit. Keep acquisition,
recording and UI shared with the existing range mode.

Compute a slow-time Hann window and FFT across chirps, shift Doppler bins, then
average RX powers to form a range–Doppler map. Do not average away complex chirp
information before the Doppler FFT. Keep the full map including zero Doppler.
Add an independently labeled, optional within-frame slow-time-mean-removed
moving-target view; it needs no separate empty recording.

**Deliverable:** Replay command and UI tab showing the full map plus moving-view
option, with native range/Doppler axes, frame validity and processing time.

**Checks:** Synthetic stationary and moving tones, positive/negative Doppler,
multiple returns, near-zero Doppler, corrupted/gapped frames and known phase
progressions. Confirm normalization and selected axes. Phase progression and
correct timing are prerequisites for a physical interpretation.

## 3. Apply CFAR to the two-dimensional map

**Implementation checkpoint:** The replay prototype is implemented with
exported noise/threshold/count maps, accepted cells, connected groups, local
maxima and slider overlays. The initial AVG16 development replay preserves
zero Doppler and finds signed motion candidates, but groups can bridge static
and moving returns and weak candidates occur outside the target path during
holds. See [development comparison](../evidence/rd-cfar2d-20261110/README.md).
Next address candidate quality and association in step 4, then freeze a concrete
operating point for independent validation captures.
The [unchanged-settings follow-up](../evidence/rd-cfar2d-followup-20261110/README.md)
shows expected motion direction at two speeds and strong close stationary
returns, but inconsistent 120 cm isolation and target-absent candidates. The
final 120 cm hold has passing nominal-range cells that often merge into a
stationary ridge, so step 4 must retain cell/group support and make unresolved
association explicit rather than reduce each group to one object.

**Work:** Add a small independently testable 2D CA-CFAR component with rectangular
training and guard regions, minimum valid reference count, explicit range-edge
handling and an explicit Doppler-edge policy. Choose windows that fit the small
16 × 33 native grid. Document any Doppler wrapping; do not silently wrap range.
Export noise/threshold maps and accepted cells. Keep the threshold empirical until
actual false-output statistics are measured; Hann windows/integration correlate
cells and do not automatically satisfy textbook Pfa assumptions.

Cluster neighboring accepted cells and generate range/Doppler candidates **before**
reducing the map to one return. Compare against the original pipeline's local
median method; do not treat its maximum-over-Doppler range profile as equivalent
to 2D CFAR. Consider OS-CFAR only if observed training contamination warrants it,
with the same tuning/validation discipline.

**Deliverable:** An explicit optional range–Doppler detector mode, replay reports,
threshold overlays and candidate diagnostics. Preserve current 1D mode and its
settings as a comparison baseline.

## 4. Associate targets and preserve stationary detection

**Implementation checkpoint:** Optional `--detector cfar2d --associate` now
confirms and associates radar features with explicit measured, tentative,
ambiguous, missed and lost states. Only confirmed unique current local maxima
produce point measurements. Accepted cells can support a bounded ambiguous
interval but cannot seed/confirm a track, move its anchor or publish a held
distance. CFAR remains unchanged. See
[algorithm/usage](RANGE_DOPPLER_ASSOCIATION.md) and
[fixed-settings two-recording review](../evidence/rd-association-20261110/README.md).
Weak transient nonzero candidates are reduced, but slow-motion coverage,
fragmented IDs and static clutter association remain open. Native feature IDs
are not verified physical objects. A live adapter and GUI now run this same
processing during capture, with host-quality gates clearing maps/measurements;
see [usage and verification](LIVE_RANGE_DOPPLER.md). This remains an experimental
feature pipeline, not completion of physical detection acceptance.

**Work:** Associate candidate groups over range and Doppler, using actual observed
data and documented gates. Keep missing frames, target loss and ambiguity explicit;
separate detection, estimate validity and any later tracking prediction.

Do not simply suppress the central Doppler bins in the only output path. That
would discard the stationary box and sufficiently slow movers. Provide both a
stationary-capable path and a moving-target path. Doppler can help distinguish
moving targets from fixed clutter; stationary target versus stationary clutter
still requires range/angle/scene constraints or a documented additional model.

Do not blacklist the 70/84 cm region: earlier unwanted returns overlap legitimate
target ranges. Fine interpolation cannot establish which reflector produced a
peak, and smoothing cannot fix a wrong association.

**Deliverable:** Clear range and motion/status outputs that survive a target
stopping only when supported by current measurements. No held stale distance
presented as a fresh detection.

## 5. Freeze and compare on independent captures

Collect a compact labeled set after the implementation/settings are frozen:

- Empty scene, stationary target present at startup, insertion/removal, approach
  and retreat, then stop and hold. Include near-zero radial motion.
- Repeated supported placements at measured antenna-face distances, with fixed
  height/orientation and operator outside the beam. Record transition times.
- Cleaner and cluttered scenes, new sessions and selected target distances;
  preserve failed placements and matched empty checks.
- A run longer than two minutes to exercise clock handling, and controlled
  unplug/stall/queued-input checks that must clear the readout.

Report any-target detection, intended-target association, output coverage,
conditional distance bias/MAE/distribution, empty output episodes/durations,
response time, transport losses and processing/display latency. Report physical
velocity error only after timing/carrier verification. Weight recordings/sessions
explicitly; correlated frames are not independent trials. Split by scene/session,
not neighboring frames. Do not report only the successful intervals.

**Exit condition:** A frozen mode meets user-agreed detection, false-output,
latency and range-error limits on new recordings, including stopping/static tests,
and performs better than the frozen 1D baseline for its intended use case. If not,
report the failed conditions and revise the measurement/profile/model before
claiming improved accuracy.

## Scope and source references

Begin with timing feasibility and synthetic/replay processing, then evaluate a
frozen prototype in a labeled live experiment. Any proposed firmware profile
change should be concrete and reviewed before hardware programming.

- [Infineon radar chirp parameters and performance](https://community.infineon.com/t5/Knowledge-Base-Articles/Radar-chirp-parameters-and-their-importance-on-radar-signal-performance/ta-p/827916)
- [Infineon radar DSP overview](https://community.infineon.com/t5/Knowledge-Base-Articles/Understanding-radar-signal-processing-An-overview-for-Infineon-XENSIV-radar/ta-p/833659)
- [MathWorks 2D CFAR reference](https://www.mathworks.com/help/phased/ref/phased.cfardetector2d-system-object.html)
- [Current range-CFAR documentation](CFAR_RANGE.md)
