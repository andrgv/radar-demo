"""Candidate-constrained raw real-tone/DC fit; experimental, no scene learning."""
from dataclasses import dataclass,asdict

import numpy as np


@dataclass(frozen=True)
class PhaseRangeConfig:
    max_residual_fraction: float = .5
    near_energy_fraction: float = .01
    max_width_bins: float = .5
    rx_gate_bins: float = .25
    min_supported_rx: int = 2

    def __post_init__(self):
        if not 0<self.max_residual_fraction<1 or not 0<self.near_energy_fraction<1:
            raise ValueError('Fit energy fractions must be in (0,1)')
        if not np.isfinite([self.max_width_bins,self.rx_gate_bins]).all() or min(self.max_width_bins,self.rx_gate_bins)<=0:
            raise ValueError('Fit width and RX gates must be positive')
        if type(self.min_supported_rx) is not int or not 1<=self.min_supported_rx<=3:
            raise ValueError('Supported RX count must be 1–3')


class CandidatePhaseRange:
    """Fit x[n]=DC+a*cos(w*n)+b*sin(w*n), with independent coefficients per trace.

    Frequency is shared across current chirp/RX traces. Both data and basis are
    projected off DC, avoiding window/negative-frequency peak-location bias.
    A fit is not presence detection, target identity or a calibrated error bound.
    """
    def __init__(self,config,settings=None):
        self.config=config;self.settings=settings or PhaseRangeConfig();self.cache={}
        self.metadata=dict(method='candidate-real-tone-dc-v1',settings=asdict(self.settings),
            model='Independent DC/cos/sin per chirp/RX; shared fast-time frequency; no window, baseline or label fit',
            support='Current accepted group half-bin boundaries only; no expansion across a boundary optimum',
            interpretation='Experimental estimator, empirical quality gates; not a detector or calibrated uncertainty')

    def _basis(self,bin_coordinate):
        phase=2*np.pi*np.asarray(bin_coordinate)[...,None]*np.arange(self.config.samples)/self.config.samples
        a=np.stack((np.cos(phase),np.sin(phase)),axis=-1)
        a-=a.mean(axis=-2,keepdims=True)
        return np.linalg.qr(a,mode='reduced')[0]

    def fit(self,frame,bins):
        c=self.config;s=self.settings
        bins=tuple(sorted(set(bins)))
        if not bins or any(type(k) is not int or not 1<=k<c.samples//2 for k in bins):
            raise ValueError('Usable candidate bins required')
        if any(b-a!=1 for a,b in zip(bins,bins[1:])):raise ValueError('Contiguous candidate support required')
        if frame.profile_id!=c.profile_id or frame.adc.shape!=(c.chirps,c.samples,3):
            raise ValueError('frame_config_mismatch')
        adc=np.asarray(frame.adc,dtype=float)[c.discard_chirps:]
        if not frame.flags&1 or not np.isfinite(adc).all() or np.any((adc<=0)|(adc>=65535)):
            raise ValueError('invalid_phase_fit_input')
        x=adc.transpose(0,2,1).reshape(-1,c.samples)
        x=x-x.mean(axis=1,keepdims=True)
        energy=float(np.sum(x*x))
        lower,upper=bins[0]-.5,bins[-1]+.5
        result=dict(**self.metadata,range_m=None,provisional_range_m=None,support_m=[lower*c.spacing_m,upper*c.spacing_m],
                    reason='no_ac_energy',residual_fraction=None,near_optimal_width_m=None,
                    per_rx_range_m=None,supported_rx=0)
        if energy<=1e-20:return result
        if bins not in self.cache:
            grid=np.linspace(lower,upper,64*len(bins)+1)
            self.cache[bins]=(grid,self._basis(grid))
        grid,q=self.cache[bins]
        projection=np.einsum('ts,gsb->gtb',x,q,optimize=True)
        scores_rx=np.sum(projection.reshape(len(grid),-1,3,2)**2,axis=(1,3))
        scores=scores_rx.sum(axis=1);k=int(np.argmax(scores))
        coordinate=float(grid[k]);best=float(scores[k])
        result['provisional_range_m']=coordinate*c.spacing_m
        result['residual_fraction']=float(max(0,1-best/energy))
        if k in (0,len(grid)-1):
            result['reason']='phase_fit_at_support_boundary';return result
        # Reject competing optima within a fixed fraction of current trace energy.
        maxima=np.flatnonzero((scores[1:-1]>=scores[:-2])&(scores[1:-1]>scores[2:]))+1
        comparable=[int(i) for i in maxima if best-scores[i]<=s.near_energy_fraction*energy]
        result['comparable_optima']=len(comparable)
        if len(comparable)>1:
            result['reason']='competing_phase_fits';return result
        lo,hi=float(grid[k-1]),float(grid[k+1]);ratio=(np.sqrt(5)-1)/2
        def score(v):return float(np.sum((x@self._basis(v))**2))
        left=hi-ratio*(hi-lo);right=lo+ratio*(hi-lo);sl,sr=score(left),score(right)
        for _ in range(24):
            if sl>sr:
                hi,right,sr=right,left,sl;left=hi-ratio*(hi-lo);sl=score(left)
            else:
                lo,left,sl=left,right,sr;right=lo+ratio*(hi-lo);sr=score(right)
        refined,refined_score=max(((coordinate,best),(left,sl),(right,sr)),key=lambda a:a[1])
        near=grid[(refined_score-scores)<=s.near_energy_fraction*energy]
        width=float(np.ptp(near)) if len(near) else 0.
        rx_indices=np.argmax(scores_rx,axis=0);rx_coordinates=grid[rx_indices]
        rx_energy=np.sum(x.reshape(-1,3,c.samples)**2,axis=(0,2))
        rx_residual=1-np.divide(scores_rx[rx_indices,np.arange(3)],rx_energy,out=np.zeros(3),where=rx_energy>0)
        supported=((rx_indices>0)&(rx_indices<len(grid)-1)&
                   (abs(rx_coordinates-refined)<=s.rx_gate_bins)&(rx_residual<=s.max_residual_fraction))
        result.update(provisional_range_m=float(refined*c.spacing_m),
            residual_fraction=float(max(0,1-refined_score/energy)),near_optimal_width_m=width*c.spacing_m,
            per_rx_range_m=(rx_coordinates*c.spacing_m).tolist(),per_rx_residual_fraction=rx_residual.tolist(),
            supported_rx=int(supported.sum()))
        if result['residual_fraction']>s.max_residual_fraction:result['reason']='poor_single_tone_model'
        elif width>s.max_width_bins:result['reason']='broad_phase_fit'
        elif int(supported.sum())<s.min_supported_rx:result['reason']='insufficient_consistent_rx'
        else:result.update(range_m=result['provisional_range_m'],reason='experimental_phase_range')
        return result
