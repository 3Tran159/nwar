"""Pinned W04f native continuation, dispatched only after accepted W04h."""
import csv
import json
import os
import shutil
import subprocess
import time
import uuid

from common import *
from cycle_policy import POLICY_ID,accepted_cycles

DEPENDENCY='ccf935c0343b46aa'
KEY='user_20261108_after_W04h_resume_W04f_GLHF_13p9148_five_cycles'
QA=DATA/'qa/W04f_after_W04h_20261108'
IMPORT=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_SIM_FINALS/W04f')


def verify(spec):
    from glhf_saved_review import sim_state
    proof=spec['imported_native_continuation']
    if spec.get('id')!='W04f' or spec.get('mode')!='resume' or (spec['H'],spec['L'])!=(1.5,30.):
        raise ValueError('Unexpected imported native continuation.')
    folder=Path(proof['folder']).resolve()
    if folder!=IMPORT.resolve() or sha(folder/'manifest.json')!=proof['manifest_sha256']:
        raise ValueError('Imported W04f manifest changed.')
    m=read(folder/'manifest.json');review=read(folder/'saved_result_review.json')
    source=folder/'checkpoint/latest.sim'
    if (Path(spec['source']).resolve()!=source.resolve() or spec['source_sha']!=m['checkpoint']['expected_sha256']
            or sha(source)!=spec['source_sha'] or abs(spec['source_time']-m['time_s'])>1e-7
            or review.get('manifest_sha256')!=proof['manifest_sha256']
            or read(folder/'independent_import_review.json').get('health',{}).get('ok') is not True
            or m.get('original_C01_sha256')!=SOURCE_SHA or m.get('release')!='2606'
            or spec['parent_segments']!=[str(folder/p) for p in m['segments']]):
        raise ValueError('Imported W04f checkpoint or preserved history differs.')
    for name,record in m['files'].items():
        if name.startswith('segments/') and sha(folder/name)!=record['sha256']:
            raise ValueError('Imported W04f raw evidence changed: '+name)
    native=sim_state(source)
    if abs(native['time_s']-spec['source_time'])>1e-7 or native['scene_count']!=30 or native['mpi']!='Np=1':
        raise ValueError('Imported native save no longer matches its exact time or scenes.')
    receipt=Path(proof['compile_receipt'])
    if sha(receipt)!=proof['compile_receipt_sha256'] or sha(Path(proof['macro']))!=read(receipt)['macro_sha256']:
        raise ValueError('Imported-continuation macro differs from its compiled receipt.')
    if not all(v.get('passed') is True for v in read(receipt)['builds']):
        raise ValueError('Missing compiled 2606 continuation macro.')
    return dict(folder=str(folder),sha256=spec['source_sha'],health_ok=True,time_s=native['time_s'])


def add_boundary_sample(folder,spec):
    """Retain the existing checkpoint sample; never interpolate a missing time step."""
    last=tail(Path(spec['parent_segments'][-1])/'history.csv')[-1]
    path=folder/'history.csv'
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
    start=spec['source_time'];dt=spec['dt']
    if abs(float(last['time_s'])-start)>1e-7 or abs(float(rows[0]['time_s'])-start-dt)>1e-7:
        raise ValueError('Native continuation boundary differs from the saved CSV endpoint.')
    boundary={key:last[key] for key in fields}
    boundary.update(time_s=start,step=0)
    staged=path.with_suffix('.boundary.tmp')
    with staged.open('w',encoding='utf8',newline='') as output:
        writer=csv.DictWriter(output,fields);writer.writeheader();writer.writerow(boundary);writer.writerows(rows)
    staged.replace(path)


def prepare():
    from wave_profiles import approved_profile
    from glhf_saved_review import sim_state
    with connection() as c:
        existing=c.execute('SELECT id FROM jobs WHERE request_key=?',(KEY,)).fetchone()
    if existing:
        verify(job(existing['id'])['spec'])
        return existing['id']
    QA.mkdir(parents=True,exist_ok=True)
    macro=QA/'NwarWaveF.java'
    source=(HERE/'NwarWave.java').read_text(encoding='utf8')
    source=source.replace('public class NwarWave extends StarMacro','public class NwarWaveF extends StarMacro')
    old='if(resume||!expanded||!(caseId.equals("W04c")||caseId.equals("W04e")||caseId.equals("W04g")||caseId.equals("W04h")))'
    if source.count(old)!=1:raise ValueError('Native setup guard changed; review before compiling.')
    source=source.replace(old,'if(!resume||!expanded||!caseId.equals("W04f")||Math.abs(beginTime-13.914800000011667)>1e-7)')
    old='(caseId.equals("W04h")&&H==.75&&lambda==15)||'
    if source.count(old)!=1:raise ValueError('Reviewed wave envelope changed.')
    source=source.replace(old,old+'(caseId.equals("W04f")&&H==1.5&&lambda==30)||')
    macro.write_text(source,encoding='utf8')
    compiler='C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe'
    build='21.04.009'
    cp=f'E:/Program Files/Siemens/{build}-R8/STAR-CCM+{build}-R8/star/lib/java/platform/modules/ext/*'
    classes=QA/'compiled_2606';classes.mkdir(exist_ok=True)
    proc=subprocess.run([compiler,'-cp',cp,'-d',str(classes),str(macro),str(HERE/'NwarNativeExport.java')],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    receipt=QA/'compile.json'
    write(receipt,dict(macro_sha256=sha(macro),builds=[dict(release='2606',passed=proc.returncode==0,messages=proc.stderr)],preserves_saved_wave_phase=True))
    if proc.returncode:raise ValueError('W04f macro compilation failed: '+proc.stderr[-1000:])
    m=read(IMPORT/'manifest.json');native=sim_state(IMPORT/'checkpoint/latest.sim')
    profile=approved_profile('W04f',verify=True)
    if profile is None:raise ValueError('Accepted PRE profile is unavailable.')
    spec=dict(id='W04f',title='H=1.5 m / wavelength=30 m · continuation of imported GLHF save',
        H=1.5,L=30.,T=period(30.),dt=.0004,ready=True,scientific='diagnostic',mode='resume',
        stop_kind='five_cycles',extra_cycles=1,smoke=0,extra_steps=0,
        source=str(IMPORT/'checkpoint/latest.sim'),source_sha=m['checkpoint']['expected_sha256'],source_time=native['time_s'],
        parent_id=None,parent_segments=[str(IMPORT/p) for p in m['segments']],
        budget_s=129600,mpi_processes=1,mesh_profile=profile,campaign_id='user_20261108_H_then_F',
        native_production=True,native_mpi='intel',allow_approved_cpu=True,resource_scope='owned_gpu_cpu11',
        overnight_queue='nwar-native-20261108-W04f',overnight_order=1,
        cycle_policy_id=POLICY_ID,target_complete_cycles=5,discard_first_cycles=1,analysis_cycle_numbers=[2,3,4,5],
        wait_for_accepted_job=DEPENDENCY,
        imported_native_continuation=dict(folder=str(IMPORT),manifest_sha256=sha(IMPORT/'manifest.json'),
            macro=str(macro),compile_receipt=str(receipt),compile_receipt_sha256=sha(receipt)))
    verify(spec)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        previous=c.execute('SELECT id FROM jobs WHERE request_key=?',(KEY,)).fetchone()
        if previous:return previous['id']
        if c.execute("SELECT 1 FROM jobs WHERE case_id='W04f' AND status IN ('queued','deferred','running','preflight','pausing')").fetchone():
            raise ValueError('W04f is already queued or running.')
        ident=uuid.uuid4().hex[:16];folder=RUNS/('W04f_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+ident[:6])
        c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)',(ident,now(),now(),'deferred','W04f',json.dumps(spec),str(folder),
            'Waiting for accepted W04h; then resume imported W04f at 13.9148 s on STAR 2606.',None,None,KEY))
    write(QA/'queued.json',dict(at=now(),job_id=ident,after_job=DEPENDENCY,source_time_s=native['time_s'],target_measured_cycles=5))
    return ident


def supervise(ident):
    from worker import OWNER,queue_wait_reason
    deadline=time.monotonic()+48*3600
    while time.monotonic()<deadline:
        current=job(ident)
        if current['status'] not in ('deferred','queued'):return
        if any(p.exists() for p in STOPS+[DATA/'PAUSE',DATA/'STOP']):
            update(ident,message='W04f waiting: manual pause or STOP preserved.');return
        previous=job(DEPENDENCY)
        if previous['status'] in ('failed','interrupted','needs_attention','needs_review','cancelled','paused'):
            update(ident,message='W04f held: W04h has not passed acceptance.');return
        validation=read(DATA/'validations'/(DEPENDENCY+'.json'))
        review=read(Path(previous['folder'])/'independent_cycle_review.json')
        owner=read(OWNER)
        if (previous['status']=='completed' and validation.get('project_accepted') is True
                and validation.get('run_verification')=='passed' and review.get('health',{}).get('ok') is True
                and accepted_cycles(review.get('cycles',{}))
                and read(Path(previous['folder'])/'stage_result.json').get('ownership')=='windows_job_closed'
                and not (owner.get('birth') and owner['birth']==birth(owner.get('pid')))):
            problem=queue_wait_reason(current['spec'])
            if problem:
                update(ident,message='W04f waiting: '+problem);time.sleep(20);continue
            verify(current['spec'])
            update(ident,status='queued',message='W04h accepted; resuming W04f from imported 13.9148 s save.')
            with (DATA/'W04f_worker.log').open('a',encoding='utf8') as log:
                p=subprocess.Popen([str(PYTHON),str(HERE/'worker.py'),'--only',ident],cwd=HERE,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            write(QA/'dispatch.json',dict(at=now(),job_id=ident,worker_pid=p.pid,worker_birth=birth(p.pid)))
            return
        time.sleep(20)
    update(ident,message='W04f held: dependency wait limit reached; saved state preserved.')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--supervise');args=p.parse_args()
    if args.supervise:supervise(args.supervise)
    else:print(prepare(),flush=True)
