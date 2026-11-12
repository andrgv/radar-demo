#!/usr/bin/env python3
"""Falsifiable direct-path vs coherent single-floor-bounce FMCW audit.

Run from radar-demo:
  .venv/bin/python tools/two_path_geometry_audit.py \
    recordings/box-angle-01 --config configs/qualification-hpf350.json \
    --output artifacts/two-path-audit-01

Training poses only: center,left,right,up,down. Other poses are never used
when fitting common receiver phases or the floor reflection coefficient.
The test uses known fixture X/Y as an *optimistic upper bound*, but never
passes held-out height to the inversion. This is NOT robot-ready localization.

The model approximates the TX/RX antennas as colocated, uses the image method
for a single ground bounce on the receive leg, neglects negative-frequency
leakage of the real ADC, and assumes a pose-independent complex reflection
coefficient. Model failure does not rule out more complex multipath.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

import numpy as np

C = 299792458.0
TRAIN = ("center", "left", "right", "up", "down")
TEST = ("check_right", "check_left", "check_up", "check_down", "center_repeat")


def fft_kernel(total_path_m, cfg, bins):
    """Linear analytic beat-tone response through repository-style range FFT.

    total_path_m is TX->target->RX; beat frequency = chirp slope * L / c.
    A per-capture unknown common carrier phase is removed by covariance fitting.
    """
    n = np.arange(cfg.samples)
    beat_hz = cfg.slope_hz_s * total_path_m / C
    tone = np.exp(2j * np.pi * (beat_hz / cfg.sample_rate_hz) * n)
    tone = (tone - tone.mean()) * np.hanning(cfg.samples)
    return np.fft.fft(tone)[np.asarray(bins, dtype=int)]


def channel_response(cfg, x, y, dz, *, domain="vendor-raw"):
    r = np.sqrt(x*x + y*y + dz*dz)
    direction = np.array([x/r, dz/r], dtype=float)
    steering = np.exp(2j*np.pi * cfg.array_geometry @ direction)
    if domain == "vendor-raw":
        return np.linalg.solve(cfg.angle_matrix, steering)
    if domain == "ideal":
        return steering
    raise ValueError(f"Unsupported response domain: {domain}")


def paths(cfg, x, y, z, sensor_height, bins, *, domain="vendor-raw"):
    """Direct TX-target-RX and RX-side floor-bounce images, before nuisance gains.

    z = target height relative to radar; target world height = sensor_height+z.
    Mirror-target relative vertical coordinate = -(z + 2*sensor_height).
    """
    rd = np.sqrt(x*x + y*y + z*z)
    mirror_dz = -z-2*sensor_height
    rb = np.sqrt(x*x + y*y + mirror_dz*mirror_dz)
    direct = fft_kernel(2*rd, cfg, bins)[:,None] * channel_response(cfg,x,y,z,domain=domain)[None,:]
    reflect = fft_kernel(rd+rb, cfg, bins)[:,None] * channel_response(cfg,x,y,mirror_dz,domain=domain)[None,:]
    # Difference in total carrier path after one bounce; constant Fresnel
    # coefficient is separate and fitted only from TRAIN captures.
    reflect *= np.exp(2j*np.pi*(rb-rd)*cfg.carrier_hz/C)
    return direct, reflect


def template(cfg, x, y, z, h, bins, theta, gamma, *, domain="vendor-raw"):
    a,b = paths(cfg,x,y,z,h,bins,domain=domain)
    channel_phases = np.exp(1j*np.r_[0.0, theta[0], theta[1]])
    return ((a + gamma*b)*channel_phases[None,:]).reshape(-1)


def normalized_covariance(signal):
    """Summarize per-chirp measured complex spectra while removing common phase.

    signal: (frames, chirps, range bins, 3 receivers). No pose labels used.
    """
    data = np.asarray(signal, complex).reshape(-1, signal.shape[-2]*3)
    norms = np.linalg.norm(data, axis=1)
    data = data[norms > 1e-12] / norms[norms > 1e-12, None]
    if len(data) < 10:
        raise ValueError("Insufficient valid chirps")
    cov = data.T @ data.conj() / len(data)
    return cov, float(np.linalg.eigvalsh(cov)[-1]), len(data)


def alignment(cov, t):
    denom = np.vdot(t,t).real
    return float(np.vdot(t,cov@t).real / max(denom,1e-24))


@dataclass
class Observation:
    name: str
    x: float
    y: float
    z_truth: float
    accepted: bool
    cov: np.ndarray
    maximum_alignment: float
    chirps: int


def model_loss(params, train, cfg, h, bins, *, bounce, domain, regularize=True):
    theta=params[:2]
    gamma=complex(params[2],params[3]) if bounce else 0j
    penalty=0.0
    if bounce:
        penalty=20 * max(0.0,abs(gamma)-1.0)**2
        if regularize:
            penalty+=0.005*abs(gamma)**2
    vals=[]
    for obs in train:
        t=template(cfg,obs.x,obs.y,obs.z_truth,h,bins,theta,gamma,domain=domain)
        vals.append(1-alignment(obs.cov,t))
    return float(np.mean(vals)+penalty)


def nelder_mead(f, start, bounds, maxiter=500):
    """Small bounded simplex optimizer; avoids adding SciPy to radar requirements."""
    x0=np.asarray(start,float)
    bounds=np.asarray(bounds,float)
    n=len(x0)
    step=np.r_[np.full(min(n,2),.28),np.full(max(0,n-2),.16)]
    clip=lambda x: np.minimum(np.maximum(x,bounds[:,0]),bounds[:,1])
    simplex=[clip(x0)]
    for i in range(n):
        v=x0.copy();v[i]+=step[i] if x0[i]+step[i]<=bounds[i,1] else -step[i]
        simplex.append(clip(v))
    simplex=np.asarray(simplex)
    scores=np.array([f(x) for x in simplex])
    for _ in range(maxiter):
        order=np.argsort(scores); simplex=simplex[order];scores=scores[order]
        if np.max(abs(simplex[1:]-simplex[0])) < 1e-5 and np.std(scores) < 1e-8:
            break
        centroid=np.mean(simplex[:-1],axis=0)
        refl=clip(centroid+(centroid-simplex[-1]));fr=f(refl)
        if fr<scores[0]:
            expand=clip(centroid+2*(refl-centroid));fe=f(expand)
            simplex[-1],scores[-1]=(expand,fe) if fe<fr else (refl,fr)
        elif fr<scores[-2]:
            simplex[-1],scores[-1]=refl,fr
        else:
            inside=fr>=scores[-1]
            contract=clip(centroid + .5*((simplex[-1] if inside else refl)-centroid))
            fc=f(contract)
            if fc < (scores[-1] if inside else fr):
                simplex[-1],scores[-1]=contract,fc
            else:
                simplex[1:]=np.array([clip(simplex[0]+.5*(v-simplex[0])) for v in simplex[1:]])
                scores[1:]=[f(v) for v in simplex[1:]]
    j=int(np.argmin(scores))
    return simplex[j],float(scores[j]),bool(np.isfinite(scores[j]))


def fit(train,cfg,h,bins,*,bounce,domain):
    starts=[np.array([a,b,0.,0.]) if bounce else np.array([a,b])
            for a,b in ((0,0),(.7,-.7),(-1,1),(2,-2))]
    if bounce:
        starts += [np.array([0.,0.,a,b]) for a,b in ((.5,0),(-.5,0),(0,.5),(0,-.5),(.5,.5),(-.5,-.5))]
    bounds=[(-np.pi,np.pi),(-np.pi,np.pi)]+([(-1,1),(-1,1)] if bounce else [])
    f=lambda p: model_loss(p,train,cfg,h,bins,bounce=bounce,domain=domain)
    results=[nelder_mead(f,s,bounds) for s in starts]
    params,loss,success=min(results,key=lambda r:r[1])
    gamma=complex(params[2],params[3]) if bounce else 0j
    return params[:2], gamma, loss, success


def invert(obs,cfg,h,bins,theta,gamma,*,domain,limits=(-.35,.45),step=.005):
    """Infer z from signal; true z is deliberately unused inside this function."""
    zs=np.linspace(limits[0],limits[1],int(round((limits[1]-limits[0])/step))+1)
    scores=np.array([alignment(obs.cov,template(cfg,obs.x,obs.y,z,h,bins,theta,gamma,domain=domain)) for z in zs])
    idx=int(np.argmax(scores))
    best=float(zs[idx])
    ambiguity=float(np.max(scores[np.abs(zs-best)>.03])) if np.any(np.abs(zs-best)>.03) else float('nan')
    near=zs[scores >= scores[idx]-0.01]
    return dict(z_est_m=best,score=float(scores[idx]),
                score_gap_nonlocal=float(scores[idx]-ambiguity),
                plausible_z_span_m=[float(near.min()),float(near.max())],
                boundary_hit=bool(idx in (0,len(zs)-1))),zs,scores


def load_observations(root,cfg,bins, *, include_weak=True):
    from radar.background import SpectralBackground
    from radar.processing import range_fft
    from radar.storage import replay
    summary=json.loads((root/'sweep-report.json').read_text())
    rows={r['name']:r for r in summary['poses']}
    result={}
    for name in (*TRAIN,*TEST):
        row=rows[name]
        if not include_weak and not row['accepted']:
            continue
        folder=root/name
        bg=SpectralBackground.from_path(folder/'spectral-background.npz',cfg)
        data=[]
        for frame in replay(folder):
            if frame.profile_id != cfg.profile_id or frame.adc.shape != (cfg.chirps,cfg.samples,3):
                raise ValueError(f'Incompatible frame at {name}')
            data.append(bg.subtract(range_fft(frame.adc,cfg),cfg)[:,bins,:])
        sig=np.asarray(data)
        cov,maximum,chirps=normalized_covariance(sig)
        x,y,z=map(float,row['xyz_m'])
        result[name]=Observation(name,x,y,z,bool(row['accepted']),cov,maximum,chirps)
    return result


def simulate_test():
    """Internal algebra test, not hardware validation."""
    class TestConfig:
        samples=64
        sample_rate_hz=5e6
        slope_hz_s=33691406250000.
        carrier_hz=60e9
        array_geometry=np.array([[0,0],[-.470,0],[0,-.470]])
        angle_matrix=np.eye(3,dtype=complex)
    cfg=TestConfig(); bins=[4,5,6,7,8]; h=.34
    true_theta=np.array([.3,-.2]);true_gamma=.45+.13j
    obs=[]
    for name,x,z in [('center',0,-.1125),('left',-.3,-.1125),('right',.3,-.1125),('up',0,.1075),('down',0,-.2225)]:
        t=template(cfg,x,2.,z,h,bins,true_theta,true_gamma)
        t=t/np.linalg.norm(t)
        cov=np.outer(t,t.conj())
        assert abs(alignment(cov,t)-1)<1e-12
        obs.append(Observation(name,x,2.,z,True,cov,1.,200))
    theta,gamma,loss,_=fit(obs,cfg,h,bins,bounce=True,domain='vendor-raw')
    assert loss < .002, (theta,gamma,loss)
    assert np.isfinite(gamma)
    print(f'PASS synthetic exact two-path templates: training mismatch {loss:.6f}; fitted |reflection|={abs(gamma):.3f}')
    # The following independent synthetic target is NOT used for the fit.
    test_z=.0525
    test_t=template(cfg,0.,2.,test_z,h,bins,true_theta,true_gamma)
    test_t=test_t/np.linalg.norm(test_t)
    obs=Observation('synthetic-heldout',0.,2.,test_z,True,np.outer(test_t,test_t.conj()),1.,300)
    predicted,_,_=invert(obs,cfg,h,bins,theta,gamma,domain='vendor-raw')
    print(f'  Synthetic UNSEEN Z: true={test_z:+.3f} m; estimated={predicted["z_est_m"]:+.3f} m; '
          f'ambiguity gap={predicted["score_gap_nonlocal"]:.5f}')
    print('NOTE: a tiny ambiguity gap means height is NOT uniquely identifiable, even with ideal input.')


def audit(root,config,output,*,h=.34,domain='vendor-raw',bins=(4,5,6,7,8)):
    from dataclasses import replace
    from radar.config import Config
    root,output=Path(root),Path(output)
    original=Config.load(config)
    if original.verified:
        raise ValueError('Expected unverified physical experiment config')
    # Work from original firmware-matched config, NOT the pilot gains referenced
    # to center_repeat. Otherwise we would leak a held-out capture into the fit.
    cfg=replace(original,mount_roll_deg=90.,gains_real=[1.,1.,1.],gains_imag=[0.,0.,0.]).validate()
    bins=tuple(int(x) for x in bins)
    if min(bins)<2 or max(bins)>=cfg.samples//2-1:
        raise ValueError('Invalid FFT bins')
    observations=load_observations(root,cfg,list(bins))
    train=[observations[n] for n in TRAIN]
    tests=[observations[n] for n in TEST]
    weak_training=[o.name for o in train if not o.accepted]
    print(f'Train captures: {len(train)}, below original quality gate: {len(weak_training)} ({", ".join(weak_training) or "none"})')
    if len(weak_training)>2:
        print('WARNING: physical fit is likely biased by weak, mixed target returns. No calibration will be exported.')
    variants=[]
    for name,bounce in [('direct',False),('direct+floor',True)]:
        print(f'Fitting {name} model using TRAIN poses only...')
        theta,gamma,loss,success=fit(train,cfg,h,bins,bounce=bounce,domain=domain)
        results=[]
        curves={}
        for obs in train+tests:
            inv,zs,scores=invert(obs,cfg,h,bins,theta,gamma,domain=domain)
            inv.update(name=obs.name,split='train' if obs.name in TRAIN else 'heldout',
                       true_z_m=obs.z_truth,error_m=inv['z_est_m']-obs.z_truth,
                       accepted_original_gate=obs.accepted,
                       peak_rank1_alignment=obs.maximum_alignment,
                       maximum_possible_score=obs.maximum_alignment,
                       sample_chirps=obs.chirps,
                       true_z_fit_score=alignment(obs.cov,template(cfg,obs.x,obs.y,obs.z_truth,h,bins,theta,gamma,domain=domain)))
            results.append(inv)
            curves[obs.name]=(zs,scores)
        heldout=[r for r in results if r['split']=='heldout']
        quality=[r for r in heldout if r['accepted_original_gate']]
        print(f'  trained RX phase offsets {np.degrees(theta).round(1).tolist()} deg; gamma={gamma.real:+.3f}{gamma.imag:+.3f}j; |gamma|={abs(gamma):.3f}')
        print(f'  training mean spectral mismatch {loss:.3f}')
        for r in heldout:
            print(f"  {r['name']:14} {'PASS' if r['accepted_original_gate'] else 'WEAK'} "
                  f"z={r['z_est_m']:+.3f} m (truth {r['true_z_m']:+.3f}, error {r['error_m']:+.3f}), "
                  f"fit={r['score']:.3f}, max={r['maximum_possible_score']:.3f}, gap={r['score_gap_nonlocal']:.3f}"
                  f" {'AMBIGUOUS' if r['score_gap_nonlocal'] < 0.02 or r['boundary_hit'] else 'local peak'}")
        mae=float(np.mean([abs(r['error_m']) for r in quality])) if quality else None
        variants.append(dict(name=name,theta_rad=theta.tolist(),gamma_real=float(gamma.real),
                             gamma_imag=float(gamma.imag),training_loss=loss,optimizer_converged=success,
                             heldout_mae_quality_only_m=mae,results=results,curves=curves))
    # Explicit no silent adoption: compare generalization, and refuse deployment
    # if physical model still misses actual heldout positions.
    direct,two=variants
    improved=(direct['heldout_mae_quality_only_m'] is not None and
              two['heldout_mae_quality_only_m'] is not None and
              two['heldout_mae_quality_only_m']<direct['heldout_mae_quality_only_m'])
    print('MODEL COMPARISON (quality-PASS heldouts only):')
    print(f"  direct MAE:       {direct['heldout_mae_quality_only_m']}")
    print(f"  direct+floor MAE: {two['heldout_mae_quality_only_m']}")
    print(f'  floor improvement: {improved}')
    print('NOT A CALIBRATION: target X/Y were known fixture coordinates; boxes and scene remain confounded.')
    output.mkdir(parents=True,exist_ok=False)
    payload={'kind':'train-only-coherent-direct-vs-floor-bounce-falsification',
             'model':'single RX-side floor bounce, common reflection coefficient, common RX phase offsets',
             'verified':False,'h_sensor_m':h,'bins':bins,'antenna_mode':domain,
             'training_names':TRAIN,'heldout_names':TEST,
             'weak_training_names':weak_training,
             'pilot_config_excluded':'center_repeat-calibrated exploratory config NOT used',
             'optimistic_xy':'true fixture X/Y supplied for heldout Z inversion; not robot-ready',
             'caveats':['One additional bounce on RX path only; no TX-bounce or higher-order paths',
                        'Approximate analytic beat-tone spectra; ADC negative-frequency leakage omitted',
                        'Floor height assumed constant and known; target centroid treated as point',
                        'Only five training poses, four below original contrast gate',
                        'Global reflection parameter may not represent support-dependent multipath',
                        'Board roll inferred during earlier exploration of same dataset',
                        'No model should be chosen for deployment based on these development checks'],
             'variants':[{k:v for k,v in variant.items() if k!='curves'} for variant in variants]}
    (output/'summary.json').write_text(json.dumps(payload,indent=2)+'\n')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,2,figsize=(14,5),layout='constrained')
        heldout=TEST
        x=np.arange(len(heldout)); width=.35
        for j,variant in enumerate(variants):
            lookup={r['name']:r for r in variant['results']}
            offsets=np.array([lookup[n]['error_m']*100 for n in heldout])
            axes[0].bar(x+(j-.5)*width,offsets,width,label=variant['name'])
        axes[0].set_xticks(x,heldout,rotation=25,ha='right')
        axes[0].axhline(0,color='black',linewidth=.7)
        axes[0].set(ylabel='Estimated Z error (cm)',title='Held-out height errors: known X/Y optimistic test')
        axes[0].legend(); axes[0].grid(axis='y',alpha=.25)
        for variant in variants:
            for name in ('check_up','check_down'):
                z,s=variant['curves'][name]
                axes[1].plot(z*100,s,label=variant['name']+' / '+name)
        for name in ('check_up','check_down'):
            axes[1].axvline(observations[name].z_truth*100,color='black',alpha=.3,linestyle=':')
        axes[1].set(xlabel='Candidate height relative radar (cm)',ylabel='Normalized spectral alignment',
                    title='Height ambiguity: peaks away from true Z invalidate model')
        axes[1].grid(alpha=.25);axes[1].legend(fontsize=8)
        fig.suptitle('Development dataset only — no independent cross-scene validation')
        fig.savefig(output/'comparison.png',dpi=160)
        plt.close(fig)
    except ImportError:
        print('matplotlib unavailable: JSON report written without plot')
    print('Saved',output/'summary.json', 'and comparison.png (if matplotlib installed)')
    return payload


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('sweep',nargs='?')
    p.add_argument('--config',default='configs/qualification-hpf350.json')
    p.add_argument('--output',default='artifacts/two-path-audit-01')
    p.add_argument('--sensor-height',type=float,default=.34)
    p.add_argument('--domain',choices=('vendor-raw','ideal'),default='vendor-raw')
    p.add_argument('--self-test',action='store_true')
    a=p.parse_args()
    if a.self_test:
        simulate_test();return
    if not a.sweep:
        p.error('Specify recordings/box-angle-01 or --self-test')
    # Allow direct copy into repo root or tools directory without pip install.
    sys.path.insert(0,str(Path.cwd()))
    audit(a.sweep,a.config,a.output,h=a.sensor_height,domain=a.domain)

if __name__=='__main__':
    main()
