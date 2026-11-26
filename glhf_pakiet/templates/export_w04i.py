"""Read-only export pinned to W04i: H=1 m, wavelength=15 m, any internal case ID."""
import argparse
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import zipfile

from export_custom_pair import EVIDENCE,add_file,inspect_case,read

LABEL='W04i'
C01='9af4857b948e0494088b5421f8ede100e66344fc2631cc00030406640d7cc295'
MIN_SIM_BYTES=400_000_000


def select(entries):
    candidates=[e for e in entries if not e['spec'].get('smoke')
                and e['spec'].get('wave_kind')!='bichromatic'
                and e['spec'].get('H')==1. and e['spec'].get('L')==15.]
    if not candidates:raise ValueError('No W04i save with H=1 m and wavelength=15 m was found.')
    # Inspect the newest matching attempt; never silently export an older result.
    return candidates[0]


def export_wave(base,output,selector=select,label=LABEL):
    config=read(base/'launcher.json');release=config['release']
    if release not in ('2602','2606'):raise ValueError('Unsupported STAR workspace.')
    data=(Path(config['workspace_root'])/release/'data').resolve()
    with closing(sqlite3.connect((data/'queue.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        entries=[dict(row,spec=json.loads(row['spec'])) for row in db.execute('SELECT * FROM jobs ORDER BY created DESC')]
    entry=selector(entries)
    manifest,folders,sim=inspect_case(entry,{j['id']:j for j in entries},data)
    if sim.stat().st_size<MIN_SIM_BYTES:raise ValueError('The saved SIM is missing or truncated.')
    if manifest['original_C01_sha256']!=C01 or manifest['dt_s']!=.0004:
        raise ValueError('Wave reference or time step differs from the NWAR campaign.')
    last=folders[-1]
    done=read(last/'completed.json') if (last/'completed.json').is_file() else {}
    independent=read(last/'independent_cycle_review.json') if (last/'independent_cycle_review.json').is_file() else {}
    count=done.get('complete_cycles',independent.get('cycles',{}).get('count'))
    completed=bool(entry['status']=='completed' and count is not None and count>=5 and manifest['saved_final_verified'])
    checkpoint_name=label+('_final.sim' if completed else '_saved.sim')
    manifest.update(case_id=label,display_id=label,original_case_id=entry['case_id'],release=release,
                    measured_cycles_reported=count,run_completed=completed,
                    independent_acceptance_required_on_import=True,files={})
    manifest['checkpoint']['path']='checkpoint/'+checkpoint_name
    paths={}
    for i,folder in enumerate(folders):
        for name in EVIDENCE:
            p=folder/name
            if p.is_file():paths[f'segments/{i:03}/{name}']=p
        histories=list(folder.glob('*.simh'))
        for p in histories:paths[f'segments/{i:03}/{p.name}']=p
        for p in (folder/'native_solve').glob('*.simh'):
            if not any(p.samefile(q) for q in histories):paths[f'segments/{i:03}/native_{p.name}']=p
    paths[manifest['checkpoint']['path']]=sim
    validation=data/'validations'/(entry['id']+'.json')
    if validation.is_file():paths['validation.json']=validation
    app=(data.parent/'app').resolve()
    # Exact solver-code provenance helps prepare the next compatible field-history patch.
    for name in ('NwarWave.java','compile_receipt.json'):
        p=app/name
        if p.is_file():paths['application/'+name]=p
    for member,path in paths.items():
        allowed=app if member.startswith('application/') else data
        if not path.resolve().is_relative_to(allowed):
            raise ValueError('A linked export member leaves its workspace: '+member)
    manifest['field_histories_included']=any(p.suffix.lower()=='.simh' for p in paths.values())
    if output.is_relative_to(data):raise ValueError('Choose an export folder outside solver data.')
    output.mkdir(parents=True,exist_ok=True)
    size=sum(p.stat().st_size for p in paths.values())
    if shutil.disk_usage(output).free<size+128*1024**2:raise ValueError(f'Export needs {size/2**30:.1f} GiB free.')
    now=datetime.now().astimezone()
    archive=output/f'GLHF_{label}_{"FINAL" if completed else "SAVED"}_{now:%Y%m%d_%H%M%S_%f}.zip'
    stamps={p:(p.stat().st_size,p.stat().st_mtime_ns) for p in paths.values()}
    print(f"{label} / {entry['case_id']}: H={entry['spec']['H']} m, wavelength={entry['spec']['L']} m; status={entry['status']}; cycles={count}.",flush=True)
    print(f"Force history {manifest['time_s']:.4f} s; SIM {manifest['checkpoint']['time_s']:.4f} s.",flush=True)
    with tempfile.TemporaryDirectory(prefix=label+'_export_',dir=output) as tmp:
        candidate=Path(tmp)/archive.name
        with zipfile.ZipFile(candidate,'x',allowZip64=True) as z:
            for member,path in paths.items():
                print('Packing '+member,flush=True)
                record=add_file(z,path,label+'/'+member)
                expected=manifest['checkpoint']['expected_sha256'] if member==manifest['checkpoint']['path'] else None
                if expected and record['sha256']!=expected:raise ValueError('Final SIM differs from its solver checksum.')
                manifest['files'][member]=record
            z.writestr(label+'/manifest.json',json.dumps(manifest,indent=2))
            z.writestr('manifest.json',json.dumps(dict(kind='glhf_regular_wave_export_v2',captured_at=now.isoformat(),
                cases={label:manifest},queue_changed=False,solver_started=False),indent=2))
        if any((p.stat().st_size,p.stat().st_mtime_ns)!=stamp for p,stamp in stamps.items()):
            raise ValueError('Saved evidence changed during export; no ZIP published.')
        print('Checking the ZIP...',flush=True)
        with zipfile.ZipFile(candidate) as z:
            if z.testzip() is not None:raise ValueError('ZIP verification failed.')
        candidate.rename(archive)
    print('EXPORT COMPLETE: '+str(archive),flush=True)
    return archive


def export_w04i(base,output):
    return export_wave(base,output)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('package_root',type=Path);parser.add_argument('--log',type=Path)
    args=parser.parse_args()
    if args.log:
        log=args.log.open('a',encoding='utf8',buffering=1)
        class Tee:
            def __init__(self,stream):self.stream=stream
            def write(self,value):self.stream.write(value);log.write(value)
            def flush(self):self.stream.flush();log.flush()
        sys.stdout=Tee(sys.stdout);sys.stderr=Tee(sys.stderr)
    try:
        root=args.package_root.resolve()
        export_w04i(root,(root/'GLHF_exports').resolve())
    except Exception as error:
        print('HOLD: '+str(error),flush=True)
        raise SystemExit(1)
