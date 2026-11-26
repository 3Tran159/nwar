"""One idempotent night-campaign step. Read-only unless --apply is supplied."""
from common import *
from pre_w04 import PRE,calm_folders,calm_values,endpoint_convergence
from cpu_coexistence import check as resources
import argparse,subprocess

POLICY=HERE/'night_campaign.json'

def decision(at,fallback,status,endpoint):
    if status not in ('calm_gate_passed','stable_reference_mismatch','wall_budget'):
        return 'review'
    if status=='calm_gate_passed' and endpoint.get('wave_allowed') is True:
        return 'original'
    if at>=fallback and status=='stable_reference_mismatch' and endpoint.get('consecutive_stable',0)>=2 and endpoint.get('stable') is True:
        return 'prepared'
    return 'continue' if status=='wall_budget' else 'review'

def markers(folder=None,include_pause=True):
    paths=STOPS+[PRE/'STOP',DATA/'STOP']+([DATA/'PAUSE'] if include_pause else [])
    if folder:paths += [Path(folder)/'STOP']
    return [str(p) for p in paths if p.exists()]

def saved_pre():
    folders=calm_folders();folder=folders[-1]
    state=read(PRE/'state.json');process=read(folder/'process.json')
    if (state.get('birth') and birth(state.get('pid'))==state['birth']) or birth(process.get('pid')):
        raise ValueError('PRE controller or solver still active')
    if markers(folder):raise ValueError('Pause/STOP preserved')
    if any(p.exists() for p in SOLVER_LOCKS+OTHER_LOCKS):raise ValueError('Resource reservation still present')
    resources()
    done=read(folder/'completed.json');stage=read(folder/'stage_result.json');receipt=read(PRE/'calm_receipt.json')
    if done.get('status') not in ('wall_budget','calm_gate_passed','stable_reference_mismatch'):
        raise ValueError('PRE stopped on an error, guard or manual request')
    if stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True or read(folder/'macro_error.json'):
        raise ValueError('PRE did not exit cleanly')
    ck=read(folder/'latest_checkpoint.json');path=folder/'final.sim';history=tail(folder/'history.csv')
    if not history or Path(ck.get('path','')).resolve()!=path.resolve() or abs(ck.get('time_s',-1)-done['time_s'])>1e-7 or abs(float(history[-1]['time_s'])-done['time_s'])>1e-7:
        raise ValueError('Checkpoint endpoint differs from history')
    if sha(path)!=receipt.get('checkpoint_sha256') or sha(SOURCE)!=SOURCE_SHA:
        raise ValueError('Checkpoint or original C01 hash mismatch')
    origin=read(folder/'source_identity.json')
    if not origin.get('path') or sha(Path(origin['path']))!=origin.get('sha256'):
        raise ValueError('PRE source changed')
    removed=read(folder/'global_ramp_completed.json');scenes=read(folder/'scene_retention.json')
    if removed.get('momentum_source_option')!='NONE' or removed.get('extra_force_active') is not False:
        raise ValueError('Startup momentum forcing remains active')
    if scenes.get('preserved') is not True or scenes.get('scene_count',0)<30:
        raise ValueError('Scene retention is unverified')
    from pre_balance import balance_seed,water_readiness
    balance=balance_seed(folders);water=water_readiness(folders,balance)
    if abs(balance['water_closure_error_m3'])>=.25 or not water['ready']:
        raise ValueError('Water readiness or mass balance requires review')
    checks=endpoint_convergence(calm_values())
    return folder,done,receipt,checks[-1] if checks else {}

def launch_pre(policy):
    # Re-check immediately before the controller reserves the solver.
    folder,done,receipt,last=saved_pre()
    log=HERE/'qa/night_pre_controller.log'
    command=[str(PYTHON),'-X','utf8',str(HERE/'run_pre_w04_global_ramp.py'),'--resume','--observe-minutes','90','--allow-approved-cpu','--night-until',policy['fallback_at']]
    with log.open('a',encoding='utf8') as stream:
        p=subprocess.Popen(command,cwd=HERE,stdout=stream,stderr=stream,creationflags=subprocess.CREATE_NO_WINDOW)
    launch=dict(at=now(),pid=p.pid,birth=birth(p.pid),log=str(log),source_checkpoint=str(folder/'final.sim'),source_sha256=receipt['checkpoint_sha256'],source_time_s=done['time_s'])
    policy.update(phase='pre_running',launch=launch);write(POLICY,policy)
    return dict(status='pre_loading',**launch)

def release_waves(policy,branch):
    folder,done,receipt,last=saved_pre()
    if decision(datetime.now().astimezone(),datetime.fromisoformat(policy['fallback_at']),done['status'],last)!=branch:
        raise ValueError('The saved PRE no longer satisfies the selected branch')
    if branch=='original':
        if receipt.get('passed') is not True or not all(receipt.get('gates',{}).values()):
            raise ValueError('Original C01 compatibility receipt missing')
        reference_id='C01_original'
    else:
        from calm_reference import accept_prepared_reference,REFERENCE_ID
        receipt=accept_prepared_reference()
        if receipt.get('passed') is not True:raise ValueError('New C01 acceptance is incomplete')
        reference_id=REFERENCE_ID
    archive=HERE/'campaign_archives'/policy['id']
    if not (archive/'manifest.json').exists():
        write(archive/'manifest.json',dict(at=now(),original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA,
          previous_campaign=read(HERE/'campaign_followup.json'),previous_report=read(HERE/'latest_report.json'),
          historical_jobs=jobs(),historical_runs={k:str(v) for k,v in EXISTING.items()},raw_files_preserved=True))
    plan=dict(id=policy['id']+'_'+branch,enabled=True,reference_mode='prepared_calm' if branch=='prepared' else 'original',
              reference_id=reference_id,sequence=policy['prepared_sequence' if branch=='prepared' else 'original_sequence'],
              stop_kind='five_cycles',scope_jobs_to_campaign=True,allow_approved_cpu=True,
              authority=policy['authority'],accepted_pre=str(folder/'final.sim'),accepted_pre_sha256=receipt['checkpoint_sha256'],
              preserve_checkpoints_scenes_and_history=True,archive=str(archive/'manifest.json'))
    write(HERE/'campaign_followup.json',plan)
    policy.update(phase='waves',branch=branch,reference_id=reference_id,decision_at=now(),waves_not_yet_released=False)
    write(POLICY,policy)
    from server import enable_report_updates
    enable_report_updates()
    from report import build_report
    build_report()
    from advance_wave_queue import step
    return dict(status='waves_released',branch=branch,reference_id=reference_id,next=step(True))

def resume_budget_wave(policy,apply):
    """Only an identified automatic wall-budget pause is removable."""
    plan=read(HERE/'campaign_followup.json')
    candidates=[j for j in jobs() if j['spec'].get('campaign_id')==plan.get('id') and not j['spec'].get('smoke')]
    if not candidates:return None
    j=max(candidates,key=lambda j:j['created']);folder=Path(j['folder'])
    if j['status']!='needs_review' or read(folder/'completed.json').get('status')!='wall_budget':return None
    owner=read(DATA/'worker.lock')
    if owner.get('birth') and birth(owner.get('pid'))==owner['birth']:return dict(status='waiting_worker')
    if markers(folder,include_pause=False):return dict(status='blocked',reason='Manual STOP preserved')
    proof=read(folder/'automatic_pause.json');marker=DATA/'PAUSE'
    if not marker.exists() or proof.get('reason')!='wall_budget' or proof.get('job_id')!=j['id'] or proof.get('marker')!=str(marker) or marker.stat().st_mtime_ns!=proof.get('mtime_ns') or sha(marker)!=proof.get('sha256'):
        return dict(status='blocked',reason='Pause is not the unchanged automatic wall-budget marker')
    if birth(j.get('controller_pid')) or birth(read(folder/'process.json').get('pid')):
        return dict(status='waiting_worker')
    # CPU classification and single GPU checks, without rt.resource_problem's PAUSE check.
    resources(launch=False)
    if any(p.exists() for p in SOLVER_LOCKS+OTHER_LOCKS):return dict(status='waiting_resources')
    stage=read(folder/'stage_result.json');done=read(folder/'completed.json');ck=read(folder/'latest_checkpoint.json');integrity=read(folder/'final_integrity.json')
    if stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True or read(folder/'macro_error.json') or ck.get('healthy') is not True:
        raise ValueError('Unhealthy wall-budget checkpoint')
    path=folder/ck['file']
    if path.resolve()!=(folder/'wave_pilot_final.sim').resolve() or sha(path)!=integrity.get('sha256') or abs(ck['time_s']-done['time_s'])>1e-7 or abs(float(tail(folder/'history.csv')[-1]['time_s'])-done['time_s'])>1e-7:
        raise ValueError('Wall-budget checkpoint/history identity mismatch')
    if sha(Path(j['spec']['source']))!=j['spec']['source_sha']:raise ValueError('Wave source changed')
    from analysis import analyze,segment_chain
    result,_,_=analyze(dict(j['spec'],id=j['case_id']),segment_chain(j))
    if not result['health']['ok']:raise ValueError('Wave health failed')
    if not apply:return dict(status='ready_to_resume',job_id=j['id'])
    # Revalidate ownership immediately before removing this exact marker.
    if marker.stat().st_mtime_ns!=proof['mtime_ns'] or sha(marker)!=proof['sha256']:raise ValueError('Pause changed')
    marker.unlink()
    write(folder/'automatic_pause_cleared.json',dict(at=now(),reason='Verified wall_budget continuation',proof=proof))
    try:
        resources()
        job_id=enqueue(j['case_id'],'resume',parent_id=j['id'],request_key=plan['id']+'_resume_'+j['id'])
        from server import ensure_worker,enable_report_updates
        enable_report_updates()
        return dict(status='wave_resumed',parent_id=j['id'],job_id=job_id,worker_pid=ensure_worker())
    except Exception:
        from worker import pause_after_limit
        pause_after_limit(j)
        raise

def step(apply=False):
    policy=read(POLICY)
    if policy.get('enabled') is not True:return dict(status='disabled')
    if policy.get('automation_ready') is not True:return dict(status='waiting_configuration')
    if policy.get('phase')=='waves':
        resumed=resume_budget_wave(policy,apply)
        if resumed:return resumed
        from advance_wave_queue import step as advance
        return advance(apply)
    folder=calm_folders()[-1];state=read(PRE/'state.json');process=read(folder/'process.json')
    launch=policy.get('launch',{})
    active=any(v.get('birth') and birth(v.get('pid'))==v['birth'] for v in (state,launch)) or birth(process.get('pid'))
    if active:
        rr=tail(folder/'history.csv')
        return dict(status='waiting_pre',folder=str(folder),time_s=number(rr[-1].get('time_s')) if rr else None)
    if markers(folder):return dict(status='blocked',reason='Pause/STOP preserved',markers=markers(folder))
    folder,done,receipt,last=saved_pre()
    choice=decision(datetime.now().astimezone(),datetime.fromisoformat(policy['fallback_at']),done['status'],last)
    if choice in ('original','prepared'):
        return release_waves(policy,choice) if apply else dict(status='ready_to_release',branch=choice)
    if choice=='continue':return launch_pre(policy) if apply else dict(status='ready_to_continue_pre')
    return dict(status='blocked',reason='PRE requires diagnosis',completed=done,endpoint=last)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    lock=HERE/'night_step.lock';token=uuid.uuid4().hex
    if lock.exists():
        prior=read(lock)
        if not prior.get('birth') or prior['birth']==birth(prior.get('pid')):raise SystemExit('Night step already running or lock requires review')
        lock.rename(HERE/('night_step.stale.'+token+'.json'))
    try:
        with lock.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid(),birth=birth(os.getpid()),token=token),f)
        try:result={'at':now(),'applied':args.apply,**step(args.apply)}
        except Exception as ex:result=dict(at=now(),applied=args.apply,status='blocked',reason=str(ex))
        if args.apply:write(HERE/'qa/night_campaign_state.json',result)
        print(json.dumps(result,ensure_ascii=False))
    finally:
        if read(lock).get('token')==token:lock.unlink()
