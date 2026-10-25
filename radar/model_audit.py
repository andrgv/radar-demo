"""Falsification tests for the saved raw measurement model, with no live fitting."""
from dataclasses import replace,asdict
from itertools import permutations
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from .config import Config,C
from .protocol import Parser
from .storage import replay
from .recording_audit import read_register_profile,nominal_waveform,factory_matrices,packing_score


def source_facts(profile, hal, firmware):
    registers,clock=read_register_profile(profile)
    definitions=Path(hal).read_text(encoding='utf-8')
    def field(register,name):
        stem='BGT60CUTR13B_'+name
        position=int(re.search(r'#define\s+'+stem+r'_pos\s+(\d+)',definitions).group(1))
        mask=int(re.search(r'#define\s+'+stem+r'_msk\s+(0x[0-9a-fA-F]+)',definitions).group(1),16)
        return (registers[register]&mask)>>position
    waveform=nominal_waveform(registers,clock)
    receivers=[]
    for rx in [1,2,3]:
        address=0x1010+4*(rx-1);prefix=f'CS_IDX0_RX{rx}_'
        hpf=[100000,350000,650000,1000000][field(address,prefix+'ABB_HPF1_SEL')]
        aaf=[1000000,2000000,5000000,6000000][field(address,prefix+'ABB_AAF_SEL')]
        receivers.append(dict(rx=rx,enabled=bool(field(address,prefix+'RX_EN')),
            gain_db=24+3*field(address,prefix+'ABB_GAIN_SEL'),hpf1_hz=hpf,
            hpf2_bypass=bool(field(address,prefix+'ABB_HPF2_BYP_EN')),aaf_hz=aaf,
            hpf1_equivalent_range_m_nominal=C*hpf/(2*waveform['slope_hz_s_nominal'])))
    code=Path(firmware).read_text()
    averaging_override=re.search(r'set_reg\(&sensor\.dev,\s*BGT60CUTR13B_REG_AVG_CTRL_SEQ0,\s*(\d+)\)',code)
    runtime_factor=2**(int(averaging_override.group(1))&15) if averaging_override else None
    return dict(waveform=waveform,rx_register_configuration=receivers,
        profile_averaging_factor=2**(registers[0x1b20]&15),runtime_averaging_factor_from_source=runtime_factor,
        runtime_truncates_after_adc_containers=17*64*3,
        adc_idx0_register=hex(registers[0x1500]),sh_idx0_start=hex(registers[0x1200]),
        sh_idx0_ramp=hex(registers[0x1204]),
        sequence_words=[dict(address=hex(a),word=hex(v)) for a,v in registers.items() if 0x3000<=a<0x4000],
        sequence_instruction_decoder_available_in_this_audit=False,chirp_interval_measured_s=None,carrier_verified_hz=None,
        firmware_sha256=hashlib.sha256(Path(firmware).read_bytes()).hexdigest(),
        loaded_profile_sha256=hashlib.sha256(Path(profile).read_bytes()).hexdigest())


def covariance(spectrum):
    return np.einsum('fcra,fcrb->frab',spectrum,spectrum.conj())/spectrum.shape[1]


def raw_session(path,config):
    parser=Parser();frames=list(replay(path,parser))
    if not frames:
        raise ValueError(f'No complete frames in {path}')
    adc=np.array([frame.adc for frame in frames])
    if adc.shape[1:]!=(config.chirps,config.samples,3):
        raise ValueError('Frame dimension mismatch')
    profiles=sorted({int(frame.profile_id) for frame in frames})
    if profiles!=[config.profile_id]:
        raise ValueError(f'Profile mismatch in {path}: {profiles}')
    raw=adc.astype(float);raw-=raw.mean(axis=2,keepdims=True)
    fft=np.fft.rfft(raw*np.hanning(config.samples)[None,None,:,None],axis=2)*(2/np.hanning(config.samples).sum())
    cov=covariance(fft[:,config.discard_chirps:])
    means=cov.mean(axis=0)
    power=means.diagonal(axis1=1,axis2=2).real.mean(axis=1)
    peak=int(np.argmax(power[2:-1])+2)
    per_chirp_power=np.mean(abs(fft[:, :,peak])**2,axis=(0,2))
    channels=fft[:,:,peak]
    cross=channels[:,:,1:]*channels[:,:,:1].conj()
    avg=np.mean(cross,axis=0)
    phase_by_slot=np.degrees(np.angle(avg))
    wrapped_difference=np.angle(avg*np.conj(avg[1:2]))
    phase_spread=float(np.degrees(np.max(abs(wrapped_difference))))
    products=channels[:,1:]*channels[:,:-1].conj()
    channel_power=np.mean(abs(channels)**2,axis=(0,2))
    adjacent_coherence=abs(products.mean(axis=(0,2)))/np.sqrt(channel_power[1:]*channel_power[:-1])
    flat=adc.reshape(len(adc),-1)
    alternative={
        'unsigned16_sample_interleaved':adc,
        'swap_adjacent_16bit_halves':flat.reshape(len(adc),-1,2)[:,:,::-1].reshape(adc.shape),
        'byte_swap_each_16bit':adc.byteswap(),
        'signed16':adc.view('<i2'),
        'rx_major_within_chirp':flat.reshape(len(adc),config.chirps,3,config.samples).transpose(0,1,3,2),
        'rx_major_within_frame':flat.reshape(len(adc),3,config.chirps,config.samples).transpose(0,2,3,1)}
    scores={key:packing_score(value) for key,value in alternative.items()}
    # Relative chirp-slot phase remains in raw RX coordinates. A discontinuity
    # can reveal structure even when physical chirp time cannot be recovered.
    timestamp=np.array([f.timestamp_us for f in frames],dtype=np.uint32)
    return cov,dict(frames=len(frames),dominant_bin=peak,packing_hypotheses=scores,
        profile_ids=profiles,flags=sorted({int(frame.flags) for frame in frames}),
        chirp_slot_relative_phase_deg=phase_by_slot.tolist(),max_slot_phase_difference_from_slot1_deg=phase_spread,
        chirp_slot_ac_power_ratio=(per_chirp_power/max(per_chirp_power.mean(),1e-12)).tolist(),
        adjacent_chirp_coherence=adjacent_coherence.tolist(),
        frame_timestamp_delta_us_p05_p50_p95=np.percentile(np.diff(timestamp),[5,50,95]).tolist(),
        saved_sequence_gaps=parser.gaps,saved_crc_failures=parser.bad_crc,
        raw_sha256=hashlib.sha256((Path(path)/'frames.grd').read_bytes()).hexdigest())


def steering_grid(config):
    # Uniform direction-cosine disk avoids counting coordinate-axis rotations
    # as different array explanations or privileging az/el corners.
    axis=np.linspace(-0.98,0.98,41)
    u,v=np.meshgrid(axis,axis)
    valid=u*u+v*v<=0.98**2
    directions=np.array([u[valid],v[valid]])
    return directions,np.exp(2j*np.pi*config.array_geometry@directions)


def dominant_mode_scores(covs,correction,order,conjugate,virtual):
    reordered=covs[:,order][:,:,order]
    if conjugate:
        reordered=reordered.conj()
    values,vectors=np.linalg.eigh(reordered)
    dominant=vectors[:,:,-1]
    signatures=np.linalg.solve(correction,virtual)
    signatures/=np.linalg.norm(signatures,axis=0,keepdims=True)
    projection=abs(dominant@signatures.conj())**2
    best=projection.max(axis=1)
    return best,projection.argmax(axis=1),values[:,-1]/np.maximum(values.sum(axis=1),1e-12)


def hypotheses(matrix):
    corrections={'identity':np.eye(3),'factory_rows':matrix,'factory_rows_conjugated':matrix.conj(),
        'factory_rows_transposed':matrix.T,'factory_rows_adjoint':matrix.conj().T,
        'factory_rows_inverse':np.linalg.inv(matrix),'factory_rows_inverse_conjugated':np.linalg.inv(matrix).conj()}
    for name,correction in corrections.items():
        for order in permutations(range(3)):
            for conjugate in [False,True]:
                yield dict(matrix=name,rx_permutation=list(order),fft_conjugated=conjugate),correction


def ambiguity_certificate(config):
    """Exhibit two nonnegative angular scenes giving the same RX covariance."""
    uv=np.array([[0,0],[.6,0],[-.6,0],[0,.6],[0,-.6],
                 [.45,.45],[-.45,.45],[.45,-.45],[-.45,-.45]])
    virtual=np.exp(2j*np.pi*config.array_geometry@uv.T)
    signatures=np.linalg.solve(config.angle_matrix,virtual)
    signatures/=np.linalg.norm(signatures,axis=0,keepdims=True)
    atoms=np.einsum('ak,bk->kab',signatures,signatures.conj())
    design=np.concatenate([atoms.real.reshape(len(uv),-1).T,atoms.imag.reshape(len(uv),-1).T],axis=0)
    _,singular,vh=np.linalg.svd(design,full_matrices=True)
    null=vh[-1]
    first=np.maximum(null,0);second=np.maximum(-null,0)
    # Normalized signatures all have trace one; null coefficients sum to zero.
    first/=first.sum();second/=second.sum()
    cov_first=np.einsum('k,kab->ab',first,atoms)
    cov_second=np.einsum('k,kab->ab',second,atoms)
    relative=float(np.linalg.norm(cov_first-cov_second)/np.linalg.norm(cov_first))
    return dict(direction_cosines_uv=uv.tolist(),scene_a_power=first.tolist(),scene_b_power=second.tolist(),
        covariance_relative_difference=relative,design_rank=int(np.linalg.matrix_rank(design)),
        singular_values=singular.tolist(),
        meaning='Two distinct nonnegative, mutually incoherent angular scenes at ONE range and Doppler have the same ideal three-RX covariance. This is an identifiability counterexample, not a description of the recorded room. It assumes this array model is exactly correct.')


def raw_ambiguity_certificate(config):
    """Equal raw channel samples from one versus three coherent scatterers."""
    uv=np.array([[0,0],[.6,0],[0,.6],[-.45,-.45]])
    virtual=np.exp(2j*np.pi*config.array_geometry@uv.T)
    response=np.linalg.solve(config.angle_matrix,virtual)
    amplitudes=np.linalg.solve(response[:,:3],response[:,3])
    first=response[:,:3]@amplitudes
    second=response[:,3]
    return dict(direction_cosines_uv=uv.tolist(),scene_a_indices=[0,1,2],scene_b_indices=[3],
        scene_a_amplitudes_real=amplitudes.real.tolist(),scene_a_amplitudes_imag=amplitudes.imag.tolist(),
        raw_complex_vector_relative_difference=float(np.linalg.norm(first-second)/np.linalg.norm(second)),
        meaning='At one range and Doppler, three coherent scatterers with these complex amplitudes and one at another direction produce the SAME raw 3-RX complex vector. Multiplying both by the same fast/slow-time waveform preserves the equality for all chirps. No angular method can uniquely choose between these scenes without additional assumptions or independent views.')


def write_audit(root,config_path,output,profile,hal,firmware):
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=True)
    config=Config.load(config_path)
    facts=source_facts(profile,hal,firmware)
    neutral=replace(config,gains_real=[1,1,1],gains_imag=[0,0,0])
    sessions={};covs=[];cell_session=[];cells=[]
    for path in sorted(root.iterdir()):
        if not (path/'frames.grd').exists():continue
        cov,report=raw_session(path,neutral)
        mean=cov.mean(axis=0);eigen=np.linalg.eigvalsh(mean)
        report['covariance_rank1_energy_fraction_by_bin']=(eigen[:,-1]/np.maximum(eigen.sum(axis=1),1e-12)).tolist()
        report['effective_observation_rank_by_bin']=(eigen.sum(axis=1)**2/np.maximum((eigen**2).sum(axis=1),1e-12)).tolist()
        trace=eigen.sum(axis=1)
        # Audit all usable cells within 20 dB of the session maximum, including
        # complex-scene cells; score predominantly rank-one cells separately.
        selected=np.flatnonzero((np.arange(len(mean))>=2)&(np.arange(len(mean))<len(mean)-1)&(trace>=trace[2:-1].max()/100))
        for b in selected:
            covs.append(mean[b]);cell_session.append(path.name);cells.append(dict(session=path.name,range_bin=int(b)))
        sessions[path.name]=report
    covs=np.array(covs)
    directions,virtual=steering_grid(config)
    models=[]
    for identity,correction in hypotheses(config.angle_matrix):
        score,indices,rank1=dominant_mode_scores(covs,correction,identity['rx_permutation'],identity['fft_conjugated'],virtual)
        summary={}
        for name in sessions:
            select=np.array([s==name for s in cell_session])
            coherent=select&(rank1>=0.9)
            summary[name]=dict(mean_projection=float(score[select].mean()),
                coherent_cell_mean_projection=float(score[coherent].mean()) if coherent.any() else None,
                cells=int(select.sum()),coherent_cells=int(coherent.sum()))
        plate=[v['coherent_cell_mean_projection'] for name,v in summary.items() if name.startswith('plate_') and v['coherent_cell_mean_projection'] is not None]
        scene=[v['coherent_cell_mean_projection'] for name,v in summary.items() if name.startswith('detkin') and v['coherent_cell_mean_projection'] is not None]
        models.append(dict(**identity,plate_score=float(np.mean(plate)),detkin_score=float(np.mean(scene)),
            per_session=summary,best_directions_uv=directions[:,indices].T.tolist(),cell_projections=score.tolist()))
    # Rank only as a diagnostic; there is NO automatic selected model/config.
    models.sort(key=lambda m:m['plate_score'],reverse=True)
    result=dict(schema=1,facts=facts,config=asdict(config),sessions=sessions,cells=cells,models=models,
        ambiguity_certificate=ambiguity_certificate(config),
        raw_ambiguity_certificate=raw_ambiguity_certificate(config),
        status='No convention selected or installed. Fit is consistency with an assumed point-source manifold, NOT geometric accuracy.',
        angular_truth='Numeric detkin suffixes have unconfirmed meaning/side/pose. Body/arm are retained as scene content.',
        invariances=['Overall complex gain cannot be identified from normalized signatures.',
            'Conjugating signatures and reflecting both direction cosines gives equal fit on a symmetric field.',
            'An orthogonal rotation/reflection of array coordinates can be offset by rotating/reflecting unknown scene directions.'],
        timing='Only frame trigger timestamps exist. Uniform physical chirp spacing and changed averaging/sequence semantics cannot be certified by static waveforms.')
    (output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Measurement-model audit','',result['status'],'',
        f"{sum(s['frames'] for s in sessions.values())} frames; {len(sessions)} sessions; {len(models)} model hypotheses; {len(cells)} range cells.",'',
        '| Rank by plate consistency | Matrix hypothesis | RX order (zero-based) | Conjugate FFT | Plate score | Detkin score |',
        '|---:|---|---|---|---:|---:|']
    for i,m in enumerate(models[:15],1):
        lines.append(f"| {i} | {m['matrix']} | {m['rx_permutation']} | {m['fft_conjugated']} | {m['plate_score']:.5f} | {m['detkin_score']:.5f} |")
    lines.extend(['','Scores are squared projections onto a normalized assumed array response, averaged equally per session over predominantly coherent range cells. They are not angle accuracy or confidence. No per-session offset or fit parameter is learned. Plate records provide a source group; detkin records provide a distinct scene group. Neither has certified angular ground truth.','',
        '## Source facts','',f"Nominal FFT spacing: {facts['waveform']['fft_bin_spacing_m_nominal']:.6f} m.",
        f"RX HPF1 corners: {[r['hpf1_hz'] for r in facts['rx_register_configuration']]} Hz; equivalent nominal range: {[r['hpf1_equivalent_range_m_nominal'] for r in facts['rx_register_configuration']]} m.",
        'The analog filter corners are not hard range cutoffs. They attenuate near-range beat frequencies; no inverse compensation was applied.',
        'Runtime averaging is changed from profile factor16 to factor1 and acquisition is truncated. No sequencer ISA/timestamp evidence in the saved data establishes chirp spacing.',
        'Carrier frequency and chirp interval remain unknown. Source files are hashed in report.json. Firmware and old configurations were not modified.','',
        '## Identifiability checks','',
        f"Two distinct nonnegative angular distributions yield the same covariance to relative error {result['ambiguity_certificate']['covariance_relative_difference']:.3g} under the configured model.",
        f"Three coherent scatterers at different directions and one scatterer at another direction yield the same raw complex RX vector to relative error {result['raw_ambiguity_certificate']['raw_complex_vector_relative_difference']:.3g}.",
        'These are mathematical counterexamples, not inferred objects in the room. They show why a unique dense scene is not determined without additional assumptions/views even with a perfectly calibrated array.',
        'See docs/MEASUREMENT_MODEL_AUDIT.md for interpretation, source provenance and remaining verification requirements.',''])
    (output/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    plot_audit(result,output)
    return result


def plot_audit(result,output):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    names=['plate_0_6m','plate_1_3m','plate_2m','detkin-empty','detkin-ipad-30','detkin-ipad-15','detkin-ipad0','detkin-ipad15','detkin-ipad30']
    names=[n for n in names if n in result['sessions']]
    figure=Figure(figsize=(12,8),layout='constrained');FigureCanvasAgg(figure)
    packing,score_axes,phase,rank=figure.subplots(2,2).ravel()
    for hypothesis in ['unsigned16_sample_interleaved','swap_adjacent_16bit_halves','byte_swap_each_16bit','rx_major_within_chirp']:
        packing.plot(np.arange(len(names)),[result['sessions'][n]['packing_hypotheses'][hypothesis]['difference_rms_over_signal_rms'] for n in names],'.-',label=hypothesis)
    packing.set_xticks(np.arange(len(names)),names,rotation=65,fontsize=7);packing.set(ylabel='Normalized fast-time roughness',title='Packing alternatives (lower is smoother)');packing.legend(fontsize=6)
    models=result['models'];score_axes.scatter([m['plate_score'] for m in models],[m['detkin_score'] for m in models],s=15)
    score_axes.set(xlabel='Plate-group model consistency',ylabel='Detkin-group model consistency',title='84 uncalibrated hypotheses; not angle accuracy')
    for name in names:
        session=result['sessions'][name]
        phase.plot(np.arange(17),np.array(session['chirp_slot_relative_phase_deg'])[:,0],'.-',label=name)
        rank.plot(np.arange(33),session['effective_observation_rank_by_bin'],label=name)
    phase.set(xlabel='Chirp slot',ylabel='RX2–RX1 phase (deg)',title='Relative phase through stored chirp slots');phase.legend(fontsize=6,ncol=2)
    rank.set(xlabel='Range bin',ylabel='Covariance participation rank',title='Scene degrees of freedom (not object count)')
    figure.savefig(output/'diagnostics.png',dpi=130)


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('recordings');parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--profile',default='firmware/vendor/presence_detection_tracking.h')
    parser.add_argument('--hal',default='../mtb_shared/sensor-xensiv-bgt60cutrxx/release-v1.1.0/register_hal/xensiv_bgt60cutrxxb_register_hal.h')
    parser.add_argument('--firmware',default='firmware/main.c')
    args=parser.parse_args();report=write_audit(args.recordings,args.config,args.output,args.profile,args.hal,args.firmware)
    print(json.dumps(dict(frames=sum(s['frames'] for s in report['sessions'].values()),hypotheses=len(report['models']),top_models=[{k:m[k] for k in ['matrix','rx_permutation','fft_conjugated','plate_score','detkin_score']} for m in report['models'][:5]]),indent=2))


if __name__=='__main__':main()
