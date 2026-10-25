"""Audit ALL detkin scene returns; body/arm returns are valid scene content."""
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.config import Config
from radar.paired import load_session
from radar.spatial import SpatialMapper


def main():
    config=Config.load('configs/range-vendor-matrix-experimental.json')
    mapper=SpatialMapper(config)
    rows=[]
    for directory in sorted(Path('recordings').glob('detkin*')):
        session=load_session(directory,config)
        covariance=session['covariance'].mean(axis=0)[2:-1]
        beam=np.einsum('ak,rab,bk->rk',mapper.weights.conj(),covariance,mapper.weights).real
        trace=covariance.diagonal(axis1=1,axis2=2).real.sum(axis=1)
        eigen=np.linalg.eigvalsh(covariance)
        peak=beam.max(axis=1)
        rows.append(dict(session=directory.name,
            ranges_under_selected_model_m=mapper.ranges.tolist(),
            visible_bins_at_8db=(np.flatnonzero(peak>=peak.max()*10**(-8/10))+2).tolist(),
            visible_bins_at_30db=(np.flatnonzero(peak>=peak.max()/1000)+2).tolist(),
            covariance_principal_energy_fraction=(eigen[:,-1]/np.maximum(trace,1e-12)).tolist(),
            best_model_direction_energy_fraction=(peak/np.maximum(trace,1e-12)).tolist()))
    out=Path('artifacts/full-scene-audit.json')
    out.write_text(json.dumps(dict(
        interpretation='All captures retained as whole scenes. Fractions describe covariance/model fit, not detection confidence, number of objects or geometric accuracy.',
        display='30 dB is a brightness cutoff only. It also displays noise and sidelobes; it does not add angular resolving power.',
        current_exclusions='DC, bin1 and Nyquist excluded; angular grid +/-60 degrees; GUI default maximum viewing range remains 4 m. No coverage behind sensor.',
        sessions=rows),indent=2),encoding='utf-8')
    print(out)


if __name__=='__main__':
    main()
