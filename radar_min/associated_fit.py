"""Experimental association of a local tone-fit maximum with presence evidence.

One native FFT spacing is an association gate, not a distance uncertainty bound.
No distance labels, history, or true target position enter candidate selection.
"""
import numpy as np
from tools.fit_range_signal import ToneFit

class AssociatedFit(ToneFit):
    def prepare(self,x):
        return x-x.mean(axis=1,keepdims=True)

    def fit_associated(self,traces,candidate_bin,qualified_bins=None,allow_boundary=False):
        x=np.asarray(traces,dtype=float)
        if x.ndim!=2 or x.shape[1]!=self.c.samples or not np.isfinite(x).all():
            raise ValueError('Expected finite traces x samples')
        x=self.prepare(x);energy=float(np.sum(x*x))
        if energy<=1e-20:return dict(range_m=None,reason='no_ac_energy')
        scores=np.sum(np.einsum('ts,gsb->gtb',x,self.q,optimize=True)**2,axis=(1,2))
        if not allow_boundary and int(np.argmax(scores)) in (0,len(scores)-1):
            return dict(range_m=None,reason='dominant_fit_at_search_limit')
        maxima=np.flatnonzero((scores[1:-1]>scores[:-2])&(scores[1:-1]>=scores[2:]))+1
        low_bin=high_bin=candidate_bin
        qualified=set(qualified_bins or [])
        while low_bin-1 in qualified:low_bin-=1
        while high_bin+1 in qualified:high_bin+=1
        lower=(low_bin-1)*self.c.spacing_m;upper=(high_bin+1)*self.c.spacing_m
        eligible=maxima[(self.grid[maxima]>=lower)&(self.grid[maxima]<=upper)]
        if not len(eligible):return dict(range_m=None,reason='no_associated_local_maximum',local_maxima_m=self.grid[maxima].tolist())
        k=int(eligible[np.argmax(scores[eligible])])
        # Local quadratic refinement of the objective, not padding-derived accuracy.
        left,middle,right=scores[k-1:k+2];curvature=left-2*middle+right
        offset=float(np.clip(.5*(left-right)/curvature,-.5,.5)) if curvature<0 else 0.
        distance=float(self.grid[k]+offset*(self.grid[1]-self.grid[0]))
        if not lower<=distance<=upper:
            return dict(range_m=None,reason='refined_peak_outside_association')
        return dict(range_m=distance,reason='experimental_associated_peak',local_maxima_m=self.grid[maxima].tolist(),candidate_bin=int(candidate_bin),residual_fraction=float(max(0,1-middle/energy)))
