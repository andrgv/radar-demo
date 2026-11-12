"""Current-frame 1D/RD evidence bank; no physical-object identity or OR detector."""
import numpy as np

from .cfar_range import refine_profile
from .core import range_spectrum
from .rx_diagnostics import receiver_group_diagnostics


def doppler_distance(a, b, count, policy):
    delta = abs(a-b)
    return min(delta, count-delta) if policy == 'wrap' else delta


class ResultBank:
    """Confirm every 1D group without changing the frozen nearest-group baseline.

    Group continuation requires reciprocal unique overlapping support and <=1
    bin peak movement. Misses reset immediately. RD identities remain owned by
    the existing associator. Cross-path matching uses current support only.
    """
    def __init__(self, config, doppler_edge='wrap'):
        self.config = config
        self.doppler_edge = doppler_edge
        self.previous = []
        self.next_id = 1
        self.receiver_diagnostics = None

    def clear(self):
        self.previous = []
        self.receiver_diagnostics = None

    def update(self, frame, baseline, association, clusters):
        config = self.config
        observations = baseline['candidates']
        links = [[j for j, old in enumerate(self.previous)
                  if set(g['bins']) & set(old['bins']) and abs(g['range_bin']-old['range_bin']) <= 1]
                 for g in observations]
        groups = []
        for i, g in enumerate(observations):
            matches = links[i]
            old = (self.previous[matches[0]] if len(matches) == 1 and
                   sum(matches[0] in other for other in links) == 1 else None)
            gid = old['id'] if old else self.next_id
            if old is None:
                self.next_id += 1
            groups.append(dict(**g, id=gid, hits=old['hits']+1 if old else 1))
        self.previous = groups
        tracks = association['tracks']
        # Include tentative current peaks in ambiguity checks, not just measured tracks.
        peaks = [p for cluster in clusters for p in cluster['local_maxima']]
        matches = [[j for j, p in enumerate(peaks) if p['range_bin'] in g['bins']] for g in groups]
        reverse = [[i for i, js in enumerate(matches) if j in js] for j in range(len(peaks))]
        track_by_cell = {(t['current_peak']['doppler_bin'], t['current_peak']['range_bin']): t
                         for t in tracks if t.get('current_peak') is not None}
        nfft = max(4096, 8*config.samples)
        # One shared dense transform per frame for all per-return refinements.
        dense = range_spectrum(frame, config, nfft=nfft) if groups or peaks else None
        dense_power=abs(dense)**2 if dense is not None else None
        raw_profile = np.mean(dense_power, axis=(0, 2)) if dense is not None else None
        per_rx_power = np.mean(dense_power,axis=0) if groups else None
        rx_groups=[]
        nd = config.chirps-config.discard_chirps
        slow_power = None

        def rd_refine(p, measured):
            nonlocal slow_power
            result = dict(method='Doppler-conditioned-Hann-dense-peak-v1', range_m=None,
                          reason='unconfirmed_rd_peak', support_m=[(p['range_bin']-.5)*config.spacing_m,
                          (p['range_bin']+.5)*config.spacing_m])
            if not measured:
                return result
            # A nearby competing maximum can contaminate the three-row Hann slice.
            if any(q is not p and abs(q['range_bin']-p['range_bin']) <= 1 and
                   doppler_distance(q['doppler_bin'], p['doppler_bin'], nd, self.doppler_edge) <= 2
                   for q in peaks):
                result['reason'] = 'competing_rd_peak_in_refinement_support'
                return result
            if slow_power is None:
                w = np.hanning(nd)
                slow = np.fft.fftshift(np.fft.fft(dense*w[:, None, None], axis=0), axes=0)/w.sum()
                slow_power = np.mean(abs(slow)**2, axis=2)
            indices = [p['doppler_bin']+d for d in (-1, 0, 1)]
            indices = ([i % nd for i in indices] if self.doppler_edge == 'wrap'
                       else [i for i in indices if 0 <= i < nd])
            result = refine_profile(slow_power[indices].mean(axis=0), config,
                                    [p['range_bin']], nfft, result['method'])
            result['doppler_support_bins'] = indices
            return result

        def peak_row(j):
            p = peaks[j]
            t = track_by_cell.get((p['doppler_bin'], p['range_bin']))
            measured = bool(t and t['state']=='measured' and t['measurement_valid'] and
                            t['last_peak_sequence']==frame.sequence)
            fine = rd_refine(p, measured)
            frequency = p['cycles_per_saved_block']
            return dict(candidate_id=f"rd:{t['track_id']}" if t else f"peak:{p['doppler_bin']}:{p['range_bin']}",
                sources=['RD'], rd_track_id=t['track_id'] if t else None,
                state='measured' if measured else (t['state'] if t else 'tentative'),
                range_bin=p['range_bin'], support_bins=[p['range_bin']],
                nominal_range_m=p['range_bin']*config.spacing_m,
                cycles_per_saved_block=frequency,
                motion='positive phase progression' if frequency>0 else
                       'negative phase progression' if frequency<0 else 'no resolved radial motion',
                rd_fine_range=fine, rd_range_m=fine['range_m'], one_d_range_m=None,
                rd_confirmed=measured, margin_db=t['current_peak'].get('margin_db') if t else None,
                experimental_range_m=fine['range_m'],
                range_method='RD conditioned' if fine['range_m'] is not None else None,
                primary_eligible=False, association='unmatched',
                reason='RD-only scene feature; not automatically a primary distance')

        rd_rows = [peak_row(j) for j in range(len(peaks))]
        rows = []
        consumed = set()
        for i, g in enumerate(groups):
            confirmed = g['hits'] >= config.confirmation_frames
            fine = (refine_profile(raw_profile, config, g['bins'], nfft) if confirmed
                    else dict(range_m=None, reason='checking_group_persistence'))
            unique = len(matches[i]) == 1 and len(reverse[matches[i][0]]) == 1
            if unique:
                j = matches[i][0]
                row = rd_rows[j]
                consumed.add(j)
                row.update(sources=['1D', 'RD'], association='unique_range_support',
                           reason='Current support match; shared ADC evidence, identity unverified')
            else:
                row = dict(candidate_id=f"1d:{g['id']}", sources=['1D'], rd_track_id=None,
                    state='measured' if confirmed else 'tentative', range_bin=g['range_bin'],
                    nominal_range_m=g['provisional_range_m'], cycles_per_saved_block=None,
                    motion='unavailable', rd_range_m=None, rd_fine_range=None,
                    experimental_range_m=None, range_method=None, primary_eligible=False,
                    association='multiple_range_matches' if matches[i] else 'unmatched',
                    reason='1D group; RD association ambiguous' if matches[i] else '1D group without an RD match')
            row.update(group_id=g['id'], group_confirmation_hits=g['hits'], support_bins=g['bins'],
                       one_d_confirmed=confirmed, one_d_range_m=fine['range_m'], one_d_fine_range=fine)
            if confirmed:
                diagnostic=receiver_group_diagnostics(frame,config,g['bins'],per_rx_power,nfft,fine['range_m'])
                diagnostic['group_id']=g['id'];rx_groups.append(diagnostic)
            if row['experimental_range_m'] is None and fine['range_m'] is not None:
                row.update(experimental_range_m=fine['range_m'], range_method='1D group')
            if row.get('rd_range_m') is not None and fine['range_m'] is not None:
                difference = abs(row['rd_range_m']-fine['range_m'])
                row['range_difference_m'] = difference
                row['range_agreement'] = 'disagree' if difference > .5*config.spacing_m else 'within_half_native_bin'
                if row['range_agreement']=='disagree':
                    row.update(experimental_range_m=None, range_method=None,
                               reason='1D/RD fine estimates disagree by more than half a native bin; inspect separately')
            else:row['range_agreement'] = 'not_comparable'
            rows.append(row)
        for j,row in enumerate(rd_rows):
            if j in consumed:continue
            if reverse[j]:
                row.update(association='ambiguous_range_support',
                           reason='Shared 1D support has competing RD peaks; no cross-path identity assigned')
            rows.append(row)
        # Explicitly retain bounded ambiguous/missing track states without old points.
        represented = {r['rd_track_id'] for r in rows if r['rd_track_id'] is not None}
        for t in tracks:
            if t['track_id'] in represented:
                continue
            rows.append(dict(candidate_id=f"rd:{t['track_id']}", sources=['RD'], rd_track_id=t['track_id'],
                state=t['state'], support_bins=sorted({r for _, r in t['current_support_cells']}),
                range_bin=None, nominal_range_m=None, cycles_per_saved_block=None,
                motion='unavailable', one_d_range_m=None, rd_range_m=None,
                experimental_range_m=None, range_method=None, primary_eligible=False,
                association='unresolved', reason=t['reason']))
        # Preserve the exact frozen scalar output. RD-only stationary nuisances must
        # not become a primary distance simply because they persist.
        value = baseline['experimental_range_m'] if baseline['target_detected'] else None
        primary = None
        if value is not None:
            primary = dict(experimental_range_m=value, source='frozen 1D baseline',
                           reason='Current confirmed 1D fine estimate; reflector identity unverified')
            for row in rows:
                if row.get('support_bins') == baseline['selected_group_bins'] and '1D' in row['sources']:
                    row['primary_eligible'] = True
                    primary['candidate_id'] = row['candidate_id']
        self.receiver_diagnostics=dict(frame_sequence=frame.sequence,groups=rx_groups,
            nearest_confirmed_group=next((g for g in rx_groups if baseline['target_detected'] and
                g['support_bins']==baseline['selected_group_bins']),None))
        return dict(frame_sequence=frame.sequence, candidates=rows, primary=primary,
                    primary_policy='Frozen 1D baseline only; RD-only features require inspection',
                    reason='baseline_distance_available' if primary else baseline['reason'])
