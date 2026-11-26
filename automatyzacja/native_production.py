"""Prepare, solve and export W04c/W04e, with no custom Java calls during solving."""
import csv
import math
import os
import re
import shutil

from common import DATA, HERE, Path, STOPS, datetime, job, now, read, sha, write
from native_pilot import sim_info
from w04b_controller import run


CHANNELS = ('Fx_N','Fz_N','Fx_pressure_N','Fx_viscous_N','max_CFL','interface_CFL',
            'max_speed_m_s','alpha_min','alpha_max','p_min_Pa','p_max_Pa','water_volume_m3')


def native_samples(path, times, begin, dt):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        pairs=[(float(row['sample_x']),float(row['value'])) for row in csv.DictReader(stream)]
    if not pairs or not all(math.isfinite(x) and math.isfinite(y) for x,y in pairs):
        raise ValueError('Empty or nonfinite native monitor: '+path.name)
    candidates=[]
    for scale in (1,10,dt):
        result={}
        for x,y in pairs:
            step=round(x/scale)
            if abs(x-step*scale)>1e-7 or step not in times and step!=begin or step in result:
                break
            result[step]=y
        else:
            result.pop(begin,None)
            if result and result not in candidates:
                candidates.append(result)
    if len(candidates)!=1:
        axis=path.with_suffix('.axis').read_text(encoding='utf-8')
        raise ValueError(f'Cannot align native monitor {path.name} ({axis}) to STAR time steps.')
    return candidates[0]


def save_csv(path, header, rows):
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf8',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    tmp.replace(path)


def prepare_history(folder, exported, times, begin, plan, *, diagnostic=False):
    dt=plan['dt_s']
    steps=sorted(times)
    if steps!=list(range(begin+1,steps[-1]+1)) or any(
            abs(times[step]-(plan['start_s']+(step-begin)*dt))>1e-7 for step in steps):
        raise ValueError('Native STAR steps or time continuity differ.')
    forces={key:native_samples(exported/(key+'.csv'),times,begin,dt) for key in CHANNELS}
    if any(set(values)!=set(steps) for values in forces.values()):
        raise ValueError('Native force and field monitors do not cover every step.')
    gauges=[]
    for i,x in enumerate(map(float,plan['probe_positions_m'].strip('[]').split(','))):
        samples=native_samples(exported/(f'eta_{i}.csv'),times,begin,dt)
        limit = plan.get('surface_limit_m')
        if not diagnostic and limit is not None and any(abs(eta)>limit for eta in samples.values()):
            raise ValueError('Native surface monitor exceeded its bound.')
        gauges.extend((times[step],x,eta) for step,eta in samples.items())
    save_csv(folder/'gauges.csv',('time_s','x_m','eta_actual_m'),sorted(gauges))
    values=[]
    for step in steps:
        fx,fz=forces['Fx_N'][step],forces['Fz_N'][step]
        values.append((times[step],step-begin,(fz-22.718189111947265)/3855.6,fx/3855.6,
                       *(forces[key][step] for key in CHANNELS)))
    save_csv(folder/'history.csv',('time_s','step','CL_hydrodynamic','CD_total',*CHANNELS),values)


def native_health_snapshot(log, plan, checkpoint_step):
    with log.open('rb') as stream:
        stream.seek(max(0, stream.seek(0, 2)-500_000))
        tail = stream.read().decode('utf8', errors='replace')
    gauges = len(plan['probe_positions_m'].strip('[]').split(','))
    steps = re.findall(r'(?m)^\s*TimeStep\s+(\d+):', tail)
    if (not steps or checkpoint_step-int(steps[-1]) > 60
            or 'NWAR native force_balance' not in tail or re.search(
            r'(?i)floating.point exception|\bdiverg(?:ed|ence)\b|unphysical free surface|macro error', tail)):
        raise ValueError('Recent numerical health samples are unavailable for this native checkpoint.')
    for line in reversed(tail.splitlines()):
        fields = line.split()
        if len(fields) != 8+13+gauges or not fields[0].isdigit():
            continue
        values = list(map(float, fields[8:]))
        balance,cfl,interface,speed,amin,amax,pmin,pmax,water = values[4:13]
        if (all(map(math.isfinite, values)) and abs(balance)<=1e-5 and 0<=cfl<=25
                and 0<=interface<=2.2 and 0<=speed<=50 and -.00001<=amin<=amax<=1.00001
                and -1e7<=pmin<=pmax<=1e7 and water>0
                and (plan.get('surface_limit_m') is None or all(abs(eta)<=plan['surface_limit_m'] for eta in values[13:]))):
            return dict(iteration=int(fields[0]),interface_cfl=interface,water_volume_m3=water,
                        maximum_abs_eta_m=max(map(abs,values[13:])))
        break
    raise ValueError('The last complete native numerical health sample did not pass.')


def surface_rule_checkpoint(parent):
    rule = read(HERE/'surface_rule.json')
    authority = Path(rule.get('authorization', ''))
    folder = Path(parent['folder'])
    review = read(folder/'native_checkpoint_review.json')
    stage = read(folder/'native_solve/stage_result.json')
    prior = parent['spec'].get('native_recovery', {})
    old_plan = read(folder/'native_plan.json')
    source = Path(review.get('source', ''))
    if (rule.get('magnitude_limit_enabled') is not False or not authority.is_file()
            or read(authority).get('authorized') is not True
            or parent['case_id'] not in ('W04c', 'W04e', 'W04g', 'W04h', 'W04k') or parent['status'] != 'failed'
            or stage.get('ownership') != 'windows_job_closed' or stage.get('source_unchanged') is not True
            or review.get('job_id') != parent['id'] or review.get('numerical_health', {}).get('ok') is not True
            or not prior or not source.is_file() or sha(source) != review.get('source_sha256')
            or any(p.exists() for p in STOPS+[DATA/'STOP', folder/'STOP'])
            or any(folder.rglob('macro_error.*'))):
        raise ValueError('The authorized surface-rule continuation lacks verified checkpoint evidence.')
    saved_step, saved_time = sim_info(source)
    time_s = old_plan['start_s']+(saved_step-prior['initial_step'])*old_plan['dt_s']
    wake = Path(prior['wake_file'])
    if (saved_step != review['checkpoint_step'] or abs(time_s-review['time_s'])>1e-7
            or abs(saved_time-time_s)>.050001 or wake.exists() or time_s>=old_plan['wake_start_s']):
        raise ValueError('The reviewed surface-rule checkpoint or wake recording changed.')
    return dict(parent_id=parent['id'], checkpoint=str(source), sha256=review['source_sha256'],
                initial_step=prior['initial_step'], checkpoint_step=saved_step, time_s=time_s,
                plan=dict(old_plan, surface_limit_m=None, surface_magnitude_limit_enabled=False),
                wake_file=str(wake), surface_rule=True, authorization=str(authority),
                authorization_sha256=sha(authority), review_sha256=sha(folder/'native_checkpoint_review.json'))


def recovery_checkpoint(parent):
    folder = Path(parent['folder'])
    solve = folder/'native_solve'
    stage = read(solve/'stage_result.json')
    if stage.get('controller_reason') in ('RAM_below16GiB','RAM_below8GiB') and (folder/'resource_resume_authorization.json').is_file():
        from native_resource_resume import verify
        return verify(parent)
    plan = read(folder/'native_plan.json')
    timed_out = stage.get('controller_reason') == 'night_progress_timeout'
    reset = stage.get('job_terminated_after_reset') or stage.get('transport_disconnected')
    cancel_path = folder/'pause_cancel_authorization.json'
    cancel = read(cancel_path)
    user_cancel = (stage.get('controller_reason') == 'user_stop'
                   and cancel.get('authorized') is True and cancel.get('job_id') == parent['id']
                   and cancel.get('action') == 'resume_after_cancelled_manual_pause'
                   and cancel.get('stage_sha256') == sha(solve/'stage_result.json'))
    if (parent['case_id'] not in ('W04c', 'W04e', 'W04g', 'W04h', 'W04k') or not parent['spec'].get('native_production')
            or parent['status'] != 'failed' or stage.get('phase') != 'NWAR_native_solve'
            or stage.get('ownership') != 'windows_job_closed' or stage.get('source_unchanged') is not True
            or not (timed_out or user_cancel or reset and not stage.get('controller_reason'))
            or any(p.exists() for p in STOPS+[DATA/'PAUSE', DATA/'STOP', folder/'STOP'])
            or any(folder.rglob('macro_error.*')) or any(folder.rglob('*.simh'))):
        raise ValueError('Native restart requires an eligible interruption before wake recording.')
    if (solve/'STOP').exists() and (not timed_out or abs((solve/'STOP').stat().st_mtime-
            datetime.fromisoformat(stage['at']).timestamp()) > 10):
        raise ValueError('A solver stop marker could not be attributed to the native watchdog.')
    prior = parent['spec'].get('native_recovery')
    if prior:
        if plan != prior['plan'] or read(folder/'native_recovery.json') != prior:
            raise ValueError('The resumed native segment has different preparation evidence.')
        begin, last_start = prior['initial_step'], prior['checkpoint_step']
        wake = Path(prior['wake_file'])
    else:
        begin, _ = sim_info(folder/'native_ready.sim')
        last_start, wake = begin, folder/'wake.simh'
    candidates = []
    for path in solve.glob('input*@*.sim'):
        match = re.fullmatch(r'input.*@(\d+)\.sim', path.name)
        if match and path.stat().st_size >= 400_000_000:
            candidates.append((int(match.group(1)), path))
    step, checkpoint = max(candidates)
    time_s = plan['start_s']+(step-begin)*plan['dt_s']
    saved_step, saved_time = sim_info(checkpoint)
    # STAR 2602 -info rounds the printed time to one decimal. The step is exact.
    if (step <= last_start or step != saved_step or abs(saved_time-time_s) > .050001 or wake.exists()
            or time_s >= min(plan['target_s'], plan['wake_start_s'])):
        raise ValueError('Native checkpoint time, header or wake boundary did not pass review.')
    receipt = dict(parent_id=parent['id'], checkpoint=str(checkpoint), sha256=sha(checkpoint),
                initial_step=begin, checkpoint_step=step, time_s=time_s, plan=plan,
                wake_file=str(wake))
    if timed_out or user_cancel:
        receipt['health_before_timeout'] = native_health_snapshot(solve/'star.log', plan, step)
    if user_cancel:
        receipt['manual_pause_cancelled'] = True
        receipt['authorization_sha256'] = sha(cancel_path)
    return receipt


def run_case(folder, source, macro, env, *, recovery=None, **kwargs):
    start_sha=sha(source)
    write(folder/'source_identity.json',dict(path=str(source),sha256=start_sha,original_preserved=True))
    prepared=folder/'native_ready.sim'
    setup=folder
    solve,export=(folder/name for name in ('native_solve','native_export'))
    for p in (solve,export):
        p.mkdir()
    phase=setup
    try:
        if recovery:
            verify = surface_rule_checkpoint if recovery.get('surface_rule') else recovery_checkpoint
            if verify(job(recovery['parent_id'])) != recovery or start_sha != recovery['sha256']:
                raise ValueError('Native checkpoint or recovery evidence changed before launch.')
            write(folder/'native_recovery.json', recovery)
            original = Path(recovery['wake_file']).parent
            for name in ('wave_setup_audit.json', 'stopping_policy.json',
                         'native_C01_rho_readback.json', 'wave_density_audit.json'):
                shutil.copy2(original/name, folder/name)
            prepared = source
            plan = recovery['plan']
            begin = recovery['initial_step']
            solve_start = recovery['checkpoint_step']
            solve_time = recovery['time_s']
            write(folder/'native_plan.json', plan)
            if recovery.get('resource_resume'):
                # The full job ID, rather than a reused basename, prevents an
                # inherited solution history from claiming the new output.
                name='wake_'+read(folder/'request.json')['id']+'.simh'
                previous=folder/'wake_previous_segment.simh'
                try:os.link(recovery['previous_wake_file'],previous)
                except OSError:shutil.copy2(recovery['previous_wake_file'],previous)
                if sha(previous)!=recovery['previous_wake_sha256']:
                    raise ValueError('Preserved previous field history differs.')
                ancestors=[]
                parent_folder=Path(job(recovery['parent_id'])['folder'])
                for entry in read(parent_folder/'field_history_segments.json').get('segments',[]):
                    old=(parent_folder/entry['file']).resolve()
                    if old==Path(recovery['previous_wake_file']).resolve():continue
                    if not old.is_relative_to(parent_folder.resolve()) or not old.is_file():
                        raise ValueError('An earlier field-history segment is missing or outside its parent.')
                    digest=sha(old)
                    if entry.get('sha256',digest)!=digest:raise ValueError('An earlier field-history segment changed.')
                    retained=folder/('wake_ancestor_'+str(len(ancestors))+'.simh')
                    try:os.link(old,retained)
                    except OSError:shutil.copy2(old,retained)
                    if sha(retained)!=digest:raise ValueError('Earlier field-history preservation failed.')
                    ancestors.append(dict(entry,file=retained.name,source=str(old),sha256=digest))
                write(folder/'field_history_segments.json',dict(segments=ancestors+[
                    dict(file=previous.name,source=recovery['previous_wake_file'],sha256=recovery['previous_wake_sha256'],
                         valid_through_s=solve_time,exclude_later_frames=True),
                    dict(file='native_solve/'+name,start_s=solve_time)],overlap_policy='Use the old segment only through the pinned checkpoint.'))
                run(setup,source,HERE/'NwarNativeResume.java',env={
                    'NWAR_NATIVE_RESUME_OUT':str(folder),'NWAR_NATIVE_RESUME_TIME':str(solve_time),
                    'NWAR_NATIVE_RESUME_TARGET':str(plan['target_s']),'NWAR_NATIVE_RESUME_DT':str(plan['dt_s']),
                    'NWAR_NATIVE_RESUME_STRIDE':str(plan['wake_stride']),
                    'NWAR_NATIVE_RESUME_START':str(math.ceil(plan['wake_start_s']/plan['dt_s'])),
                    'NWAR_NATIVE_RESUME_WAKE':name},phase='NWAR_native_resume_setup',watch_progress=True,status_dir=folder,**kwargs)
                proof=read(folder/'native_resume_prepared.json')
                prepared=folder/'native_ready.sim'
                if (proof.get('passed') is not True or proof.get('steps_advanced')!=0
                        or proof.get('scene_count')!=30 or proof.get('wake_file')!=name
                        or abs(proof.get('time_s',-1)-solve_time)>1e-7):
                    raise ValueError('Native continuation preparation failed zero-step verification.')
                from native_resource_resume import saved_header
                prepared_step,prepared_time,_=saved_header(prepared)
                if prepared_step!=solve_start or abs(prepared_time-solve_time)>1e-7:
                    raise ValueError('Prepared native checkpoint time or step changed.')
                shutil.copy2(folder/'stage_result.json',folder/'native_setup_stage_result.json')
                plan=dict(plan,wake_filename=name)
                write(folder/'native_plan.json',plan)
            if recovery.get('surface_rule'):
                run(setup,source,HERE/'NwarNativeSurfaceRule.java',
                    env={'NWAR_SURFACE_RULE_OUT':str(folder), 'NWAR_SURFACE_RULE_TIME':str(solve_time)},
                    phase='NWAR_native_surface_rule',watch_progress=True,status_dir=folder,**kwargs)
                proof = read(folder/'native_surface_rule_applied.json')
                prepared = folder/'native_ready.sim'
                if (proof.get('passed') is not True or proof.get('steps_advanced')!=0
                        or abs(proof['time_s']-solve_time)>1e-7 or sim_info(prepared)[0]!=solve_start):
                    raise ValueError('The saved native surface rule did not pass verification.')
                shutil.copy2(folder/'stage_result.json',folder/'native_setup_stage_result.json')
                policy = read(folder/'stopping_policy.json')
                policy.update(surface_elevation_limit_m=None, surface_magnitude_limit_enabled=False,
                              surface_rule_authorization=recovery['authorization'])
                write(folder/'stopping_policy.json',policy)
                audit = read(folder/'wave_setup_audit.json')
                audit.update(stopping_policy=policy, surface_rule_authorization=recovery['authorization'])
                write(folder/'wave_setup_audit.json',audit)
        else:
            run(setup,source,macro,env={**env,'NWAR_NATIVE_PRODUCTION':'1'},
                phase='NWAR_native_setup',watch_progress=True,status_dir=folder,**kwargs)
            shutil.copy2(folder/'stage_result.json',folder/'native_setup_stage_result.json')
            plan=read(folder/'native_plan.json')
            begin,_=sim_info(prepared)
            solve_start, solve_time = begin, plan['start_s']
        phase=solve
        run(solve,prepared,macro,env={},native_batch=True,phase='NWAR_native_solve',
            watch_progress=True,status_dir=folder,native_initial_step=solve_start,
            native_initial_time=solve_time,native_dt=plan['dt_s'],
            native_target_step=begin+round((plan['target_s']-plan['start_s'])/plan['dt_s']),**kwargs)
        log=(solve/'star.log').read_text(encoding='utf-8')
        dt = plan['dt_s']
        newest = begin+round((plan['target_s']-plan['start_s'])/dt)
        times = {step:plan['start_s']+(step-begin)*dt for step in range(begin+1,newest+1)}
        if any(abs(times.get(int(step),math.inf)-float(t))>1e-7
               for step,t in re.findall(r'\bTimeStep\s+(\d+):\s+Time\s+([0-9.Ee+-]+)',log)):
            raise ValueError('Native solver log differs from the checkpoint time grid.')
        candidates=[path for path in solve.glob('*.sim') if path.name!='input.sim'
                    and path.stat().st_size>=400_000_000 and sim_info(path)[0]==newest]
        if not candidates:
            raise ValueError('Native solver stopped before the planned window or did not save the final step.')
        # STAR can save both the rolling time-step snapshot and the batch-final
        # iteration-named file at the same verified final step.
        final_checkpoint = max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))
        phase=export
        exported=folder/'native_monitors'
        run(export,final_checkpoint,HERE/'NwarNativeExport.java',env={'NWAR_NATIVE_EXPORT':str(exported)},
            phase='NWAR_native_export',watch_progress=True,**kwargs)
        finish_native_output(folder,final_checkpoint,source,start_sha,begin,plan,exported)
    except Exception:
        stage=read(phase/'stage_result.json')
        if stage:
            write(folder/'stage_result.json',stage)
        raise


def finish_native_output(folder, checkpoint, source, source_sha, begin, plan, exported):
    """Verify saved native output independently of the batch console connection."""
    from analysis import analyze
    from cycle_policy import accepted_cycles
    stage = read(folder/'native_solve/stage_result.json')
    export_stage = read(folder/'native_export/stage_result.json')
    step, _ = sim_info(checkpoint)
    end = plan['start_s']+(step-begin)*plan['dt_s']
    if (abs(end-plan['target_s'])>1e-7 or abs(float((exported/'final_time.txt').read_text())-end)>1e-7
            or sha(source)!=source_sha or stage.get('source_unchanged') is not True
            or stage.get('ownership')!='windows_job_closed'
            or stage.get('controller_reason') not in (None,'native_target_saved','night_progress_timeout')
            or export_stage.get('exit_code')!=0 or export_stage.get('source_unchanged') is not True
            or any(folder.rglob('macro_error.*'))):
        raise ValueError('Native final state, export or unchanged source did not pass verification.')
    times = {k:plan['start_s']+(k-begin)*plan['dt_s'] for k in range(begin+1,step+1)}
    prepare_history(folder,exported,times,begin,plan)
    spec = read(folder/'request.json')
    if spec.get('imported_native_continuation'):
        from imported_native_resume import add_boundary_sample
        add_boundary_sample(folder,spec)
    segments=[Path(p) for p in spec.get('parent_segments',[])]+[folder] if spec.get('imported_native_continuation') else [folder]
    result,_,_ = analyze(dict(spec,id=spec['id']),segments)
    if not result['health']['ok']:
        raise ValueError('Exported native history failed the independent numerical review.')
    final = folder/'wave_pilot_final.sim'
    shutil.copy2(checkpoint,final)
    wake = folder/'native_solve'/plan.get('wake_filename','wake.simh')
    resource_resume = spec.get('native_recovery',{}).get('resource_resume')
    if resource_resume and (not wake.is_file() or wake.stat().st_size==0
            or sha(folder/'wake_previous_segment.simh')!=spec['native_recovery']['previous_wake_sha256']):
        raise ValueError('Native continuation requires both preserved and newly recorded field histories.')
    if not wake.is_file() and spec.get('native_recovery'):
        wake = Path(spec['native_recovery']['wake_file'])
    if wake.is_file():
        collected = folder/'wake.simh'
        if resource_resume and collected.exists() and sha(collected)!=sha(wake):
            # A disabled inherited history may create an empty container when
            # loading. Preserve it under an explicit name; publish the new data.
            retained=folder/'disabled_inherited_wake.simh'
            if retained.exists():raise ValueError('Existing inherited field container needs review.')
            collected.rename(retained)
        if not collected.exists():
            try:
                os.link(wake,collected)
            except OSError:
                shutil.copy2(wake,collected)
    final_sha = sha(final)
    write(folder/'latest_checkpoint.json',dict(file=final.name,time_s=end,step=step-begin,healthy=True,sha256=final_sha))
    write(folder/'completed.json',dict(status='five_cycles_recorded' if accepted_cycles(result['cycles']) else 'native_review',
          steps=step-begin,time_s=end,complete_cycles=result['cycles']['count']))
    write(folder/'independent_cycle_review.json',result)
    write(folder/'stage_result.json',dict(stage,native_batch=True))
    write(folder/'native_completion_review.json',dict(at=now(),verified=True,time_s=end,target_s=plan['target_s'],
          checkpoint_sha256=final_sha,numerical_health_ok=True,original_exit_code=stage['exit_code'],
          original_stage_sha256=sha(folder/'native_solve/stage_result.json'),
          export_stage_sha256=sha(folder/'native_export/stage_result.json'),
          proof='Exact final STAR step, exported physical time, complete monitor history and numerical health.'))
    return result


def native_completion_verified(folder):
    proof = read(folder/'native_completion_review.json')
    if not proof.get('verified') or proof.get('numerical_health_ok') is not True:
        return False
    return (proof['original_stage_sha256']==sha(folder/'native_solve/stage_result.json')
            and proof['export_stage_sha256']==sha(folder/'native_export/stage_result.json')
            and proof['checkpoint_sha256']==sha(folder/'wave_pilot_final.sim')
            and abs(proof['time_s']-read(folder/'native_plan.json')['target_s'])<1e-7)
