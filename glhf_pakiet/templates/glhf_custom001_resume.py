"""Resume the specifically reviewed GLHF CUSTOM001 surface-limit stop."""
import json
import importlib
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.request import Request, urlopen


CASE = 'CUSTOM001'
ERROR = 'Unphysical free surface at gauge x=-6.0: eta=1.0014672823102977'
INSERT = ('    if receipt.get("case_id") == "CUSTOM001":\n'
          '        from glhf_custom001_resume import verify_custom_resume\n'
          '        return verify_custom_resume(path, receipt)\n')


def approved_stop(entry):
    from common import DATA, HERE, read, sha
    p=Path(entry['folder']).resolve()
    spec=entry['spec']
    patch=read(HERE/'compile_receipt.json')
    approved=patch.get('glhf_custom001_surface_limit',{})
    stage=read(p/'stage_result.json')
    if (entry['case_id']!=CASE or entry['status']!='failed' or (spec.get('H'),spec.get('L'))!=(1.5,20.0)
            or not p.is_relative_to((DATA/'runs').resolve())
            or approved.get('run_id')!=entry['id'] or approved.get('magnitude_limit_disabled') is not True
            or patch.get('macro_sha256')!=sha(HERE/'NwarWave.java')
            or ERROR not in read(p/'macro_error.json').get('error','')
            or (p/'macro_error.txt').exists() or (p/'STOP').exists()
            or stage.get('exit_code')!=1 or stage.get('source_unchanged') is not True
            or stage.get('controller_reason') is not None):
        raise ValueError('This is not the authorized, stopped CUSTOM001 run.')
    if sha(Path(spec['source']))!=spec['source_sha']:
        raise ValueError('The original source identity differs.')
    return p


def verify_custom_resume(path, receipt):
    from common import DATA, job, read, sha
    from analysis import health, merge_segments, segment_chain
    from glhf_transfer import checkpoint_for
    entry=job(receipt['parent_id'])
    original=approved_stop(entry)
    path=Path(path).resolve()
    if (path!=(DATA/'glhf_resume'/entry['id']/'glhf_resume.json').resolve()
            or Path(receipt['original_folder']).resolve()!=original):
        raise ValueError('Unexpected CUSTOM001 recovery view.')
    checkpoint, saved=checkpoint_for(entry)
    if (abs(saved['time_s']-9.4)>1e-7 or abs(receipt['time_s']-saved['time_s'])>1e-7
            or Path(receipt['checkpoint']).resolve()!=checkpoint
            or receipt['checkpoint_sha256']!=saved['sha256']):
        raise ValueError('The saved CUSTOM001 checkpoint differs from the verified 9.4000 s save.')
    chain=[p.resolve() for p in segment_chain(entry)]
    view=[*chain[:-1],path.parent]
    if not all(p.is_relative_to(DATA.resolve()) for p in chain) or [Path(p).resolve() for p in receipt['segments']]!=view:
        raise ValueError('Unexpected CUSTOM001 history lineage.')
    raw_names=('history.csv','gauges.csv','source_identity.json','wave_setup_audit.json')
    raw={str(p/name):sha(p/name) for p in chain for name in raw_names}
    expected_prefix={'history.csv','gauges.csv','wave_setup_audit.json','source_identity.json',
                     'native_C01_rho_readback.json','wave_density_audit.json','latest_checkpoint.json'}
    if (raw!=receipt['raw_files'] or set(receipt['prefix_files'])!=expected_prefix
            or any(sha(path.parent/name)!=digest for name,digest in receipt['prefix_files'].items())):
        raise ValueError('CUSTOM001 history evidence changed.')
    data,_=merge_segments(view)
    if not health(data)['ok'] or abs(float(data['time_s'][-1])-saved['time_s'])>1e-7:
        raise ValueError('CUSTOM001 prefix failed the checkpoint health check.')
    return receipt


def install(app):
    target=app/'glhf_transfer.py'
    original=target.read_bytes()
    newline='\r\n' if b'\r\n' in original else '\n'
    text=original.decode('utf-8')
    signature='def verify_resume(path):'+newline
    hook='    receipt = read(path)'+newline
    offset=text.index(signature)
    end=text.index(hook,offset)+len(hook)
    if INSERT.replace('\n',newline) not in text:
        backup=target.with_name('glhf_transfer.before_custom001_resume.py')
        if backup.exists():
            raise ValueError('Existing GLHF recovery backup requires review.')
        shutil.copy2(target,backup)
        revised=text[:end]+INSERT.replace('\n',newline)+text[end:]
        compile(revised,str(target),'exec')
        staged=target.with_suffix('.tmp')
        staged.write_bytes(revised.encode('utf-8'))
        staged.replace(target)
    installed=app/'glhf_custom001_resume.py'
    if installed.resolve()!=Path(__file__).resolve():
        shutil.copy2(__file__,installed)


def dispatch(app):
    from common import DATA, HERE, OTHER_LOCKS, SOLVER_LOCKS, STOPS, birth, connection, enqueue, job, jobs, read, sha, write, now, datetime
    from analysis import segment_chain
    from worker import native,rt
    patch=read(HERE/'compile_receipt.json').get('glhf_custom001_surface_limit',{})
    entry=job(patch['run_id'])
    folder=approved_stop(entry)
    key='glhf_custom001_94000_resume_'+entry['id']
    previous=next((j for j in jobs() if j['request_key']==key),None)
    if previous and previous['status']!='queued':
        return f'Continuation already exists ({previous["status"]}). Check the dashboard.'
    if native() or any(j['status'] in ('queued','deferred','preflight','running','pausing') and j['id']!=(previous or {}).get('id') for j in jobs()):
        raise ValueError('Another solver or queue job is active.')
    if any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS+[DATA/'worker.lock',DATA/'STOP']):
        raise ValueError('A stop or solver reservation is still present.')
    problem=rt.resource_problem()
    if problem:
        raise ValueError(problem)
    panel=read(DATA/'server.json')
    url=panel.get('url','')
    if not panel.get('birth') or birth(panel.get('pid'))!=panel['birth'] or not re.fullmatch(r'http://127\.0\.0\.1:\d+',url):
        raise ValueError('Open the existing GLHF NWAR dashboard first.')
    with urlopen(url+'/',timeout=10) as response:
        token=re.search(r'name="nwar-token" content="([^"]+)"',response.read().decode('utf-8')).group(1)

    install(app)
    import glhf_transfer
    transfer=importlib.reload(glhf_transfer)
    sim,checkpoint=transfer.checkpoint_for(entry)
    if abs(checkpoint['time_s']-9.4)>1e-7:
        raise ValueError('Expected the healthy 9.4000 s checkpoint.')
    receipt=transfer.prepare_resume(entry,segment_chain(entry),checkpoint,sim)
    verify_custom_resume(receipt,read(receipt))
    pause=DATA/'PAUSE'
    archived=folder/'pause_before_custom001_resume'
    stamp=None
    if pause.exists():
        stamp=pause.stat()
        if (pause.read_bytes()!=b'' or archived.exists()
                or abs(stamp.st_mtime-datetime.fromisoformat(entry['updated']).timestamp())>5):
            raise ValueError('The queue pause does not match the stopped CUSTOM001 run.')
    try:
        with connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            ident=enqueue(CASE,'resume',request_key=key,conn=conn,mpi_processes=1,glhf_recovery=receipt)
            conn.execute("UPDATE jobs SET status='queued',message=? WHERE id=?",
                         ('Verified GLHF continuation from 9.4000 s.',ident))
            if stamp:
                if pause.stat().st_mtime_ns!=stamp.st_mtime_ns:
                    raise ValueError('Queue pause changed during dispatch.')
                pause.rename(archived)
    except Exception:
        if stamp and archived.exists() and not pause.exists():
            archived.rename(pause)
        raise
    write(receipt.with_name('dispatch.json'),dict(at=now(),job_id=ident,checkpoint_sha256=sha(sim),
          time_s=checkpoint['time_s'],target_measured_cycles=5))
    request=Request(url+'/api/continue',data=b'{}',headers={
        'Content-Type':'application/json','X-NWAR-Token':token,'Origin':url})
    if native() or any(p.exists() for p in STOPS+[pause,DATA/'STOP']):
        raise ValueError('A new stop or active solver appeared before dispatch.')
    with urlopen(request,timeout=20) as response:
        response.read()
    return f'CUSTOM001 queued from 9.4000 s. Job {ident}. Check for fresh samples in the dashboard.'


if __name__=='__main__':
    try:
        root=Path(sys.argv[1]).resolve()
        launcher=json.loads((root/'launcher.json').read_text(encoding='utf-8-sig'))
        release=launcher['release']
        if release not in ('2602','2606'):
            raise ValueError('Invalid GLHF STAR release.')
        work=(Path(launcher['workspace_root'])/release).resolve()
        app=work/'app'
        bundle=Path(__file__).resolve().parent
        manifest=bundle/'custom001_no_surface_cap_manifest.json'
        if manifest.is_file():
            from patch_glhf_custom001_surface import apply,read
            print(apply(root,read(manifest)),flush=True)
        os.environ.update(NWAR_PACKAGE_ROOT=str(root),NWAR_WORKSPACE=str(work),NWAR_STAR_RELEASE=release)
        sys.path[:0]=[str(app),str(root/'lib')]
        print(dispatch(app))
    except Exception as exc:
        print('HOLD: '+str(exc))
        raise SystemExit(1)
