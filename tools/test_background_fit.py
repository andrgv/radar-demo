"""Experimental fitted background nuisance model, offline only."""
import argparse,json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from tools.fit_range_signal import ToneFit
from tools.diagnose_hpf_channels import cube


class BackgroundFit:
    def __init__(self,c,reference):
        self.c=c;self.t=np.arange(c.samples)/c.sample_rate_hz
        self.grid=np.linspace(.15,1.5,271)
        # Per-RX average background shape, with a discrete Hilbert quadrature.
        # Finite-record Hilbert quadrature is an approximation, not measured RF phase.
        bg=reference.mean(axis=0);bg-=bg.mean(axis=1,keepdims=True)
        h=np.zeros(c.samples);h[1:c.samples//2]=-1;h[c.samples//2+1:]=1
        quad=np.fft.ifft(np.fft.fft(bg,axis=1)*(1j*h),axis=1).real
        templates=np.stack([bg,quad],axis=-1)
        u,s,_=np.linalg.svd(templates,full_matrices=False)
        self.n=u*(s>np.maximum(s[:,:1]*1e-8,1e-10))[:,None,:]
        self.q=np.array([self.basis(r) for r in self.grid])

    def basis(self,r):
        phase=2*np.pi*2*self.c.slope_hz_s*r/299792458*self.t
        a=np.stack([np.cos(phase),np.sin(phase)],axis=-1);a-=a.mean(axis=0)
        a=np.broadcast_to(a,(3,*a.shape)).copy()
        a-=np.einsum('rsk,rtk,rtb->rsb',self.n,self.n,a,optimize=True)
        u,s,_=np.linalg.svd(a,full_matrices=False)
        return u*(s>1e-7)[:,None,:]

    def fit(self,x):
        x=x.transpose(1,0,2);x=x-x.mean(axis=2,keepdims=True)
        original=float(np.sum(x*x))
        x-=np.einsum('rsk,rtk,rct->rcs',self.n,self.n,x,optimize=True)
        energy=float(np.sum(x*x))
        if energy<=max(original*1e-12,1e-16):
            return dict(range_m=None,remaining_energy_fraction=energy/max(original,1e-16),residual_fraction=None,width_m=None)
        def score(r):return float(np.sum(np.einsum('rcs,rsb->rcb',x,self.basis(r))**2))
        scores=np.sum(np.einsum('rcs,grsb->grcb',x,self.q,optimize=True)**2,axis=(1,2,3));k=int(np.argmax(scores))
        lo=self.grid[max(0,k-1)];hi=self.grid[min(len(self.grid)-1,k+1)]
        g=(np.sqrt(5)-1)/2;l=hi-g*(hi-lo);r=lo+g*(hi-lo);sl=score(l);sr=score(r)
        for _ in range(35):
            if sl>sr:hi,r,sr=r,l,sl;l=hi-g*(hi-lo);sl=score(l)
            else:lo,l,sl=l,r,sr;r=lo+g*(hi-lo);sr=score(r)
        estimate,best=max([(float(self.grid[k]),float(scores[k])),(float(l),sl),(float(r),sr)],key=lambda a:a[1])
        near=self.grid[best-scores<=.01*original]
        return dict(range_m=estimate,remaining_energy_fraction=energy/original,
            residual_fraction=max(0,(energy-best)/original),width_m=float(np.ptp(near)) if len(near) else 0.)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    from radar_min.core import Config
    c=Config();t=np.arange(64)/c.sample_rate_hz
    tone=lambda d,p:np.cos(2*np.pi*2*c.slope_hz_s*d/299792458*t+p)
    reference=np.tile(tone(.9,0),(16,3,1));model=BackgroundFit(c,reference);synthetic=[]
    for d in [.3,.4,.5]:
        errors=[]
        for phase in np.arange(12)*2*np.pi/12:
            # Positive control exactly in the assumed nuisance span.
            bg=100*model.n[:,:,0]+70*np.sin(phase)*model.n[:,:,1]
            x=np.tile(bg,(16,1,1))+np.tile(20*tone(d,phase),(16,3,1))+10000
            fit=model.fit(x);errors.append(abs(fit['range_m']-d))
        synthetic.append(dict(distance_m=d,max_error_m=max(errors)))
    # A physically phase-shifted sinusoid need not lie in the finite-window Hilbert span.
    off_model=[]
    for d in [.3,.4,.5]:
        errors=[]
        for phase in np.arange(12)*2*np.pi/12:
            x=10000+np.tile((70+20*np.sin(phase))*tone(.9,phase)+20*tone(d,.7),(16,3,1))
            result=model.fit(x);errors.append(abs(result['range_m']-d))
        off_model.append(dict(distance_m=d,max_error_cm=max(errors)*100,mean_error_cm=float(np.mean(errors)*100)))
    coincident=BackgroundFit(c,np.tile(tone(.4,0),(16,3,1))).fit(np.tile(100*tone(.4,0),(16,3,1))+1000)
    report=dict(synthetic=synthetic,physical_phase_shift=off_model,coincident_target=coincident,rows=[],method=__doc__,limits='No fitted target labels or new gate. Background modes can absorb target. Late empty capture is not used for training.')
    with (a.output/'frames.jsonl').open('w') as out:
        for run in ['350-a','100-a','350-b']:
            c,empty,_=read_recording(Path(f'recordings/hpf{run}-empty-before'))
            model=BackgroundFit(c,np.mean([cube(f,c) for f in empty[:30]],axis=0))
            for suffix,label,skip in [('30cm',.3,0),('50cm',.5,0),('40cm',.4,0),('40cm-repeat',.4,0),('empty-before',None,90),('empty-after',None,30)]:
                path=Path(f'recordings/hpf{run}-{suffix}');_,frames,_=read_recording(path,c);results=[]
                for i,f in enumerate(frames[skip:]):
                    result=model.fit(cube(f,c));results.append(result);out.write(json.dumps(dict(recording=path.name,index=i+skip,**result))+'\n')
                values=np.array([r['range_m'] if r['range_m'] is not None else np.nan for r in results])
                row=dict(recording=path.name,label_m=label,frames=len(results),valid=int(np.isfinite(values).sum()),median_m=float(np.nanmedian(values)),mae_cm=float(np.nanmean(abs(values-label))*100) if label is not None else None,median_remaining_energy=float(np.median([r['remaining_energy_fraction'] for r in results])),median_residual=float(np.median([r['residual_fraction'] for r in results if r['range_m'] is not None])),median_width_m=float(np.median([r['width_m'] for r in results if r['range_m'] is not None])))
                report['rows'].append(row);print(row,flush=True)
    (a.output/'report.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
