"""Owned continuation of PRE W04; preserve every source and the global ramp clock."""
from common import *
from pre_w04 import PRE,CALM_RUN,REFERENCE,calm_folders,calm_values,convergence,export
from prepare_w04_geometry import OUT
from worker import rt,native,owned_lock
from run_pre_w04 import state
from pre_balance import balance_seed,water_readiness
import shutil

def main():
 folders=calm_folders();parent=folders[-1];source=parent/'final.sim'
 owner=read(PRE/'state.json')
 assert not (owner.get('birth') and owner['birth']==birth(owner.get('pid'))),'PRE already running'
 assert not native(),'Another solver is active'
 assert not any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS+[PRE/'STOP',DATA/'PAUSE']),'Stop or reservation active'
 assert not any(j['status'] in ('queued','running','preflight','pausing') for j in jobs()),'Queue is not idle'
 prior=read(PRE/'calm_receipt.json');done=read(parent/'completed.json')
 assert done.get('status') in ('field_health_guard','wall_budget','stopped_by_marker','scene_prepared'),'Not a resumable PRE checkpoint'
 if done.get('status')=='scene_prepared':
  scenes=read(parent/'scene_receipt.json')
  assert scenes.get('passed') and scenes.get('steps_advanced')==0 and scenes.get('physics_changed') is False
  assert read(parent/'stage_result.json').get('exit_code')==0 and read(parent/'stage_result.json').get('source_unchanged') is True
 assert Path(prior['checkpoint']).resolve()==source.resolve() and sha(source)==prior['checkpoint_sha256']
 assert sha(SOURCE)==SOURCE_SHA and prior['initialization']=='fresh_from_rest'
 geometry=read(OUT/'geometry_receipt.json');protected=read(OUT/'protected_receipt.json')
 assert geometry.get('passed') and protected.get('passed') and geometry['cells']==572176
 assert sha(OUT/'geometry/mesh.CGNS')==geometry['mesh_sha256']==protected['mesh_sha256']
 seed=balance_seed(folders);start=done['time_s']
 assert abs(seed['last_time_s']-start)<1e-8 and abs(seed['water_closure_error_m3'])<.25
 assert start<8 and source.stat().st_size>400_000_000
 from build_pre_w04_resume import build
 compile_receipt=build()
 stamp=datetime.now().strftime('%Y%m%d_%H%M%S');folder=PRE/('calm_resume_'+stamp)
 assert not folder.exists()
 boundary=PRE/('resume_boundary_'+stamp+'.csv')
 boundary.write_text((parent/'history.csv').read_text(encoding='utf8').splitlines()[-1]+'\n',encoding='utf8')
 write(PRE/('resume_preflight_'+stamp+'.json'),dict(parent=str(parent),source=str(source),source_sha256=prior['checkpoint_sha256'],
       source_time_s=start,balance=seed,compiled=compile_receipt,fields_retained=True,physics_changed=False,
       guard='Flux-corrected inventory error <=0.25 m3. Startup surface elevation is recorded without stopping; calm inventory and surface limits must pass after the ramp before wave acceptance. Other field/CFL limits unchanged.'))
 shutil.copy2(PRE/'calm_receipt.json',PRE/('calm_receipt_before_'+stamp+'.json'))
 owned=[];token=uuid.uuid4().hex
 try:
  for p in SOLVER_LOCKS:owned_lock(p,token,'PRE_W04_resume');owned.append(p)
  assert not native(),'A solver started during reservation'
  write(PRE/'continuation.json',dict(folders=list(map(str,folders+[folder])),updated_at=now()))
  state('calm_running',cells=572176,initialization='fresh_from_rest',resumed_from=str(source),resume_time_s=start,ramp_s=1.)
  env={'NTNU_STAB_OUT':str(folder),'NTNU_STAB_DT':'.0004','NTNU_STAB_TARGET':'8.0','NTNU_STAB_INNER':'10',
       'NTNU_STAB_CELLS':'572176','NTNU_STAB_START':str(start),'NTNU_STAB_INIT':'false','NTNU_STAB_ORDER':'SECOND_ORDER',
       'NTNU_STAB_BUDGET':'14100','NTNU_CALM_SETTLE':'true','NTNU_GCI_MAX_CFL':'25','NTNU_GCI_INTERFACE_CFL':'2.2',
       'PRE_W04_EXPECTED_WATER':str(seed['last_water_m3']),'PRE_W04_BALANCE_SEED':seed['seed_csv'],
       'PRE_W04_BOUNDARY_ROW':str(boundary)}
  try:rt.stage(folder,source,PRE/'PreW04Resume.java',env=env,workers=1,gpu=True,mask=12598275,budget_s=14400,protect_main=False,phase='PRE_W04_calm_resume')
  except AssertionError:
   stage=read(folder/'stage_result.json')
   if not (stage.get('exit_code')==0 and stage.get('source_unchanged') and read(folder/'completed.json')):raise
  done=read(folder/'completed.json');stage=read(folder/'stage_result.json')
  checks=convergence(calm_values(),0,ramp_s=1.);last=checks[-1] if checks else {}
  balance=balance_seed(calm_folders())
  water=water_readiness(calm_folders(),balance)
  gates=dict(native_calm_gate=done.get('status')=='calm_gate_passed',independent_history_gate=last.get('wave_allowed') is True,
             original_C01_preserved=sha(SOURCE)==SOURCE_SHA,source_checkpoint_preserved=sha(source)==prior['checkpoint_sha256'],
             clean_solver_exit=stage.get('exit_code')==0 and stage.get('source_unchanged') is True,
             flux_corrected_inventory=abs(balance['water_closure_error_m3'])<.25,post_ramp_water_ready=water['ready'],final_checkpoint=(folder/'final.sim').is_file())
  receipt=dict(passed=all(gates.values()),gates=gates,reference=REFERENCE,original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA,
               final_check=last,completed=done,mesh_sha256=geometry['mesh_sha256'],cells=572176,
               geometry_source=str(SOURCE),geometry_source_sha256=SOURCE_SHA,initialization='fresh_from_rest',
               ramp_s=1.,no_new_Q_reference=True,history_folders=list(map(str,calm_folders())),balance=balance,water_readiness=water)
  if gates['final_checkpoint']:receipt.update(checkpoint=str(folder/'final.sim'),checkpoint_sha256=sha(folder/'final.sim'),checkpoint_time_s=done.get('time_s'))
  write(PRE/'calm_receipt.json',receipt);export()
  state('ready_for_wave' if receipt['passed'] else 'stable_reference_mismatch' if done.get('status')=='stable_reference_mismatch' else 'paused' if done.get('status')=='stopped_by_marker' else 'needs_review',receipt=str(PRE/'calm_receipt.json'))
 except Exception as ex:
  state('needs_review',error=rt.guard.redact(str(ex))[:900])
  try:export()
  except Exception:pass
  raise
 finally:
  if not native():
   for p in reversed(owned):
    if read(p).get('token')==token:p.unlink()
  try:
   from report import build_report
   build_report()
  except Exception as ex:write(DATA/'report_error.json',dict(error=str(ex),at=now()))

if __name__=='__main__':main()
