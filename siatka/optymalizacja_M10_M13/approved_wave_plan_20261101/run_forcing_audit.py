"""Two sequential zero-step STAR audits on source copies; never change original simulations."""
from pathlib import Path
from datetime import datetime
import sys,os,json,uuid,hashlib
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'approved_wave_plan_20261101';W=R/'wave_surface_only';P=R/'M13_wave_direct_20261031'
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029');sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
ROOT=D/'forcing_audit';MACRO=D/'AuditM13Forcing.java'
SOURCES={'wave_R4V':P/'M13_GPU_W20_H050_continuation_R4V_20261101'/'wave_pilot_final.sim','calm_M13':R/'M13_farfield15_20261031'/'M13_GPU_calm_dt0004'/'final.sim'}
LOCKS=[D/'forcing_audit.lock',R/'m13_wave_gpu.lock',W/'wave_inlet.lock',R/'parallel_cpu_20261031'/'auxiliary.lock']
def gate():
 assert datetime.now().astimezone()<datetime.fromisoformat('2026-11-02T09:00:00+01:00')
 assert rt.sha(R/'AUTONOMOUS_RECOVERY_PROMPT.md')==rt.read(R/'plan.json')['recovery_policy']['runbook_sha256']
 assert rt.read(D/'authorization.json')['until_local']=='2026-11-02T09:00:00+01:00'
 assert rt.resource_problem() is None,rt.resource_problem()
 assert not ROOT.exists() and not any(k.exists() for k in LOCKS),'Existing audit/ownership conflict'
 assert rt.read(F/'campaign_hold.json').get('active') is True
 assert (D/'compiled_audit'/'macro'/'AuditM13Forcing.class').exists()
 assert not any(name.lower().startswith(('starccm+','star-ccm+')) for _,name in rt.guard.processes().values()),'Another STAR process active'
 for label,src in SOURCES.items():
  assert src.is_file() and src.stat().st_size>400000000
  assert rt.read(src.parent/'stage_result.json').get('source_unchanged') is True
  assert rt.read(src.parent/'stage_result.json').get('exit_code')==0
 return {'at':rt.now(),'no_new_CFD_timesteps':True,'source_count':2,'macro_sha256':rt.sha(MACRO)}
def main():
 pre=gate()
 if '--preflight-only' in sys.argv:print(json.dumps(dict(pre,status='PASS')));return
 assert '--run' in sys.argv,'Explicit --run required'
 owned=[];token=uuid.uuid4().hex;folder=None;all_ok=False
 try:
  for lock in LOCKS:
   with lock.open('x',encoding='utf8') as f:json.dump({'pid':os.getpid(),'token':token,'at':rt.now(),'purpose':'zero_step_M13_forcing_audit'},f)
   owned.append(lock)
  ROOT.mkdir();rt.write(ROOT/'preflight.json',pre)
  receipts=[]
  for label,src in SOURCES.items():
   assert rt.resource_problem() is None
   folder=ROOT/label
   d,stage=rt.stage(folder,src,MACRO,env={'NTNU_M13_AUDIT_OUT':str(folder)},workers=1,gpu=False,mask=1<<22,budget_s=900,protect_main=False,phase='zero_step_M13_forcing_'+label)
   audit=rt.read(folder/'audit.json')
   ok=audit.get('steps_taken')==0 and audit.get('time_after')==audit.get('time_s') and audit.get('no_sim_save') is True and stage.get('source_unchanged') is True and not (folder/'audit_error.json').exists()
   receipt={'at':rt.now(),'case':label,'audit_complete':ok,'source_sha256':rt.sha(src),'copy_sha256':rt.sha(folder/'input.sim'),'zero_steps':True,'source_unchanged':stage.get('source_unchanged')}
   rt.write(folder/'receipt.json',receipt);receipts.append(receipt)
   print(json.dumps({'event':'forcing_audit_case_done','case':label,'complete':ok,'no_steps':True}),flush=True)
   assert ok,'Audit incomplete, do not accept exit code alone'
  all_ok=True;rt.write(ROOT/'completed.json',{'at':rt.now(),'status':'both_read_only_audits_complete','cases':receipts,'scientific_review_pending':True})
 except BaseException as ex:
  if ROOT.exists():rt.write(ROOT/'controller_error.json',{'at':rt.now(),'error':rt.guard.redact(str(ex))[:500],'no_auto_retry':True})
  raise
 finally:
  pid=rt.read(folder/'process.json').get('pid') if folder else None
  if not pid or not rt.guard.alive(pid):
   for lock in reversed(owned):
    if rt.read(lock).get('token')==token:lock.unlink()
if __name__=='__main__':main()
