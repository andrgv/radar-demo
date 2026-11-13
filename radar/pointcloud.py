"""Frame-local range/Doppler/angle scattering-center extraction."""
from dataclasses import dataclass
import numpy as np
from .spatial import SpatialMapper
from .processing import noise_threshold, interpolated_range


@dataclass
class PointCloud:
    xyz: np.ndarray
    range_bins: np.ndarray
    doppler_cycles_per_chirp: np.ndarray
    snr_db: np.ndarray
    model_fit: np.ndarray
    angular_width_deg: np.ndarray
    power_db: np.ndarray


class CloudProcessor:
    def __init__(self, config, snr_db=8, minimum_fit=0.65):
        self.config=config
        self.mapper=SpatialMapper(config)
        self.snr_db=snr_db
        self.minimum_fit=minimum_fit

    def process(self, spectrum):
        n=len(spectrum)
        window=np.hanning(n)
        rd=np.fft.fftshift(np.fft.fft(spectrum*window[:,None,None],axis=0),axes=0)/window.sum()
        power=np.mean(abs(rd)**2,axis=2)
        thresholds=np.array([noise_threshold(row,10**(self.snr_db/10)) for row in power])
        # Nonmaximum suppression is performed before angle fitting; stationary
        # energy is retained and different Doppler peaks at one range survive.
        candidates=[]
        for d in range(n):
            for r in range(2,len(self.config.ranges)-1):
                local=power[np.array([(d-1)%n,d,(d+1)%n])[:,None],np.arange(r-1,r+2)]
                if power[d,r]<=thresholds[d,r] or power[d,r]<local.max():
                    continue
                raw=rd[d,r]
                total=float(np.vdot(raw,raw).real)
                response=abs(self.mapper.weights.conj().T@raw)**2
                peak=int(response.argmax())
                fit=float(response[peak]/max(total,1e-12))
                if fit<self.minimum_fit:
                    continue
                e,a=np.unravel_index(peak,(len(self.mapper.elevations),len(self.mapper.azimuths)))
                az,el=np.radians([self.mapper.azimuths[a],self.mapper.elevations[e]])
                distance=interpolated_range(power[d],r,self.config)
                mask=(response>=response[peak]/2).reshape(len(self.mapper.elevations),len(self.mapper.azimuths))
                ai=np.flatnonzero(mask.any(axis=0));ei=np.flatnonzero(mask.any(axis=1))
                width=[self.mapper.azimuths[ai[-1]]-self.mapper.azimuths[ai[0]],
                       self.mapper.elevations[ei[-1]]-self.mapper.elevations[ei[0]]]
                candidates.append(([distance*np.sin(az)*np.cos(el),distance*np.cos(az)*np.cos(el),distance*np.sin(el)],
                    r,float(np.fft.fftshift(np.fft.fftfreq(n))[d]),
                    float(10*np.log10(power[d,r]/max(thresholds[d,r]/10**(self.snr_db/10),1e-12))),fit,width,
                    float(10*np.log10(max(response[peak],1e-12)))))
        return PointCloud(np.array([x[0] for x in candidates]).reshape(-1,3),
            np.array([x[1] for x in candidates],dtype=int),np.array([x[2] for x in candidates]),
            np.array([x[3] for x in candidates]),np.array([x[4] for x in candidates]),
            np.array([x[5] for x in candidates]).reshape(-1,2),np.array([x[6] for x in candidates]))


def main(argv=None):
    import argparse,json,time
    from pathlib import Path
    from dataclasses import asdict
    from .obstacle3d import load_config
    from .material import _check_frame
    from .protocol import Parser
    from .storage import replay
    from .processing import range_fft
    p=argparse.ArgumentParser()
    p.add_argument('recording');p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--method', choices=('deblend','fft'), default='deblend')
    args=p.parse_args(argv)
    config=load_config(args.config)
    if args.method == 'deblend':
        from .reconstruction import SceneReconstructor
        processor = SceneReconstructor(config)
    else:
        processor = CloudProcessor(config)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    counts=[];timings=[];all_xyz=[]
    parser=Parser();previous=None
    with (out/'points.jsonl').open('w',encoding='utf-8') as destination:
        for frame in replay(args.recording,parser):
            _check_frame(frame, config, previous);previous=frame
            start=time.perf_counter()
            cloud=processor.process(frame.adc if args.method=='deblend' else range_fft(frame.adc,config))
            timings.append((time.perf_counter()-start)*1000)
            destination.write(json.dumps(dict(sequence=frame.sequence,timestamp_us=frame.timestamp_us,
                **{k:v.tolist() for k,v in asdict(cloud).items()},
                **(dict(reconstruction=processor.last_report) if args.method=='deblend' else {})),allow_nan=False)+'\n')
            counts.append(len(cloud.xyz));all_xyz.extend(cloud.xyz)
    if not counts or any(getattr(parser,k) for k in ('bad_crc','bad_headers','gaps','restarts','discarded_bytes')) or parser.buffer:
        raise ValueError('Empty, corrupt or discontinuous raw recording; partial diagnostic output preserved')
    report=dict(frames=len(counts),points=int(sum(counts)),points_per_frame_p05_median_p95=np.percentile(counts,[5,50,95]).tolist(),
        processing_ms_p50_p95=np.percentile(timings,[50,95]).tolist(),
        config=asdict(config),method=args.method,caveats='Uncalibrated sensor-relative scattering centers, not surfaces. Doppler units are cycles/chirp because timing is unverified. Model fit is not probability. No temporal accumulation/pose estimation.')
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='config'},indent=2))


if __name__=='__main__':main()
