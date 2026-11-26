"""Verify GLHF custom-wave evidence and publish canonical W04 names on backup."""
import hashlib
import math
import os
import shutil
import uuid
import zipfile

from common import HERE, SOURCE, SOURCE_SHA, Path, now, period, read, sha, write
from glhf_bundle import PRE, path_under

REGISTRY=HERE/'glhf_custom_imports.json'
REPO=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_SIM_FINALS')
ALIASES={(1.5,20.):'W04c',(1.5,30.):'W04f',(1.,15.):'W04i',(.5,15.):'W04j'}


def register_catalog(paths):
    """Expose imported amplitude cases as saved cards without creating local jobs."""
    target=HERE/'short_wave_scan.json';scan=read(target);cases=scan.get('cases',[])
    for folder in paths:
        m=read(folder/'manifest.json');label=m['case_id']
        if label not in ('W04i','W04j'):continue
        receipt=read(folder/'saved_result_review.json');accepted=receipt['project_accepted']
        item=next((c for c in cases if c.get('queue_label')==label),None)
        if item is None:item={};cases.append(item)
        item.update(order={'W04i':9,'W04j':10}[label],wavelength_m=m['lambda_m'],height_m=m['H_m'],
            steepness=m['H_m']/m['lambda_m'],nominal_linear_encounter_period_s=period(m['lambda_m']),
            status='completed_external' if accepted else 'saved_external',case_id=None,queue_label=label,
            title='Amplitude series at wavelength 15 m',launch_authorized=False,local_queue_excluded=True,
            external_case_id=m['original_case_id'],external_job_id=m['job_id'],queue_status='completed' if accepted else 'saved',
            reason=(f"Accepted GLHF result at {receipt['time_s']:.4f} s; five measured cycles and cycles 2-5 independently verified."
                    if accepted else 'Saved GLHF diagnostic; independent acceptance is pending.'))
    scan['cases']=sorted(cases,key=lambda c:c.get('order',0));scan['queue_entries']=len(cases)
    write(target,scan)


def review(folder):
    from analysis import analyze, numeric_rows
    from cycle_policy import accepted_cycles
    from glhf_saved_review import sim_state
    from project_results import policy
    import numpy as np
    manifest=read(folder/'manifest.json')
    label=manifest['case_id']
    case=dict(id=label,H=manifest['H_m'],L=manifest['lambda_m'])
    segments=[path_under(folder,p) for p in manifest['segments']]
    result,data,_=analyze(case,segments)
    checkpoint=path_under(folder,manifest['checkpoint']['path'])
    native=sim_state(checkpoint)
    setup=read(segments[-1]/'wave_setup_audit.json')
    start=setup['begin_time_s']
    end=result['time_s']
    dt=manifest['dt_s']
    ck=manifest['checkpoint']
    if (abs(native['time_s']-end)>1e-7 or abs(end-ck['time_s'])>1e-7
            or native['step']-round(start/dt)!=ck['step']
            or not np.allclose(np.diff(data['time_s']),dt,rtol=0,atol=1e-7)
            or native['scene_count']!=30 or not native['release'].startswith('21.04.')
            or native['mpi']!='Np=1' or dt not in native['time_steps']
            or len(native['wave_numbers'])!=1 or abs(native['wave_numbers'][0]-math.tau/case['L'])>1e-8):
        raise ValueError('Saved native state, scene inventory or complete CSV time grid differs: '+label)
    for index,segment in enumerate(segments):
        audit=read(segment/'wave_setup_audit.json')
        if (audit.get('H_m')!=case['H'] or audit.get('lambda_m')!=case['L']
                or audit.get('global_initialization') is not False or audit.get('scene_count')!=30):
            raise ValueError('Wave setup differs between continuation segments: '+label)
        if index==0 and read(segment/'source_identity.json').get('sha256')!=PRE:
            raise ValueError('Initial segment does not identify the pinned PRE checkpoint.')
    for coefficient,force,offset in [('CD_total','Fx_N',0),('CL_hydrodynamic','Fz_N',22.718189111947265)]:
        if np.max(np.abs(data[coefficient]-(data[force]-offset)/3855.6))>=1e-10:
            raise ValueError('Imported force normalization differs from C01.')
    if 'target_H_m' in data:
        settled=data['time_s']>=result['wave_origin_s']+2*period(case['L'])+dt
        heights=data['target_H_m']
        if np.any(heights<0) or np.any(heights>case['H']+1e-8) or not np.any(settled) or np.max(np.abs(heights[settled]-case['H']))>1e-8:
            raise ValueError('The recorded target wave height after the startup ramp differs.')
    stage=read(segments[-1]/'stage_result.json')
    clean=stage.get('exit_code')==0 and stage.get('source_unchanged') is True
    cy=result['cycles']
    numerical_ok=result['health']['ok']
    eligible=accepted_cycles(cy)
    accepted=bool(clean and numerical_ok and eligible and manifest['saved_final_verified'])
    def check(key,title,passed,values,pending=False):
        return dict(id=key,title=title,criterion=title,group='run',status='passed' if passed else 'pending' if pending else 'failed',values=values,
                    evidence_files=[str(folder/'manifest.json'),str(checkpoint)])
    checks=[check('checkpoint','Native SIM matches the final force-history step',True,native),
            check('reference','Pinned original C01 and PRE lineage',sha(SOURCE)==SOURCE_SHA,dict(C01_sha256=SOURCE_SHA,PRE_sha256=PRE)),
            check('solver_exit','Clean saved solver exit',clean,stage),
            check('health','Independent joined-history numerical health',numerical_ok,result['health']),
            check('cycles','Five measured cycles; discard cycle 1 and analyze cycles 2–5',cy['count']>=5,
                  {k:cy.get(k) for k in ('count','analyzed_cycle_numbers','discarded_cycle_numbers','cycle_policy_id')},pending=True),
            check('repeatability','Repeatability of measured cycles 2–5',eligible,cy.get('metrics',{}),pending=cy['count']<5)]
    verification='passed' if accepted else 'failed' if any(c['status']=='failed' for c in checks) else 'pending'
    receipt=dict(id='GLHF_'+label+'_'+manifest['job_id'],case_id=label,generated_at=now(),project_accepted=accepted,
        run_verification=verification,verification_kind='glhf_saved_state',policy_id=policy()['id'],
        scope='Independent review of imported GLHF native save and cycles 2–5',
        manifest_sha256=sha(folder/'manifest.json'),checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),
        checkpoint_bytes=checkpoint.stat().st_size,checkpoint_mtime_ns=checkpoint.stat().st_mtime_ns,
        time_s=end,measured_cycles=cy['count'],checks=checks,counts={k:sum(c['status']==k for c in checks) for k in ('passed','failed','pending','future')})
    write(folder/'independent_import_review.json',result)
    write(folder/'saved_result_review.json',receipt)
    return receipt,result


def import_pair(archive):
    import json
    registry=read(REGISTRY,dict(bundles=[]))
    paths=[]
    with zipfile.ZipFile(archive) as bundle:
        original=bundle.read('manifest.json')
        collection=json.loads(original)
        if collection.get('kind')!='glhf_custom_pair_v1' or set(collection['cases'])not in({'CUSTOM001','CUSTOM002'},{'CUSTOM003','CUSTOM004'}):
            raise ValueError('Expected the GLHF CUSTOM001/CUSTOM002 or CUSTOM003/CUSTOM004 export.')
        if len(bundle.namelist())!=len(set(bundle.namelist())):
            raise ValueError('Duplicate archive member.')
        for custom,raw in collection['cases'].items():
            label=ALIASES.get((raw.get('H_m'),raw.get('lambda_m')))
            if (label!={'CUSTOM001':'W04c','CUSTOM002':'W04f','CUSTOM003':'W04i','CUSTOM004':'W04j'}.get(custom)
                    or raw.get('case_id')!=custom or raw.get('dt_s')!=.0004
                    or raw.get('original_C01_sha256')!=SOURCE_SHA or raw.get('release')!='2606'):
                raise ValueError('Unknown imported wave parameters or reference.')
            target=REPO/label
            source_manifest_sha=hashlib.sha256(bundle.read(custom+'/manifest.json')).hexdigest()
            if target.exists():
                if read(target/'manifest.json').get('source_export_manifest_sha256')!=source_manifest_sha:
                    raise ValueError('Existing backup result preserved: '+str(target))
            else:
                staging=REPO/(label+'.partial-'+uuid.uuid4().hex[:8]);staging.mkdir()
                try:
                    normalized=dict(raw,case_id=label,display_id=label,original_case_id=custom,
                        exported_at=collection['captured_at'],source_export_manifest_sha256=source_manifest_sha,
                        archive_source_name=Path(archive).name)
                    normalized['files']={}
                    expected_segments=[f'segments/{i:03}' for i in range(len(raw['segments']))]
                    if raw['segments']!=expected_segments:raise ValueError('Unexpected segment order.')
                    for member,record in raw['files'].items():
                        if (member!=raw['checkpoint']['path'] and member!='validation.json'
                                and str(Path(member).parent).replace('\\','/') not in expected_segments):
                            raise ValueError('Unexpected transfer member.')
                        relative='checkpoint/latest.sim' if member==raw['checkpoint']['path'] else member
                        dest=path_under(staging,relative);dest.parent.mkdir(parents=True,exist_ok=True)
                        digest=hashlib.sha256();size=0
                        with bundle.open(custom+'/'+member) as source,dest.open('xb') as output:
                            for block in iter(lambda:source.read(4*1024**2),b''):
                                output.write(block);digest.update(block);size+=len(block)
                        if record!=dict(bytes=size,sha256=digest.hexdigest()):
                            raise ValueError('Export checksum mismatch: '+custom+'/'+member)
                        normalized['files'][relative]=record
                    normalized['checkpoint']=dict(raw['checkpoint'],path='checkpoint/latest.sim')
                    if normalized['files']['checkpoint/latest.sim']['sha256']!=raw['checkpoint']['expected_sha256']:
                        raise ValueError('Checkpoint integrity receipt differs from the SIM hash.')
                    write(staging/'manifest.json',normalized)
                    (staging/'original_export_manifest.json').write_bytes(original)
                    staging.rename(target)
                except Exception:
                    # Preserve partial evidence for diagnosis; never publish it in the dashboard.
                    raise
            receipt,result=review(target)
            sim=path_under(target,'checkpoint/latest.sim')
            name=label+'_final.sim' if receipt['project_accepted'] else label+f"_saved_t{receipt['time_s']:.4f}.sim"
            for link in (target/name,REPO/name):
                if link.exists():
                    if sha(link)!=receipt['checkpoint_sha256']:raise ValueError('Conflicting SIM shortcut preserved.')
                else:os.link(sim,link)
            record=dict(folder=str(target),manifest_sha256=sha(target/'manifest.json'),case_id=label)
            registry['bundles']=[r for r in registry['bundles'] if r['case_id']!=label]+[record]
            paths.append(target)
            print(f"{custom} -> {label}: {result['time_s']:.4f} s; {result['cycles']['count']} measured cycles; accepted={receipt['project_accepted']}",flush=True)
    register_catalog(paths)
    registry['updated_at']=now();write(REGISTRY,registry)
    return paths


def imported_entries():
    entries=[]
    for record in read(REGISTRY).get('bundles',[]):
        folder=Path(record['folder'])
        try:
            if not folder.resolve().is_relative_to(REPO.resolve()) or sha(folder/'manifest.json')!=record['manifest_sha256']:
                continue
            m=read(folder/'manifest.json');validation=read(folder/'saved_result_review.json')
            if validation.get('manifest_sha256')!=record['manifest_sha256']:continue
            checkpoint=Path(validation['checkpoint']);stat=checkpoint.stat()
            if (stat.st_size,stat.st_mtime_ns)!=(validation['checkpoint_bytes'],validation['checkpoint_mtime_ns']):continue
            segments=[str(path_under(folder,p)) for p in m['segments']]
            result=read(folder/'independent_import_review.json')
            entries.append(dict(id=validation['id'],case_id=m['case_id'],imported=True,external=True,
                status='completed' if validation['project_accepted'] else 'saved',validation=validation,
                reviewed_partial=bool(not validation['project_accepted'] and result['health']['ok']),
                folder=segments[-1],updated=m['exported_at'],reference_id='C01_original',
                spec=dict(parent_segments=segments[:-1]),
                message=('Accepted imported GLHF result' if validation['project_accepted'] else
                         'Saved GLHF history; five measured cycles are not yet accepted'),
                import_checkpoint_time_s=validation['time_s'],import_recorded_cycles=result['cycles']['count']))
        except (OSError,ValueError,KeyError,TypeError):continue
    return entries


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);args=p.parse_args()
    import_pair(args.archive.resolve())
