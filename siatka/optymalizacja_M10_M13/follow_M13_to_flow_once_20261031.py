"""Bounded one-shot handoff: finished M13 build -> independent prism audit -> GPU calm solve.
No original controller edits, no numerical threshold relaxation, no wave duplicate.
"""
from pathlib import Path
from datetime import datetime
import sys,os,json,time,uuid,subprocess,shutil,importlib.util
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'M13_farfield15_20261031'
B=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030')
PY=Path(r'E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\python\python.exe')
sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
TOKEN=uuid.uuid4().hex;LOCK=D/'flow_handoff.lock';OUT=D/'M13_GPU_calm_dt0004'
def state(status,**kw):rt.write(D/'flow_state.json',dict(status=status,at=rt.now(),controller_pid=os.getpid(),directory=str(OUT),**kw))
def main():
 assert not LOCK.exists() and not OUT.exists()
 assert rt.read(R/'mesh_queue_completed_M10.json').get('project_primary_pass') is True
 assert rt.read(R/'mesh_queue_state.json').get('status')=='done'
 assert rt.read(D/'candidate.json')['change']['outer_base_m_after']==.2875
 with LOCK.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'token':TOKEN,'at':rt.now()},f)
 try:
  deadline=time.monotonic()+2400
  state('waiting_for_geometry_and_mapping')
  while True:
   b=rt.read(D/'build_state.json')
   assert rt.resource_problem() is None
   if b.get('status')=='needs_review':raise RuntimeError('Build needs review: '+str(b.get('error')))
   if b.get('status')=='ready_for_flow':break
   assert time.monotonic()<deadline,'Build handoff timeout; no extra solver launched'
   if (D/'STOP').exists():raise RuntimeError('User stop')
   time.sleep(10)
  assert datetime.now().date()==datetime(2026,10,31).date()
  state('independent_protected_geometry_audit')
  with (D/'protected_audit.log').open('x',encoding='utf-8') as f:
   a=subprocess.run([str(PY),str(R/'audit_M13_protected_regions.py')],stdout=f,stderr=subprocess.STDOUT,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
  assert a.returncode==0 and rt.read(D/'protected_audit/protected_regions_pass.json').get('pass') is True,'Protected geometry audit failed'
  plan=rt.read(D/'candidate.json');cells=plan['actual_cells'];assert cells<317277,'M13 is not lighter than M10'
  mapping=rt.read(D/'mapped/mapping_audit.json');assert mapping.get('pass') is True
  source=D/'mapped/mapped.sim';start=mapping['time_s'];dt=.0004
  assert source.is_file() and rt.resource_problem() is None
  gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
  assert gpu.returncode==0 and int(gpu.stdout.strip().splitlines()[0])>=4000,'GPU unavailable'
  assert rt.read(R/'mesh_queue_state.json').get('status')=='done' and not (R/'mesh_queue_launch.lock').exists()
  macro=B/'ContinueCalmGPULive.java';receipt=rt.read(B/'gpu_live_macro_receipt.json')
  assert receipt.get('status')=='javac_passed' and receipt.get('GPU_macro_sha256')==rt.sha(macro)
  runtime=(R/'owned_experiment_runtime_20261031.py').read_text(encoding='utf-8')
  anchor="    if reason:(folder/'STOP').touch()"
  assert runtime.count(anchor)==1
  replacement="""    if phase=='foil' and reason is None:
     import mesh_queue_worker_M10_dt4_20261031 as checks
     checks.DT=.0004
     primary=checks.project_check(folder,[])
     if primary:
      write(folder/'project_primary_evidence.json',primary)
      reason='project_primary_two_passes'
    if reason:(folder/'STOP').touch()"""
  runtime=runtime.replace(anchor,replacement,1)
  runtime=runtime.replace("assert reason is None,'Bounded stage stopped: '+str(reason)","assert reason in (None,'project_primary_two_passes'),'Bounded stage stopped: '+str(reason)")
  helper=D/'M13_flow_runtime.py';assert not helper.exists();helper.write_text(runtime,encoding='utf-8')
  spec=importlib.util.spec_from_file_location('M13_flow_runtime',helper);run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
  OUT.mkdir();(OUT/'prior_history.csv').write_text('wall_seconds,step,iteration,physical_time_s,dt_s,Fx_slice_N,Fz_slice_N,pressure_drag_N,viscous_drag_N,CD,CL_total,max_velocity_m_s,max_CFL,interface_max_CFL,mean_yplus,min_yplus,max_yplus,CL\n',encoding='utf-8')
  env=dict(NTNU_STAB_OUT=str(OUT),NTNU_MAP_OUT=str(OUT),NTNU_STAB_DT=str(dt),NTNU_STAB_TARGET=str(start+1.2),NTNU_STAB_INNER='10',NTNU_STAB_CELLS=str(cells),NTNU_STAB_START=str(start),NTNU_STAB_INIT='false',NTNU_STAB_ORDER='SECOND_ORDER',NTNU_STAB_BUDGET='4200',NTNU_STAB_PRIOR_HISTORY=str(OUT/'prior_history.csv'),NTNU_CALM_SETTLE='true',NTNU_GCI_MAX_CFL='25',NTNU_GCI_INTERFACE_CFL='1')
  plan.update(status='flow_launch_requested',flow_solver_started=True);rt.write(D/'candidate.json',plan)
  state('launching_GPU_calm',cells=cells,dt_s=dt,start_time_s=start)
  run.stage(OUT,source,macro,env,workers=1,gpu=True,mask=sum(1<<i for i in (4,5,6,7)),budget_s=4500,phase='foil')
  done=rt.read(OUT/'completed.json');export=rt.read(OUT/'EXPORT_OK.json');ev=rt.read(OUT/'project_primary_evidence.json')
  assert done.get('status') in ('stopped_by_marker','stabilized','target_reached') and (OUT/'final.sim').is_file()
  assert export.get('time_s')==done.get('time_s'),'Final export receipt missing'
  accepted=bool(ev.get('raw_independently_recomputed') and len(ev.get('checks_s',[]))==2)
  rt.write(OUT/'queue_stage_result.json',{'stage':'M13','project_primary_pass':accepted,'done':done,'two_primary_checks':ev,'output':str(OUT),'at':rt.now(),'source_preserved':True})
  plan.update(status='flow_saved_primary_accepted' if accepted else 'flow_saved_review_required');rt.write(D/'candidate.json',plan)
  state(plan['status'],time_s=done.get('time_s'),project_primary_pass=accepted)
 except BaseException as ex:
  state('needs_review_no_retry',error=rt.guard.redact(str(ex))[:600]);raise
 finally:
  if rt.read(LOCK).get('token')==TOKEN:LOCK.unlink()
if __name__=='__main__':main()
