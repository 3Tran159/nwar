"""Read-only export of saved GLHF CUSTOM001 and CUSTOM002, including fields."""
import argparse
from contextlib import closing
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import zipfile

CASES=('CUSTOM001','CUSTOM002')
ACTIVE={'queued','deferred','preflight','running','pausing'}
EVIDENCE=('history.csv','gauges.csv','wave_setup_audit.json','source_identity.json',
          'native_C01_rho_readback.json','wave_density_audit.json','stopping_policy.json',
          'latest_checkpoint.json','final_integrity.json','completed.json','stage_result.json',
          'independent_cycle_review.json','wake_history.json','wake_history_config.json',
          'native_plan.json','native_completion_review.json','seed.json')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def records(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        rows=list(reader)
        if not rows or any(None in row or None in row.values() for row in rows):
            raise ValueError('Missing or incomplete CSV: '+str(path))
        return reader.fieldnames,rows


def chain(entry,entries,data,seen=None):
    seen=set() if seen is None else seen
    if entry['id'] in seen:
        raise ValueError('Circular segment lineage.')
    seen.add(entry['id'])
    parent=entry['spec'].get('parent_id')
    if parent:
        previous=entries[parent]
        if previous['case_id']!=entry['case_id']:
            raise ValueError('Mixed cases in the continuation lineage.')
        folders=chain(previous,entries,data,seen)
    else:
        folders=[Path(p).resolve() for p in entry['spec'].get('parent_segments',[])]
    folders.append(Path(entry['folder']).resolve())
    if any(not p.is_relative_to(data) for p in folders):
        raise ValueError('A segment leaves the selected GLHF workspace.')
    return folders


def inspect_case(entry,entries,data):
    if entry['status'] in ACTIVE:
        raise ValueError(entry['case_id']+' is still active. Wait for its final save.')
    folders=chain(entry,entries,data)
    folder=folders[-1]
    checkpoint=read(folder/'latest_checkpoint.json')
    name=checkpoint.get('file','')
    if Path(name).name!=name or not name.lower().endswith('.sim') or checkpoint.get('healthy') is not True:
        raise ValueError(entry['case_id']+' has no recorded healthy checkpoint.')
    sim=(folder/name).resolve()
    if sim.parent!=folder or not sim.is_file():
        raise ValueError('Missing checkpoint for '+entry['case_id'])
    fields,rows=records(folder/'history.csv')
    end=float(rows[-1]['time_s'])
    t=float(checkpoint['time_s'])
    matched=[r for r in rows if abs(float(r['time_s'])-t)<1e-7]
    if len(matched)!=1 or int(float(matched[0]['step']))!=int(checkpoint['step']):
        raise ValueError('Checkpoint and force-history step differ for '+entry['case_id'])
    integrity=read(folder/'final_integrity.json') if (folder/'final_integrity.json').exists() else {}
    final=bool(abs(end-t)<1e-7 and integrity.get('sha256') and abs(float(integrity.get('time_s',-1))-t)<1e-7)
    if final and integrity.get('bytes') is not None and integrity['bytes']!=sim.stat().st_size:
        raise ValueError('Final SIM size differs from its integrity receipt.')
    spec=entry['spec']
    for segment in folders:
        setup=read(segment/'wave_setup_audit.json')
        if abs(float(setup['H_m'])-spec['H'])>1e-8 or abs(float(setup['lambda_m'])-spec['L'])>1e-8:
            raise ValueError('Wave dimensions differ between saved segments.')
        records(segment/'history.csv')
        records(segment/'gauges.csv')
    done=read(folder/'completed.json') if (folder/'completed.json').exists() else {}
    return dict(case_id=entry['case_id'],job_id=entry['id'],job_status=entry['status'],
                H_m=spec['H'],lambda_m=spec['L'],dt_s=spec['dt'],time_s=end,
                checkpoint=dict(path='checkpoint/'+entry['case_id']+'_final.sim',time_s=t,
                                step=checkpoint['step'],final_step_matches_history=abs(end-t)<1e-7,
                                expected_sha256=integrity.get('sha256') if final else None),
                saved_final_verified=final,completed_state=done.get('status'),
                original_C01_sha256=spec.get('mesh_profile',{}).get('original_C01_sha256'),
                acceptance_copied_as_evidence_only=True,segments=[f'segments/{i:03}' for i in range(len(folders))]),folders,sim


def add_file(bundle,path,member):
    before=path.stat()
    record=zipfile.ZipInfo(member)
    record.compress_type=zipfile.ZIP_STORED if path.suffix.lower() in ('.sim','.simh') else zipfile.ZIP_DEFLATED
    digest=hashlib.sha256()
    size=0
    with path.open('rb') as stream,bundle.open(record,'w',force_zip64=True) as target:
        for block in iter(lambda:stream.read(4*1024**2),b''):
            target.write(block);digest.update(block);size+=len(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or size!=before.st_size:
        raise ValueError('File changed while exporting: '+path.name)
    return dict(bytes=size,sha256=digest.hexdigest())


def export_pair(base,output):
    config=read(base/'launcher.json')
    release=config['release']
    if release not in ('2602','2606'):
        raise ValueError('Unsupported STAR workspace.')
    data=(Path(config['workspace_root'])/release/'data').resolve()
    with closing(sqlite3.connect((data/'queue.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        entries=[dict(r,spec=json.loads(r['spec'])) for r in db.execute('SELECT * FROM jobs ORDER BY created DESC')]
    by_id={r['id']:r for r in entries}
    manifests={};paths={};expected={}
    for case in CASES:
        entry=next((j for j in entries if j['case_id']==case and not j['spec'].get('smoke')
                    and (Path(j['folder'])/'history.csv').is_file()),None)
        if entry is None:
            raise ValueError('No saved history for '+case)
        manifest,folders,sim=inspect_case(entry,by_id,data)
        manifest.update(release=release,files={})
        manifests[case]=manifest
        for i,folder in enumerate(folders):
            members=[folder/name for name in EVIDENCE if (folder/name).is_file()]
            members.extend(folder.glob('*.simh'))
            for p in members:
                if p.resolve().parent!=folder:
                    raise ValueError('Linked evidence outside its segment.')
                member=f'{case}/segments/{i:03}/{p.name}'
                paths[member]=p
        validation=data/'validations'/(entry['id']+'.json')
        if validation.is_file():paths[case+'/validation.json']=validation
        final_member=case+'/'+manifest['checkpoint']['path']
        paths[final_member]=sim
        expected[final_member]=manifest['checkpoint']['expected_sha256']
        print(f"{case}: H={manifest['H_m']}, wavelength={manifest['lambda_m']} m; "
              f"history {manifest['time_s']:.4f} s; SIM {manifest['checkpoint']['time_s']:.4f} s.",flush=True)
    if output.is_relative_to(data):
        raise ValueError('Export folder must be outside solver data.')
    output.mkdir(parents=True,exist_ok=True)
    size=sum(p.stat().st_size for p in paths.values())
    if shutil.disk_usage(output).free<size+128*1024**2:
        raise ValueError(f'Export needs at least {size/2**30:.1f} GiB free.')
    captured=datetime.now().astimezone()
    archive=output/f'GLHF_CUSTOM001_CUSTOM002_{captured:%Y%m%d_%H%M%S_%f}.zip'
    stamps={p:(p.stat().st_size,p.stat().st_mtime_ns) for p in paths.values()}
    with tempfile.TemporaryDirectory(prefix='custom_export_',dir=output) as temp:
        staged=Path(temp)/archive.name
        with zipfile.ZipFile(staged,'x',allowZip64=True) as bundle:
            for member,path in paths.items():
                print('Packing '+member,flush=True)
                record=add_file(bundle,path,member)
                if expected.get(member) and record['sha256']!=expected[member]:
                    raise ValueError('Final SIM checksum differs from solver receipt.')
                case,relative=member.split('/',1)
                manifests[case]['files'][relative]=record
            for case,manifest in manifests.items():
                bundle.writestr(case+'/manifest.json',json.dumps(manifest,indent=2))
            bundle.writestr('manifest.json',json.dumps(dict(kind='glhf_custom_pair_v1',
                captured_at=captured.isoformat(),cases=manifests,solver_started=False,queue_changed=False),indent=2))
        if any((p.stat().st_size,p.stat().st_mtime_ns)!=stamp for p,stamp in stamps.items()):
            raise ValueError('Saved evidence changed during export. No final ZIP published.')
        print('Checking the ZIP...',flush=True)
        with zipfile.ZipFile(staged) as bundle:
            if bundle.testzip() is not None:raise ValueError('ZIP verification failed.')
        staged.rename(archive)
    print('EXPORT COMPLETE: '+str(archive),flush=True)
    return archive


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package_root',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--log',type=Path)
    args=parser.parse_args()
    if args.log:
        log=args.log.open('a',encoding='utf8',buffering=1)
        class Tee:
            def __init__(self,stream):self.stream=stream
            def write(self,value):self.stream.write(value);log.write(value)
            def flush(self):self.stream.flush();log.flush()
        sys.stdout=Tee(sys.stdout)
        sys.stderr=Tee(sys.stderr)
    try:
        base=args.package_root.resolve()
        export_pair(base,(args.output or base/'GLHF_exports').resolve())
    except Exception as error:
        print('HOLD: '+str(error),flush=True)
        raise SystemExit(1)
