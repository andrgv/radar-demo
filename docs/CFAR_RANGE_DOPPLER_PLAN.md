# CFAR and range–Doppler: stage review and next steps

## Current decision

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

No additional software change is currently required to demonstrate completion of
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

**Work:** Audit the actual chirp schedule, retained chirps, carrier frequency,
RX ordering and phase consistency. Distinguish the MCU frame timer from the radar
chirp clock. The newly fitted MCU/host rate is not a calibration of ADC rate,
ramp slope, carrier or chirp spacing.

The active shape is 17 acquired chirps, 64 ADC samples and three RX, with one
chirp discarded. That leaves only 16 slow-time samples. Existing broad-pipeline
configuration uses an unverified 1 ms chirp-interval placeholder. The current
acquisition elapsed field is around 3.46 ms for the whole readout path; it is
**not** a measured chirp interval and cannot validate the placeholder. Do not
infer chirp spacing simply by dividing acquisition duration by chirp count.

Derive/read back the programmed timing where possible and independently verify
uniform spacing and phase consistency. At verified carrier wavelength lambda and
chirp spacing T, nominal Doppler bin spacing is lambda/(2*N*T), and unambiguous
radial speed is approximately ±lambda/(4*T). Windowing broadens spectral peaks.
Calculate these before promising separation of slow hand/box motion from clutter.

**Deliverable:** Explicit timing/verification metadata and a short feasibility
report for the current burst. Until then, plots may show Doppler index or
cycles/chirp, clearly marked as timing-unverified diagnostics; do not publish m/s.

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
