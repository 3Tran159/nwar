"""Owned fresh startup and calm compatibility gate on the completed W04 mesh."""
from common import *
from pre_w04 import PRE,CALM_RUN,REFERENCE,convergence,export
from prepare_w04_geometry import OUT
from worker import rt,native,owned_lock
from history_view import _history
from run_pre_w04 import state

def main():
 owned=[];token=uuid.uuid4().hex
 assert not CALM_RUN.exists(),'Existing calm run preserved'
 assert not native(),'Another solver is active'
 assert not any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS+[PRE/'STOP',DATA/'PAUSE']),'Stop or resource reservation active'
 source=SOURCE;source_sha=sha(source)
 geometry=read(OUT/'geometry_receipt.json');protected=read(OUT/'protected_receipt.json')
 assert geometry.get('passed') and protected.get('passed') and geometry['cells']==572176
 assert sha(OUT/'geometry/mesh.CGNS')==geometry['mesh_sha256']==protected['mesh_sha256']
 assert sha(SOURCE)==SOURCE_SHA
 from build_pre_w04_fresh import build
 build()
 try:
  for p in SOLVER_LOCKS:owned_lock(p,token,'PRE_W04_fresh');owned.append(p)
  assert not native(),'A solver started during reservation'
  state('calm_running',cells=572176,initialization='fresh_from_rest',ramp_s=1.,source=str(source),source_sha256=source_sha)
  env={'NTNU_STAB_OUT':str(CALM_RUN),'NTNU_STAB_DT':'.0004','NTNU_STAB_TARGET':'8.0','NTNU_STAB_INNER':'10',
       'NTNU_STAB_CELLS':'572176','NTNU_STAB_START':'0','NTNU_STAB_INIT':'true','NTNU_STAB_ORDER':'SECOND_ORDER',
       'NTNU_STAB_BUDGET':'14100','NTNU_CALM_SETTLE':'true','NTNU_GCI_MAX_CFL':'25','NTNU_GCI_INTERFACE_CFL':'2.2',
       'PRE_W04_MESH':str(OUT/'geometry/mesh.CGNS')}
  try:rt.stage(CALM_RUN,source,PRE/'PreW04Fresh.java',env=env,workers=1,gpu=True,mask=12598275,budget_s=14400,protect_main=False,phase='PRE_W04_fresh_calm')
  except AssertionError:
   stage=read(CALM_RUN/'stage_result.json')
   if not (stage.get('exit_code')==0 and stage.get('source_unchanged') and read(CALM_RUN/'completed.json')):raise
  done=read(CALM_RUN/'completed.json');stage=read(CALM_RUN/'stage_result.json')
  checks=convergence(_history(CALM_RUN),0,ramp_s=1.);last=checks[-1] if checks else {}
  gates=dict(native_calm_gate=done.get('status')=='calm_gate_passed',independent_history_gate=last.get('wave_allowed') is True,
             original_C01_preserved=sha(SOURCE)==SOURCE_SHA,geometry_source_preserved=sha(source)==source_sha,
             clean_solver_exit=stage.get('exit_code')==0 and stage.get('source_unchanged') is True,final_checkpoint=(CALM_RUN/'final.sim').is_file())
  receipt=dict(passed=all(gates.values()),gates=gates,reference=REFERENCE,original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA,
               final_check=last,completed=done,mesh_sha256=geometry['mesh_sha256'],cells=572176,geometry_source=str(source),geometry_source_sha256=source_sha,
               initialization='fresh_from_rest',ramp_s=1.,no_new_Q_reference=True)
  if gates['final_checkpoint']:receipt.update(checkpoint=str(CALM_RUN/'final.sim'),checkpoint_sha256=sha(CALM_RUN/'final.sim'),checkpoint_time_s=done.get('time_s'))
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
  if (PRE/'calm_receipt.json').exists():
   try:
    from report import build_report
    build_report()
   except Exception as ex:write(DATA/'report_error.json',dict(error=str(ex),at=now()))

if __name__=='__main__':main()
