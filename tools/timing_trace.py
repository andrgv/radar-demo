"""Trace documented timing facts without inventing sequencer opcodes."""
import json
from pathlib import Path
import re
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from radar.recording_audit import read_register_profile,nominal_waveform
from radar.storage import replay


def trace(root=ROOT):
    profile=root/'firmware/vendor/presence_detection_tracking.h'
    registers,clock=read_register_profile(profile)
    waveform=nominal_waveform(registers,clock)
    named={int(a,16):(int(v,16),name) for a,v,name in re.findall(
        r'\{(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+)\},\s*//\s*(\w+)',profile.read_text())}
    relevant=[dict(address=hex(a),name=n,value=hex(v)) for a,(v,n) in named.items()
        if a in [0x20,0x30,0x1500,0x1b10,0x1b20,0x1b00] or 0x1200<=a<=0x122c or 0x1400<=a<=0x1444]
    sessions=[]
    for directory in sorted((root/'recordings').iterdir()):
        if not (directory/'frames.grd').exists():continue
        frames=list(replay(directory))
        if len(frames)<2:continue
        ticks=np.array([f.timestamp_us for f in frames],dtype=np.uint32)
        sequence=np.array([f.sequence for f in frames],dtype=np.uint32)
        deltas=np.diff(ticks).astype(float);steps=np.diff(sequence).astype(float)
        elapsed=[f.capture_elapsed_us for f in frames if f.capture_elapsed_us is not None]
        arrivals=[json.loads(line) for line in (directory/'arrivals.jsonl').read_text().splitlines()]
        host={row['sequence']:row['host_unix_ns'] for row in arrivals}
        common=[f for f in frames if f.sequence in host]
        host_span=(host[common[-1].sequence]-host[common[0].sequence])/1e9 if len(common)>1 else None
        device_span=float(np.sum(np.diff(np.array([f.timestamp_us for f in common],dtype=np.uint32))))/1e6 if len(common)>1 else None
        trend=None
        if len(common)>60:
            device=np.r_[0,np.cumsum(np.diff(np.array([f.timestamp_us for f in common],dtype=np.uint32)).astype(float))]/1e6
            arrival=np.array([(host[f.sequence]-host[common[0].sequence])/1e9 for f in common])
            i,j=np.triu_indices(len(common),k=50)
            slope=(arrival[j]-arrival[i])/(device[j]-device[i])
            ratio=np.percentile(slope,[5,50,95])
            trend=dict(long_separation_host_over_device_ratio_p05_p50_p95=ratio.tolist(),
                       nominal_100ms_schedule_in_host_ms=100*float(ratio[1]),
                       caveat='Host wall clock and device timer comparison; not an external timing standard. USB/processing latency and wall-clock adjustments can bias it. Do not apply to RF timing or range.')
        sessions.append(dict(session=directory.name,frames=len(frames),
            frame_trigger_spacing_us_p05_p50_p95=np.percentile(deltas,[5,50,95]).tolist(),
            spacing_per_sequence_step_us_p05_p50_p95=np.percentile(deltas/np.maximum(steps,1),[5,50,95]).tolist(),
            host_span_s=host_span,device_span_s=device_span,
            host_over_device_span_ratio=host_span/device_span if device_span else None,
            host_device_trend=trend,
            capture_path_elapsed_us_p05_p50_p95=np.percentile(elapsed,[5,50,95]).tolist() if elapsed else None))
    return dict(system_clock_hz_nominal=clock,register_trace=relevant,
        sample_rate_hz_nominal=waveform['sample_rate_hz_nominal'],
        adc_sampling_window_us_nominal=64/waveform['sample_rate_hz_nominal']*1e6,
        sampled_first_to_last_span_us_nominal=63/waveform['sample_rate_hz_nominal']*1e6,
        source_frame_schedule_us=100000,
        chirp_interval_s=None,burst_duration_s=None,carrier_hz=None,
        unresolved='The 42 encoded sequence words are preserved, but no documented instruction decoder or matching raw timing metadata was found in the public driver/config headers. SH trigger counts alone do not establish chirp start-to-start spacing.',
        sequence_words=[dict(address=hex(a),word=hex(v)) for a,(v,n) in named.items() if n.startswith('SEQ_BUFFER')],
        sessions=sessions,
        independent_check='Host arrival elapsed time provides a separate frame-cadence consistency check. It includes USB, OS and processing delays and is not an intra-chirp timing measurement.',
        qualification_elapsed='New firmware variants set header flag bit1 and word10 to elapsed time from before trigger write through FIFO reads and stop/IRQ checks. Do not divide by 17 to assign chirp spacing.')


if __name__=='__main__':
    result=trace();output=ROOT/'artifacts/qualification';output.mkdir(parents=True,exist_ok=True)
    (output/'timing-trace.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({key:result[key] for key in ['adc_sampling_window_us_nominal','chirp_interval_s','burst_duration_s','source_frame_schedule_us']},indent=2))
