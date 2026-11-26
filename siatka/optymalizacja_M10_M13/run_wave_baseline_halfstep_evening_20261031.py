"""Isolated 0.5 ms temporal diagnostic from the SAME healthy baseline calm state.
Only dt changes versus the failed 1 ms attempt; no acceptance or relaxed guards.
"""
from pathlib import Path
import sys,os,json,uuid,shutil
R=Path(r'E:\ntnu_mesh_optimization_20261030');W=R/'wave_surface_only';sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
OLD=W/'zero_start_matrix_evening_20261031_182305_689cb9/waves/L20_H500_baseline'
OUT=W/'zero_start_matrix_evening_dt05_20261031/waves/L20_H500_baseline'
LOCKS=[R/'parallel_cpu_20261031/auxiliary.lock',W/'wave_inlet.lock',W/'wave_mesh_comparison.lock']
TOKEN=uuid.uuid4().hex
# Separate runtime: preserve the running M13 builder's loaded module and source file.
text=(R/'owned_experiment_runtime_20261031.py').read_text(encoding='utf-8')
anchor="    if reason:(folder/'STOP').touch()"
assert text.count(anchor)==1
text=text.replace(anchor,"""    if (folder/'macro_error.json').exists():
     failure=read(folder/'macro_error.json')
     reason=reason or 'macro_error'
     lost='Connection reset' in str(failure.get('error',''))
     hist=folder/'history.csv'
     stale=hist.exists() and time.time()-hist.stat().st_mtime>120
     saving=any(time.time()-f.stat().st_mtime<90 for f in folder.glob('*.sim'))
     if lost and stale and not saving:
      write(folder/'failed_client_shutdown.json',{'at':now(),'pid':proc.pid,'reason':'Lost server, stale steps, no save in progress; own process only'})
      subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    if reason:(folder/'STOP').touch()""",1)
runtime=R/'wave_halfstep_runtime_20261031.py'
assert not runtime.exists();runtime.write_text(text,encoding='utf-8')
import wave_halfstep_runtime_20261031 as wr

def main():
 assert not OUT.exists() and not any(p.exists() for p in LOCKS),'Previous wave controller still owns resources'
 assert rt.resource_problem() is None
 evidence=rt.read(OLD/'verified_failed_frontend_shutdown.json');assert evidence.get('taskkill_returncode')==0
 assert not rt.guard.alive(27088) and not rt.guard.alive(22592),'Previous controller not fully ended'
 source=Path(rt.read(OLD/'identity.json')['source'])
 assert rt.sha(source)==rt.read(OLD/'identity.json')['source_sha256']
 done=rt.read(source.parent/'completed.json');assert abs(done.get('time_s',0)-.4)<1e-8
 hist=rt.rows(source.parent/'history.csv');assert hist and abs(float(hist[-1]['max_speed_m_s'])-18)<.1
 original=OLD/'WaveFromOwnCalm_20261031.java'
 assert original.is_file()
 macrotext=original.read_text(encoding='utf-8');assert macrotext.count('private final double t0=.4, dt=.001;')==1
 macrotext=macrotext.replace('WaveFromOwnCalm_20261031','WaveFromOwnCalmDtHalfEvening').replace('private final double t0=.4, dt=.001;','private final double t0=.4, dt=.0005;')
 macro=OUT.parent.parent/'WaveFromOwnCalmDtHalfEvening.java';macro.parent.mkdir(parents=True,exist_ok=False);macro.write_text(macrotext,encoding='utf-8')
 captured=[]
 try:
  for lk in LOCKS:
   with lk.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'token':TOKEN,'kind':'baseline_temporal_dt05_diagnostic','at':rt.now()},f)
   captured.append(lk)
  rt.write(OUT.parent.parent/'decision.json',{'at':rt.now(),'old_attempt':str(OLD),'only_numerical_change':'dt 0.001 to 0.0005 s','same_mesh_cells':53200,'same_CPU_workers':1,'same_inner':10,'same_calm_source':str(source),'steps':1600,'purpose':'Bounded timestep diagnostic; not full propagation validation','original_wave_hold_preserved':True})
  env={'NTNU_NOFOIL_WAVE_OUT':str(OUT),'NTNU_NOFOIL_OUT':str(OUT),'NTNU_NOFOIL_CELLS':'53200','NTNU_NOFOIL_WATER_M3':'38.4','NTNU_NOFOIL_LAMBDA':'20','NTNU_NOFOIL_H':'.5','NTNU_NOFOIL_XMIN':'-35','NTNU_NOFOIL_XMAX':'45','NTNU_NOFOIL_WAVE_PERIOD_S':str(20/23.612),'NTNU_NOFOIL_WAVE_STEPS':'1600'}
  rt.write(W/'evening_wave_dt05_state.json',{'at':rt.now(),'status':'starting','directory':str(OUT),'controller_pid':os.getpid(),'dt_s':.0005})
  wr.stage(OUT,source,macro,env,workers=1,mask=1<<22,budget_s=3000,protect_main=True,phase='waves')
  rt.write(W/'evening_wave_dt05_state.json',{'at':rt.now(),'status':'saved_pending_review','directory':str(OUT),'completed':rt.read(OUT/'completed.json')})
 except BaseException as ex:
  rt.write(W/'evening_wave_dt05_state.json',{'at':rt.now(),'status':'failed_or_guarded','directory':str(OUT),'error':rt.guard.redact(str(ex))[:400]});raise
 finally:
  for lk in reversed(captured):
   if rt.read(lk).get('token')==TOKEN:lk.unlink()
if __name__=='__main__':main()
