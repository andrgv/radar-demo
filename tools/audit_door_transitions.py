"""Recover transition data retained in the original continuous serial stream.

The door and operator can both move in transition intervals. No transition
return is automatically labeled as glass. Host timestamps come from wire logs.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from radar.config import Config
from radar.processing import range_fft
from radar.protocol import Parser


def audit(root,output):
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=False)
    summary={}
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    manifests=[p for p in sorted(root.glob('*/door-check.json')) if json.loads(p.read_text()).get('complete')]
    fig=Figure(figsize=(12,4*len(manifests)),tight_layout=True);FigureCanvasAgg(fig)
    axes=np.atleast_1d(fig.subplots(len(manifests),1))
    for axis,manifest_path in zip(axes,manifests):
        experiment=manifest_path.parent;config=Config.load(experiment/'config.json')
        parser=Parser();hosts=[];sequences=[];power=[];channels=[]
        with (experiment/'stream/serial-wire.bin').open('rb') as wire:
            for line in (experiment/'stream/transport.jsonl').read_text().splitlines():
                arrival=json.loads(line)
                data=wire.read(arrival['bytes'])
                if len(data)!=arrival['bytes']:raise ValueError('Truncated wire stream')
                for frame in parser.feed(data):
                    spectrum=range_fft(frame.adc,config)
                    hosts.append(arrival['host_unix_ns']);sequences.append(frame.sequence)
                    power.append(np.mean(abs(spectrum)**2,axis=0))
                    channels.append(np.mean(spectrum,axis=0))
        hosts=np.array(hosts,dtype=np.int64);power=np.array(power);channels=np.array(channels)
        seconds=(hosts-hosts[0])/1e9
        intervals=[]
        for path in sorted(experiment.glob('open-*'))+sorted(experiment.glob('closed-*')):
            arrivals=[json.loads(line) for line in (path/'arrivals.jsonl').read_text().splitlines()]
            intervals.append(dict(name=path.name,start_s=(arrivals[0]['host_unix_ns']-int(hosts[0]))/1e9,
                                  end_s=(arrivals[-1]['host_unix_ns']-int(hosts[0]))/1e9))
        intervals.sort(key=lambda a:a['start_s'])
        np.savez_compressed(output/f'{experiment.name}-stream.npz',host_unix_ns=hosts,sequence=np.array(sequences),
                            mean_spectrum=channels,mean_power=power)
        mean=10*np.log10(np.maximum(power.mean(axis=2),1e-12))
        artist=axis.pcolormesh(seconds,np.arange(1,11),mean[:,1:11].T,shading='auto',cmap='viridis')
        for interval in intervals:
            axis.axvline(interval['start_s'],color='white',alpha=.7,linestyle='--')
            axis.axvline(interval['end_s'],color='white',alpha=.7,linestyle='--')
            axis.text((interval['start_s']+interval['end_s'])/2,10,interval['name'],ha='center',va='top',color='white',fontsize=8)
        axis.set(title=experiment.name+' original stream: captures and intervening transitions',
                 xlabel='Elapsed host seconds',ylabel='Native range bin')
        fig.colorbar(artist,ax=axis,label='Mean RX power (dB ADC²)')
        summary[experiment.name]=dict(frames=len(hosts),duration_s=float(seconds[-1]),intervals=intervals,
                parser_counters={k:getattr(parser,k) for k in ('bad_crc','bad_headers','gaps','restarts')},
                trailing_unparsed_bytes=len(parser.buffer))
    fig.savefig(output/'transitions.png',dpi=150)
    (output/'summary.json').write_text(json.dumps(dict(sessions=summary,limitations=__doc__),indent=2))
    print(json.dumps({name:dict(frames=v['frames'],duration_s=v['duration_s']) for name,v in summary.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('output');a=p.parse_args();audit(a.root,a.output)
