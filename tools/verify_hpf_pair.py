"""Offline checks of built HPF variants; no hardware access."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import numpy as np
from radar_min.core import Config, power
from radar.protocol import Frame, Parser, encode


def verify(root, output):
    output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((root/'manifest.json').read_text())
    project=Path(manifest['stage'])/'radar-demo'
    gcc=Path.home()/'Applications/mtb-gcc-arm-eabi/14.2.1/gcc/bin/arm-none-eabi-gcc'
    pairs=re.findall(r'\{(0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+)\}',(project/'firmware/vendor/presence_detection_tracking.h').read_text())
    packed=b''.join(struct.pack('<II',int(a,16),int(b,16)) for a,b in pairs)
    texts=[];checks=[]
    for entry in manifest['builds']:
        h=entry['hpf_khz'];folder=root/f'hpf{h}'
        for name,digest in entry['files'].items():
            if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Build hash mismatch: '+name)
        rsp=next(project.glob(f'build/qualification-{h}/**/main.o.rsp'))
        text=subprocess.check_output([str(gcc),'-E','-P','-mcpu=cortex-m4','-mthumb',
            '-mfloat-abi=softfp','-mfpu=fpv4-sp-d16','@'+str(rsp),
            'experiments/qualification/main.c'],cwd=project,text=True)
        texts.append(text)
        c=Config.load(folder/'range-config.json')
        if c.profile_id!={350:0x33514802,100:0x33514801}[h]: raise ValueError('Wrong profile')
        f=Frame(0,0,c.profile_id,np.full((17,64,3),12000,dtype=np.uint16),
            flags=3 if h==350 else 7,capture_elapsed_us=1200)
        decoded=Parser().feed(encode(f))[0];power(decoded,c)
        wrong=False
        try:power(decoded,Config())
        except ValueError:wrong=True
        if not wrong or decoded.capture_elapsed_us!=1200 or decoded.flags!=f.flags:
            raise ValueError('Host compatibility check failed')
        mem={};base=0
        for line in (folder/'glass-radar-3rx.hex').read_text().splitlines():
            b=bytes.fromhex(line[1:])
            if not line.startswith(':') or len(b)!=b[0]+5 or sum(b)%256:
                raise ValueError('Invalid Intel HEX record')
            if b[3]==4:base=int.from_bytes(b[4:-1],'big')<<16
            elif b[3]==2:base=int.from_bytes(b[4:-1],'big')<<4
            elif b[3]==0:
                addr=base+int.from_bytes(b[1:3],'big')
                for i,v in enumerate(b[4:-1]):mem[addr+i]=v
            elif b[3]==1:break
        matches=[hex(a) for a,v in mem.items() if v==packed[0] and a%4==0
                 and all(mem.get(a+i)==x for i,x in enumerate(packed))]
        if len(matches)!=1:raise ValueError('Register array absent or duplicated in image')
        checks.append(dict(hpf_khz=h,profile_id=hex(c.profile_id),flags=decoded.flags,
            elapsed_telemetry_roundtrip=True,wrong_profile_rejected=True,
            hex_checksums_valid=True,register_array_address=matches[0],register_pairs=len(pairs)))
    if len(texts)!=2 or texts[0].count('(350 == 100)')!=3 or texts[0].replace('(350 == 100)','(100 == 100)')!=texts[1]:
        raise ValueError('Unexpected preprocessed source difference')
    diff='\n'.join(difflib.unified_diff(texts[0].splitlines(),texts[1].splitlines(),
        fromfile='350kHz preprocessed',tofile='100kHz preprocessed'))+'\n'
    (output/'preprocessed.diff').write_text(diff)
    (output/'verification.json').write_text(json.dumps(checks,indent=2))
    return checks


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('build',type=Path);ap.add_argument('output',type=Path)
    args=ap.parse_args();print(json.dumps(verify(args.build,args.output),indent=2))
