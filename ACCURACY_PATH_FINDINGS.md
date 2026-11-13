# Accuracy diagnosis: firmware image and short-window estimator

The October 28 saved HEX contains the complete 603-pair source register array,
byte for byte, at address 0x10009a08. The array also appears in the ELF at file
offset 43528. Intel HEX record checksums were validated. HEX SHA256:
06d8a1729f79d861a36e7c0a63997c2fffbfc7e015a60a08c1740cf98a49d123.
This strengthens the source-to-build chain beyond matching filenames. The user's
confirmation that they flashed October 28 supports using this as the working
baseline; it is not device flash/register readback. No hardware was accessed.

## Configuration findings

The source-derived 80 MHz clock, ADC divider 16, ramp step 690 and 64 samples
give nominal Fs=5 MHz, S=33.69140625 THz/s, capture length 12.8 us and FFT spacing
0.347585 m. This reproduces the host conversion; no arithmetic mismatch was found.
Actual ramp timing, oscillator and analog response remain unmeasured. Runtime
source disables the profile's factor-16 averaging and changes FIFO draining.
Finding the register array in the image does not validate all runtime behavior.

All three RX registers are 0x000a1161: source decode selects HPF1 350 kHz,
HPF2 active, gain 42 dB. The official
[datasheet, section 8](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bgt60cutr13aip-datasheet-en.pdf)
specifies selectable HPF1 corners including 100 and 350 kHz and nominal HPF2
40 kHz. These are attenuating filter corners, not hard minimum-range cutoffs.

| Actual distance | Expected nominal beat | Cycles in 64 samples |
|---|---:|---:|
| 30 cm | 67.43 kHz | 0.863 |
| 40 cm | 89.91 kHz | 1.151 |
| 50 cm | 112.38 kHz | 1.438 |

These beats are below HPF1's nominal corner. Filter attenuation is a concrete
hardware hypothesis, not proof that the signal is absent or the sole error cause.

## New software experiment: known tones, no noise or clutter

Generate real cosines at exactly the expected beat frequencies, sweeping starting
phase through 360 equally spaced values. Apply our 64-sample mean removal, Hann
window, 4096-point FFT and unchanged 0.15–1.50 m peak-search interval. This isolates
the estimator response; it does not simulate analog startup or actual RX phases.
There is no empty subtraction in this ideal zero-background experiment.

| True simulated distance | Min / median / max estimated distance over phase |
|---|---:|
| 30 cm | 15.2 / 33.1 / 36.9 cm |
| 40 cm | 28.8 / 37.5 / 40.7 cm |
| 50 cm | 42.9 / 46.2 / 48.3 cm |

The lower 15.2 cm value is the fixed search boundary. These are phase-sweep extrema,
not real-world error bounds or probabilities. A real sinusoid has positive and
negative frequency components; for so few cycles, their windowed lobes overlap.
Mean subtraction also changes the signal itself. Thus even an exact FFT and dense
interpolation do not guarantee an unbiased peak. The synthetic 28.8 cm result is
consistent with one possible mechanism for observed 40 cm bias, not attribution.

Removing mean subtraction improves the ideal 40/50 cm examples but is not a live
fix: replaying both actual sweeps with identically processed empty references
made all eight target-recording MAEs worse. ADC offsets/leakage/clutter are absent
from the ideal-tone example. This ablation changes only mean removal; it does not
validate a better background model. Neither variant supplies empty-scene rejection.

| Recording | Current peak MAE | Without mean removal |
|---|---:|---:|
| Sweep 1, 30 cm | 4.43 cm | 20.54 cm |
| Sweep 1, 40 cm | 4.95 cm | 24.79 cm |
| Sweep 1, 50 cm | 19.69 cm | 41.89 cm |
| Sweep 1, 40 cm repeat | 15.97 cm | 24.79 cm |
| Sweep 2, 30 cm | 13.51 cm | 14.72 cm |
| Sweep 2, 40 cm | 10.82 cm | 17.15 cm |
| Sweep 2, 50 cm | 11.38 cm | 22.11 cm |
| Sweep 2, 40 cm repeat | 11.19 cm | 23.97 cm |

All frames are included. Current values reproduce the prior sweep method.
The saved spectra show broad overlapping changes. Sweep 2's 30 cm median peak
is 73.24 kHz, while 40 cm is 65.92 kHz and its repeat 64.70 kHz: movement is not
monotonic. A single conversion-factor correction cannot resolve this inversion.
Empty holdouts also produce spectral maxima; none of these ungated maxima is
an independently established target identity.

## Concrete next experiment

First test an offline physical signal fit that estimates sinusoid frequency,
phase/amplitude and DC offset jointly, rather than discarding the sample mean
and taking a windowed peak. Require recovery of known frequencies across phase,
then evaluate entire held-out real recordings and empty controls. Fix the search
interval before scoring and report ambiguous fits and model residuals. This is
a falsifiable candidate, not a promise it can separate multipath from a box.
Existing recordings suffice; do not request more box captures for this step.

If that fails, the prepared HPF qualification experiment is the hardware next
step: matched 350 -> 100 -> 350 kHz variants with readback, fixed waveform/gain,
fresh empty reference and unused empty holdout for each variant, and supported
30/40/50 cm placements in repeated order. Score raw spectra, accuracy, rejected
readings, clipping and empty false alarms together. Compile/review both isolated
variants and preserve the original image before requesting explicit flash approval.
The only intended RX-register change is 0xa1161 -> 0xa1061 at 0x1010/14/18.
Existing qualification sources are not newly built or flashed in this analysis.
Lower HPF can increase leakage and may not improve accuracy. Wider sampled
bandwidth remains a separate experiment if these steps are inadequate.

## Reproduce

From the isolated wavvy-range-v1 directory, choose a new output directory:

```sh
MPLCONFIGDIR=/tmp/wavvy-mpl /Users/chekaylimeyer/radar-work/radar-demo/.venv/bin/python -m tools.check_accuracy_path /Users/chekaylimeyer/radar-work/radar-demo artifacts/new-accuracy-check
./range-v1 test
```

Evidence: `evidence/accuracy-path-1/report.json` and `spectra.png` contain the
binary match, numerical results, recording hashes and spectra. The diagnostic
does not change live processing, firmware, recordings or the original repository.
