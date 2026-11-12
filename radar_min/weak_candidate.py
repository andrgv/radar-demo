"""Experimental weak-candidate inspection, not an automatic primary policy."""
import numpy as np

from .cfar_os import select_os_candidate
from .phase_range import PhaseRangeConfig


SETTINGS=PhaseRangeConfig()
METADATA=dict(method='os-rd-raw-peak-support-v1',min_interior_rx=SETTINGS.min_supported_rx,
    rx_gate_bins=SETTINGS.rx_gate_bins,max_width_bins=SETTINGS.max_width_bins,
    scope='One confirmed OS group, resolved OS fine peak, unique current raw RD maximum, interior raw-tone optimum and two RX frequency optima nearby',
    interpretation='Inspection only; geometry checks do not accept the phase range model. Global residual/model rejection stays visible. Existing OS FFT estimate is not calibrated target identity.')


def select_weak_candidate(reading,clusters,phase,config):
    """Use fixed peak geometry checks independently of global fit-energy quality.

    The existing phase estimator and its accepted range are never modified.
    Frequency-only RX support can survive a stronger outside return, but does
    not validate the model, physical reflector or scalar distance.
    """
    os=select_os_candidate(reading,clusters)
    result=dict(experimental_range_m=None,primary_eligible=False,inspection_only=True,
        reason=os['reason'],shape_supported=False,interior_rx=0,phase_model_accepted=False,
        phase_model_reason=None,raw_model_peak_m=None,raw_model_residual_fraction=None)
    if os['experimental_range_m']is None:return result
    if not phase:
        result['reason']='no_current_raw_peak_fit';return result
    if phase.get('frame_sequence')!=reading['frame_sequence']:
        result['reason']='mismatched_raw_peak_sequence';return result
    bins=reading['selected_group_bins'];lo=(min(bins)-.5)*config.spacing_m;hi=(max(bins)+.5)*config.spacing_m
    support=phase.get('support_m',[])
    if len(support)!=2 or not np.allclose(support,[lo,hi],rtol=0,atol=1e-12):
        result['reason']='mismatched_raw_peak_support';return result
    result.update(phase_model_reason=phase['reason'],raw_model_residual_fraction=phase.get('residual_fraction'))
    value=phase.get('provisional_range_m');result['raw_model_peak_m']=value
    result['phase_model_accepted']=phase.get('range_m')is not None
    if value is None or not np.isfinite(value)or not lo<value<hi or phase['reason']=='phase_fit_at_support_boundary':
        result['reason']='raw_peak_at_support_boundary';return result
    if phase.get('comparable_optima')!=1:
        result['reason']='raw_peak_competing_or_unresolved';return result
    width=phase.get('near_optimal_width_m')
    if width is None or not np.isfinite(width)or width>SETTINGS.max_width_bins*config.spacing_m:
        result['reason']='raw_peak_too_broad';return result
    rx=phase.get('per_rx_range_m')or[]
    supported=sum(np.isfinite(v)and lo<v<hi and abs(v-value)<=SETTINGS.rx_gate_bins*config.spacing_m for v in rx)
    result['interior_rx']=int(supported)
    if supported<SETTINGS.min_supported_rx:
        result['reason']='insufficient_interior_rx_peak_support';return result
    result.update(experimental_range_m=os['experimental_range_m'],shape_supported=True,
        reason='experimental_weak_candidate_shape_support',rd_range_bin=os['rd_range_bin'],
        rd_cycles_per_saved_block=os['rd_cycles_per_saved_block'])
    return result
