import hashlib
import json
from pathlib import Path
import re
import numpy as np
from .config import C, Config
from .protocol import Parser
from .storage import replay


def read_register_profile(path):
    content = Path(path).read_text(encoding="utf-8")
    pairs = re.findall(r"\{(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+)\}", content)
    registers = {int(address, 16): int(value, 16) for address, value in pairs}
    clock_match = re.search(r"#define\s+SYSTEM_CLOCK_HZ\s+(\d+)", content)
    if not registers or clock_match is None:
        raise ValueError("Expected a generated register-pair header with SYSTEM_CLOCK_HZ")
    return registers, int(clock_match.group(1))


def nominal_waveform(registers, clock_hz):
    control = registers[0x1500]
    divider = (control >> 16) & 0x3ff
    decimation = 1 << ((control >> 4) & 3)
    ramp_step = registers[0x1204] & 0x1ffffff
    if divider == 0 or ramp_step == 0:
        raise ValueError("This audit supports the positive-ramp ADC_IDX0/SH_IDX0 raw profile only")
    sample_rate = clock_hz / divider / decimation
    slope = ramp_step * clock_hz**2 / 2**17
    samples = registers[0x1224] & 0xfff
    crosschecks = []
    for step, count, published in [(667, 64, 0.36527864281192735), (770, 256, 0.07817353628520499)]:
        reference_slope = step * 80_000_000**2 / 2**17
        predicted = C * 5_000_000 / (2 * reference_slope * (count - 1))
        crosschecks.append({"ramp_step": step, "samples": count, "sample_rate_hz": 5_000_000,
            "published_resolution_m": published, "reproduced_resolution_m": predicted,
            "absolute_difference_m": abs(predicted - published)})
    return {"system_clock_hz_from_profile": clock_hz, "adc_sr_div": divider,
        "adc_decimation": decimation, "samples_from_sh_idx0": samples,
        "sample_rate_hz_nominal": sample_rate, "slope_hz_s_nominal": slope,
        "fft_bin_spacing_m_nominal": C * sample_rate / (2 * slope * samples),
        "sample_span_resolution_m_nominal": C * sample_rate / (2 * slope * (samples - 1)),
        "independent_official_metadata_crosschecks": crosschecks,
        "derivation_status": "Nominal source-derived model, corroborated by official configuration metadata; clock and sequencer timing not measured on hardware.",
        "chirp_interval_s": None, "carrier_hz": None}


def decode_q15_pair(word):
    upper = (word >> 16) & 0xffff
    lower = word & 0xffff
    real = upper - 65536 if upper >= 32768 else upper
    imaginary = lower - 65536 if lower >= 32768 else lower
    return complex(real, imaginary) / 32768


def factory_matrices(registers):
    addresses = {"H": [[0x1e00, 0x1e04, 0x1e08], [0x1e10, 0x1e14, 0x1e18]],
                 "E": [[0x1e40, 0x1e44, 0x1e48], [0x1e60, 0x1e64, 0x1e68]]}
    return {plane: np.array([[decode_q15_pair(registers[address]) for address in row] for row in rows])
            for plane, rows in addresses.items()}


def raw_spectrum(values):
    values = np.asarray(values, dtype=float)
    centered = values - values.mean(axis=2, keepdims=True)
    window = np.hanning(values.shape[2])
    return np.fft.rfft(centered * window[None, None, :, None], axis=2) * (2 / window.sum())


def circular_summary(radians):
    radians = np.asarray(radians)
    mean = float(np.angle(np.mean(np.exp(1j * radians))))
    concentration = float(abs(np.mean(np.exp(1j * radians))))
    differences = np.angle(np.exp(1j * (radians - mean)))
    return {"circular_mean_deg": float(np.degrees(mean)), "concentration": concentration,
        "circular_std_deg": float(np.degrees(np.sqrt(max(0, -2 * np.log(max(concentration, 1e-12)))))),
        "p05_median_p95_deg_about_mean": np.degrees(mean + np.percentile(differences, [5, 50, 95])).tolist()}


def packing_score(values):
    values = np.asarray(values, dtype=float)
    centered = values - values.mean(axis=2, keepdims=True)
    signal_rms = np.sqrt(np.mean(centered**2))
    roughness = float(np.sqrt(np.mean(np.diff(values, axis=2)**2)) / max(signal_rms, 1e-12))
    power = np.mean(abs(raw_spectrum(values))**2, axis=(0, 1, 3))
    peak = int(np.argmax(power[1:-1]) + 1)
    concentration = float(power[max(1, peak - 1):min(len(power), peak + 2)].sum() / max(power[1:].sum(), 1e-12))
    return {"difference_rms_over_signal_rms": roughness, "dominant_bin": peak,
        "three_bin_spectral_energy_fraction": concentration}


def audit_recording(path, waveform, matrices):
    path = Path(path)
    config = Config.load(path / "config.json")
    parser = Parser()
    frames = list(replay(path, parser))
    if not frames:
        raise ValueError(f"No complete frames: {path}")
    if any(frame.adc.shape != (config.chirps, config.samples, 3) for frame in frames):
        raise ValueError(f"Mixed frame dimensions: {path}")
    adc = np.array([frame.adc for frame in frames])
    frame_count, chirps, samples, receivers = adc.shape
    values = adc.astype(float)
    centered = values - values.mean(axis=2, keepdims=True)
    spectrum = raw_spectrum(values)
    power = np.mean(abs(spectrum)**2, axis=(0, 1))
    combined = power.mean(axis=1)
    peak = int(np.argmax(combined[1:-1]) + 1)
    logged = np.log(np.maximum(combined, 1e-12))
    curvature = logged[peak - 1] - 2 * logged[peak] + logged[peak + 1]
    sub_bin = float(peak + (np.clip(0.5 * (logged[peak - 1] - logged[peak + 1]) / curvature, -0.5, 0.5)
                          if curvature < -1e-12 else 0))
    rms_by_chirp = np.sqrt(np.mean(centered**2, axis=(0, 2, 3)))
    consecutive = np.sum(centered[:, 1:] * centered[:, :-1], axis=2) / np.maximum(
        np.sqrt(np.sum(centered[:, 1:]**2, axis=2) * np.sum(centered[:, :-1]**2, axis=2)), 1e-12)
    chirp_peaks = (np.argmax(np.mean(abs(spectrum)**2, axis=(0, 3))[:, 1:-1], axis=1) + 1).tolist()
    timestamps = np.array([frame.timestamp_us for frame in frames], dtype=np.uint64)
    periods = (np.diff(timestamps) & 0xffffffff).astype(float)
    nominal_spacing = waveform["fft_bin_spacing_m_nominal"]
    channels = spectrum[:, :, peak]
    cross = np.mean(channels * channels[:, :, :1].conj(), axis=1)
    raw_phase = [circular_summary(np.angle(cross[:, receiver])) for receiver in [1, 2]]
    matrix_phases = {}
    for plane, matrix in matrices.items():
        converted = np.einsum("ab,fcb->fca", matrix, channels)
        relative = np.mean(converted[:, :, 1] * converted[:, :, 0].conj(), axis=1)
        matrix_phases[plane] = circular_summary(np.angle(relative))
    variants = {"unsigned16_sample_interleaved": adc,
        "signed16_sample_interleaved": adc.astype(np.int16),
        "byte_swapped_unsigned16": adc.byteswap(),
        "receiver_major_within_chirp": adc.reshape(frame_count, chirps, receivers, samples).transpose(0, 1, 3, 2),
        "receiver_major_whole_frame": adc.reshape(frame_count, receivers, chirps, samples).transpose(0, 2, 3, 1)}
    report = {"recording": str(path), "frames": frame_count, "adc_shape": list(adc.shape),
        "samples_total": int(adc.size), "sha256_frames_grd": hashlib.sha256((path / "frames.grd").read_bytes()).hexdigest(),
        "recorded_profile_ids": sorted({frame.profile_id for frame in frames}),
        "saved_stream_crc_errors": parser.bad_crc, "saved_stream_header_errors": parser.bad_headers,
        "saved_stream_incomplete_tail_bytes": len(parser.buffer), "sequence_gaps": parser.gaps,
        "restarts": parser.restarts, "device_error_counter_increase": (frames[-1].errors - frames[0].errors) & 0xffffffff,
        "device_drop_counter_increase": (frames[-1].dropped - frames[0].dropped) & 0xffffffff,
        "trigger_interval_p05_median_p95_us": np.percentile(periods, [5, 50, 95]).tolist() if len(periods) else [],
        "adc_min_per_rx": adc.min(axis=(0, 1, 2)).tolist(), "adc_max_per_rx": adc.max(axis=(0, 1, 2)).tolist(),
        "container_rail_fraction": float(np.mean((adc == 0) | (adc == 65535))),
        "bit_one_fraction_lsb_first": [float(np.mean((adc & (1 << bit)) != 0)) for bit in range(16)],
        "channel_exact_equality_fractions": {f"RX{first + 1}_RX{second + 1}": float(np.mean(adc[:, :, :, first] == adc[:, :, :, second]))
                                             for first, second in [(0, 1), (0, 2), (1, 2)]},
        "chirp_rms_relative_to_median": (rms_by_chirp / max(np.median(rms_by_chirp), 1e-12)).tolist(),
        "chirp_peak_bins": chirp_peaks,
        "consecutive_chirp_correlation_p05_median_p95": np.percentile(consecutive, [5, 50, 95]).tolist(),
        "packing_hypotheses": {name: packing_score(candidate) for name, candidate in variants.items()},
        "raw_peak_bin": peak, "raw_peak_sub_bin": sub_bin,
        "nominal_source_model_peak_range_m": sub_bin * nominal_spacing,
        "raw_relative_phase_rx2_rx3": raw_phase,
        "factory_profile_candidate_phase_H_E": matrix_phases,
        "matrix_packing_assumption": "signed Q0.15, high half real/A, low half imaginary/B; offline comparison only, not certified by these recordings",
        "recorded_config_sample_rate_hz": config.sample_rate_hz,
        "recorded_config_slope_hz_s": config.slope_hz_s,
        "recorded_config_chirp_interval_s": config.chirp_interval_s,
        "physical_rx_order_verified": False, "chirp_interval_verified": False}
    return report, adc, spectrum


def write_audit(root, output, profile):
    root, output, profile = Path(root), Path(output), Path(profile)
    registers, clock = read_register_profile(profile)
    waveform = nominal_waveform(registers, clock)
    matrices = factory_matrices(registers)
    output.mkdir(parents=True, exist_ok=True)
    sessions = []
    plate_results = []
    for directory in sorted(root.iterdir()):
        if not (directory / "frames.grd").exists():
            continue
        report, adc, spectrum = audit_recording(directory, waveform, matrices)
        sessions.append(report)
        plot_raw_audit(directory.name, adc, spectrum, output / (directory.name + ".png"))
        truth = {"plate_0_6m": 0.6, "plate_1_3m": 1.3, "plate_2m": 2.0}.get(directory.name)
        if truth is not None:
            plate_results.append({"recording": directory.name, "surveyed_range_m": truth,
                "peak_bin": report["raw_peak_bin"], "sub_bin": report["raw_peak_sub_bin"],
                "nominal_range_m": report["nominal_source_model_peak_range_m"],
                "error_m": report["nominal_source_model_peak_range_m"] - truth})
    if not sessions:
        raise ValueError("No recording folders with frames.grd were found")
    results = {"audit_kind": "offline source and saved ADC audit; no acquisition or live configuration changes",
        "nominal_waveform": waveform, "factory_matrices_real_imag": {
            name: [[[float(value.real), float(value.imag)] for value in row] for row in matrix]
            for name, matrix in matrices.items()}, "sessions": sessions, "plate_nominal_range_checks": plate_results,
        "total_frames": sum(session["frames"] for session in sessions),
        "total_adc_containers": sum(session["samples_total"] for session in sessions),
        "limits": ["No per-chirp timestamps or sensor register readback in saved packets",
                   "Recording contains validated packets, not discarded serial bytes",
                   "Physical RX permutation cannot be identified from unnamed static scene returns alone",
                   "No labeled angular positions in current captures: factory-matrix applicability and angle accuracy remain unverified"]}
    (output / "audit.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    lines = ["# Existing-recording audit", "", f"Analyzed {results['total_frames']} frames / {results['total_adc_containers']} uint16 containers.",
        "No files in recordings, firmware or live configs were changed.", "", "## Source-derived range model", "",
        f"Nominal ADC rate: {waveform['sample_rate_hz_nominal']:.0f} Hz; ramp slope: {waveform['slope_hz_s_nominal'] / 1e12:.9f} THz/s.",
        f"FFT grid spacing at 64 samples: {waveform['fft_bin_spacing_m_nominal']:.9f} m. These values are not fitted to the plate distances.",
        "", "| Plate position | Raw peak bin | Nominal estimate | Error |", "|---|---:|---:|---:|"]
    lines += [f"| {row['surveyed_range_m']:.1f} m | {row['sub_bin']:.4f} | {row['nominal_range_m']:.4f} m | {row['error_m']:+.4f} m |" for row in plate_results]
    lines += ["", "## Raw acquisition evidence", "", "| Session | Frames | Sequence gaps | Median adjacent-chirp correlation |", "|---|---:|---:|---:|"]
    lines += [f"| {Path(row['recording']).name} | {row['frames']} | {row['sequence_gaps']} | {row['consecutive_chirp_correlation_p05_median_p95'][1]:.5f} |" for row in sessions]
    lines += ["", "## Interpretation", "",
        "The saved samples can test packing hypotheses, repeatability and range response. Correlation and smoothness do not certify physical RX labels, ADC bit alignment, unaveraged output or exact chirp timing.",
        "The nominal range derivation is independently cross-checked against two official configuration metadata values; see docs/RECORDING_AUDIT.md for provenance and the N-versus-N-1 distinction.",
        "The host angle path omits the 2x3 H/E calibration matrices present in the loaded profile. Candidate matrix phases are reported, not installed or certified.",
        "The existing 1 ms chirp interval and 60 GHz carrier remain unverified. Trigger timestamps measure approximately 100 ms frame scheduling, not intra-frame chirp timing.",
        "No new capture or sweep is required to obtain these findings. Additional work should address the identified measurement-model gaps first."]
    (output / "audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results


def plot_raw_audit(name, adc, spectrum, path):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figure = Figure(figsize=(13, 9), layout="constrained")
    FigureCanvasAgg(figure)
    figure.suptitle(name + " - raw ADC audit: no gain correction, background removal or detection threshold")
    axes = figure.subplots(2, 2)
    frame = adc[len(adc) // 2]
    for receiver in range(3):
        axes[0, 0].plot(frame[1, :, receiver], label=f"RX{receiver + 1}")
        power = np.mean(abs(spectrum[:, :, :, receiver])**2, axis=(0, 1))
        axes[0, 1].plot(10 * np.log10(power + 1e-12), label=f"RX{receiver + 1}")
    axes[0, 0].set(xlabel="Sample index", ylabel="Stored unsigned 16-bit value", title="Second chirp in a middle frame")
    axes[0, 0].legend()
    axes[0, 1].set(xlabel="FFT bin (no physical-axis assumption)", ylabel="Power (dB ADC squared)", title="All-chirp mean spectra")
    axes[0, 1].legend()
    centered = adc.astype(float) - adc.mean(axis=2, keepdims=True)
    rms = np.sqrt(np.mean(centered**2, axis=(2, 3)))
    axes[1, 0].imshow(rms.T, origin="lower", aspect="auto")
    axes[1, 0].set(xlabel="Recorded frame", ylabel="Chirp index", title="Per-chirp AC RMS (no samples discarded)")
    axes[1, 1].plot(np.sqrt(np.mean(centered**2, axis=(0, 2, 3))), "o-")
    axes[1, 1].set(xlabel="Chirp index", ylabel="AC RMS counts", title="Mean chirp amplitude through frame")
    figure.savefig(path, dpi=135)
