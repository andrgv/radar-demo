"""Review saved joint live timing and stationary near-range detection evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.core import Config, db


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='Existing joint regression output directory')
    parser.add_argument('--nominal-target-m',type=float,required=True)
    args=parser.parse_args()
    config=Config.load(args.recording/'config.json')
    rows=[json.loads(x) for x in (args.recording/'readings.jsonl').read_text().splitlines()]
    settings=json.loads((args.recording/'metadata.json').read_text())['detector']['one_d_cfar']
    times=np.array([r['clock_sync']['host_elapsed_s'] for r in rows])
    p=np.array([r['one_d']['power'] for r in rows])
    threshold=np.array([r['one_d']['threshold_power'] for r in rows],dtype=float)
    bins=sorted({int(np.floor(args.nominal_target_m/config.spacing_m)),int(np.ceil(args.nominal_target_m/config.spacing_m))})
    measurements=[[t['measurement'] for t in r['association']['tracks'] if t['measurement_valid']] for r in rows]
    fine=[(times[i],c['range_bin'],c['rd_range_m']) for i,r in enumerate(rows) for c in r['results']['candidates'] if c.get('rd_range_m') is not None]
    frozen=[r for r in rows if r['clock_sync']['state']=='frozen']
    strong_reference=[]
    for k in bins:
        usable=np.arange(1,len(p[0])-1)
        distance=abs(usable-k)
        refs=usable[(distance>settings['guard_cells']) & (distance<=settings['guard_cells']+settings['training_cells'])]
        fraction=(p[:,[6,7]].sum(axis=1)/p[:,refs].sum(axis=1)) if 6 in refs and 7 in refs else None
        strong_reference.append(dict(tested_bin=k,reference_bins=refs.tolist(),
            median_reference_power_fraction_from_bins6_7=float(np.median(fraction)) if fraction is not None else None))
    report=dict(recording=str(args.recording),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        raw_sha256=hashlib.sha256((args.recording/'frames.grd').read_bytes()).hexdigest(),
        nominal_target_m=args.nominal_target_m,endpoint_region_bins=bins,
        interpretation='Approximate user target placement; endpoint-bin feature counts do not establish reflector identity. Strong farther returns contribute to current 1D training references; their physical origin is unverified.',
        frames=len(rows),host_span_s=float(times[-1]),
        clock_states=dict(Counter(r['clock_sync']['state'] for r in rows)),
        frozen_residual_ms_p50_p95_max=np.percentile([abs(r['clock_sync']['residual_s'])*1000 for r in frozen],[50,95,100]).tolist() if frozen else None,
        fit_diagnostics=frozen[0]['clock_sync'].get('fit_diagnostics') if frozen else None,
        primary_frames=sum(bool(r['results']['primary']) for r in rows),
        one_d_reasons=dict(Counter(r['one_d']['reason'] for r in rows)),
        one_d_qualified_frames=sum(bool(r['one_d']['qualified_bins']) for r in rows),
        rd_confirmed_endpoint_region_frames=sum(any(p['range_bin'] in bins for p in row) for row in measurements),
        rd_confirmed_bin_counts=dict(Counter(str(p['range_bin']) for row in measurements for p in row)),
        native_margin_db_p05_p50_p95_bins1_9=np.percentile(db(p[:,1:10]/threshold[:,1:10]),[5,50,95],axis=0).tolist(),
        endpoint_reference_diagnostics=strong_reference,
        rd_fine_range_cm_by_bin={str(k):dict(frames=sum(b==k for _,b,_ in fine),
            p05_p50_p95=np.percentile([v*100 for _,b,v in fine if b==k],[5,50,95]).tolist()) for k in sorted({b for _,b,_ in fine})})
    (args.output/'scene-review.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(12,10),layout='constrained')
    axes[0].plot(times,[r['clock_sync']['residual_s']*1000 for r in rows],'.',ms=2)
    if frozen:axes[0].axvline(frozen[0]['clock_sync']['host_elapsed_s'],color='gray',ls='--',label='Clock frozen')
    axes[0].set(xlabel='Host elapsed seconds',ylabel='Clock residual (ms)',title='Recorded clock mapping; no rejections')
    axes[0].legend()
    x=np.arange(1,10)*config.spacing_m
    axes[1].plot(x,np.median(db(p[:,1:10]),axis=0),'o-',label='Native power')
    axes[1].plot(x,np.median(db(threshold[:,1:10]),axis=0),'o-',label='1D threshold')
    axes[1].axvline(args.nominal_target_m,color='black',ls='--',label='Approximate target placement')
    axes[1].axvspan(.5*config.spacing_m,4.5*config.spacing_m,color='gray',alpha=.1,label='1D tested bins 1–4')
    axes[1].set(xlabel='Nominal range (m)',ylabel='Median dB ADC units²',title='Farther bins contribute to near-range thresholds')
    axes[1].legend(fontsize=8)
    for k in sorted({b for _,b,_ in fine}):
        points=[(t,v*100) for t,b,v in fine if b==k]
        axes[2].plot([t for t,_ in points],[v for _,v in points],'.',ms=2,label=f'RD fine, native bin {k}')
    axes[2].axhline(args.nominal_target_m*100,color='black',ls='--')
    axes[2].set(xlabel='Host elapsed seconds',ylabel='Experimental cm',ylim=(0,250),title='Current RD fine inspection values; 1D primary blank throughout')
    axes[2].legend(fontsize=8,ncol=3)
    fig.savefig(args.output/'scene-review.png',dpi=150);plt.close(fig)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
