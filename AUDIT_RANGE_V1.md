# Wavvy takeover audit — November 1, 2026

The software MVP is runnable; **reliable close-range ranging is not demonstrated**.
All physical meter outputs remain null. The new detector misses every saved close target.

## Repository and preservation

Inspected `/Users/chekaylimeyer/radar-work/radar-demo` before editing. HEAD is
`cwm`, `a6d7a089d9a44814d4258b3593a28b9daffbd8ae`, matching the cached `origin/cwm`.
`shafaa` exists at `fe7e5070b83cb45a9daa3aeee1d70194bc3aee78`.
Local `main` (`c85d926`) is one ahead/one behind cached `origin/main` (`33e03bf`).
No network fetch was performed; remote refs are cached observations.
Remote: `https://github.com/andrgv/radar-demo.git`.
The only initial dirty file was tracked `.DS_Store`; it remains untouched.
Recordings are ignored, not tracked. No stashing, flashing, pushing or deletion occurred.

Implementation lives in a separate `--no-hardlinks` local clone at
`/Users/chekaylimeyer/Documents/ChatGPT/SENIOR/wavvy-range-v1`, branch
`codex/range-v1`. Its origin is the original local repository. Do not push to that
origin casually: it is a working checkout, not the team's GitHub remote.
Original history, firmware and research modules remain intact.

`shafaa...cwm` has 19 changed files: tracking/GUI, backup copies, an unintegrated
`wavvy_range_filter.py`, generated BSP files, dependency lock and qualification
metadata. The median deque is **5 frames**; nominally 0.5 s of samples, with
variable startup length. Three-frame confirmation is additional state, not a
fixed total latency guarantee. The global current-frame threshold check appears
twice. It checks whether *any* bin has signal, not the historical selected bin.
Thus a changed signal elsewhere can permit a stale median-selected candidate.
The new MVP has no temporal median and requires current evidence at its selected bin.

The simplified GUI really landed: large BIN/UNCALIBRATED label, two plots, and
an Advanced diagnostics tab preserving old panels. `Processor` still has a
global argmax for its general profile peak; it is not the short-range detector.
The old GUI still runs the broad processor. Offscreen synthetic and saved-replay
launch/exit smoke checks succeeded; this is not a visual or hardware validation.

## Wire and configuration

`firmware/main.c` streams GRD3 v1: 48-byte little-endian header, 6528-byte ADC
payload, 4-byte CRC32, total 6580 bytes. Header and whole packet have CRC32 checks.
Payload is interpreted as unsigned 16-bit containers shaped [17 chirps, 64 samples,
3 interleaved RX]. Physical RX labels and effective ADC bits are not established
by that container format. The driver reads FIFO levels in samples and FIFO words
as two containers; no proven packing correction is warranted.

Baud 2,000,000, 8N1; `B` starts and `c` stops. A 1 MHz 32-bit timer timestamps
capture start, wrapping after about 71.6 minutes. Nominal triggers are 100 ms
apart. Sequence increments on attempted captures; cumulative drop/error counters
are transmitted. FIFO/timeout errors suppress a packet. Source uses flags=1;
no per-chirp timestamps, build hash, device identity or RF register readback are
sent. The parser supports an optional capture-duration field that this source
leaves zero/absent. Profile `0x33525801` is a constant, **not a config hash**.

Source includes `firmware/vendor/presence_detection_tracking.h`; runtime overrides
AVG_CTRL_SEQ0 to zero (factor 1 rather than profile factor 16) and FIFO threshold
to 191, captures 3264 containers, and resets FSM. The nominal model recomputed
from the header and installed official release-v1.1.0 HAL agrees with
`configs/range-source-derived.json`: 80 MHz source clock, ADC divider 16,
decimation 1, 64 samples, ramp step 690, 5 MHz sampling, 33.69140625 THz/s slope.
`evidence/firmware.json` records source/profile/build hashes and decoded fields.
Those hashes do not establish what binary is flashed.

All RX source settings are enabled, gain 42 dB, HPF1 350 kHz, HPF2 not bypassed,
AAF 2 MHz. Infineon's [BGT60CUTR13AIP datasheet, §8](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60cutr13aip-datasheet-en.pdf)
describes a two-stage HPF that suppresses close returns, with an approximately
40 kHz second stage. Source settings plus that behavior make attenuation plausible;
there is no measured transfer function or proven causal diagnosis here.

**Exact on-board configuration remains unknown.** No `/dev/cu.usbmodem*` device
was present (only Bluetooth and debug console). No hardware opened or flashed.
Clock, chirp timing, absolute scale/offset, physical RX order and actual firmware
identity require hardware evidence. `verified:false` remains appropriate.

## Saved data and reproduced outcomes

Six ADC files, 364 frames total; all decode with no saved-file CRC/header errors,
sequence gaps, restart indicators or incomplete tails. Device drop/error counters
are zero. No original serial-wire dumps exist, so these accepted-frame files
cannot prove that acquisition rejected no bytes. Full filenames, sizes, SHA256,
metadata and timing are in `evidence/recording-files.json` and `recordings.json`.

| Session | Available stages | Frames | Measured labels |
|---|---|---|---|
| box_range_01 | empty, near | 61, 60 | near 0.245 m |
| box_range_02 | empty only | 61 | none |
| box_range_20261028_002954 | empty, near, far | 61, 61, 60 | 0.25, 0.55 m |

Only the last has a completed range-check manifest/report. Other plate/detkin
captures discussed in historical docs are absent here. Do not treat their old
reported results as reproduced evidence. Ground truth is operator-entered;
pose, photographs, reflector dimensions, firmware identity and uncertainty are missing.

The original range-check analyzer writes its report, so it was run on a disposable
copy, never on the original recordings. It carries tracker state between stages.
The saved historical report exactly matches `shafaa`, not current `cwm`:

| Method, original continuous-stage analysis | Empty positives /31 | Near /61 | Far /60 |
|---|---:|---:|---:|
| shafaa (saved report reproduced) | 26 (bin1:20, bin2:6) | 22 (bin1) | 18 (bin1:2, bin2:16) |
| cwm | 26 (bin1:22, bin2:4) | 26 (bin1) | 16 (bin1:2, bin2:14) |

Median excess at dominant bins remains 4.11/3.39/2.53 dB. Global residual
ranking puts near bin9 first (+7.85 dB); far bin15 is first (+5.46 dB), below
that analyzer's 6 dB criterion, so its accepted far bin is null.

For a fair independent-stage replay, reset each detector at every stage and fit
only the first 30 empty frames. `evidence/mvp-comparison.json` records all outcomes:

| Session / stage | cwm detections | MVP detections | Denominator |
|---|---:|---:|---:|
| 01 empty holdout | 18 | 0 | 31 |
| 01 near 0.245 m | 6 | 0 | 60 |
| 02 empty holdout | 0 | 0 | 31 |
| 002954 empty holdout | 26 | 0 | 31 |
| 002954 near 0.25 m | 24 | 0 | 61 |
| 002954 far 0.55 m | 15 | 0 | 60 |

This is **lower observed false alarms at the cost of complete close-target misses**,
not a validated improvement in range accuracy. Primary-session bin1–4 thresholds
are 16.38, 19.29, 15.02, 6.91 dB, reflecting variable empty training evidence.
They were not tuned on the holdouts. Candidate bins and reasons remain visible.
The MVP mask is bins1–4; old cwm includes bin5. This comparison changes more than
one policy and is not an ablation establishing which change caused the result.

Same-session holdout frames are nonoverlapping but temporally correlated. Separate
acquisition-session empty stress tests are also reported. With the 002954 reference,
01 and 02 yield 0/61 each. **With the 02 reference, 002954 yields 35/61 false alarms.**
Sensor/scene invariance across these recordings is not certified; this nevertheless
shows that transferring an empty reference is unsafe. No universal low false-alarm
claim, calibrated confidence, MAE or RMSE is justified.

## Verification and limitations

- New suite: 11 passing tests, covering FFT frequency/amplitude, configuration,
  bad ADC, persistence/dropout, bin change, sequence/timestamp/error handling,
  CRC resync, raw wire recording, serial timeout/close, baseline replay/overlap.
- Legacy suite: 94 tests pass in the independent clone when its existing sibling
  vendor HAL is made available through a local symlink. Initial clone run had
  two missing-HAL errors. Original checkout run had one permission error in
  qualification generation; its dirty status remained exactly `.DS_Store`.
- Both old GUI smoke checks exited successfully with Qt's offscreen backend.
- CLI baseline and all three primary replay paths ran successfully. Tests use
  mocked serial; actual hardware acquisition is still blocked by absent device.
- Live timing compares elapsed device and host time and rejects growing backlog,
  gaps and timeout. It cannot certify initial absolute freshness without a firmware
  acknowledgment/identity protocol. No automatic reconnect or false claim of freshness.

Physical acceptance is explicitly pending; see `RANGE_V1.md` for commands, DSP
assumptions and the validation plan.
