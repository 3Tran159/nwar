"""One bounded copied-state API/monitor audit; NEVER requests CFD steps or saves .sim."""
from pathlib import Path
from datetime import datetime
import os,sys,json,shutil,subprocess,threading,time,re,uuid
R=Path(r'E:\ntnu_mesh_optimization_20261030');W=R/'wave_surface_only';D=W/'failure_diagnostic_20261031_2323'
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
sys.path.insert(0,str(R));import wave_halfstep_runtime_20261031 as rt
OUT=D/'flat_calm_zero_step';M=D/'AuditWaveSetupZeroStep.java'
SOURCE=W/'WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c'/'calm_pilot_final.sim'
LOCKS=[R/'parallel_cpu_20261031'/'auxiliary.lock',W/'wave_inlet.lock',W/'wave_mesh_comparison.lock',W/'wave_pressure_audit.lock']
def active_star():
 return {pid:name for pid,(parent,name) in rt.guard.processes().items() if name.lower() in ('starccm+.exe','star-ccm+.exe')}
def main():
 assert datetime.now().astimezone()<datetime.fromisoformat('2026-11-01T09:00:00+01:00')
 assert not OUT.exists(),'One-shot audit already attempted'
 assert rt.sha(R/'AUTONOMOUS_RECOVERY_PROMPT.md')==rt.read(R/'plan.json')['recovery_policy']['runbook_sha256']
 assert rt.resource_problem() is None,rt.resource_problem()
 assert rt.read(F/'campaign_hold.json').get('active') is True
 assert not (R/'m13_wave_gpu.lock').exists(),'GPU pilot ownership conflict'
 assert not active_star(),'Existing STAR execution; no competing audit'
 assert not any(p.exists() for p in LOCKS),'Existing auxiliary/wave ownership'
 assert rt.sha(SOURCE)=='fdc5d295ac806813dbc783f6ba30c9e626f2ee5c2f91b7825164e69660bc5d28'
 assert (D/'compiled'/'macro'/'AuditWaveSetupZeroStep.class').is_file(),'Compile audit first'
 code=M.read_text(encoding='utf-8');assert 'getSimulationIterator()' not in code and 'saveState(' not in code and 'initializeSolution(' not in code
 token=uuid.uuid4().hex;captured=[];proc=None
 try:
  for p in LOCKS:
   with p.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'at':rt.now(),'token':token,'kind':'zero_step_state_audit','directory':str(OUT)},f)
   captured.append(p)
  assert not active_star(),'STAR appeared during audit lock acquisition'
  OUT.mkdir(exist_ok=False);rt.set_owned_affinity(1<<22)
  digest=rt.sha(SOURCE);shutil.copy2(SOURCE,OUT/'input.sim');assert rt.sha(OUT/'input.sim')==digest
  shutil.copy2(M,OUT/M.name)
  rt.write(OUT/'decision.json',{'at':rt.now(),'purpose':'read normalization/legacy report bindings; test analytical wave period evaluation without CFD','source':str(SOURCE),'source_sha256':digest,'macro_sha256':rt.sha(M),'solver_steps_requested':0,'source_save_allowed':False,'workers':1,'gpu':False,'priority':'BELOW_NORMAL','no_BC_binding_changes':True})
  env=dict(os.environ,NTNU_ZERO_STEP_AUDIT_OUT=str(OUT))
  args=[str(rt.guard.STAR),*rt.guard.saved_options(1),'-batch',str(OUT/M.name),str(OUT/'input.sim')]
  with (OUT/'star.log').open('x',encoding='utf-8') as log:
   proc=subprocess.Popen(args,cwd=OUT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   rt.write(OUT/'process.json',{'at':rt.now(),'pid':proc.pid,'controller_pid':os.getpid(),'zero_step_audit':True})
   def drain():
    for line in proc.stdout:log.write(rt.guard.redact(line));log.flush()
   thread=threading.Thread(target=drain,daemon=True);thread.start()
   try:proc.wait(timeout=420)
   except subprocess.TimeoutExpired:
    rt.write(OUT/'audit_timeout.json',{'at':rt.now(),'action':'No restart or forced kill. Keep locks until all native processes verified ended.','pid':proc.pid});return
   thread.join(20)
  text=(OUT/'star.log').read_text(encoding='utf-8',errors='replace')
  natives=re.findall(r'Process rank\s+\d+\s+\S+\s+(\d+)',text)
  result={'at':rt.now(),'exit_code':proc.returncode,'marker_complete':'ZERO_STEP_AUDIT_COMPLETE_NO_STEPS_NO_SAVE' in text,'source_hash_unchanged':rt.sha(SOURCE)==digest,'input_hash_unchanged':rt.sha(OUT/'input.sim')==digest,'solver_timestep_lines':len(re.findall(r'^TimeStep\s+',text,re.M)),'native_pids':[int(x) for x in natives],'period':rt.read(OUT/'period_evaluation_audit.json'),'report':str(OUT/'monitor_audit.json')}
  rt.write(OUT/'receipt.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
 finally:
  # A dead frontend is insufficient. Do not release while any native STAR remains.
  if not active_star() and (proc is None or proc.poll() is not None):
   for p in reversed(captured):
    if rt.read(p).get('token')==token:p.unlink()
  elif captured:rt.write(D/'audit_retained_ownership.json',{'at':rt.now(),'reason':'Native STAR or frontend remains; retain lock, never automatic retry','native_processes':active_star()})
if __name__=='__main__':main()
