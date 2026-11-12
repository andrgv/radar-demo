"""Reproduce the stationary AVG16 edge schedule and saved-block phase review."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from radar.protocol import Parser
from radar.storage import replay

ROOT = Path(__file__).resolve().parents[1]


def review():
    recording = ROOT / 'recordings/avg16-timing-01'
    output = ROOT / 'evidence/rd-avg16-20261110'
    output.mkdir(parents=True, exist_ok=True)
    parser = Parser()
    frames = list(replay(recording, parser))
    if not frames or parser.bad_crc or parser.bad_headers or parser.buffer or parser.discarded_bytes:
        raise ValueError('Empty or damaged saved recording')
    if any(f.profile_id != 0x33515403 or f.edge_count != 272 or f.edge_overflow for f in frames):
        raise ValueError('Unexpected AVG16 profile or edge schedule')
    edges = np.array([f.edge_times_us for f in frames])
    if np.any(np.diff(edges, axis=1) <= 0):
        raise ValueError('Unordered edge timestamps')
    starts = edges[:, ::16]
    periods = np.diff(starts, axis=1)
    endpoint_period = (starts[:, -1] - starts[:, 0]) / 16
    adc = np.stack([f.adc for f in frames]).astype(float)
    adc -= adc.mean(axis=2, keepdims=True)
    window = np.hanning(64)
    spectra = np.fft.rfft(adc * window[None, None, :, None], axis=2) * (2 / window.sum())
    retained = spectra[:, 1:]
    increments = retained[:, 1:] * retained[:, :-1].conj()
    unit = increments / np.maximum(abs(increments), 1e-20)
    resultant = abs(np.mean(unit, axis=1))
    phase = np.angle(increments[:, :, 2, :])  # fixed diagnostic bin, not a target identity
    reasons = Counter(json.loads(line)['reason'] for line in (recording/'readings.jsonl').read_text().splitlines())
    period = float(np.median(endpoint_period))
    report = dict(
        recording=str(recording.relative_to(ROOT)), frames=len(frames), profile_id='0x33515403',
        raw_sha256=hashlib.sha256((recording/'frames.grd').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        saved_integrity={k: getattr(parser, k) for k in ('gaps', 'bad_crc', 'bad_headers', 'restarts', 'discarded_bytes')},
        device_errors=sorted({f.errors for f in frames}), device_drops=sorted({f.dropped for f in frames}),
        edge_counts=dict(Counter(f.edge_count for f in frames)), edge_overflow_frames=sum(f.edge_overflow for f in frames),
        groups_per_frame=17, edges_per_group=16,
        group_start_interval_us_p0_p5_p50_p95_p100=np.percentile(periods, [0, 5, 50, 95, 100]).tolist(),
        endpoint_group_period_us_p0_p5_p50_p95_p100=np.percentile(endpoint_period, [0, 5, 50, 95, 100]).tolist(),
        acquisition_path_us_p0_p5_p50_p95_p100=np.percentile([f.capture_elapsed_us for f in frames], [0, 5, 50, 95, 100]).tolist(),
        median_adjacent_phase_resultant_by_bin_rx=np.median(resultant, axis=0).tolist(),
        bin2_adjacent_phase_median_rad=np.median(phase, axis=(0, 2)).tolist(),
        host_reading_reasons=dict(reasons),
        conditional_60GHz_model=dict(assumed_saved_block_period_us=period,
            native_16_block_velocity_grid_m_s=299792458/(60e9*2*16*period*1e-6),
            unambiguous_radial_speed_m_s=299792458/(60e9*4*period*1e-6),
            verified=False, limitation='Requires AVG16 group-to-block correspondence, calibrated time/carrier and motion coherence; Hann broadens peaks.'),
        conclusion='Expected complete AVG16 schedule and stable stationary phase. Proceed to controlled motion with this image; retain timing-unverified labels.')
    (output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), constrained_layout=True)
    axes[0].eventplot(edges[1]/1000, linewidths=0.7)
    axes[0].set(xlabel='Nominal MCU time after trigger path starts (ms)', yticks=[],
                title='One complete frame: 17 groups of 16 CHIRP_ACTIVE edges')
    axes[1].plot(np.arange(1, 17), np.median(periods, axis=0), 'o-')
    axes[1].fill_between(np.arange(1, 17), np.percentile(periods, 5, axis=0),
                         np.percentile(periods, 95, axis=0), alpha=0.25, label='5th–95th percentile')
    axes[1].set(xlabel='Adjacent group-start interval', ylabel='MCU timer µs', ylim=(498, 511))
    axes[1].legend()
    for rx in range(3):
        axes[2].plot(np.arange(1, 16), np.median(phase[:, :, rx], axis=0), 'o-', label=f'RX {rx+1}')
    axes[2].axhline(0, color='black', linewidth=0.7)
    axes[2].set(xlabel='Adjacent retained-block pair', ylabel='Median phase step (rad)',
                title='Stationary phase at fixed range bin 2; timing/coherence under motion unverified')
    axes[2].legend()
    fig.savefig(output/'timing-and-phase.png', dpi=150)
    plt.close(fig)
    print(json.dumps({k: report[k] for k in ('frames', 'edge_counts', 'edge_overflow_frames', 'endpoint_group_period_us_p0_p5_p50_p95_p100', 'host_reading_reasons', 'conditional_60GHz_model')}, indent=2))


if __name__ == '__main__':
    review()
