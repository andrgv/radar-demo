"""Offline near component plus two outside-support nuisance tones per RX."""
import numpy as np
from tools.supported_nuisance_fit import SupportedNuisanceFit

class MultiComponentFit(SupportedNuisanceFit):
    @staticmethod
    def span(columns):
        u,s,_=np.linalg.svd(np.column_stack(columns),full_matrices=False)
        return u[:,s>1e-6]
    def fit_associated(self,traces,candidate_bin,qualified_bins=None,max_iterations=8):
        x=np.array(traces,dtype=float,copy=True)
        if x.ndim!=2 or x.shape[1]!=self.c.samples or x.shape[0]%3 or not np.isfinite(x).all():raise ValueError('Expected finite three-RX traces')
        x=x.reshape(-1,3,self.c.samples);x-=x.mean(axis=2,keepdims=True);energy=float(np.sum(x*x))
        if energy<=1e-20:return dict(range_m=None,reason='no_ac_energy')
        low=high=candidate_bin;qset=set(qualified_bins or [])
        while low-1 in qset:low-=1
        while high+1 in qset:high+=1
        lower=(low-1)*self.c.spacing_m;upper=(high+1)*self.c.spacing_m
        mask=(self.wide_grid<lower)|(self.wide_grid>upper);grid=self.wide_grid[mask];bases=self.wide_q[mask]
        far=np.zeros((3,2),dtype=int)
        for rx in range(3):
            for j in range(2):
                q=bases if j==0 else self.projected_bases(bases,bases[far[rx,0]])
                score=np.sum(np.einsum('cn,gnk->gck',x[:,rx,:],q,optimize=True)**2,axis=(1,2));far[rx,j]=int(np.argmax(score))
        near=None;history=[];converged=False
        def objective():
            total=0.
            for rx in range(3):
                u=self.span([self.q[near],*[bases[k] for k in far[rx]]]);total+=float(np.sum((x[:,rx,:]@u)**2))
            return total/energy
        for iteration in range(max_iterations):
            oldnear=near;oldfar=far.copy();score=np.zeros(len(self.grid))
            for rx in range(3):
                u=self.span([bases[k] for k in far[rx]]);q=self.projected_bases(self.q,u)
                score+=np.sum(np.einsum('cn,gnk->gck',x[:,rx,:],q,optimize=True)**2,axis=(1,2))
            if np.argmax(score) in (0,len(score)-1):return dict(range_m=None,reason='near_search_boundary',objective_history=history)
            ids=np.flatnonzero((score[1:-1]>score[:-2])&(score[1:-1]>=score[2:]))+1;ids=ids[(self.grid[ids]>=lower)&(self.grid[ids]<=upper)]
            if not len(ids):return dict(range_m=None,reason='no_associated_peak',objective_history=history)
            proposal=int(ids[np.argmax(score[ids])])
            if near is None or score[proposal]>=score[near]:near=proposal
            history.append(objective())
            for rx in range(3):
                for j in range(2):
                    u=self.span([self.q[near],bases[far[rx,1-j]]]);q=self.projected_bases(bases,u)
                    scores=np.sum(np.einsum('cn,gnk->gck',x[:,rx,:],q,optimize=True)**2,axis=(1,2));far[rx,j]=int(np.argmax(scores))
            history.append(objective())
            if near==oldnear and np.array_equal(far,oldfar):converged=True;break
        return dict(range_m=float(self.grid[near]),reason='experimental_three_components',nuisance_m=grid[far].tolist(),iterations=iteration+1,converged=converged,residual_fraction=max(0.,1-history[-1]),objective_history=history)
