"""Replay maps and optional empirical CFAR candidates; no physical velocity scale."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .core import Continuity, db, range_spectrum


class RangeDoppler:
    def __init__(self, config):
        self.config = config
        self.count = config.chirps - config.discard_chirps
        if self.count < 4:
            raise ValueError('Doppler diagnostics require at least four retained chirps')
        self.window = np.hanning(self.count)
        self.doppler = np.fft.fftshift(np.fft.fftfreq(self.count))
        self.guard = Continuity(config)

    def update(self, frame):
        start = time.perf_counter()
        reason = self.guard.check(frame)
        full = moving = None
        diagnostics = dict(sequence=frame.sequence, timestamp_us=frame.timestamp_us,
                           valid=False, reason=reason, phase_probe=None)
        try:
            if not frame.flags & 1:
                raise ValueError('invalid_frame_flags')
            spectrum = range_spectrum(frame, self.config)
            if reason:
                raise ValueError(reason)

            def transform(x):
                slow = np.fft.fftshift(np.fft.fft(
                    x*self.window[:, None, None], axis=0), axes=0)/self.window.sum()
                return np.mean(np.abs(slow)**2, axis=2)

            full = transform(spectrum)
            moving = transform(spectrum-spectrum.mean(axis=0, keepdims=True))
            # A diagnostic probe, not an associated target or coherence certificate.
            range_power = np.mean(np.abs(spectrum)**2, axis=(0, 2))
            k = int(np.argmax(range_power[1:-1]))+1
            channels = spectrum[:, k, :]
            increments = channels[1:]*channels[:-1].conj()
            weights = np.abs(increments)
            unit = np.divide(increments, weights, out=np.zeros_like(increments), where=weights > 0)
            resultant = np.mean(unit, axis=0)
            probe = dict(range_bin=k, mean_power=float(range_power[k]),
                         phase_step_rad=np.angle(resultant).tolist(),
                         phase_step_resultant=np.abs(resultant).tolist(),
                         amplitude_by_chirp_rx=np.abs(channels).tolist(),
                         adjacent_phase_step_rad=np.angle(increments).tolist())
            # Exclude fast-time DC/Nyquist only from the diagnostic peak search.
            d, r = np.unravel_index(np.argmax(full[:, 1:-1]), full[:, 1:-1].shape)
            diagnostics.update(valid=True, reason='diagnostic_only', phase_probe=probe,
                               peak_range_bin=int(r+1), peak_doppler_bin=int(d),
                               peak_cycles_per_saved_block=float(self.doppler[d]))
        except ValueError as error:
            diagnostics['reason'] = str(error)
        diagnostics['processing_ms'] = (time.perf_counter()-start)*1000
        return full, moving, diagnostics


def viewer(full, moving, diagnostics, config, doppler, *, snapshot=None, show=False, cfar=None):
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharex=True, sharey=True)
    fig.subplots_adjust(bottom=0.23, top=0.78, wspace=0.18)
    # Shared scale within each frame makes subtraction effects directly comparable.
    extent = [-0.5, config.samples/2+0.5,
              doppler[0]-0.5/len(doppler), doppler[-1]+0.5/len(doppler)]
    images = [ax.imshow(np.zeros(full.shape[1:]), origin='lower', aspect='auto', extent=extent)
              for ax in axes]
    titles = ('Full map — accepted cells outlined; × = local maxima', 'Full power / empirical CFAR threshold') if cfar else (
        'Full map — stationary returns retained', 'Slow-time mean removed — may suppress slow obstacles')
    for ax, title in zip(axes, titles):
        ax.set_title(title, fontsize=10)
        ax.set_xlabel(f'Native range bin (nominal spacing {config.spacing_m:.3f} m)')
    axes[0].set_ylabel('Cycles/saved block — physical timing unverified')
    if cfar:
        fig.colorbar(images[0], ax=axes[0], label='dB ADC units²')
        fig.colorbar(images[1], ax=axes[1], label='dB above/below CFAR threshold')
        outlines = axes[0].scatter([], [], marker='s', facecolors='none', edgecolors='white', s=28, linewidths=.6)
        peaks = axes[0].scatter([], [], marker='x', c='red', s=35)
        if 'associations' in cfar:
            axes[0].set_title('Full map: CFAR × · measured tracks ○ · ambiguous support ◇',fontsize=9)
            measured_tracks = axes[0].scatter([],[],marker='o',facecolors='none',edgecolors='cyan',s=85,linewidths=1.5)
            ambiguous_support = axes[0].scatter([],[],marker='D',facecolors='none',edgecolors='orange',s=40,linewidths=.9)
            track_labels = []
    else:
        fig.colorbar(images[0], ax=axes, label='dB ADC units²')
    slider = Slider(fig.add_axes([0.18, 0.08, 0.62, 0.035]), 'Frame',
                    0, max(1, len(diagnostics)-1), valinit=0, valstep=1)

    def draw(index):
        index = min(int(index), len(diagnostics)-1)
        item = diagnostics[index]
        valid = item['valid']
        ceiling = float(db(np.max(full[index]))) if valid else 0
        images[0].set_data(db(full[index]) if valid else np.ma.masked_all(full.shape[1:]))
        images[0].set_clim(ceiling-60, ceiling)
        if cfar:
            ratio = np.divide(full[index], cfar['threshold'][index],
                              out=np.full_like(full[index], np.nan), where=np.isfinite(cfar['threshold'][index]))
            images[1].set_data(np.ma.masked_invalid(db(ratio)) if valid else np.ma.masked_all(full.shape[1:]))
            images[1].set_clim(-12, 12)
            cells = np.argwhere(cfar['accepted'][index])
            outlines.set_offsets(np.array([[r, doppler[d]] for d, r in cells]).reshape(-1, 2))
            maxima = [p for group in cfar['reports'][index]['clusters'] for p in group['local_maxima']]
            peaks.set_offsets(np.array([[p['range_bin'], p['cycles_per_saved_block']] for p in maxima]).reshape(-1, 2))
            detail = f"{len(cells)} accepted cells · {len(cfar['reports'][index]['clusters'])} candidate groups · no object association"
            if 'associations' in cfar:
                from collections import Counter
                report = cfar['associations'][index]
                measured = [t for t in report['tracks'] if t['measurement_valid']]
                coords = [(t['measurement']['range_bin'],t['measurement']['cycles_per_saved_block'])for t in measured]
                measured_tracks.set_offsets(np.array(coords).reshape(-1,2))
                support = sorted({tuple(cell)for t in report['tracks']if t['state']=='ambiguous'for cell in t['current_support_cells']})
                ambiguous_support.set_offsets(np.array([(r,doppler[d])for d,r in support]).reshape(-1,2))
                for label in track_labels:label.remove()
                track_labels.clear()
                for track,(x,y)in zip(measured,coords):
                    track_labels.append(axes[0].annotate(str(track['track_id']),(x,y),xytext=(4,5),
                        textcoords='offset points',color='cyan',fontsize=8))
                states = Counter(t['state']for t in report['tracks'])
                detail = (f"{len(measured)} measured · {states['tentative']} tentative · "
                          f"{states['ambiguous']} ambiguous · {states['missed']} missed · feature IDs, object identity unverified")
        else:
            images[1].set_data(db(moving[index]) if valid else np.ma.masked_all(full.shape[1:]))
            images[1].set_clim(ceiling-60, ceiling)
            detail = 'Timing/carrier unverified · no m/s, object detection or calibrated distance'
        reason = cfar['reports'][index]['reason'] if cfar else item['reason']
        if cfar and 'associations' in cfar:reason = cfar['associations'][index]['reason']
        elapsed = item['processing_ms']+item.get('cfar_processing_ms', 0)+item.get('association_processing_ms',0)
        fig.suptitle(f"Sequence {item['sequence']} | {reason} | "
                     f"DSP {elapsed:.2f} ms\n"
                     + detail)
        fig.canvas.draw_idle()

    slider.on_changed(draw)
    draw(0)
    if snapshot:
        fig.savefig(snapshot, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def run_replay(args):
    from .__main__ import read_recording, stats

    config, frames, parser = read_recording(args.recording)
    processor = RangeDoppler(config)
    cfar_detector = None
    cfar = None
    associator = None
    associations = []
    if getattr(args,'associate',False) and getattr(args,'detector','none')!='cfar2d':
        raise ValueError('--associate requires --detector cfar2d')
    if getattr(args, 'detector', 'none') == 'cfar2d':
        from .cfar_2d import CaCfar2D, Cfar2DConfig
        settings = Cfar2DConfig(args.rd_guard_range, args.rd_guard_doppler,
            args.rd_training_range, args.rd_training_doppler, args.rd_min_training,
            args.rd_factor, args.rd_doppler_edge)
        cfar_detector = CaCfar2D((processor.count, config.samples//2+1), settings)
        if getattr(args,'associate',False):
            from .rd_association import AssociationConfig, CandidateAssociator
            association_settings = AssociationConfig(args.track_confirmation,args.track_birth_margin,
                args.track_range_gate,args.track_doppler_gate,args.track_max_missed,
                args.track_max_ambiguous,args.track_ambiguity_gap,getattr(args,'track_range_metric','native'))
            associator = CandidateAssociator(config,association_settings,settings.doppler_edge)
    output = Path(args.output) if args.output else None
    if output:
        output.mkdir(parents=True, exist_ok=False)
    shape = (len(frames), processor.count, config.samples//2+1)
    full = np.full(shape, np.nan)
    moving = np.full(shape, np.nan)
    diagnostics = []
    if cfar_detector:
        cfar = dict(noise=np.full(shape, np.nan), threshold=np.full(shape, np.nan),
                    accepted=np.zeros(shape, dtype=bool), reports=[])
        if associator:cfar['associations'] = associations
    for i, frame in enumerate(frames):
        a, b, item = processor.update(frame)
        if item['valid']:
            full[i], moving[i] = a, b
        if cfar_detector:
            started = time.perf_counter()
            clusters = []
            if item['valid']:
                noise, threshold, accepted, clusters = cfar_detector.detect(a)
                cfar['noise'][i], cfar['threshold'][i], cfar['accepted'][i] = noise, threshold, accepted
                for group in clusters:
                    for peak in [group['peak'], *group['local_maxima']]:
                        d, r = peak['doppler_bin'], peak['range_bin']
                        peak.update(noise_power=float(noise[d, r]), threshold_power=float(threshold[d, r]),
                                    margin_db=float(db(a[d, r]/threshold[d, r])))
            item.update(cfar_processing_ms=(time.perf_counter()-started)*1000,
                        cfar_accepted_cells=int(cfar['accepted'][i].sum()), cfar_clusters=len(clusters))
            cfar['reports'].append(dict(sequence=frame.sequence, timestamp_us=frame.timestamp_us,
                valid=item['valid'], reason='cfar_candidates_only' if item['valid'] else item['reason'], clusters=clusters))
            if associator:
                started = time.perf_counter()
                association = associator.update(frame,a,cfar['threshold'][i],cfar['accepted'][i],clusters,
                                                valid=item['valid'],reason=item['reason'])
                associations.append(association)
                item.update(association_processing_ms=(time.perf_counter()-started)*1000,
                            association_valid=association['valid'],association_reason=association['reason'],
                            measured_tracks=sum(t['measurement_valid']for t in association['tracks']),
                            ambiguous_tracks=sum(t['state']=='ambiguous'for t in association['tracks']))
        diagnostics.append(item)
    metadata = dict(
        algorithm='range-doppler-diagnostic-v1', config=asdict(config),
        config_fingerprint=config.fingerprint,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        range_source_sha256=hashlib.sha256(Path(__file__).with_name('core.py').read_bytes()).hexdigest(),
        recording=str(Path(args.recording).resolve()),
        raw_sha256=hashlib.sha256((Path(args.recording)/'frames.grd').read_bytes()).hexdigest(),
        frames=len(frames), valid_frames=sum(d['valid'] for d in diagnostics), serial=stats(parser),
        axes=['frame', 'shifted_doppler', 'range'], power_units='ADC units squared',
        normalization='fast-time 2/sum(Hann); slow-time 1/sum(Hann); mean RX power',
        timing_verified=False, carrier_verified=False, calibrated=False,
        doppler_units='cycles/saved block (physical timing unverified)',
        legacy_axis_alias='maps.npz cycles_per_chirp is an alias of cycles_per_saved_block for existing replay tools; it does not certify chirp correspondence',
        motion_sign='positive means positive phase progression, physical approach sign unverified',
        validity='frame ADC/flags and device continuity only; no host freshness or RF coherence certification',
        moving_view='unweighted slow-time mean removed before Hann; no central-bin notch',
        phase_probe='strongest usable range bin each frame; may switch reflectors; not proof of timing/coherence',
        limitations='No CFAR or target identity. DC/Nyquist retained in maps, excluded from peak search. '
                     'Independent bursts never stitched. Nominal range scale only.')
    if cfar_detector:
        metadata.update(algorithm='range-doppler-ca-cfar-replay-v1', cfar=asdict(settings),
            cfar_source_sha256=hashlib.sha256(Path(__file__).with_name('cfar_2d.py').read_bytes()).hexdigest(),
            cfar_input='Full linear-power map; zero Doppler retained; no mean or background subtraction',
            cfar_range_policy='DC/Nyquist excluded from tests and references; all other bins tested; range truncated, never wrapped',
            cfar_doppler_policy=settings.doppler_edge,
            clustering='Eight-connected accepted cells with the same Doppler edge policy; all local maxima exported inside each component',
            threshold_interpretation='Empirical multiplier; no calibrated Pfa or measured false-output rate',
            limitations='Candidate cells/groups only; no target identity, tracking or calibrated velocity/distance. '
                         'Connected groups can merge moving and stationary returns; local maxima expose ambiguity.')
    if associator:
        metadata.update(algorithm='range-doppler-associated-cfar-replay-v1',association=asdict(association_settings),
            association_source_sha256=hashlib.sha256(Path(__file__).with_name('rd_association.py').read_bytes()).hexdigest(),
            association_policy='Reciprocal unique best native-bin gating; ambiguous competition withheld; IDs are radar features, not semantic objects',
            association_measurements='Confirmed unique current local maxima only; no extrapolated/held distance. Accepted-cell-only support is bounded ambiguity and never moves the anchor or confirms a track.',
            association_validity='Device continuity and map validity; reset on gaps/invalid frames. No original host freshness certification.',
            association_valid_frames=sum(r['valid']for r in associations),
            limitations='Conservative radar feature tracks only. Static clutter can confirm; merges/crossings can fragment IDs. '
                         'Ambiguous/missed/lost tracks have no measurement. No calibrated range/velocity or intended-object identity.')
    if output:
        (output/'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False))
        with (output/'diagnostics.jsonl').open('w') as stream:
            for item in diagnostics:
                stream.write(json.dumps(item, allow_nan=False)+'\n')
        np.savez_compressed(output/'maps.npz', full_power=full, moving_power=moving,
                            cycles_per_saved_block=processor.doppler,
                            cycles_per_chirp=processor.doppler,
                            nominal_range_m=np.arange(shape[2])*config.spacing_m,
                            valid=np.array([d['valid'] for d in diagnostics]))
        if cfar_detector:
            np.savez_compressed(output/'cfar.npz', noise_power=cfar['noise'], threshold_power=cfar['threshold'],
                reference_count=cfar_detector.counts, accepted=cfar['accepted'],
                testable=cfar_detector.testable, valid=np.array([d['valid'] for d in diagnostics]))
            with (output/'candidates.jsonl').open('w') as stream:
                for item in cfar['reports']:
                    stream.write(json.dumps(item, allow_nan=False)+'\n')
        if associator:
            with (output/'tracks.jsonl').open('w') as stream:
                for report in associations:
                    stream.write(json.dumps(report,allow_nan=False)+'\n')
    viewer(full, moving, diagnostics, config, processor.doppler,
           snapshot=output/'preview.png' if output else None,
           show=args.show or output is None, cfar=cfar)
    print(json.dumps(dict(frames=metadata['frames'], valid_frames=metadata['valid_frames'],
                          output=str(output) if output else None, timing_verified=False)))
    return 0
