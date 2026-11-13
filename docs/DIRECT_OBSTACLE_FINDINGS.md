# Reference-free glass-obstacle investigation

Date: 2026-11-07. Goal remains reliable detection of glass as an obstacle without
scene-specific open/closed templates. The earlier obstacle-template implementation
does not meet this goal. This investigation does not claim it is achieved.

## Reproducible evidence

From the checkout, using new output directories:

```powershell
.\.venv\Scripts\python.exe -m tools.audit_direct_obstacles recordings artifacts\direct-obstacle-03
.\.venv\Scripts\python.exe -m tools.audit_subspace_returns recordings artifacts\subspace-obstacle-02
.\.venv\Scripts\python.exe -m tools.audit_door_transitions recordings artifacts\door-transitions-02
```

Current outputs are `artifacts/direct-obstacle-02`, `artifacts/subspace-obstacle-01`
and `artifacts/door-transitions-01`. Raw captures are unchanged. Complete door03,
door04 and door07 are included, all three pairs each. Incomplete door05/door06
are excluded. Every included capture passes the implemented raw quality checks.

## Reference-free local-return test

Process each scene independently: retain stationary energy, discard the configured
startup chirp, subtract fast-time DC, apply Hann and unpadded range FFT. Compute
power per receiver and median over nonoverlapping roughly one-second windows.
Require a local peak in average RX power and support on at least two receivers
above each receiver's local median noise/clutter estimate. Guard +/-1 native bin;
reference offsets 2 through 5, excluding DC and Nyquist. Fixed contrast thresholds
3, 6, 10 dB are all exported; no choice was made per scene. This is not a
statistically calibrated CFAR false-alarm rate.

Only after selecting candidates across the full range, compare their positions
with the measured pane distance. Match tolerance is +/- one nominal native bin
(0.348 m), not a certified measurement uncertainty. Coordinates derive from source
sampling/slope, not a new fit to the pane labels.

At 6 dB contrast:

| Setup | Closed windows with a candidate near pane | Open windows with candidate in same neighborhood |
|---|---:|---:|
| door03, 44 inches | 0/90 | 0/90 |
| door04, 25 inches | 90/90 | 0/90 |
| door07, 60 inches | 90/90 | 62/90 |

At 3 dB, door03 and door04 counts are unchanged, while door07 open counts increase
to 90/90. At 10 dB, door07 open counts are 60/90; all other counts are unchanged.
Correlated windows are not independent success trials. Open recordings contain
real background obstacles: near-pane open candidates are association ambiguity,
not proof those reflections are false objects. A near-pane candidate in a closed
recording is not independently proven to be glass rather than its frame/background.

## Receiver diversity and stationary phase

The averaged spectrum conceals a repeatable RX2 local maximum at native bin
3 in door03 closed captures. Interpolating the existing spectrum with an 8x
zero-padded FFT places that RX2 maximum at 3.25, 3.25, 3.125 native bins across
the three closed recordings; the measured pane maps nominally to bin 3.215.
The corresponding RX2 interpolated neighborhood contains no local maximum in
the three open recordings. RX1/RX3 already have nearby maxima with the door
open (around 2.75 and 2.875). This is a candidate glass-related response, not
proof that selecting RX2 alone produces a portable detector.

Door04 closed interpolated maxima are around 2.25–2.50 bins across RX; open
maxima are around 2.375–2.75. Native bin quantization therefore exaggerates the
apparent distinction between open peak 3 and closed peak 2. The native test's
success in that experiment is not independently validated localization.

Door07 closed maxima on RX1/RX3 occur near 4.375 bins in the first two pairs,
and about 4.5 in the last pair, near the nominal measured bin 4.385. Nearby
maxima already exist in the open scene. Zero padding locates spectral maxima
more finely; it does not add independent resolving power.

At the scoring bins, chirp coherence and cross-RX coherence are close to one
in both states. A stable wall/clutter return is coherent too. Coherence alone
does not solve the detection/association problem. Raw inter-RX phase changes
when doors move, but physical angular interpretation depends on unverified
RX conventions and angle calibration. For example the current factory-matrix
interpretation places door03 bin-3 closed returns at roughly +50 degrees elevation,
which is not evidence of a centered pane without independent pose information.

## Multi-tone separation

A second audit uses real-trace Hankel smoothing, shared-receiver ESPRIT frequency
estimates, and least-squares sinusoid amplitudes. Orders 2 through 16 are compared
with a BIC penalty; assumptions about white residual noise are only approximate.
Neither the expected range nor the open/closed label enters frequency estimation
or model-order selection. This is a spectral model test, not a proven detector.

It finds at least one component within one nominal bin of the measured pane in
ALL 90 closed and ALL 90 open windows for every setup. In door03 both states
include components near bin 3.3–3.4. Resolving extra tones therefore does not
establish which component belongs to the pane. A synthetic three-tone check
does recover known frequencies without range labels; that validates the numerical
estimator on that model, not its physical interpretation in the room.

Method reference: Roy and Kailath, ESPRIT (1989),
https://alumni.media.mit.edu/~aggelos/papers/roykailath89.pdf .

## Recovered transition evidence

The original continuous serial logs contain 3,113 frames for door03, 3,340 for
door04, and 3,629 for door07 (10,082 total). The six labeled static captures per
experiment use only 5,457 of these frames; 4,625 additional frames include setup,
door transitions and waiting periods. Complex mean range spectra, per-RX powers,
timestamps and sequence numbers are now preserved in compact stream NPZ files.
Capture intervals are overlaid on `transitions.png`. The operator may also move
in the unlabeled intervals, so motion is not automatically labeled as glass.

Door07's third open recording has a substantially different receiver/spectral
pattern than its first two. This remains a scene/pose-change hypothesis, not a
proven sensor move. User setup confirmation is pending. These original stream
data enable further investigation without asking for another capture immediately.

## Physical path hypothesis and remaining work

A pane can produce an early return while transmitting energy that reflects from
background objects and passes back through the pane. With hypothetical 50% power
transmission on each crossing, background power is multiplied by 0.25 before
other path losses. This is a physical hypothesis, not a universal observed ratio.
The unknown background scene, material transmission and specular return direction
make a particular two-peak ratio insufficient evidence of glass on its own.
Pane front/back-face echoes may be unresolved at the current bandwidth.

The [Acconeer radar principles](https://docs.acconeer.com/en/latest/pcr_tech/radar_principles.html)
explain transmission, interface reflections and flat-target directionality.
[TI's robotics white paper](https://www.ti.com/lit/wp/spry311a/spry311a.pdf)
demonstrates glass and a wall behind it on different hardware; this establishes
feasibility in that setup, not guaranteed performance for this three-RX stream.

Next actions: inspect the recovered transition spectra for consistent return
trajectories ending at the closed-pane range; quantify cross-RX fitting stability
without using pane labels to select a receiver; audit acquisition/filter choices
before requesting any targeted new data. The current HPF350 configuration has
a nominal 350 kHz high-pass corner corresponding to about 1.56 m for this slope;
it is not a hard minimum range or an established cause of these misses. Previously
tested HPF100 firmware is available, but no new firmware was flashed here.

Reliable unpaired glass-obstacle detection remains unverified. This is evidence
against treating a strongest-peak, coherence-only, or unconstrained multi-tone
fit as the completed detector; it is not a proof that all possible methods fail.

## Follow-up: independent fast-time portions and transition tracks

Reproducers:

```powershell
.\.venv\Scripts\python.exe -m tools.audit_stable_returns recordings artifacts\stable-returns-02
.\.venv\Scripts\python.exe -m tools.track_transition_returns recordings artifacts\door-transitions-01 artifacts\transition-tracks-02
```

Saved outputs: `artifacts/stable-returns-01/audit.json` and
`artifacts/transition-tracks-01/tracks.json`.

For each one-second window, estimate components on the full 64 samples, first
48 samples, and last 48 samples. Keep a full-aperture frequency only if each
shorter-aperture estimate has a component within 0.25 native bins. The agreement
test does not use pane position or state. This is a model-consistency diagnostic,
not a calibrated confidence interval. The shorter apertures have less information;
failure does not prove that a physical reflector does not exist.

With +/-0.25 nominal-bin scoring tolerance around the measured pane:

| Setup | Open windows with stable near-pane component | Closed windows with stable near-pane component |
|---|---:|---:|
| door03 | 11/90 | 29/90 |
| door04 | 0/90 | 0/90 |
| door07 | 60/90 | 90/90 |

Widening scoring tolerance to one nominal bin changes door04 closed to 84/90
and door07 open to 62/90. Door03 counts do not improve. Frequencies near the
pane in door03 closed pair 1 survive in 28/30 windows, but pair 2 has 0/30 and
pair 3 only 1/30. Thus the fitted near-pane component is not a robust identified
glass return across the repeat recordings under this consistency test.

Receiver-specific native peaks were tracked through each complete original
stream with fixed nearest-frequency association (max 0.75 bins, no gap over
0.3 s, retain tracks with at least five frames). Interpolated peak coordinates
are diagnostic, not additional physical resolution. Capture labels and pane
positions were consulted only after full-stream tracking.

In the first five seconds of each door03 closed capture, the RX2 track's median
bin is 3.48, 3.46 and 3.41. No track lies within one nominal bin of the pane in
the corresponding open captures. This strengthens the evidence for a door-linked
RX2 response. But associations merge/split during transitions, and there is no
independent timing/position label distinguishing the pane, moving frame, and
operator. Selecting that RX/feature because it matches these labels would again
be retrospective scene-dependent selection, not validation of a generic detector.

Door04 and door07 have near-pane tracks in both open and closed captures.
Tracking alone therefore does not solve surface ownership or in-path association.

Across all non-DC/non-Nyquist bins, door07 open-03 versus open-01 has per-RX
median absolute complex-phase changes of 73.8, 101.5, 106.8 degrees and median
absolute power changes of 3.97, 3.59, 5.57 dB. Open-02 versus open-01 changes
only 5.3, 8.0, 8.2 degrees and 0.96, 1.53, 0.97 dB. These measurements support
investigating a pose/scene change; they do not establish its cause. Setup
confirmation remains pending and no new capture or hardware action was taken.

The generic local-return detector, multi-tone estimator, subset-consistency check,
and peak tracker all have synthetic numerical tests. Passing those tests does not
establish reliable glass detection. There is still no independently verified
association of these returned components to the physical pane across all setups.
