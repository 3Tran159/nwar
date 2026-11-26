"""Wait for the owned W04 geometry job, then map C01 and run its calm gate."""
from common import *
from pre_w04 import PRE,CALM_RUN,REFERENCE,convergence,export
from prepare_w04_geometry import OUT,REVIEW
from worker import rt,native,owned_lock
from history_view import _history
import subprocess

def state(status,**more):
 value=dict(status=status,at=now(),pid=os.getpid(),birth=birth(os.getpid()),case='PRE W04',**more)
 write(PRE/'state.json',value);print(json.dumps(value),flush=True)

def main():
 token=uuid.uuid4().hex;owned=[]
 assert not (PRE/'state.json').exists(),'Existing preparation preserved'
 # The mesh controller owns its locks until it exits. Do not queue a competing solver.
 deadline=time.monotonic()+5400
 while True:
  if any(p.exists() for p in STOPS+[PRE/'STOP',DATA/'PAUSE']):raise RuntimeError('Stop requested before PRE W04')
  geom=read(REVIEW/'state.json');alive=geom.get('birth')==birth(geom.get('pid')) and bool(geom.get('birth'))
  if not alive:
   assert geom.get('status')=='geometry_ready_for_protected_region_audit','Geometry preparation did not finish successfully'
   break
  if time.monotonic()>deadline:raise RuntimeError('Geometry wait limit reached')
  time.sleep(10)
 try:
  assert not native(),'Another solver is active'
  assert not any(p.exists() for p in SOLVER_LOCKS+OTHER_LOCKS),'Resource reservation active'
  assert not any(j['status'] in ('queued','running','preflight','pausing') for j in jobs()),'Queue is not idle'
  for p in SOLVER_LOCKS:owned_lock(p,token,'PRE_W04');owned.append(p)
  assert not native(),'A solver started during reservation'
  geometry=read(OUT/'geometry_receipt.json');assert geometry['passed']
  assert sha(OUT/'geometry/mesh.CGNS')==geometry['mesh_sha256']
  assert sha(SOURCE)==SOURCE_SHA,'Original C01 identity changed'
  state('auditing_protected_mesh',cells=geometry['cells'])
  from audit_w04_mesh import audit
  protected=audit()
  from build_pre_w04 import build
  build()
  if any(p.exists() for p in STOPS+[PRE/'STOP',DATA/'PAUSE']):state('paused');return
  state('mapping_C01',cells=geometry['cells'])
  folder=PRE/'mapping'
  rt.stage(folder,SOURCE,PRE/'MapPreW04.java',env={'NTNU_MAP_OUT':str(folder),'NTNU_MAP_EXPECTED_START':str(T0),
       'NTNU_MAP_MESH':str(OUT/'geometry/mesh.CGNS'),'NTNU_MAP_CELLS':str(geometry['cells'])},workers=4,gpu=False,mask=240,budget_s=1800,protect_main=False,phase='PRE_W04_mapping')
  mapping=read(folder/'mapping_audit.json');assert mapping.get('pass')
  source=folder/'mapped.sim';assert source.is_file();mapped_sha=sha(source)
  expected_water=mapping['after']['water']
  assert 76<expected_water<78,'Expanded water inventory mismatch'
  if any(p.exists() for p in STOPS+[PRE/'STOP',DATA/'PAUSE']):state('paused');return
  state('calm_running',cells=geometry['cells'],source=str(source),source_sha256=mapped_sha,original_C01_sha256=SOURCE_SHA)
  env={'NTNU_STAB_OUT':str(CALM_RUN),'NTNU_STAB_DT':'.0004','NTNU_STAB_TARGET':str(T0+2),
       'NTNU_STAB_INNER':'10','NTNU_STAB_CELLS':str(geometry['cells']),'NTNU_STAB_START':str(T0),
       'NTNU_STAB_INIT':'false','NTNU_STAB_ORDER':'SECOND_ORDER','NTNU_STAB_BUDGET':'6900','NTNU_CALM_SETTLE':'true',
       'NTNU_GCI_MAX_CFL':'25','NTNU_GCI_INTERFACE_CFL':'2.2','PRE_W04_EXPECTED_WATER':str(expected_water)}
  try:rt.stage(CALM_RUN,source,PRE/'PreW04Calm.java',env=env,workers=1,gpu=True,mask=12598275,budget_s=7200,protect_main=False,phase='PRE_W04_calm')
  except AssertionError:
   done=read(CALM_RUN/'completed.json');stage=read(CALM_RUN/'stage_result.json')
   if not (stage.get('exit_code')==0 and stage.get('source_unchanged') and done):raise
  done=read(CALM_RUN/'completed.json');stage=read(CALM_RUN/'stage_result.json')
  checks=convergence(_history(CALM_RUN),T0);last=checks[-1] if checks else {}
  gates=dict(native_calm_gate=done.get('status')=='calm_gate_passed',independent_history_gate=last.get('wave_allowed') is True,
             original_C01_preserved=sha(SOURCE)==SOURCE_SHA,mapped_source_preserved=sha(source)==mapped_sha,
             clean_solver_exit=stage.get('exit_code')==0 and stage.get('source_unchanged') is True,
             final_checkpoint=(CALM_RUN/'final.sim').is_file())
  receipt=dict(passed=all(gates.values()),gates=gates,reference=REFERENCE,original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA,
               final_check=last,completed=done,mesh_sha256=geometry['mesh_sha256'],cells=geometry['cells'],
               mapped_source=str(source),mapped_source_sha256=mapped_sha,no_new_Q_reference=True)
  if gates['final_checkpoint']:
   receipt.update(checkpoint=str(CALM_RUN/'final.sim'),checkpoint_sha256=sha(CALM_RUN/'final.sim'),checkpoint_time_s=done.get('time_s'))
  write(PRE/'calm_receipt.json',receipt);export()
  state('ready_for_wave' if receipt['passed'] else 'stable_reference_mismatch' if done.get('status')=='stable_reference_mismatch' else 'paused' if done.get('status')=='stopped_by_marker' else 'needs_review',receipt=str(PRE/'calm_receipt.json'),cells=geometry['cells'])
 except Exception as ex:
  state('needs_review',error=rt.guard.redact(str(ex))[:900])
  try:export()
  except Exception:pass
  raise
 finally:
  if not native():
   for p in reversed(owned):
    if read(p).get('token')==token:p.unlink()

if __name__=='__main__':main()
