"""Offline diagnostic: candidate tone plus one separated nuisance tone per RX.

No presence/quality acceptance policy. Lower residual alone cannot identify a target.
"""
import numpy as np

from radar_min.phase_range import CandidatePhaseRange


class ResidualRangeModel:
    def __init__(self,config):
        self.config=config
        self.single=CandidatePhaseRange(config)
        self.cache={}
        self.metadata=dict(method='candidate-separated-nuisance-diagnostic-v1',
            candidate_grid_steps_per_bin=64,nuisance_grid_steps_per_bin=16,
            minimum_nuisance_gap_bins=1,max_iterations=4,
            interpretation='Offline diagnostic only, no accepted target distance; same-frame real tones, no scene reference or label fit')

    @staticmethod
    def projected(bases,nuisance):
        z=bases-np.einsum('ni,mi,gmk->gnk',nuisance,nuisance,bases,optimize=True)
        u,s,_=np.linalg.svd(z,full_matrices=False)
        return u*(s>1e-8)[:,None,:]

    @staticmethod
    def scores(x,q):
        return np.sum(np.einsum('tn,gnk->gtk',x,q,optimize=True)**2,axis=(1,2))

    def fit(self,frame,bins):
        # Reuse the existing input validation and preserve its single-tone decision.
        single=self.single.fit(frame,bins)
        c=self.config;bins=tuple(sorted(set(bins)))
        result=dict(single=single,diagnostic_range_m=None,reason='no_ac_energy')
        x=np.asarray(frame.adc[c.discard_chirps:],float).transpose(0,2,1)
        x=x-x.mean(axis=2,keepdims=True);energy=float(np.sum(x*x))
        if energy<=1e-20:return result
        if bins not in self.cache:
            lower,upper=bins[0]-.5,bins[-1]+.5
            near=np.linspace(lower,upper,64*len(bins)+1)
            far=np.arange(upper+1,c.samples/2-.5+1e-9,1/16)
            self.cache[bins]=(near,self.single._basis(near),far,self.single._basis(far))
        near,nq,far,fq=self.cache[bins]
        if not len(far):return dict(result,reason='no_separated_nuisance_support')
        initial=np.array([self.scores(x[:,rx],fq)for rx in range(3)])
        fi=np.argmax(initial,axis=1);nk=None;history=[];converged=False
        for iteration in range(4):
            previous=(nk,tuple(fi));score=np.zeros(len(near))
            for rx in range(3):score+=self.scores(x[:,rx],self.projected(nq,fq[fi[rx]]))
            nk=int(np.argmax(score))
            for rx in range(3):fi[rx]=int(np.argmax(self.scores(x[:,rx],self.projected(fq,nq[nk]))))
            history.append((nk,tuple(int(v)for v in fi)))
            if previous==history[-1]:converged=True;break
        # Recompute the candidate optimum after the last nuisance update.
        conditional=np.array([self.scores(x[:,rx],self.projected(nq,fq[fi[rx]]))for rx in range(3)])
        score=conditional.sum(axis=0);nk=int(np.argmax(score));coordinate=float(near[nk])
        if 0<nk<len(near)-1:
            lo,hi=float(near[nk-1]),float(near[nk+1]);ratio=(np.sqrt(5)-1)/2
            def objective(v):
                basis=self.single._basis([v])
                return sum(float(self.scores(x[:,rx],self.projected(basis,fq[fi[rx]]))[0])for rx in range(3))
            left=hi-ratio*(hi-lo);right=lo+ratio*(hi-lo);sl,sr=objective(left),objective(right)
            for _ in range(20):
                if sl>sr:
                    hi,right,sr=right,left,sl;left=hi-ratio*(hi-lo);sl=objective(left)
                else:
                    lo,left,sl=left,right,sr;right=lo+ratio*(hi-lo);sr=objective(right)
            coordinate=max(((coordinate,float(score[nk])),(left,sl),(right,sr)),key=lambda z:z[1])[0]
        qnear=self.single._basis(coordinate);residual=np.zeros_like(x);far_energy=0.;single_energy=0.
        per_rx_energy=np.sum(x*x,axis=(0,2));rx_best=near[np.argmax(conditional,axis=1)]
        for rx in range(3):
            a=np.column_stack((qnear,fq[fi[rx]]));u,s,_=np.linalg.svd(a,full_matrices=False);u=u[:,s>1e-8]
            residual[:,rx]=x[:,rx]-(x[:,rx]@u)@u.T
            far_energy+=float(np.sum((x[:,rx]@fq[fi[rx]])**2))
            single_energy+=float(np.sum((x[:,rx]@qnear)**2))
        residual_rx=np.sum(residual**2,axis=(0,2));two_energy=energy-float(residual_rx.sum())
        # Windowed residual peak is descriptive, not another accepted return.
        profile=np.mean(abs(np.fft.rfft(residual*np.hanning(c.samples),n=4096,axis=2))**2,axis=(0,1))
        axis=np.arange(len(profile))*c.samples*c.spacing_m/4096
        peak=int(np.argmax(profile[1:-1]))+1
        result.update(diagnostic_range_m=coordinate*c.spacing_m,
            reason='candidate_boundary'if nk in (0,len(near)-1)else'diagnostic_only',
            nuisance_m=(far[fi]*c.spacing_m).tolist(),nuisance_boundary=bool(np.any((fi==0)|(fi==len(far)-1))),
            nuisance_support_m=[float(far[0]*c.spacing_m),float(far[-1]*c.spacing_m)],
            iterations=iteration+1,grid_converged=converged,
            residual_fraction=float(residual_rx.sum()/energy),
            per_rx_residual_fraction=np.divide(residual_rx,per_rx_energy,out=np.ones(3),where=per_rx_energy>0).tolist(),
            candidate_unique_energy_fraction=float(max(0,two_energy-far_energy)/energy),
            nuisance_unique_energy_fraction=float(max(0,two_energy-single_energy)/energy),
            conditional_rx_range_m=(rx_best*c.spacing_m).tolist(),
            conditional_rx_spread_m=float(np.ptp(rx_best)*c.spacing_m),
            conditional_rx_boundary=((np.argmax(conditional,axis=1)==0)|(np.argmax(conditional,axis=1)==len(near)-1)).tolist(),
            comparable_candidate_optima=int(np.sum((score[1:-1]>=score[:-2])&(score[1:-1]>score[2:])&
                (score.max()-score[1:-1]<=.01*energy))),
            conditional_width_m=float(np.ptp(near[score.max()-score<=.01*energy])*c.spacing_m),
            residual_peak_m=float(axis[peak]),
            diagnostic_warning='Extra components improve in-sample fit by construction; frequency/identity and uncertainty are not validated')
        return result
