# Built HPF pair and hardware experiment status

**Current hardware:** Returned to the reviewed HPF350 qualification image after
completing the 100-a captures. The 100-a separate empty-after has 0/101 false
detections (earlier unused empty frames: 0/71). The return flash verified and its
startup check returned 30 valid frames, profile 0x33514802 / flags 3, no errors
or ADC container rails. Evidence: `evidence/hpf-pair-2/flash-350-b/`.
All three authorized flashes are complete. Fresh 350-b reference/target/empty
captures remain to check repeatability before drawing the filter comparison.

**Latest state:** The 350-a control series is complete (empty, 30/50/40 cm,
untouched 40 cm repeat, empty-after). Its separate empty-after has 0/101 false
detections; earlier unused empty frames had 0/71. Individual target errors and
misses are retained in `evidence/hpf-pair-2/target-350-a-*.json`.
The authorized 100 kHz image has now been programmed and verified. Its startup
check returned 30 valid frames, profile 0x33514801 / flags 7, no transport/device
errors or ADC container rails. Evidence: `evidence/hpf-pair-2/flash-100-a/`.
Next: fresh 100-a empty reference and target series; then the authorized return
to 350. The startup check is not calibration or accuracy evidence.

**Update November 1:** User explicitly authorized the 350 -> 100 -> 350 flash
sequence. The reviewed HPF350 image was programmed, verified and reset on probe
170D0E8300023400 / CY8C624AFNI-S2D43. A three-second startup check produced 30
valid frames with profile 0x33514802, flags 3, zero transport/device errors and
no ADC container rails. Acquisition elapsed telemetry was 3461–3473 us; it is
not chirp spacing. Startup scene was unspecified and is excluded from calibration.
Evidence: `evidence/hpf-pair-2/flash-350-a/`. KitProg3's old-firmware warning was
retained; its firmware was not updated. Capture the 350-a scenes next, before
the already-authorized 100 and return-to-350 flashes. The first serial attempt
was sandbox-blocked; its partial directory is preserved. The successful check
is `recordings/hpf350-a-startup-check-2`. Original restoration image is unchanged.

The sections below describe the build-time review; statements that no flash had
occurred apply to that earlier build-only phase. Current state is recorded above.

Two isolated variants compiled successfully with ModusToolbox 3.9 and ARM GCC
14.2.1. No program, erase, reset, probe connection or serial command was executed.
Sources, BSP, generated library metadata and dependencies were copied into a
temporary build tree; the original radar-demo checkout was not used as a build
destination. All final binaries and restoration files are retained in the isolated
workspace under `artifacts/hpf-pair-2` independently of that temporary tree.

## Exact images

| Variant | Profile ID | HEX SHA256 |
|---|---|---|
| HPF350 control | 0x33514802 | a68e0646857d76d1511be8a5ec9ba2c8130a7d3ff897966afd6e391073163897 |
| HPF100 experiment | 0x33514801 | c5cd0aaf9e2a0fcdbece5194ee5d33b98b42777198ffaefe06ff605b32395389 |
| October 28 restoration | 0x33525801 | 06d8a1729f79d861a36e7c0a63997c2fffbfc7e015a60a08c1740cf98a49d123 |

Images: `artifacts/hpf-pair-2/hpf350/glass-radar-3rx.hex` and
`artifacts/hpf-pair-2/hpf100/glass-radar-3rx.hex`. Each folder also contains ELF,
linker map, build log and minimal `range-config.json`. Original HEX and ELF were
copied and hash-checked in `artifacts/hpf-pair-2/restore-oct28/` before compiling.
The restoration is the user's saved October 28 image, not a new device readback.

## Reviewed change and verification

At addresses 0x1010/0x1014/0x1018, HPF350 preserves 0x000a1161 and HPF100 clears
bit8 to obtain 0x000a1061. The operation masks only HPF1 bits 0x300 and preserves
gain, HPF2, AAF and RX enable. Common startup code reads each register, writes
the selected value, reads it back, and refuses to stream on failure. This checks
bank0 initialization only; it does not independently prove sequencer bank use,
actual analog cutoff or ramp timing. Readback checks are compiled, NOT executed
on hardware yet. There is no external scope-pin rerouting in either build.

Compared with October 28, both qualification variants add this readback logic,
new profile IDs, header flags and acquisition-path elapsed-time telemetry. That
elapsed time is not a measured chirp interval. They retain the existing waveform,
64 samples, 17 chirps, 3 RX, averaging override, gain, FIFO handling, 100 ms
schedule and 2 Mbaud UART. The original and qualification350 are not byte-identical.

The complete preprocessed source differs between the two qualification builds
in exactly THREE expressions: HPF selection, profile ID and HPF packet flag.
No other preprocessed code difference was found. Compiled main disassembly was
inspected: the 350 branch sets bit8 after clearing the mask; the 100 branch does
not. Both retain the write/read/compare loop and failure exit. Compiler relocation
addresses differ, so binary bytes are not expected to differ in only three places.

Both Intel HEX checksums pass; the complete 603-pair original register table is
present in each image. Lowering HPF happens after loading that table. Simulated
wire frames for both profiles pass the existing parser/power path, preserve
elapsed telemetry and flags, and are rejected against the old default profile.
This is host compatibility testing, not proof of live streaming after flash.

Both links warn of a LOAD segment with RWX permissions. No compiler error occurred;
the same unchanged BSP linker script is used for both images. Flash utilization:
47,100 bytes for HPF350 and 47,092 for HPF100 out of 2,097,152 available. The
warning is retained in the logs; no linker/security configuration was changed.
All 25 minimal host tests pass.

The first sandboxed attempt failed in Qt-based mtbquery CPU-feature detection
before compilation. The approved build-only retry outside the sandbox succeeded.
The failed output directory is retained as artifacts/hpf-pair-1.

## Physical experiment after explicit approval

1. Close GUI/serial readers. Program and verify the frozen HPF350 HEX using
   KitProg3, targeting the previously identified CY8C624AFNI-S2D43. Recheck its
   SHA256 before programming. Do not rebuild implicitly during flashing.
2. Confirm fresh CRC-valid frames with profile 0x33514802, flags 3, sensible
   acquisition telemetry, no device errors and no clipping. If startup fails,
   stop and diagnose; do not proceed as if a capture succeeded.
3. Keep the sensor/support/box orientation fixed. Allow the same settling period
   after each flash. Capture an empty reference (first 30 frames for fitting;
   remaining frames reserved), supported 30/50/40 cm targets, an untouched 40 cm
   repeat, then a separate empty-after recording. Ten seconds each is sufficient
   for the first comparison; labels are measured antenna-face to box front.
4. Repeat the same sequence with HPF100 (profile 0x33514801, flags 7), then HPF350
   again. The return to 350 tests drift/reproducibility. Never reuse references
   across variants/sessions. No hand-held target and no 1 m placement required.
5. Replay both frozen estimators on every frame, report MAE/bias/percentiles and
   presence acceptance separately, include empty false positives, fit residuals,
   rails/clipping and transport failures. Do not choose thresholds from holdouts.
   A brighter signal alone is not evidence of more accurate distance.

The user already confirmed the measurement reference and stationary support;
these are not unresolved setup questions. Lowering HPF is a hypothesis test and
does not add bandwidth or guarantee centimeter accuracy. No outcome is claimed
until the physical data exist. Final 350 is the qualification build; the original
image remains available for a separately authorized restoration.

Example capture ONLY after the corresponding flash has been approved/performed:

```sh
sleep 5; ./range-v1 capture recordings/hpf350-a-empty-before --port /dev/cu.usbmodem103 --config artifacts/hpf-pair-2/hpf350/range-config.json --seconds 10
```

Subsequent names: `hpf350-a-30cm`, `hpf350-a-50cm`, `hpf350-a-40cm`,
`hpf350-a-40cm-repeat`, `hpf350-a-empty-after`. Use `hpf100-a-*` with its own config
and `hpf350-b-*` on returning to 350. Capture one scene at a time with physical
repositioning between commands. New output names protect prior recordings.
Do not run this with the default old firmware config or assume a numeric fit
means the box is detected. We will inspect the first capture before continuing.

## Reproduce build-only

```sh
/Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.build_hpf_pair artifacts/new-hpf-pair
./range-v1 test
```

The builder has no programming action. It now invokes the offline verifier after
both compiles. The verifier was executed separately on the current frozen pair:

```sh
/Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.verify_hpf_pair artifacts/hpf-pair-2 artifacts/new-hpf-verification
```

The verifier uses the retained temporary build tree for preprocessing. For a
future rebuild if that tree is cleaned, use the build-only command again with a
new output directory. Evidence under `evidence/hpf-pair-2` includes manifests,
preprocessed difference, verification results and build/test logs. The binary
images remain local artifacts, not committed Git payloads.

Next user decision: explicitly approve the reviewed 350 -> 100 -> 350 flash
sequence. This approval is requested because the user's original instruction
prohibits flashing without explicit approval; build approval is not flash approval.
