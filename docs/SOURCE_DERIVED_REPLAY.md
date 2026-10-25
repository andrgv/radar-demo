# Replay with nominal firmware-derived range parameters

The additive configuration `configs/range-source-derived.json` uses the audited
5 MHz sample rate and 33.69140625 THz/s slope, with no empirical scale or offset.
Existing configurations and recordings are preserved. It retains the current
one-chirp discard policy; the audit's all-chirp calculation is independent.

From the project root in PowerShell:

```powershell
python -m radar gui --replay recordings/plate_1_3m --config configs/range-source-derived.json
```

The same command accepts `recordings/plate_0_6m` and `recordings/plate_2m`.
Passing `--config` explicitly overrides the historical metadata during replay;
it does not edit the recorded files.

This configuration validates range work only. Carrier frequency and chirp
interval remain placeholders required by the current processing API. Velocity,
angle heatmaps and 3D directions are unvalidated. The factory matrix packing,
phase convention and applicability to these raw samples remain to be resolved;
the offline matrix candidate has deliberately not been installed in processing.
See [the recording audit](RECORDING_AUDIT.md) for evidence and limitations.
