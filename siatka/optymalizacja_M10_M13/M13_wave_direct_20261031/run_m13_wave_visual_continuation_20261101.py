"""Conditional long M13 GPU foil+wave continuation from a verified finished R2 pilot.
Independent output, same bound wave and physical fields, no wave re-initialization.
Never launch automatically without command --run and all scientific checks.
"""
from pathlib import Path
from datetime import datetime
import sys,os,json,subprocess,math,time
R=Path(r"E:\ntnu_mesh_optimization_20261030")
P=R/"M13_wave_direct_20261031"
W=R/"wave_surface_only"
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
PRIOR=P/"M13_GPU_W20_H050_pilot_20261031_r2"
SOURCE=PRIOR/"wave_pilot_final.sim"
MACRO=P/"M13ContinueWaveR3Visual.java"
OUT=P/"M13_GPU_W20_H050_continuation_R3V_20261101"
LOCKS=[P/"M13_wave_gpu_pilot.lock",R/"m13_wave_gpu.lock",W/"wave_inlet.lock"]
sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
def val(v):
 try:
  f=float(v)
  return f if math.isfinite(f) else None
 except (TypeError,ValueError):return None
def gates():
 assert datetime.now().astimezone()<datetime.fromisoformat("2026-11-01T09:00:00+01:00"),"Night authorization expired"
 plan=rt.read(R/"plan.json")
 assert rt.sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"]
 assert rt.resource_problem() is None,rt.resource_problem()
 assert rt.read(F/"campaign_hold.json").get("active") is True,"Historical foil-wave hold must stay untouched"
 assert not OUT.exists() and not any(k.exists() for k in LOCKS),"Previous stage/controller still owns GPU or wave resources"
 assert not (P/"M13_GPU_W20_H050_continuation_R3_20261101").exists(),"Another R3 continuation already exists; inspect, do not duplicate"
 compile_r3=rt.read(P/"m13_wave_visual_compile_receipt.json")
 assert compile_r3.get("status")=="javac_pass"
 assert rt.sha(MACRO)==compile_r3["new_sha256"] and (P/"compiled_r3visual"/"macro"/"M13ContinueWaveR3Visual.class").is_file()
 prior_result=rt.read(PRIOR/"stage_result.json")
 done=rt.read(PRIOR/"completed.json")
 accepted=rt.read(PRIOR/"pilot_result.json")
 assert prior_result.get("exit_code")==0 and prior_result.get("source_unchanged") is True and prior_result.get("controller_reason") is None
 assert done.get("status") in ("target_reached","wall_budget") and accepted.get("pilot_saved") is True
 assert done.get("propagation_validated") is False,"Short startup pilot must not be misclassified"
 history=rt.rows(PRIOR/"history.csv")
 assert len(history)>=500 and int(history[-1]["step"])>=500
 t=val(history[-1].get("time_s")); dt0=val(history[-1].get("wall_s"))
 assert t is not None and t>4.095 and abs(t-float(done["time_s"]))<1e-7
 assert all(val(history[-1].get(k)) is not None for k in
   ("CL_hydrodynamic","CD_total","max_CFL","max_speed_m_s","water_volume_m3","alpha_min","alpha_max","p_min_Pa","p_max_Pa"))
 assert 0<=float(history[-1]["alpha_min"]) and float(history[-1]["alpha_max"])<=1.00001
 assert float(history[-1]["max_CFL"])<25 and float(history[-1]["max_speed_m_s"])<50
 assert 30<float(history[-1]["water_volume_m3"])<45 and -1e7<float(history[-1]["p_min_Pa"]) and float(history[-1]["p_max_Pa"])<1e7
 source_audit=rt.read(PRIOR/"wave_setup_audit.json")
 assert source_audit.get("cells")==309441 and source_audit.get("foil_present") is True and source_audit.get("wave_inlet_only") is True
 assert source_audit.get("global_initialization") is False and source_audit.get("scientific_accepted") is False
 assert SOURCE.is_file() and SOURCE.stat().st_size>300000000
 first_failed=rt.read(P/"M13_GPU_W20_H050_pilot_20261031"/"macro_error.json")
 assert first_failed.get("error")=="java.lang.IllegalStateException: Unexpected wave period"
 assert not rt.guard.alive(rt.read(PRIOR/"process.json").get("pid")),"R2 source process still alive"
 # Prevent accidental double GPU or overwrite. Existing UI/HF processes are not solver instances.
 procs=rt.guard.processes()
 other=[(pid,name) for pid,(parent,name) in procs.items()
  if name.lower().startswith(("starccm+","star-ccm+"))]
 assert not other,"Existing STAR solver(s) still alive: "+str(other)
 smi=subprocess.run(["nvidia-smi","--query-gpu=memory.free,utilization.gpu","--format=csv,noheader,nounits"],
   capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
 assert smi.returncode==0,"GPU query unavailable"
 gpu=int(smi.stdout.splitlines()[0].split(",")[0].strip())
 assert gpu>=4000,"Insufficient GPU memory"
 return {"at":rt.now(),"source":str(SOURCE),"source_sha256":rt.sha(SOURCE),
   "start_physical_s":t,"last_saved_CL_hydro":val(history[-1]["CL_hydrodynamic"]),
   "last_saved_CD_total":val(history[-1]["CD_total"]),"last_saved_CFL":val(history[-1]["max_CFL"]),
   "macro_sha256":rt.sha(MACRO),"gpu_free_mib":gpu,"M13_cells":309441,
   "dt_s":.0004,"steps":12000,"budget_s":14000,"wave_origin_s":3.899199999999636,
   "lambda_m":20,"H_m":.5,"model":"FifthOrderVofWave already bound in source",
   "interpretation":"Exploratory continuation; post-arrival periodicity and wave accuracy unverified"}
def main():
 checked=gates()
 if "--preflight-only" in sys.argv:
  print(json.dumps({"preflight":"PASS","at":rt.now(),"source":str(SOURCE),"time_s":checked["start_physical_s"],
   "source_sha256":checked["source_sha256"],"gpu_free_mib":checked["gpu_free_mib"],"solver_started":False}),flush=True);return
 if "--run" not in sys.argv:raise RuntimeError("--run or --preflight-only required")
 taken=[]
 try:
  for lock in LOCKS:
   with lock.open("x",encoding="utf-8") as f:json.dump({"pid":os.getpid(),"source_sha256":checked["source_sha256"],"at":rt.now(),"scope":"M13_wave_continuation"},f)
   taken.append(lock)
  OUT.mkdir(exist_ok=False)
  rt.write(OUT/"decision.json",dict(checked,source_preserved=True,old_F_hold_preserved=True,
   ready_for_20_cycles=False,auto_acceptance=False,old_R2_unmodified=True))
  rt.write(P/"M13_wave_visual_continuation_status.json",{"status":"starting","at":rt.now(),"directory":str(OUT)})
  env={"NTNU_M13_WAVE_OUT":str(OUT),"NTNU_M13_WAVE_DT":".0004",
       "NTNU_M13_WAVE_STEPS":"12000","NTNU_M13_WAVE_INNER":"10",
       "NTNU_M13_WAVE_BUDGET":"14000","NTNU_M13_WAVE_START_T":str(checked["start_physical_s"])}
  folder,stage=rt.stage(OUT,SOURCE,MACRO,env=env,workers=1,gpu=True,mask=240,
    budget_s=14300,protect_main=False,phase="M13_foil_wave_R3_continuation")
  latest=rt.rows(OUT/"history.csv")
  done=rt.read(OUT/"completed.json")
  finite=bool(latest and val(latest[-1].get("CL_hydrodynamic")) is not None and val(latest[-1].get("CD_total")) is not None)
  saved=bool(stage["exit_code"]==0 and stage.get("source_unchanged") and done.get("status") in ("target_reached","wall_budget")
             and finite and (OUT/"wave_pilot_final.sim").exists())
  report={"status":"saved_exploratory" if saved else "incomplete","at":rt.now(),
   "source_unchanged":rt.sha(SOURCE)==checked["source_sha256"],"completed":done,
   "latest_force_history_row":latest[-1] if latest else None,"wave_propagation_validated":False,
   "force_cycles_validated":False}
  rt.write(OUT/"continuation_result.json",report)
  rt.write(P/"M13_wave_visual_continuation_status.json",dict(report,directory=str(OUT)))
  print(json.dumps({"event":"M13_wave_R3_continuation_result","saved":saved,"steps":done.get("steps"),"t":done.get("time_s"),"validation":False}))
 except BaseException as ex:
  if OUT.exists():
   (OUT/"STOP").touch()
   rt.write(OUT/"controller_error.json",{"at":rt.now(),"type":type(ex).__name__,"error":rt.guard.redact(str(ex))[:600],"no_auto_retry":True})
   rt.write(P/"M13_wave_visual_continuation_status.json",{"status":"failed_or_guarded","directory":str(OUT),"at":rt.now()})
  raise
 finally:
  front=rt.read(OUT/"process.json").get("pid") if OUT.exists() else None
  if not front or not rt.guard.alive(front):
   for lock in reversed(taken):
    if rt.read(lock).get("source_sha256")==checked["source_sha256"]:lock.unlink()
if __name__=="__main__":main()
