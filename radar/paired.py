"""Paired session analysis. Association evidence is not material/angle calibration."""
import hashlib
import json
import re
import zlib
from pathlib import Path
import numpy as np
from .config import Config
from .processing import range_fft
from .protocol import Parser, HEADER, MAGIC
from .storage import replay
from .spatial import SpatialMapper


def audit_wire(path):
    wire = Path(path)/'serial-wire.bin'
    if not wire.exists():
        return None
    parser=Parser()
    frames=0
    with wire.open('rb') as source:
        while chunk:=source.read(65536):
            frames+=len(parser.feed(chunk))
    data=wire.read_bytes()
    headers=[]
    offset=0
    while True:
        offset=data.find(MAGIC,offset)
        if offset<0:
            break
        if offset+HEADER.size<=len(data):
            fields=HEADER.unpack_from(data,offset)
            if (fields[1] in (1,2,3,4) and fields[2]==HEADER.size and
                    zlib.crc32(data[offset:offset+HEADER.size-4])==fields[-1]):
                expected=HEADER.size+fields[3]+4
                complete=offset+expected<=len(data)
                crc_ok=complete and zlib.crc32(data[offset:offset+expected-4])==int.from_bytes(data[offset+expected-4:offset+expected],'little')
                headers.append((offset,fields[4],expected,crc_ok))
        offset+=1
    failures=[dict(wire_offset=h[0],sequence=h[1],expected_packet_bytes=h[2],
        bytes_to_next_valid_header=n[0]-h[0],boundary_shortfall_bytes=h[2]-(n[0]-h[0]))
        for h,n in zip(headers,headers[1:]) if not h[3]][:20]
    return dict(bytes=wire.stat().st_size,accepted_frames=frames,crc_failures=parser.bad_crc,
        bad_headers=parser.bad_headers,missing_sequences=parser.gaps,restarts=parser.restarts,
        discarded_bytes=parser.discarded_bytes,tail_bytes=len(parser.buffer),rejected_packet_boundaries=failures)


def load_session(path, config):
    path = Path(path)
    saved = Config.load(path/'config.json')
    if (saved.profile_id, saved.samples, saved.chirps, saved.discard_chirps) != (
            config.profile_id, config.samples, config.chirps, config.discard_chirps):
        raise ValueError('Incompatible acquisition dimensions/profile/discard policy')
    parser = Parser()
    frames = list(replay(path, parser))
    if len(frames) < 10:
        raise ValueError('At least ten complete frames required')
    spectra = np.array([range_fft(frame.adc, config) for frame in frames])
    # Independent rectangular-window view checks whether a high-bin feature is
    # created solely by the Hann window. Preserve this as evidence, not a veto.
    raw = np.array([f.adc[config.discard_chirps:] for f in frames],dtype=float)
    raw -= raw.mean(axis=2,keepdims=True)
    rectangular = np.fft.rfft(raw,axis=2)*(2/config.samples)*config.gains
    rectangular_power = np.mean(abs(rectangular)**2,axis=(0,1,3))
    covariance = np.einsum('fcra,fcrb->frab', spectra, spectra.conj()) / spectra.shape[1]
    power = covariance.diagonal(axis1=2,axis2=3).real.mean(axis=2)
    return dict(path=str(path), covariance=covariance, power=power,
        rectangular_power=rectangular_power,
        integrity=dict(frames=len(frames), saved_crc_failures=parser.bad_crc,
            saved_missing_sequences=parser.gaps, saved_restarts=parser.restarts,
            saved_tail_bytes=len(parser.buffer),
            device_errors_first_last=[frames[0].errors,frames[-1].errors],
            device_drops_first_last=[frames[0].dropped,frames[-1].dropped],
            raw_hash=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
            transport_wire_log_present=(path/'serial-wire.bin').exists(),wire_audit=audit_wire(path)))


def block_mean(values, rng, block=5):
    # Circular moving blocks preserve short-term correlation within each session.
    starts = rng.integers(0,len(values),size=int(np.ceil(len(values)/block)))
    indices = ((starts[:,None]+np.arange(block))%len(values)).ravel()[:len(values)]
    return values[indices].mean(axis=0)


def compare(control, target, config, target_bin=4, bootstrap=200):
    if not 2 <= target_bin < len(config.ranges)-1:
        raise ValueError('Target bin outside usable spectrum')
    p0,p1 = control['power'], target['power']
    gain = 10*np.log10(np.maximum(p1.mean(axis=0),1e-12)/np.maximum(p0.mean(axis=0),1e-12))
    rng = np.random.default_rng(82)
    ci=[]
    mapper = SpatialMapper(config)
    weights = mapper.weights
    def beam(cov):
        return np.einsum('ak,ab,bk->k',weights.conj(),cov,weights).real
    c0=control['covariance'][:,target_bin]
    c1=target['covariance'][:,target_bin]
    difference=c1.mean(axis=0)-c0.mean(axis=0)
    delta_map=beam(difference)
    def angles(index):
        e,a=np.unravel_index(index,(len(mapper.elevations),len(mapper.azimuths)))
        return [float(mapper.azimuths[a]),float(mapper.elevations[e])]
    samples=[]
    for _ in range(bootstrap):
        mean0=block_mean(c0,rng);mean1=block_mean(c1,rng)
        ci.append(10*np.log10(max(np.trace(mean1).real,1e-12)/max(np.trace(mean0).real,1e-12)))
        differential=beam(mean1-mean0)
        if differential.max()>0:
            samples.append(angles(int(differential.argmax())))
    raw_cross=np.mean(c1,axis=0)[1:,0]
    per_frame_cross=c1[:,1:,0]
    relative=np.angle(per_frame_cross)
    concentration=np.abs(np.exp(1j*relative).mean(axis=0))
    phase_std=np.degrees(np.sqrt(-2*np.log(np.clip(concentration,1e-12,1))))
    per_frame_angles=np.array([angles(int(beam(c-c0.mean(axis=0)).argmax())) for c in c1])
    mask=(delta_map>0)&(delta_map>=delta_map.max()/2) if delta_map.max()>0 else np.zeros_like(delta_map,dtype=bool)
    cells=np.array([angles(i) for i in np.flatnonzero(mask)])
    # A within-control split provides a limited negative check, not a population FPR.
    reference=p0[:len(p0)//2,target_bin]
    holdout=p0[len(p0)//2:,target_bin]
    threshold=float(np.quantile(reference,0.99))
    result=dict(control=control['path'],target=target['path'],target_bin=target_bin,
        range_m_under_selected_model=float(config.ranges[target_bin]),
        target_control_gain_db=float(gain[target_bin]),gain_block_bootstrap_95_db=np.percentile(ci,[2.5,97.5]).tolist(),
        gain_by_bin_db=gain.tolist(),
        per_rx_gain_db=(10*np.log10(np.maximum(c1.diagonal(axis1=1,axis2=2).real.mean(axis=0),1e-12)/
            np.maximum(c0.diagonal(axis1=1,axis2=2).real.mean(axis=0),1e-12))).tolist(),
        target_fraction_above_control_reference_q99=float(np.mean(p1[:,target_bin]>threshold)),
        control_holdout_fraction_above_reference_q99=float(np.mean(holdout>threshold)),
        raw_relative_phase_mean_deg=np.degrees(np.angle(raw_cross)).tolist(),
        raw_relative_phase_circular_std_deg=phase_std.tolist(),
        differential_peak_az_el_deg=angles(int(delta_map.argmax())) if delta_map.max()>0 else None,
        bootstrap_positive_peak_fraction=len(samples)/bootstrap,
        differential_peak_bootstrap_95_az_el_deg=np.percentile(samples,[2.5,97.5],axis=0).tolist() if samples else None,
        angular_grid_step_deg=5,bootstrap_block_frames=5,bootstrap_replicates=bootstrap,
        uncertainty_warning='A collapsed bootstrap interval is grid quantization, not zero angular uncertainty.',
        per_frame_differential_peak_p05_p50_p95_deg=np.percentile(per_frame_angles,[5,50,95],axis=0).tolist(),
        differential_response_minus3db_az_el_bounds=[cells.min(axis=0).tolist(),cells.max(axis=0).tolist()] if len(cells) else None,
        differential_covariance_eigenvalues=np.linalg.eigvalsh(difference).tolist(),
        differential_beam_power=delta_map.reshape(len(mapper.elevations),len(mapper.azimuths)).tolist(),
        bin23_gain_db=float(gain[23]) if len(gain)>23 else None,
        caveats=['Target-associated change includes operator/body/scene changes; not uniquely iPad.',
          'No angular ground truth: bootstrap repeatability excludes calibration/model bias.',
          'Signed covariance difference retained; no PSD clipping or coherent baseline subtraction.',
          'Broad response width is distinct from uncertainty of the peak location.',
          'Reference-quantile exceedance is not calibrated detection probability or population false-alarm rate.'])
    return result


def investigate_bin(session, index=23):
    power=session['power']
    central=power[:,index]
    neighbors=np.median(power[:,max(2,index-3):index+4],axis=1)
    rectangular=session['rectangular_power']
    return dict(bin=index,mean_power_db=float(10*np.log10(max(central.mean(),1e-12))),
        rectangular_window_power_db=float(10*np.log10(max(rectangular[index],1e-12))),
        rectangular_window_local_peak=bool(rectangular[index]>max(rectangular[index-1],rectangular[index+1])),
        median_local_contrast_db=float(np.median(10*np.log10(np.maximum(central,1e-12)/np.maximum(neighbors,1e-12)))),
        local_peak_fraction=float(np.mean((central>power[:,index-1])&(central>power[:,index+1]))),
        temporal_cv=float(central.std()/max(central.mean(),1e-12)),
        per_rx_power_db=(10*np.log10(np.maximum(session['covariance'][:,index].diagonal(axis1=1,axis2=2).real.mean(axis=0),1e-12))).tolist())


def write_report(root, config_path, output):
    root,output=Path(root),Path(output)
    config=Config.load(config_path)
    sessions={p.name:load_session(p,config) for p in root.iterdir() if (p/'frames.grd').exists()}
    pairs=[('bottle_only_03','target_with_bottle_03'),('empty_usb_left_02','target_bottle_usb_left_02')]
    if 'detkin-empty' in sessions:
        pairs.extend(('detkin-empty',name) for name in sorted(sessions) if name.startswith('detkin-ipad'))
    result=dict(config=json.loads(Path(config_path).read_text()),
        pairing_basis='User history and directory names; metadata contain placeholder labels. Pair02 also changes bottle. Pair03 retains bottle. detkin-ipad* compared with shared detkin-empty; numeric suffix meaning/sign requires confirmation.',
        sessions={name:dict(integrity=s['integrity'],bin23=investigate_bin(s)) for name,s in sessions.items()},
        pairs=[compare(sessions[c],sessions[t],config) for c,t in pairs if c in sessions and t in sessions])
    output.mkdir(parents=True,exist_ok=True)
    (output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    for pair in result['pairs']:
        c=sessions[Path(pair['control']).name];t=sessions[Path(pair['target']).name]
        figure=Figure(figsize=(11,5),layout='constrained');FigureCanvasAgg(figure)
        left,right=figure.subplots(1,2)
        for data,label in [(c,'Control'),(t,'Target condition')]:
            left.plot(np.arange(len(config.ranges)),10*np.log10(np.maximum(data['power'].mean(axis=0),1e-12)),label=label)
        left.axvline(4,color='gray',ls=':');left.axvline(23,color='gray',ls=':')
        left.set(xlabel='FFT bin',ylabel='Mean power (dB ADC squared)',title='Absolute spectra; bins 4 and 23 marked');left.legend()
        right.plot(pair['gain_by_bin_db']);right.axhline(0,color='gray')
        right.set(xlabel='FFT bin',ylabel='Target/control gain (dB)',title='Paired change; not coherent subtraction')
        figure.savefig(output/(Path(pair['target']).name+'.png'),dpi=120)
        angular=Figure(figsize=(10,4),layout='constrained');FigureCanvasAgg(angular)
        ax,trace=angular.subplots(1,2)
        values=np.array(pair['differential_beam_power'])
        limit=max(float(abs(values).max()),1e-12)
        image=ax.imshow(values,origin='lower',extent=[-60,60,-60,60],cmap='coolwarm',vmin=-limit,vmax=limit,aspect='auto')
        ax.set(xlabel='Azimuth (deg; uncalibrated)',ylabel='Elevation (deg; uncalibrated)',title='Signed target-control angular response')
        angular.colorbar(image,ax=ax,label='Differential matched-filter power (ADC squared)')
        for data,label in [(c,'Control'),(t,'Target condition')]:
            trace.plot(10*np.log10(np.maximum(data['power'][:,4],1e-12)),label=label)
        trace.set(xlabel='Within-session frame index (separate sessions)',ylabel='Bin 4 power (dB ADC squared)',title='Repeatability, not angular calibration');trace.legend()
        angular.savefig(output/(Path(pair['target']).name+'-angular.png'),dpi=120)
    detkin=[p for p in result['pairs'] if Path(p['target']).name.startswith('detkin-ipad')]
    if detkin:
        def label(pair):
            return int(re.search(r'detkin-ipad(-?\d+)$',Path(pair['target']).name).group(1))
        detkin.sort(key=label)
        summary=['# Detkin angle-label series','',
            'Labels below are folder suffixes, not independently verified ground-truth angles. All sessions use the single shared detkin-empty control. No calibration was fitted.','',
            '| Folder label | Frames | Bin 4 gain (dB) | 95% block interval (dB) | Differential az/el peak (deg) | CRC failures / gaps |',
            '|---:|---:|---:|---|---|---|']
        for p in detkin:
            integrity=result['sessions'][Path(p['target']).name]['integrity']
            wire=integrity['wire_audit']
            ci=p['gain_block_bootstrap_95_db']
            summary.append(f"| {label(p):+d} | {integrity['frames']} | {p['target_control_gain_db']:.2f} | {ci[0]:.2f} to {ci[1]:.2f} | {p['differential_peak_az_el_deg']} | {wire['crc_failures'] if wire else 'not logged'} / {integrity['saved_missing_sequences']} |")
        summary.extend(['','The current model does not produce a consistent progression across folder labels. Raw-phase signs, coordinate mapping, coefficient applicability and scene contributions remain unresolved. A shared control cannot separate iPad, operator motion, changed occlusion or drift.','',
            'In detkin-ipad30, sequence 2721 has a valid header but fails packet CRC. The next valid header is 6553 bytes later, versus 6580 bytes expected: a 27-byte boundary shortfall. This supports byte loss in the stream, but does not locate whether it occurred at UART transmission, the bridge, driver or host. Partial final packets at timed shutdown are reported separately, not counted as CRC errors.','',
            'Bin 23 changes little against control except label -30, where it falls about 11.38 dB. It is therefore not an invariant fixed-amplitude feature. That does not distinguish multipath, occlusion, changed scene or interference.',''])
        (output/'detkin-summary.md').write_text('\n'.join(summary),encoding='utf-8')
        fig=Figure(figsize=(11,5),layout='constrained');FigureCanvasAgg(fig)
        gains,directions=fig.subplots(1,2)
        labels=np.array([label(p) for p in detkin])
        means=np.array([p['target_control_gain_db'] for p in detkin])
        intervals=np.array([p['gain_block_bootstrap_95_db'] for p in detkin])
        gains.errorbar(labels,means,yerr=[means-intervals[:,0],intervals[:,1]-means],fmt='o',capsize=4)
        gains.set(xlabel='Folder angle label (definition unconfirmed)',ylabel='Bin 4 target/control gain (dB)',title='Target-associated range change')
        for index,name in [(0,'Azimuth'),(1,'Elevation')]:
            percentiles=np.array([p['per_frame_differential_peak_p05_p50_p95_deg'] for p in detkin])[:,:,index]
            directions.plot(labels,percentiles[:,1],'.-',label=name)
            directions.fill_between(labels,percentiles[:,0],percentiles[:,2],alpha=0.15)
        directions.set(xlabel='Folder angle label (definition unconfirmed)',ylabel='Model angle (deg; uncalibrated)',title='Median and 5–95% frame variability');directions.legend()
        fig.savefig(output/'detkin-series.png',dpi=120)
    return result
