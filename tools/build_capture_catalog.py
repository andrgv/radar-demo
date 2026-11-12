"""Build the physical-setup catalog from curated facts, scene manifests and saved metadata."""
import hashlib
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def link(path,label=None):
    return f'[{label or path}](../{path})'


def cell(value):
    return str(value).replace('|','\\|').replace('\n',' ')


def span(values):
    return '–'.join(f'{v:.2f}' for v in values)+' s'


def main():
    curated=load(ROOT/'configs/capture-setups.json')['recordings']
    manifest_paths=[];annotations={}
    for path in sorted((ROOT/'configs').glob('*.json')):
        if path.name=='capture-setups.json':continue
        m=load(path);cases=m.get('cases',[])
        if m.get('recording') and m.get('windows'):
            cases=cases+[dict(recording=m['recording'],windows=m['windows'])]
        for case in cases:
            if not isinstance(case,dict) or 'recording' not in case:continue
            relative=str(path.relative_to(ROOT))
            annotations.setdefault(case['recording'],[]).append(dict(
                manifest=relative,sha256=digest(path),labels=m.get('labels',m.get('description')),
                scene=m.get('scene'),segments=m.get('segments'),case=case))
            if relative not in manifest_paths:manifest_paths.append(relative)
    references=[]
    for directory in ('docs','evidence'):
        for path in sorted((ROOT/directory).rglob('*.md')):
            if path.name=='CAPTURE_CATALOG.md':continue
            if directory=='evidence' and path.name not in ('README.md','REVIEW.md'):continue
            references.append((str(path.relative_to(ROOT)),path.read_text()))
    records=[]
    for config_path in sorted((ROOT/'recordings').rglob('config.json')):
        directory=config_path.parent;name=str(directory.relative_to(ROOT))
        meta_path=directory/'metadata.json';summary_path=directory/'capture-summary.json'
        config=load(config_path);metadata=load(meta_path)
        notes=curated.get(name,{})
        refs=sorted(set(notes.get('references',[])+[p for p,text in references if name in text]))
        records.append(dict(recording=name,has_raw_frames=(directory/'frames.grd').exists(),
            config=config,metadata=metadata,capture_summary=load(summary_path),
            source_hashes={p.name:digest(p) for p in (config_path,meta_path,summary_path) if p.exists()},
            setup=notes.get('setup','Physical setup not established in this catalog; saved label alone is not ground truth.'),
            annotations=annotations.get(name,[]),references=refs))
    names={r['recording'] for r in records}
    assert all(name in names for name in curated),'Curated capture missing from inventory'
    assert {str(p.parent.relative_to(ROOT)) for p in (ROOT/'recordings').rglob('frames.grd')}<=names
    raw=sum(r['has_raw_frames'] for r in records)
    catalog=dict(schema=1,as_of='2026-11-11',
        interpretation='User-reported physical setup, saved metadata and analysis windows have distinct provenance. Unknown is not empty. Nominal placement is not independently verified reflector identity. Profile IDs are not firmware hashes.',
        curated_source='configs/capture-setups.json',curated_sha256=digest(ROOT/'configs/capture-setups.json'),
        builder_sha256=digest(Path(__file__)),manifest_paths=manifest_paths,recordings=records)
    (ROOT/'configs/capture-catalog.json').write_text(json.dumps(catalog,indent=2,allow_nan=False)+'\n')
    lines=['# Data collection setup and evaluation catalog','',
        f'As of November 11, 2026: **{raw} raw recordings**, plus {len(records)-raw} configuration-only parent directories. '
        f'{len(curated)} captures have curated physical-setup notes below. Every saved configuration is indexed in the inventory; missing setup facts are explicitly unknown.','',
        'This is a setup/annotation index, not a detector acceptance report. User-reported placement, '
        'saved acquisition configuration, and analyst-selected scoring windows are kept separate. '
        'Do not infer target material or operator position in an earlier recording from a later one. '
        '“Empty” means the added target is absent; walls, people and other reflectors may remain.','',
        '## How to evaluate a capture','',
        '1. Use the exact full recording path; `live-001`/`live-002` alone are not unique. '
        'Load its saved `config.json`, raw `frames.grd`, `metadata.json`, and, when available, '
        '`arrivals.jsonl`, `readings.jsonl`, `capture-summary.json` and original `serial-wire.bin`.',
        '2. Choose the scene manifest linked below. User durations start at the first saved frame '
        'unless explicitly noted. Use half-open intervals in host seconds, derived from '
        '`(host_unix_ns − first_host_unix_ns) / 1e9`; do not fit an offset to detector output. '
        'Exclude handling/ignored intervals and preserve unlabeled tails. Two-second trims are '
        'primary where provided; one-second trims are sensitivity checks, not additional independent data.',
        '3. Read timing/transport and label caveats in the linked review. A valid packet or clock '
        'does not certify range accuracy. Do not pool overlapping windows, use the display as '
        'ground truth, or compare historical firmware profiles as an isolated firmware A/B test.',
        '4. Keep detector/configuration settings frozen, score numeric coverage and empty outputs '
        'alongside conditional placement differences, and preserve misses/rejections. The phase fit '
        'requires an existing candidate; its empty silence can be inherited from that detector. '
        'Physical target identity and calibrated speed remain unverified.','',
        'The AVG16 working profile is `0x33515403` (64 samples, 17 saved blocks, discard first, '
        '3 RX; vendor averaging 16). Earlier profiles differ. **A profile ID is not a firmware hash.** '
        'Firmware identity is often explicitly unknown in saved metadata; consult '
        '[timing/firmware provenance](AVG16_TIMING_TEST.md), [older timing images](MCU_EDGE_TIMING.md), '
        'and each capture’s metadata before replay.','',
        '## Detailed known collections','',
        'Tables distinguish original user hold intervals from scored interiors. Where a manifest '
        'only preserves a scored window, no original boundary is invented. Full manifests retain '
        'alternate trims and any approximate operator splits.','']
    by_name={r['recording']:r for r in records}
    for name in curated:
        r=by_name[name];c=r['config'];m=r['metadata'];pid=c.get('profile_id')
        lines.extend([f'### `{name}`','',r['setup'],'',
            f"Saved acquisition: profile `{pid:#010x}`; samples={c.get('samples','unknown')}, "
            f"saved chirps/blocks={c.get('chirps','unknown')}, discard={c.get('discard_chirps','unknown')}, "
            f"frame interval={c.get('frame_interval_s','unknown')} s. "
            f"Detector: `{(m.get('detector') or {}).get('algorithm','not recorded')}`. "
            f"{link(name+'/config.json','Configuration')} · {link(name+'/metadata.json','Metadata')}",''])
        summary=r['capture_summary']
        if summary:
            lines.extend([f"Capture summary: {summary.get('frames','unknown')} frames; "
                f"{summary.get('rejected_frames','unknown')} rejected; serial counters "
                f"`{json.dumps(summary.get('serial',{}),sort_keys=True)}`. "
                'These are saved capture counters, not a fresh replay audit.',''])
        for a in r['annotations']:
            lines.extend([f"Scene annotation: {link(a['manifest'])}.",''])
            if a['labels']:lines.extend([a['labels'],''])
            if a['segments']:
                lines.extend(['| Supplied segment | Original host interval | Duration |','|---|---:|---:|'])
                for s in a['segments']:
                    lines.append(f"| {cell(s['label'])} | {span([s['start_s'],s['end_s']])} | {s['duration_s']:.2f} s |")
                lines.append('')
            windows=[w for w in a['case'].get('windows',[]) if w.get('trim_s')!=1 and not w.get('operator_split_approximate')]
            if windows:
                lines.extend(['| State / label | Original interval if preserved | Scored host interval | Nominal placement |',
                              '|---|---:|---:|---:|'])
                for w in windows:
                    original=span(w['original_window_host_s']) if 'original_window_host_s'in w else 'not separately preserved'
                    target=f"{w['nominal_target_m']*100:g} cm" if w.get('nominal_target_m') is not None else '—'
                    lines.append(f"| {cell(w['label'])} | {original} | {span(w['window_host_s'])} | {target} |")
                lines.append('')
            elif 'interval_seconds'in a['case']:
                lines.extend([f"Alternating-label rule: {a['case']['interval_count']} intervals of "
                    f"{a['case']['interval_seconds']} s; target nominal {a['case'].get('target_m')} m. "
                    'See manifest/review for interpretation.',''])
        refs=[p for p in r['references'] if p not in [a['manifest'] for a in r['annotations']]]
        if refs:lines.extend(['Sources / reviews: '+' · '.join(link(p) for p in refs),''])
    lines.extend(['## Complete saved-configuration inventory','',
        'Each row links the actual recording directory/configuration. “Unspecified” means physical '
        'setup is not established here, even if a filename suggests a range. Saved metadata labels '
        'and distances below are provenance, not independently verified truth. Consult the detailed '
        'sections above or linked reviews before scoring. Configuration-only parents are not extra '
        'captures. The machine-readable catalog retains complete saved configs/metadata and all '
        'discovered exact-path review references.','',
        '| Recording | Raw | Profile | Saved label / distance | Setup / evidence |',
        '|---|---|---|---|---|'])
    for r in records:
        name=r['recording'];m=r['metadata'];pid=r['config'].get('profile_id')
        label=m.get('label','unspecified')
        if m.get('measured_distance_m')is not None:label+=f"; reported {m['measured_distance_m']} m"
        if m.get('scene_id') not in (None,'unspecified'):label+='; scene '+str(m['scene_id'])
        setup='Detailed above' if name in curated else 'Physical setup unspecified here'
        if r['references']:
            setup+='; '+' · '.join(link(p,Path(p).parent.name+'/'+Path(p).name) for p in r['references'][:4])
            if len(r['references'])>4:setup+='; more in JSON'
        lines.append(f"| {link(name+'/config.json',name.removeprefix('recordings/'))} | {'yes' if r['has_raw_frames'] else 'configuration only'} | `{pid:#010x}` | {cell(label)} | {setup} |")
    lines.extend(['','## Keeping this catalog current','',
        'Add physical setup facts and their provenance to [capture-setups.json](../configs/capture-setups.json), '
        'and write explicit timing labels in a separate scene manifest under `configs/`. Preserve '
        'raw data and original metadata. Record target dimensions/material/orientation/support, '
        'antenna-to-front-surface distance and uncertainty, sensor height/motion, background geometry, '
        'operator position/motion, firmware hash/profile, timing origin and ignored intervals. '
        'Distinguish reported facts from intended setup and inference.','',
        'Regenerate both this document and [the machine-readable catalog](../configs/capture-catalog.json):','',
        '```sh','.venv/bin/python -m tools.build_capture_catalog','```','',
        'Replay a newly labeled joint capture with [the joint audit](JOINT_RANGE_DOPPLER.md), '
        'and compare phase fits without changing live output:','',
        '```sh','MPLCONFIGDIR=/private/tmp/radar-mpl .venv/bin/python -m tools.evaluate_phase_range \\',
        '  --manifest configs/foil-box-repeat-20261111.json --output evidence/NEW-PHASE-REVIEW','```',''])
    (ROOT/'docs/CAPTURE_CATALOG.md').write_text('\n'.join(lines))
    print(f'Cataloged {raw} raw recordings / {len(records)} saved configurations; {len(curated)} curated setups')


if __name__=='__main__':main()
