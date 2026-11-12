"""Current 1D-support RX diagnostics; never select, suppress or calibrate distance."""
import numpy as np

from .cfar_range import refine_profile


METADATA=dict(method='rx-Hann-support-and-tone-residual-v1',
    spread_note_bins=.25,residual_note_fraction=.5,
    scope='Confirmed current 1D group, raw chirps across Doppler; inspection only',
    interpretation='RX peaks share scene/data; agreement is not accuracy or identity. Residual at pooled FFT range includes other returns and peak bias, not a fitted confidence.')


def receiver_group_diagnostics(frame,config,bins,per_rx_power,nfft,pooled_range_m):
    """Reuse the result bank's dense power, with three bounded linear fits.

    RX peaks use existing refinement rejection rules. The residual describes a
    DC/sine/cosine model at the existing pooled FFT range, not a new frequency
    search or the offline phase estimator. No value feeds back into detection.
    """
    axis=np.arange(len(per_rx_power))*config.spacing_m*config.samples/nfft
    receivers=[]
    for rx in range(3):
        fine=refine_profile(per_rx_power[:,rx],config,bins,nfft)
        value=fine['range_m']
        receivers.append(dict(rx=rx+1,range_m=value,reason=fine['reason'],boundary=fine['boundary'],
            peak_power_db=float(10*np.log10(max(float(np.interp(value,axis,per_rx_power[:,rx])),1e-12)))if value is not None else None))
    values=[r['range_m']for r in receivers if r['range_m']is not None]
    spread=float(np.ptp(values))if len(values)>=2 else None
    x=np.asarray(frame.adc[config.discard_chirps:],float).transpose(0,2,1)
    x=x-x.mean(axis=2,keepdims=True);energy_rx=np.sum(x*x,axis=(0,2))
    residual=None;residual_rx=None
    if pooled_range_m is not None and float(energy_rx.sum())>1e-20:
        phase=2*np.pi*(pooled_range_m/config.spacing_m)*np.arange(config.samples)/config.samples
        a=np.column_stack((np.cos(phase),np.sin(phase)));a-=a.mean(axis=0)
        q=np.linalg.qr(a,mode='reduced')[0]
        fitted_rx=np.sum((x@q)**2,axis=(0,2))
        residual_rx=np.clip(1-np.divide(fitted_rx,energy_rx,out=np.zeros(3),where=energy_rx>0),0,1).tolist()
        residual=float(np.clip(1-fitted_rx.sum()/energy_rx.sum(),0,1))
    flags=[]
    if len(values)<3:flags.append('rx_peak_unresolved')
    if spread is not None and spread>METADATA['spread_note_bins']*config.spacing_m:flags.append('rx_peak_disagreement')
    if residual is not None and residual>METADATA['residual_note_fraction']:flags.append('single_tone_mismatch_at_fft_range')
    return dict(frame_sequence=frame.sequence,method=METADATA['method'],support_bins=list(bins),
        support_m=[(min(bins)-.5)*config.spacing_m,(max(bins)+.5)*config.spacing_m],
        receivers=receivers,resolved_rx=len(values),spread_m=spread,flags=flags,
        pooled_fft_range_m=pooled_range_m,single_tone_residual_fraction=residual,
        per_rx_residual_fraction=residual_rx,inspection_only=True)


def current_receiver_diagnostic(reading,candidate_id=None):
    """Selection changes inspection only; mismatched or missing data never hold."""
    report=reading.get('receiver_diagnostics')
    if not reading.get('valid')or not report or report['frame_sequence']!=reading.get('frame_sequence'):return None
    if candidate_id is None:return report['nearest_confirmed_group']
    row=next((r for r in reading.get('results',{}).get('candidates',[])if r['candidate_id']==candidate_id),None)
    if not row or not row.get('one_d_confirmed'):return None
    return next((g for g in report['groups']if g['group_id']==row.get('group_id')),None)
