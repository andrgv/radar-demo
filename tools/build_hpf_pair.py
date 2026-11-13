"""Build-only macOS HPF comparison. No programming or device access commands."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from dataclasses import replace
from radar_min.core import Config
from tools.prepare_qualification import prepare

ROOT=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output',type=Path)
    ap.add_argument('--original',type=Path,default=Path.home()/'radar-work/radar-demo')
    ap.add_argument('--tools',default='/Applications/ModusToolbox/tools_3.9')
    a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=a.original.resolve()
    backup=out/'restore-oct28';backup.mkdir()
    for ext in ['hex','elf']:
        src=original/f'build/last_config/glass-radar-3rx.{ext}'
        dst=backup/src.name;shutil.copy2(src,dst)
        if sha(src)!=sha(dst): raise ValueError('Backup mismatch')
    stage=Path(tempfile.mkdtemp(prefix='wavvy-hpf-build-'))
    project=stage/'radar-demo';project.mkdir()
    for name in ['firmware','bsps','deps','configs']:
        shutil.copytree(ROOT/name,project/name)
    shutil.copytree(original/'libs',project/'libs')
    shutil.copytree(original.parent/'mtb_shared',stage/'mtb_shared',symlinks=True)
    for name in ['Makefile','.cyignore']: shutil.copy2(ROOT/name,project/name)
    source_manifest=prepare(project)
    # Verify the generated qualification C is exactly the reviewed source.
    if (project/'experiments/qualification/main.c').read_bytes()!=(ROOT/'experiments/qualification/main.c').read_bytes():
        raise ValueError('Generated qualification source differs from reviewed source')
    manifest=dict(stage=str(stage),original=str(original),flash_performed=False,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        original_firmware_sha256=sha(original/'firmware/main.c'),
        qualification_sha256=sha(project/'experiments/qualification/main.c'),
        source_manifest=source_manifest,
        restoration={p.name:sha(p) for p in backup.iterdir()},builds=[])
    for hpf,profile in [(350,0x33514802),(100,0x33514801)]:
        build=out/f'hpf{hpf}';build.mkdir()
        command=['make','build','-j4',f'CY_TOOLS_DIR={a.tools}',
            f'CY_BUILD_LOCATION=build/qualification-{hpf}',
            'RADAR_QUALIFICATION=1',f'RADAR_HPF_KHZ={hpf}','RADAR_SCOPE_OUTPUT=0']
        print('BUILD',hpf,'in',project,flush=True)
        with (build/'build.log').open('w') as log:
            result=subprocess.run(command,cwd=project,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            print((build/'build.log').read_text()[-12000:],flush=True)
            raise SystemExit(result.returncode)
        products=project/f'build/qualification-{hpf}/APP_CYSBSYSKIT-DEV-01/Release'
        for ext in ['hex','elf','map']:
            shutil.copy2(products/f'glass-radar-3rx.{ext}',build/f'glass-radar-3rx.{ext}')
        replace(Config(),profile_id=profile).save(build/'range-config.json')
        entry=dict(hpf_khz=hpf,profile_id=hex(profile),command=command,
                   files={p.name:sha(p) for p in build.iterdir() if p.name!='build.log'})
        manifest['builds'].append(entry)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
        print('BUILT',hpf,entry['files']['glass-radar-3rx.hex'],flush=True)
    shutil.copy2(project/'experiments/qualification/main.c',out/'qualification-main.c')
    from tools.verify_hpf_pair import verify
    verify(out,out/'verification')
    print('Build-only complete:',out,flush=True)


if __name__=='__main__':main()
