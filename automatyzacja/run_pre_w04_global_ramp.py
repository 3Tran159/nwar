"""Start a separate whole-domain ramp from the latest saved PRE W04 with scenes."""
from common import *
from pre_w04 import PRE,REFERENCE,calm_folders,calm_values,convergence,endpoint_convergence,export
from prepare_w04_geometry import OUT
from worker import rt,native,owned_lock
from pre_balance import balance_seed,water_readiness
from run_pre_w04 import state
from build_pre_w04_global_ramp import build,MACRO
import shutil,subprocess,argparse

SUMMARY_NAMES=['state.json','continuation.json','calm_receipt.json','history.csv','convergence.csv',
 'PRE_W04_history.png','PRE_W04_history.svg','PRE_W04_settling.png','PRE_W04_settling.svg','PRE_W04_convergence.png']

def main(resume=False,source_run=None,observe_minutes=0,allow_approved_cpu=False,night_until=None):
    assert observe_minutes==0 or (resume and 1<=observe_minutes<=90),'Observation requires a saved-field continuation of 1–90 minutes'
    assert not allow_approved_cpu or (resume and observe_minutes),'CPU coexistence is scoped to the approved PRE observation'
    if night_until:
        assert resume and observe_minutes,'Night policy requires bounded saved-field continuation'
        policy=read(HERE/'night_campaign.json')
        assert policy.get('enabled') is True and policy.get('fallback_at')==night_until,'Night policy is not authorized'
        fallback=datetime.fromisoformat(night_until)
        assert fallback.tzinfo is not None,'Timezone required'
    def resource_check(launch=True):
        if allow_approved_cpu:
            from cpu_coexistence import check
            return check(launch=launch)
        assert not native(),'Another STAR/MPI solver is active'
        return dict(at=now(),allowed_cpu=[])
    owner=read(PRE/'state.json')
    assert not (owner.get('birth') and owner['birth']==birth(owner.get('pid'))),'Previous PRE controller still running'
    coexistence=resource_check()
    assert not any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS+[PRE/'STOP',DATA/'PAUSE']),'Stop or resource reservation active'
    assert not any(j['status'] in ('queued','running','preflight','pausing') for j in jobs()),'Queue is not idle'
    assert sha(SOURCE)==SOURCE_SHA,'Original C01 changed'
    prior_folders=calm_folders();parent=Path(source_run).resolve() if source_run else prior_folders[-1]
    assert parent.resolve().is_relative_to(PRE.resolve()),'Source checkpoint outside PRE W04'
    assert not (resume and source_run),'A continuation must use the active history endpoint'
    source=parent/'final.sim'
    done=read(parent/'completed.json');stage=read(parent/'stage_result.json')
    allowed=('stopped_by_marker','wall_budget','field_health_guard','CFL_guard','stability_guard')
    if observe_minutes:allowed=('stable_reference_mismatch','calm_gate_passed','wall_budget')
    assert done.get('status') in allowed,'Latest PRE has no resumable final save'
    assert stage.get('exit_code')==0 and stage.get('source_unchanged') is True
    assert source.is_file() and source.stat().st_size>400_000_000
    latest=read(parent/'latest_checkpoint.json')
    assert Path(latest['path']).resolve()==source.resolve() and abs(latest['time_s']-done['time_s'])<1e-8
    source_hash=sha(source)
    if observe_minutes:
        assert not read(parent/'macro_error.json'),'Do not observe after a solver error'
        assert abs(float(tail(parent/'history.csv')[-1]['time_s'])-done['time_s'])<1e-7,'Checkpoint/history mismatch'
        assert read(parent/'global_ramp_completed.json').get('momentum_source_option')=='NONE'
        assert read(parent/'global_ramp_completed.json').get('extra_force_active') is False
    geometry=read(OUT/'geometry_receipt.json');protected=read(OUT/'protected_receipt.json')
    assert geometry.get('passed') and protected.get('passed') and geometry['cells']==572176
    assert geometry['mesh_sha256']==protected['mesh_sha256']==sha(OUT/'geometry/mesh.CGNS')
    compile_receipt=build()
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    folder=PRE/(('calm_global_resume_' if resume else 'calm_global_')+stamp)
    assert not folder.exists()
    archive=PRE/('archive_before_global_'+stamp);archive.mkdir(exist_ok=False)
    for name in SUMMARY_NAMES:
        if (PRE/name).exists():shutil.copy2(PRE/name,archive/name)
    write(archive/'archive_receipt.json',dict(at=now(),source_checkpoint=str(source),source_sha256=source_hash,
        source_time_s=done['time_s'],raw_folders=list(map(str,prior_folders)),raw_data_preserved=True,
        previous_report=read(HERE/'latest_report.json'),action='Resume global ramp' if resume else 'Fresh whole-domain startup; reset active PRE history'))
    start=done['time_s'] if resume else 0.
    env={'NTNU_STAB_OUT':str(folder),'NTNU_STAB_DT':'.0004','NTNU_STAB_TARGET':'8.0','NTNU_STAB_INNER':'10',
         'NTNU_STAB_CELLS':'572176','NTNU_STAB_START':str(start),'NTNU_STAB_INIT':'false' if resume else 'true',
         'NTNU_STAB_ORDER':'SECOND_ORDER','NTNU_STAB_BUDGET':'28200','NTNU_CALM_SETTLE':'true',
         'NTNU_GCI_MAX_CFL':'25','NTNU_GCI_INTERFACE_CFL':'2.2'}
    budget_s=28800
    if observe_minutes:
        budget_s=round(observe_minutes*60)+240
        env.update(PRE_W04_OBSERVE_ONLY='true',NTNU_STAB_BUDGET=str(round(observe_minutes*60)))
    if night_until:
        env['PRE_W04_NIGHT_FALLBACK_MS']=str(round(fallback.timestamp()*1000))
        env['NTNU_STAB_TARGET']=str(max(8.,start+8.))
    if resume:
        assert read(parent/'setup.json').get('initialization')=='whole_domain_momentum_ramp'
        seed=balance_seed(prior_folders)
        boundary=archive/'resume_boundary.csv';boundary.write_text((parent/'history.csv').read_text().splitlines()[-1]+'\n')
        env.update(PRE_W04_EXPECTED_WATER=str(seed['last_water_m3']),PRE_W04_BALANCE_SEED=seed['seed_csv'],PRE_W04_BOUNDARY_ROW=str(boundary))
    selected=prior_folders+[folder] if resume else [folder]
    owned=[];token=uuid.uuid4().hex
    try:
        for p in SOLVER_LOCKS:owned_lock(p,token,'PRE_W04_global_ramp');owned.append(p)
        coexistence=resource_check()
        write(folder/'resource_preflight.json',coexistence)
        write(PRE/'continuation.json',dict(root_folder=str(selected[0]),folders=list(map(str,selected)),updated_at=now(),
              initialization='whole_domain_momentum_ramp',previous_attempt_archive=str(archive)))
        write(PRE/'calm_receipt.json',dict(passed=False,pending='Whole-domain acceleration ramp and calm stabilization',
              initialization='whole_domain_momentum_ramp',reference=REFERENCE,original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA,
              cells=572176,mesh_sha256=geometry['mesh_sha256'],no_new_Q_reference=True,ramp_s=1.,history_folders=list(map(str,selected)),
              source_checkpoint=str(source),source_checkpoint_sha256=source_hash,previous_attempt_archive=str(archive)))
        if not resume:
            # Remove only archived, derived PRE summaries. All raw runs and checkpoints stay in place.
            for name in SUMMARY_NAMES[3:]:
                target=(PRE/name).resolve()
                assert target.parent==PRE.resolve() and (archive/name).exists()==target.exists()
                if target.exists():target.unlink()
        state('calm_running',cells=572176,initialization='whole_domain_momentum_ramp',fresh_start=not resume,
              source=str(source),source_sha256=source_hash,source_time_s=done['time_s'],ramp_s=1.,folder=str(folder),observation_only=bool(observe_minutes))
        if observe_minutes:
            write(folder/'observation_request.json',dict(at=now(),minutes=observe_minutes,source=str(source),source_sha256=source_hash,
                  source_time_s=done['time_s'],no_reinitialize=True,auto_wave_start=False,reference_acceptance=False,
                  night_fallback_at=night_until,
                  instruction='Night campaign: original C01 compatibility can finish early; after the authorized time accept only twice-stable PRE.' if night_until else 'One additional observation interval; save at its wall limit and await user decision.'))
        # Refresh only published artifacts; no second STAR client is opened.
        with (archive/'report_reset.log').open('a',encoding='utf8') as log:
            subprocess.Popen([str(PYTHON),'-X','utf8',str(HERE/'report.py')],cwd=HERE,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        try:rt.stage(folder,source,MACRO,env=env,workers=1,gpu=True,mask=12598275,budget_s=budget_s,protect_main=False,phase='PRE_W04_observation' if observe_minutes else 'PRE_W04_whole_domain_ramp')
        except AssertionError:
            st=read(folder/'stage_result.json')
            if not (st.get('exit_code')==0 and st.get('source_unchanged') is True and read(folder/'completed.json')):raise
        result=read(folder/'completed.json');stage=read(folder/'stage_result.json')
        checks=endpoint_convergence(calm_values()) if night_until else convergence(calm_values(),0,ramp_s=1.);last=checks[-1] if checks else {}
        balance=balance_seed(calm_folders());water=water_readiness(calm_folders(),balance)
        removed=read(folder/'global_ramp_completed.json')
        gates=dict(native_calm_gate=result.get('status')=='calm_gate_passed',independent_history_gate=last.get('wave_allowed') is True,
          original_C01_preserved=sha(SOURCE)==SOURCE_SHA,source_checkpoint_preserved=sha(source)==source_hash,
          clean_solver_exit=stage.get('exit_code')==0 and stage.get('source_unchanged') is True,
          flux_corrected_inventory=abs(balance['water_closure_error_m3'])<.25,post_ramp_water_ready=water['ready'],
          startup_momentum_source_removed=removed.get('extra_force_active') is False and removed.get('momentum_source_option')=='NONE',
          final_checkpoint=(folder/'final.sim').is_file())
        receipt=dict(passed=all(gates.values()),gates=gates,reference=REFERENCE,original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA,
          final_check=last,completed=result,cells=572176,mesh_sha256=geometry['mesh_sha256'],initialization='whole_domain_momentum_ramp',
          ramp_s=1.,no_new_Q_reference=True,history_folders=list(map(str,calm_folders())),balance=balance,water_readiness=water,
          global_ramp=read(folder/'global_ramp_configuration.json'),startup_force_removal=removed,previous_attempt_archive=str(archive))
        receipt.update(night_fallback_at=night_until,independent_endpoint_checks=checks[-2:])
        if gates['final_checkpoint']:receipt.update(checkpoint=str(folder/'final.sim'),checkpoint_sha256=sha(folder/'final.sim'),checkpoint_time_s=result['time_s'])
        write(PRE/'calm_receipt.json',receipt);export()
        state('observation_complete' if observe_minutes and result.get('status')=='wall_budget' else 'ready_for_wave' if receipt['passed'] else 'stable_reference_mismatch' if result.get('status')=='stable_reference_mismatch' else 'paused' if result.get('status')=='stopped_by_marker' else 'needs_review',receipt=str(PRE/'calm_receipt.json'))
    except Exception as ex:
        state('needs_review',error=rt.guard.redact(str(ex))[:900])
        raise
    finally:
        # The launcher can exit a moment before its native child disappears.
        released=False
        for _ in range(15):
            try:
                resource_check(launch=False);released=True;break
            except (AssertionError,RuntimeError,ValueError):pass
            time.sleep(1)
        if released:
            for p in reversed(owned):
                if read(p).get('token')==token:p.unlink()
        try:
            from report import build_report
            build_report()
        except Exception as ex:write(DATA/'report_error.json',dict(error=str(ex),at=now()))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');parser.add_argument('--source-run');parser.add_argument('--observe-minutes',type=float,default=0)
    parser.add_argument('--allow-approved-cpu',action='store_true')
    parser.add_argument('--night-until')
    args=parser.parse_args();main(args.resume,args.source_run,args.observe_minutes,args.allow_approved_cpu,args.night_until)
