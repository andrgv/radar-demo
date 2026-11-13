"""Reconstruct saved joint fits and inspect residuals without fitting labels."""
import json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from tools.fit_range_signal import ToneFit,traces

def main():
    out=Path('evidence/joint-residual-1');out.mkdir(parents=True,exist_ok=True)
    fitted=[json.loads(s) for s in Path('evidence/joint-component-1/frames.jsonl').read_text().splitlines()]
    groups={}
    for row in fitted:groups.setdefault(row['recording'],{})[row['sequence']]=row
    report=[]
    with (out/'frames.jsonl').open('w') as stream:
        for path,saved in groups.items():
            p=Path(path);refpath=(p.parent/'empty-001' if p.name.startswith('live-') else p.parent/(p.name.split('-')[0]+'-'+p.name.split('-')[1]+'-empty-before'))
            c,e,_=read_recording(refpath);ref=np.mean([traces(f,c) for f in e[:30]],axis=0);_,frames,_=read_recording(p,c);fit=ToneFit(c)
            axis=np.fft.rfftfreq(1024,1/c.sample_rate_hz)*299792458/(2*c.slope_hz_s);ids=np.flatnonzero((axis>=.15)&(axis<=5));near=axis<=1.5;results=[]
            for f in frames:
                record=saved.get(f.sequence)
                if record is None or record['range_m'] is None:continue
                x=(traces(f,c)-ref).reshape(-1,3,c.samples);x-=x.mean(axis=2,keepdims=True);res=np.empty_like(x)
                for rx,far in enumerate(record['diagnostic']['far_m']):
                    u,s,_=np.linalg.svd(np.column_stack((fit.basis(record['range_m']),fit.basis(far))),full_matrices=False);u=u[:,s>1e-6]
                    res[:,rx]=x[:,rx]-(x[:,rx]@u)@u.T
                fraction=float(np.sum(res**2)/np.sum(x**2))
                assert abs(fraction-record['diagnostic']['residual_fraction'])<1e-8
                spec=np.fft.rfft(res*np.hanning(c.samples)[None,None,:],n=1024,axis=2);power=np.mean(abs(spec)**2,axis=0)
                perrx=np.sum(res**2,axis=(0,2))/np.maximum(np.sum(x**2,axis=(0,2)),1e-20)
                row=dict(recording=path,sequence=f.sequence,range_m=record['range_m'],residual_fraction=fraction,rx_residual_fractions=perrx.tolist(),residual_peaks_m=axis[ids[np.argmax(power[:,ids],axis=1)]].tolist(),residual_near_power_fraction=(np.sum(power[:,near],axis=1)/np.maximum(np.sum(power,axis=1),1e-20)).tolist(),coherent_residual_fraction=float(np.sum(np.mean(res,axis=0)**2)/np.mean(np.sum(res**2,axis=(1,2)))))
                stream.write(json.dumps(row)+'\n');results.append(row)
            if results:
                report.append(dict(recording=path,frames=len(results),median_residual_fraction=float(np.median([r['residual_fraction'] for r in results])),median_rx_residual_fraction=np.median([r['rx_residual_fractions'] for r in results],axis=0).tolist(),median_rx_residual_peak_m=np.median([r['residual_peaks_m'] for r in results],axis=0).tolist(),median_rx_near_power_fraction=np.median([r['residual_near_power_fraction'] for r in results],axis=0).tolist(),median_coherent_residual_fraction=float(np.median([r['coherent_residual_fraction'] for r in results]))))
                print(p.name,report[-1],flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
