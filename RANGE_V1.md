# Wavvy range-only MVP

**Runnable experiment, not a validated distance instrument.** Saved close targets
are missed by the conservative detector. Empty references can fail across sessions.
Read [the audit](AUDIT_RANGE_V1.md) and the checked-in evidence before interpreting
any plotted coordinate. No changes to firmware are required or authorized here.

## Run

```sh
cd /Users/chekaylimeyer/Documents/ChatGPT/SENIOR/wavvy-range-v1
./range-v1 test
```

The wrapper uses `WAVVY_PYTHON`, a local `.venv`, the existing original project's
virtualenv, or `python3`, in that order. It changes to this checkout before import;
it does not modify the original virtualenv. A separate machine needs Python 3.11+
and NumPy/pyserial (`python3 -m pip install numpy pyserial` in its own environment).
The MVP does not import Qt, Matplotlib or the broad processing module. Existing
package installation still includes legacy GUI dependencies for compatibility.

One-command replay comparison of every available session:

```sh
PYTHONPATH=. /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python tools/compare_range_min.py /Users/chekaylimeyer/radar-work/radar-demo/recordings
```

A fitted primary-session baseline is already available locally at
`artifacts/empty-baseline.json`; full per-frame profiles are in
`artifacts/holdout.jsonl`, `near.jsonl`, `far.jsonl`. These generated files are
ignored by Git. Recreate the baseline with a **new** output filename:

```sh
./range-v1 baseline /Users/chekaylimeyer/radar-work/radar-demo/recordings/box_range_20261028_002954/empty artifacts/new-empty.json --count 30
./range-v1 replay /Users/chekaylimeyer/radar-work/radar-demo/recordings/box_range_20261028_002954/empty --baseline artifacts/new-empty.json --skip 30
./range-v1 replay /Users/chekaylimeyer/radar-work/radar-demo/recordings/box_range_20261028_002954/near --baseline artifacts/new-empty.json
```

Replay emits per-frame JSON, including linear power, excess profile, candidate,
threshold, rejection reason and processing time; summary goes to stderr. It refuses
training/evaluation overlap for the same raw-file hash. Renaming a recording does
not bypass that check. Separate files containing overlapping samples remain an
operator provenance responsibility. Raw CRC errors/truncated saved files fail loudly.

When a radar port is present, fix the sensor, remove the target and leave the beam.
Use a new output directory each time. Substitute the actual port, never an old
hardcoded name; run only one serial reader.

```sh
./range-v1 capture recordings/new-empty --port /dev/cu.usbmodemACTUAL --seconds 8
./range-v1 baseline recordings/new-empty artifacts/session-empty.json --count 30
./range-v1 replay recordings/new-empty --baseline artifacts/session-empty.json --skip 30
./range-v1 live recordings/new-target --port /dev/cu.usbmodemACTUAL --baseline artifacts/session-empty.json --seconds 60
```

`live` shows a single terminal status line: BIN and **provisional** coordinate, or
NO RELIABLE READING, reason and transport counters. Redirected output is compact
JSONL. It always records full readings/profiles separately. No GUI is needed.
Ctrl-C sends stop and closes recording/serial; no firmware flashing occurs.
Restart the command after an unplug/error and explicitly decide whether the same
empty scene still applies. Device restart/duplicate invalidates the detector's
baseline for that process; it does not silently reacquire.

Files: `frames.grd` contains accepted CRC-valid raw packets; `serial-wire.bin`
contains original serial chunks including rejected bytes; `transport.jsonl`
records parsing counters/host timestamps; `arrivals.jsonl` records accepted-frame
arrival times; `config.json` and `metadata.json` hold provenance;
`readings.jsonl` and `capture-summary.json` record results. Invalid DSP frames still
remain in raw recordings. A one-second frame timeout clears the readout and exits
with error. Growing timing mismatch (>0.5 s), >2 queued frames, gaps and device
counter changes reject current readings. Relative timing is not absolute freshness;
a firmware start acknowledgment and identity readback remain future work.

## Exact processing policy

1. Validate shape/profile, finite ADC values and container rails. Reject rails;
   this does not establish the effective physical ADC saturation threshold.
2. Discard first chirp for compatibility with prior processing. This is an
   unverified startup policy, not a proven necessity; compare all chirps in a
   future preregistered experiment.
3. Remove each chirp/RX sample mean, apply symmetric NumPy Hann (64 samples),
   compute unpadded real FFT, normalize by `2/sum(window)`, average squared
   magnitude over remaining chirps and RX. No complex background subtraction,
   angular gains, Doppler processing, interpolation or learned offset.
4. Fit per-bin median **log power** to >=20 empty frames (default 30). This
   differs slightly from log of median linear power for an even frame count.
   Use `sigma = 1.4826*median(abs(db-median_db))`; threshold is
   `max(3 dB, 6*sigma)`. These are fixed conservative engineering defaults,
   not a Gaussian noise claim, six-sigma guarantee or CFAR false-alarm rate.
5. Search explicit bins1–4, roughly provisional 0.348–1.390 m. Bin0 and Nyquist
   are not accepted; all bins are still exported. This mask is a restricted
   experiment window, **not a verified minimum/maximum physical range**.
6. Choose largest current excess; require its variability threshold and 2 dB
   lead over nonadjacent bins in the mask. Adjacent Hann energy is not a separate
   competing target. A stronger unstable candidate can conservatively block a
   weaker one. This detector is single-return, not object identification.
7. Require 3 consecutive valid frames at exactly that bin (nominal 0.2 s from
   first qualifying frame). No median history, hysteresis or distance smoothing.
   Absence, ambiguity, movement to another bin, sequence/time gap or corruption
   cannot create a held measurement. Reacquisition needs fresh persistence.
8. `range_m` is **always null**, `calibrated` always false. `range_bin` is present
   only on detection; `candidate_bin` preserves rejected evidence. The nominal
   coordinate uses source sampling/slope, ignoring legacy scale, offset and
   `verified` flags. There is no arbitrary numeric confidence score.

## Physics and close-range limitations

Assuming a linear FMCW ramp, static target and correct sampling model:
`tau=2R/c`, `fb=S*tau`, `delta_f=fs/N`, `delta_R=c*fs/(2*S*N)`.
For this source model: duration N/fs=12.8 us, sampled bandwidth convention
S*N/fs=431.25 MHz, FFT spacing 78.125 kHz, nominal range grid **0.347585 m**.
The first-to-last sample span uses N-1 and is 424.512 MHz (~0.353103 m reciprocal
bandwidth scale). Neither is a measured accuracy guarantee. Hann broadens peaks;
zero padding or interpolation would not add independent physical resolution.

At 0.15–0.55 m the provisional beat frequency is about 33.7–123.6 kHz, or
0.43–1.58 bins. Mean removal and bin0 exclusion affect this region; analog HPF1
is configured to 350 kHz (~1.557 m beat-coordinate equivalent) with the second
HPF active. Corners are not hard cutoffs. Leakage, baseline variability, broad
lobes and multipath may dominate. Range resolution, detectability and accuracy
are different quantities. Moving bin1 to bin2 does not establish that a box moved
or that either coordinate is its distance. No physical calibration can be fitted
responsibly to the current detector's all-miss close-range evidence.

## Physical validation plan and blocked experiments

All new hardware experiments are **blocked now: no radar serial port was present**.
No firmware or hardware settings were changed. Identity/readback and any later
profile change must be reviewed separately; flashing still needs explicit approval.

1. Record board/antenna photos, serial identity, source/build SHA256, actual flashed
   revision if obtainable without flashing, room layout, reflector dimensions,
   gain/profile, pose, temperature, antenna-face measurement convention, tape
   measurement uncertainty and operator position. Save original wire bytes.
2. In each fixed scene collect >=30 training empty frames, pause, then a separate
   >=60 s empty acquisition. Freeze thresholds before inspecting holdout results.
   Repeat with new sessions/restarts and several rooms; never pool different
   backgrounds as if one stationary distribution. Report positives/total and
   contiguous false-positive episodes; correlated frames are not independent trials.
3. Place the same reflector at 0.15/0.25/0.40/0.55/0.75/0.90/1.20/1.50 m, randomize
   order, repeat >=3 placements each with separate labels and >=60 frames. Capture
   empty before/after and keep people out of beam. Report bin histograms, detection
   fraction, misses and excess distributions, including failed close targets.
4. Repeat insertion/removal and inward/outward motion. Measure latency in device
   timestamps and wall time, disappearance/ghost persistence, nonmonotonic changes,
   and raw gaps. Check serial unplug, duplicate/corrupt packets and slow consumers.
5. Establish actual clock/ramp/readback and analog response. Compare all-chirp vs
   discard-first, per-RX vs mean power and DC policies offline before changes.
   A lower-HPF or different-bandwidth firmware experiment requires explicit approval,
   a new profile identity, preserved baseline binary and paired raw captures.
6. Only after useful detections exist, split measured distances/sessions into
   calibration and independent validation sets. Fit one documented mapping with
   uncertainty and range-of-validity, then report validation bias/MAE/RMSE and
   failure fraction together. Do not fit offsets to each recording or score error
   only on successful frames without reporting misses. Set acceptance limits from
   project requirements and evidence; no centimeter claim is currently justified.

## Files and verification

- `radar_min/core.py`: minimal typed config, spectrum, background, continuity, detector.
- `radar_min/__main__.py`: capture/baseline/replay/live; reuses existing wire/storage.
- `tests_min/test_range_min.py`: 11 offline unit/integration tests.
- `tools/compare_range_min.py`: reset-state before/after and separate-session stress.
- `tools/audit_range_baseline.py`: original inventory/register/historical replay audit;
  accepts original repository and a new output directory. Requires its local `shafaa`
  branch and sibling vendor HAL, as found in this audit.
- `range-v1`: launcher; `pyproject.toml`: includes the new package.
- `AUDIT_RANGE_V1.md`, this document and `evidence/`: findings and reproducible outputs.

Legacy full suite additionally needs the existing official HAL at
`../mtb_shared/sensor-xensiv-bgt60cutrxx/release-v1.1.0/`. A local sibling symlink
was created in this workspace to the installed original vendor directory; it is
not a vendored dependency or committed artifact. The MVP suite needs no HAL.
