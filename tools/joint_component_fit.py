"""Offline alternating two-component fit; no hardware or live integration.

One shared near frequency and one far nuisance frequency per RX. Amplitudes,
phases and DC are independent for every chirp/RX. Frequency grids are fixed.
"""
import numpy as np
from tools.evaluate_far_component import FarComponentFit

class JointComponentFit(FarComponentFit):
    def projected_bases(self,bases,nuisance):
        z=bases-np.einsum('nm,gmk->gnk',nuisance@nuisance.T,bases,optimize=True)
        q,s,_=np.linalg.svd(z,full_matrices=False)
        return q*(s>1e-6)[:,None,:]

    def total_score(self,x,near,far):
        total=0.
        for rx,k in enumerate(far):
            u,s,_=np.linalg.svd(np.column_stack((self.q[near],self.far_q[k])),full_matrices=False)
            u=u[:,s>1e-6];total+=float(np.sum((x[:,rx,:]@u)**2))
        return total

    def fit_associated(self,traces,candidate_bin,qualified_bins=None,max_iterations=8):
        a=np.asarray(traces,dtype=float)
        if a.ndim!=2 or a.shape[1]!=self.c.samples or a.shape[0]%3 or not np.isfinite(a).all():
            raise ValueError('Expected finite chirp-major, three-RX traces')
        x=a.reshape(-1,3,self.c.samples);x=x-x.mean(axis=2,keepdims=True)
        energy=float(np.sum(x*x))
        if energy<=1e-20:return dict(range_m=None,reason='no_ac_energy')
        low=high=candidate_bin;qualified=set(qualified_bins or [])
        while low-1 in qualified:low-=1
        while high+1 in qualified:high+=1
        initial=np.sum(np.einsum('crn,gnk->rgck',x,self.far_q,optimize=True)**2,axis=(2,3))
        far=np.argmax(initial,axis=1);near=None;history=[];converged=False
        for iteration in range(max_iterations):
            oldnear=near;oldfar=far.copy();scores=np.zeros(len(self.grid))
            for rx,k in enumerate(far):
                q=self.projected_bases(self.q,self.far_q[k])
                scores+=np.sum(np.einsum('cn,gnk->gck',x[:,rx,:],q,optimize=True)**2,axis=(1,2))
            if np.argmax(scores) in (0,len(scores)-1):
                return dict(range_m=None,reason='near_search_boundary',iterations=iteration,objective_history=history)
            ids=np.flatnonzero((scores[1:-1]>scores[:-2])&(scores[1:-1]>=scores[2:]))+1
            ids=ids[(self.grid[ids]>=(low-1)*self.c.spacing_m)&(self.grid[ids]<=(high+1)*self.c.spacing_m)]
            if not len(ids):return dict(range_m=None,reason='no_associated_peak',iterations=iteration,objective_history=history)
            proposal=int(ids[np.argmax(scores[ids])])
            # Preserve coordinate descent if a new local-maximum selection is worse.
            if near is None or scores[proposal]>=scores[near]:near=proposal
            history.append(self.total_score(x,near,far)/energy)
            for rx in range(3):
                q=self.projected_bases(self.far_q,self.q[near])
                scores_rx=np.sum(np.einsum('cn,gnk->gck',x[:,rx,:],q,optimize=True)**2,axis=(1,2))
                far[rx]=int(np.argmax(scores_rx))
            history.append(self.total_score(x,near,far)/energy)
            if near==oldnear and np.array_equal(far,oldfar):converged=True;break
        return dict(range_m=float(self.grid[near]),reason='experimental_joint_components',far_m=self.far_grid[far].tolist(),iterations=iteration+1,converged=converged,objective_history=history,residual_fraction=max(0.,1-history[-1]),far_boundary=bool(np.any((far==0)|(far==len(self.far_grid)-1))))
