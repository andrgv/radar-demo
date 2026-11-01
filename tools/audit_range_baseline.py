"""Audit this known repository; requires local shafaa branch and vendor HAL sibling. Never writes recordings."""
import json, hashlib, shutil, subprocess, argparse, tempfile
from pathlib import Path
from radar.storage import replay
from radar.protocol import Parser
from radar.model_audit import source_facts
from radar.range_check import analyze_range_check
arguments=argparse.ArgumentParser()
arguments.add_argument('repository',type=Path)
arguments.add_argument('output',type=Path)
a=arguments.parse_args()
root=a.repository.resolve();out=a.output
out.mkdir(parents=True,exist_ok=False)
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inventory=[]
for p in sorted((root/'recordings').rglob('*')):
 if p.is_file(): inventory.append(dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=sha(p)))
(out/'recording-files.json').write_text(json.dumps(inventory,indent=2))
rows=[]
for p in sorted((root/'recordings').rglob('frames.grd')):
 parser=Parser(); fs=list(replay(p,parser))
 rows.append(dict(path=str(p.parent.relative_to(root)),frames=len(fs),span_s=((fs[-1].timestamp_us-fs[0].timestamp_us)&0xffffffff)/1e6 if fs else None,gaps=parser.gaps,restarts=parser.restarts,bad_crc=parser.bad_crc,bad_headers=parser.bad_headers,tail_bytes=len(parser.buffer),profiles=sorted({f.profile_id for f in fs}),device_errors=sorted({f.errors for f in fs}),device_drops=sorted({f.dropped for f in fs}),metadata=json.loads((p.parent/'metadata.json').read_text())))
(out/'recordings.json').write_text(json.dumps(rows,indent=2))
facts=source_facts(root/'firmware/vendor/presence_detection_tracking.h',root.parent/'mtb_shared/sensor-xensiv-bgt60cutrxx/release-v1.1.0/register_hal/xensiv_bgt60cutrxxb_register_hal.h',root/'firmware/main.c')
facts['build_artifacts']=[dict(path=str(p.relative_to(root)),sha256=sha(p),bytes=p.stat().st_size) for p in (root/'build').rglob('*') if p.suffix in ('.hex','.elf')]
(out/'firmware.json').write_text(json.dumps(facts,indent=2))
temporary=tempfile.TemporaryDirectory()
p=Path(temporary.name)/'baseline-copy'
shutil.copytree(root/'recordings/box_range_20261028_002954',p)
(out/'historical-report.json').write_text((p/'range-check-report.json').read_text())
(out/'cwm-replay.json').write_text(json.dumps(analyze_range_check(p),indent=2))
# Load only historical tracking module; all its dependencies are identical at the two commits.
import radar.range_check as rc
import types,sys
m=types.ModuleType('radar._shafaa_tracking');m.__package__='radar';sys.modules[m.__name__]=m
exec(subprocess.check_output(['git','-C',str(root),'show','shafaa:radar/tracking.py'],text=True),m.__dict__)
rc.ShortRangeAmplitudeTracker=m.ShortRangeAmplitudeTracker
(out/'shafaa-replay.json').write_text(json.dumps(rc.analyze_range_check(p),indent=2))
temporary.cleanup()
print(json.dumps(rows,indent=2))
for name in ['historical-report','shafaa-replay','cwm-replay']:
 d=json.loads((out/(name+'.json')).read_text());print(name,d['short_range_live_selector'])
print(facts['waveform']);print(facts['rx_register_configuration'])
