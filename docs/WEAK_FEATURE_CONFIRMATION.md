# Confirmation of weak scene features

**Fixed-position material control:** operator B, box footprint/orientation
unchanged, bare → foil → bare at 50 cm. Foil gives continuous baseline ~46.1 cm
and offline model-qualified ~51 cm. The first bare hold is blank; the second
has **257/274 confirmed weak values near 29.1 cm**, while the main distance stays
blank and both raw models reject it. Temporal confirmation is not box-front
correspondence. See [review](../evidence/material-control-20261112/README.md).
No immediate repeat is needed. Next expose model quality and a separate
experimental model-qualified range/status in the GUI without promoting weak
scene-feature distance to the primary.

**Fresh operator-B check:** the new bare-box 50/50/120 cm recording has no
numeric baseline or confirmed weak ranges in its 821 scored target frames.
The repeated 50 cm hold has sustained CFAR presence but two competing fine
peaks; the other holds fail thresholding. Timing is valid. This limits the
earlier development success and does not justify primary promotion. See
[the independent capture review](../evidence/bare-box-b-20261111/README.md).
The [matched background investigation](../evidence/matched-background-20261111/README.md)
now finds strong scene changes but no correct blind range maxima after fixed
power or waveform subtraction. Later empty holds also break the fixed-waveform
change gate. The [variable-background test](../evidence/empty-trained-tone-20261111/README.md)
is now complete: no accepted bare-box ranges, despite plausible results on
both foil recordings. No live fallback is justified. Next collect a
[same-position bare/foil/bare control](EMPTY_TRAINED_BACKGROUND.md) to separate
reflector changes from placement variation.

The existing `--experimental-weak` mode now confirms consecutive supported
weak peaks into separate `weak:` feature IDs. The GUI shows a confirmed feature
and its processed history, even when the original RD birth-margin guard keeps
the strong feature tentative. This does not change strong RD tracks, the primary
distance, motion policy or physical-object identity claims.

## Use

Restart the GUI; no firmware change or additional flag is needed:

```sh
./range-v1 rd-gui --replay recordings/rd-gui-20261111-133435-428121/live-001 \
  --experimental-weak --view-range-bins 8
```

Live capture uses the existing AVG16 configuration:

```sh
./range-v1 rd-gui --config configs/qualification-avg16-timing.json \
  --port /dev/cu.usbmodemACTUAL --experimental-weak --view-range-bins 8
```

**Confirmed weak scene feature (inspection)** means a repeatable current
OS/RD/raw-shape feature. It does not mean the box, a calibrated distance, or a
new physical object. A return can also appear in the original 1D/RD bank; do
not add the two sets as independent object counts. The optional weak history
uses current measurements, with gaps on missing support and breaks between IDs.

## Rule and freshness

The confirmer requires the original weak-selector support: confirmed OS group,
resolved current OS FFT range, unique RD peak and inherited raw/RX frequency
geometry. It also requires the original RD CFAR observation to exceed its
unchanged cell threshold. It rejects unresolved/overlapping strong association
dispositions and neighboring RD competitors using the existing refinement
isolation guard (one range bin, two Doppler bins).

Three consecutive eligible observations confirm a weak feature by default.
Confirmation count and native range/Doppler continuation gates are inherited
from the association configuration, with the original Doppler edge policy.
There is no global reduction of the strong track-birth margin. OS must already
be confirmed: with a newly appearing group and default settings, the earliest
weak confirmation is on the fifth raw frame, not the third.

Every confirmed point is the current OS Hann/FFT fine estimate. No smoothing,
prediction, held value, range offset or rejected phase estimate is substituted.
Original phase-model rejection stays visible in the candidate inspection.
RX/OS/RD evidence shares ADC data; confirmation does not turn it into independent
evidence or a calibrated false-alarm probability.

Gaps, missing support, stale/mismatched results, ambiguity and rejection revoke
confirmation immediately. Reappearance gets a new `weak:` ID and must reconfirm.
Native-gate violations also start a new hypothesis. IDs are never merged into
the original strong RD namespace; a same-frame strong track ID is only a
cross-reference. History does not join different IDs into a smooth trajectory.

New enabled readings record `weak_feature_result`; metadata preserves the
method, inherited settings and source hash. The mode is disabled by default.
No extra FFT or raw-frequency search is needed beyond the existing weak branch.
The default and `--motion-aware` large readouts remain unchanged.

## What the data show

Across 15,534 frames in eleven recordings, the ~80 cm stationary case retains
267/714 confirmed weak-feature frames from 297 eligible candidates, in eight
episodes (longest 16.2 nominal seconds), median 87.7 cm. All 3,045 scored
target-absent frames have no weak confirmed point; that silence is inherited
from the prerequisite weak selector, not an independent absence test.

The bare-box 120 cm hold retains 15/178 samples near 31.8 cm. **The user later
confirmed being at position A / within range during that hold.** That return
is therefore operator-confounded: it is not established as spurious, nor as
the box return. It demonstrates why persistence cannot establish physical
correspondence. Other old biased holds remain biased; this component confirms
features rather than repairing the range estimator.

All 188 tests pass. Enabled-adapter replay preserves all prior result banks,
RD association, motion/RX/weak inspections and primary outputs, while matching
the independent cached-data confirmation review. No new hardware/timing or
physical accuracy acceptance is claimed.

## Useful next capture

The remaining uncertainty calls for a clean **bare-cardboard** control at B,
rather than another foil repeat. Keep the same sensor/box height, front-face
orientation and background. Measure antenna face to box front surface and mark
the positions. Stand still at the previous position B throughout every quiet
target and empty interval, and exclude all handling/walking:

| Quiet state | Suggested duration |
|---|---:|
| Empty | 20 s |
| Bare box at 80 cm | 25 s |
| Empty | 15 s |
| Repeat same 80 cm placement | 25 s |
| Empty | 15 s |
| Bare box at 120 cm | 25 s |
| Final empty | 20 s |

Take whatever transition time is needed and supply those times separately.
Use **Start live + record** with `--experimental-weak`; keep current thresholds
and firmware. Note any setup changes. This tests the new confirmation on new
data and removes the known operator-A confound; it does not guarantee the
remaining reflectors are separable. No labels or thresholds should be adjusted
to make it pass.

[Window metrics and limits](../evidence/weak-features-20261111/README.md) ·
[GUI/parity review](../evidence/weak-features-live-20261111/README.md) ·
[Capture setup catalog](CAPTURE_CATALOG.md)
