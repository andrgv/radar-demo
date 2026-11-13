"""Read-only firmware/profile check and offline near-range estimator diagnosis."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import numpy as np
from radar_min.__main__ import read_recording
from radar.recording_audit import read_register_profile, nominal_waveform


def spectrum(x, remove_mean=True):
    x = np.asarray(x, dtype=float)
    if remove_mean:
        x = x - x.mean(axis=-1, keepdims=True)
    w = np.hanning(x.shape[-1])
    return abs(np.fft.rfft(x*w, n=4096, axis=-1)*2/w.sum())**2


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('original', type=Path)
    ap.add_argument('output', type=Path)
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    header = a.original/'firmware/vendor/presence_detection_tracking.h'
    pairs = re.findall(r'\{(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+)\}', header.read_text())
    packed = b''.join(struct.pack('<II', int(x,16), int(y,16)) for x,y in pairs)
    elf = (a.original/'build/last_config/glass-radar-3rx.elf').read_bytes()
    # Compare load-image bytes as well as ELF, validating Intel HEX checksums.
    mem = {}; base = 0
    hexfile = a.original/'build/last_config/glass-radar-3rx.hex'
    for line in hexfile.read_text().splitlines():
        b = bytes.fromhex(line[1:]); assert line.startswith(':') and sum(b)%256 == 0
        assert len(b) == b[0]+5
        addr = int.from_bytes(b[1:3], 'big'); kind = b[3]; data = b[4:-1]
        if kind == 4: base = int.from_bytes(data,'big') << 16
        elif kind == 2: base = int.from_bytes(data,'big') << 4
        elif kind == 0:
            for i,v in enumerate(data): mem[base+addr+i] = v
        elif kind == 1: break
    matches = []
    for addr in sorted(mem):
        if mem[addr] == packed[0] and all(mem.get(addr+i)==v for i,v in enumerate(packed)):
            matches.append(hex(addr))
    regs, clock = read_register_profile(header)
    waveform = nominal_waveform(regs, clock)
    report = dict(elf_sha256=hashlib.sha256(elf).hexdigest(),
        hex_sha256=hashlib.sha256(hexfile.read_bytes()).hexdigest(),
        register_pairs=len(pairs), full_register_array_elf_offset=elf.find(packed),
        full_register_array_hex_addresses=matches, waveform=waveform,
        rx_registers={hex(k):hex(regs[k]) for k in [0x1010,0x1014,0x1018]},
        limits='Binary array match is not device readback or proof of sequencer timing. Synthetic tones omit analog settling, multipath and noise. No changes to firmware or live processing.')
    c,_,_ = read_recording(Path('recordings/distance-sweep-2-empty-before'))
    freq = np.fft.rfftfreq(4096, 1/c.sample_rate_hz)
    axis = freq*299792458/(2*c.slope_hz_s)
    ids = np.flatnonzero((axis>=.15)&(axis<=1.5))
    phases = np.arange(360)*2*np.pi/360
    synthetic = []
    for distance in [.15,.30,.35,.40,.50]:
        beat = 2*c.slope_hz_s*distance/299792458
        x = np.cos(2*np.pi*beat*np.arange(c.samples)[None,:]/c.sample_rate_hz+phases[:,None])
        row = dict(distance_m=distance, expected_beat_hz=beat, cycles_in_window=beat*c.samples/c.sample_rate_hz)
        for dc in [True,False]:
            p = spectrum(x,dc)
            peaks = axis[ids[np.argmax(p[:,ids],axis=1)]]
            row['mean_removed' if dc else 'no_mean_removal'] = dict(min_median_max_m=np.percentile(peaks,[0,50,100]).tolist())
        synthetic.append(row)
    report['synthetic_phase_sweep'] = synthetic
    rows = []; plotdata=[]
    for sweep in [1,2]:
        c,empty,_ = read_recording(Path(f'recordings/distance-sweep-{sweep}-empty-before'))
        def powers(frames, remove_mean=True):
            return np.array([spectrum(f.adc[c.discard_chirps:].transpose(0,2,1),remove_mean).mean(axis=(0,1)) for f in frames])
        ref = np.median(powers(empty[:30]),axis=0)
        ref_no_dc = np.median(powers(empty[:30],False),axis=0)
        for suffix,label in [('empty-before',None),('30cm',.3),('40cm',.4),('50cm',.5),('40cm-repeat',.4),('empty-after',None)]:
            path=Path(f'recordings/distance-sweep-{sweep}-{suffix}')
            _,frames,_=read_recording(path)
            if suffix=='empty-before': frames=frames[30:]
            residual=powers(frames)-ref
            peaks=axis[ids[np.argmax(residual[:,ids],axis=1)]]
            no_dc_residual=powers(frames,False)-ref_no_dc
            no_dc_peaks=axis[ids[np.argmax(no_dc_residual[:,ids],axis=1)]]
            row=dict(recording=path.name,label_m=label,frames=len(frames),
                raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                peak_frequency_p05_median_p95_hz=(np.percentile(peaks,[5,50,95])*2*c.slope_hz_s/299792458).tolist(),
                peak_range_p05_median_p95_m=np.percentile(peaks,[5,50,95]).tolist(),
                no_mean_removal_peak_range_p05_median_p95_m=np.percentile(no_dc_peaks,[5,50,95]).tolist(),
                mae_m=float(np.mean(abs(peaks-label))) if label is not None else None,
                no_mean_removal_mae_m=float(np.mean(abs(no_dc_peaks-label))) if label is not None else None)
            rows.append(row)
            plotdata.append((sweep,suffix,label,np.median(residual,axis=0)))
    report['recordings']=rows
    (a.output/'report.json').write_text(json.dumps(report,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,8),layout='constrained')
    for sweep,ax in enumerate(axes,1):
        for s,name,label,y in plotdata:
            if s!=sweep: continue
            line,=ax.plot(freq/1000,y,label=name,alpha=.85)
            if label is not None:
                ax.axvline(2*c.slope_hz_s*label/299792458/1000,color=line.get_color(),ls=':',alpha=.5)
        ax.axvline(350,color='black',ls='--',label='HPF1 nominal corner')
        ax.axhline(0,color='gray',lw=.5)
        ax.set(xlim=(0,400),xlabel='Beat frequency (kHz)',ylabel='Median excess linear power (ADC units²)',title=f'Sweep {sweep}; dotted lines = expected target frequencies')
        ax.legend(fontsize=8)
    fig.savefig(a.output/'spectra.png',dpi=150)
    print(json.dumps({k:v for k,v in report.items() if k not in ['waveform','recordings']},indent=2))
    for row in rows: print(row['recording'],row['peak_frequency_p05_median_p95_hz'])


if __name__=='__main__': main()
