"""One isolated GPU M13 calm->inlet-wave pilot authorized by the user.
No wave-only prerequisite, no F:/ legacy C01 hold changes, no remeshing or old solver scripts edited.
Check preflight explicitly before --run. Pilot completion != wave-propagation acceptance.
"""
from pathlib import Path
from datetime import datetime
import os,sys,json,hashlib,subprocess,shutil,time
R=Path(r"E:\ntnu_mesh_optimization_20261030")
P=R/"M13_wave_direct_20261031"
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
W=R/"wave_surface_only"
SOURCE=R/"M13_farfield15_20261031"/"M13_GPU_calm_dt0004"/"final.sim"
MACRO=P/"M13InletWavePilot.java"
OUT=P/"M13_GPU_W20_H050_pilot_20261031"
LOCKS=[P/"M13_wave_gpu_pilot.lock",R/"m13_wave_gpu.lock",W/"wave_inlet.lock"]
sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
def time_local():return datetime.now().astimezone()
def m13_preflight():
 now=time_local()
 assert now<datetime.fromisoformat("2026-11-01T09:00:00+01:00"),"Overnight authorization ended"
 plan=rt.read(R/"plan.json")
 assert rt.sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"],"Changed runbook"
 assert plan["selection"]["lightweight_optimization_screen"]["both_required"] and plan["selection"]["lightweight_optimization_screen"]["max_abs_relative_difference_each_pct"]==5
 assert rt.resource_problem() is None,rt.resource_problem()
 assert not OUT.exists(),"Attempt already exists; cannot overwrite/duplicate"
 assert not any(x.exists() for x in LOCKS),"Another owned wave controller is holding locks"
 assert rt.read(F/"campaign_hold.json").get("active") is True,"Legacy campaign hold unexpectedly changed"
 assert rt.read(R/"M13_farfield15_20261031"/"flow_state.json").get("status")=="flow_saved_primary_accepted","M13 not saved"
 done=rt.read(SOURCE.parent/"completed.json")
 export=rt.read(SOURCE.parent/"EXPORT_OK.json")
 evidence=rt.read(SOURCE.parent/"project_primary_evidence.json")
 assert done.get("status")=="stopped_by_marker" and done.get("steps")>=1500 and abs(float(done.get("time_s",0))-3.8992)<.00000001
 assert export.get("cells")==309441 and abs(float(export.get("time_s",0))-float(done["time_s"]))<.00000001
 assert evidence.get("raw_independently_recomputed") is True and len(evidence.get("checks_s",[]))==2
 assert SOURCE.is_file() and SOURCE.stat().st_size>400000000
 assert MACRO.is_file() and MACRO.stat().st_size>12000
 assert (P/"compiled"/"macro"/"M13InletWavePilot.class").is_file(),"Macro not compiled"
 assert rt.guard.alive(9352) is False,"M13 calm GPU solver has not ended"
 failed=rt.read(W/"WAVE_H050_pressure_aligned_CPU1_20261031_once"/"stage_result.json")
 assert failed.get("exit_code")==1 and failed.get("source_unchanged") is True
 history=W/"WAVE_H050_pressure_aligned_CPU1_20261031_once"/"history.csv"
 assert history.exists() and time.time()-history.stat().st_mtime>600,"Old CPU wave attempt still progressing"
 processes=rt.guard.processes()
 unexpected=[(pid,name) for pid,(parent,name) in processes.items()
   if (name.lower().startswith("starccm+") or name.lower().startswith("star-ccm+"))
   and pid not in (30288,3520,6932)]
 assert not unexpected,"Unexpected STAR-CCM server/process already active: "+str(unexpected)
 # Known PIDs above are proven abandoned child processes from the failed CPU1 wave experiment.
 # Do not touch or terminate their process trees. This independent pilot uses the idle GPU.
 smi=subprocess.run(["nvidia-smi","--query-gpu=memory.free,utilization.gpu","--format=csv,noheader,nounits"],
   capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
 assert smi.returncode==0, "GPU query failed"
 vals=smi.stdout.strip().splitlines()[0].split(",")
 gpu_free=int(vals[0].strip());gpu_util=int(vals[1].strip())
 assert gpu_free>=4000 and gpu_util<=45,"GPU memory unavailable or active GPU workload"
 return {"at":now.isoformat(),"project":"M13 calm->upstream inlet wave H0.5 lambda20",
   "candidate_cells":309441,"source":str(SOURCE),"source_sha256":rt.sha(SOURCE),
   "macro":str(MACRO),"macro_sha256":rt.sha(MACRO),"time_s":float(done["time_s"]),
   "gpu_free_mib":gpu_free,"gpu_util_pct":gpu_util,"unknown_active_star":unexpected,
   "old_failed_cpu_wave_orphans":[30288,3520,6932],"legacy_hold_active":True,
   "source_untouched":True,"no_full_wave_claim":True,"pilot_dt_s":.0004,"steps":1200,
   "processor":"1 GPU, 1 worker","outputs_E_only":True}
def main():
 state=m13_preflight()
 if "--preflight-only" in sys.argv:
  print(json.dumps({"preflight":"PASS","time":state["at"],"source_sha256":state["source_sha256"],
    "gpu_free_mib":state["gpu_free_mib"],"old_cpu_wave_orphans_present":True,"no_solver_started":True}),flush=True)
  return
 if "--run" not in sys.argv:raise RuntimeError("Specify --preflight-only or --run; no implicit launch")
 captured=[]
 try:
  for lock in LOCKS:
   with lock.open("x",encoding="utf8") as f:json.dump({"pid":os.getpid(),"at":state["at"],"purpose":"isolated_M13_gpu_wave","source_sha256":state["source_sha256"]},f)
   captured.append(lock)
  OUT.mkdir(exist_ok=False)
  rt.write(OUT/"decision.json",dict(state,source_safety="calm M13 source untouched",
   wave_only_blocker_acknowledged="This exploratory pilot skips no-foil wave acceptance by explicit later user order",
   wave_setup="M13 flat field, inlet FifthOrder ramp, no whole-domain reinitialization",
   foil_force_stat_status="Pre-arrival reference provisional only",
   numerics="dt=.0004s, 10inner, second-order, bounded 1200 steps, stop on numerical guard",
   old_campaign_hold="unchanged on F:", scientific_validation="NOT YET ACCEPTED"))
  env={"NTNU_M13_WAVE_OUT":str(OUT),"NTNU_M13_WAVE_DT":".0004",
    "NTNU_M13_WAVE_STEPS":"1200","NTNU_M13_WAVE_INNER":"10","NTNU_M13_WAVE_BUDGET":"2200"}
  rt.write(P/"M13_wave_status.json",{"status":"starting","at":rt.now(),"directory":str(OUT),"source":str(SOURCE)})
  folder,stage=rt.stage(OUT,SOURCE,MACRO,env=env,workers=1,gpu=True,mask=240,budget_s=2400,protect_main=False,phase="isolated_M13_gpu_foil_wave_pilot")
  completed=rt.read(OUT/"completed.json");hist=rt.rows(OUT/"history.csv")
  last=hist[-1] if hist else {}
  accepted_pilot=bool(completed.get("status") in ("target_reached","wall_budget") and
    len(hist)>=50 and float(last.get("time_s",0))>3.92 and
    completed.get("propagation_validated") is False and (OUT/"wave_pilot_final.sim").is_file())
  result={"at":rt.now(),"pilot_saved":accepted_pilot,"not_full_wave_validation":True,
   "last_measured_step":last.get("step"),"last_physical_time_s":last.get("time_s"),
   "completion":completed,"source_unchanged":rt.sha(SOURCE)==state["source_sha256"]}
  rt.write(OUT/"pilot_result.json",result)
  rt.write(P/"M13_wave_status.json",{"status":"saved_exploratory_pilot" if accepted_pilot else "pilot_incomplete",
    "directory":str(OUT),"at":rt.now(),"progress":result,"propagation_validated":False})
  print(json.dumps({"event":"M13_GPU_foil_wave_pilot_result","saved":accepted_pilot,
   "steps":completed.get("steps"),"time_s":completed.get("time_s"),"wave_validated":False}),flush=True)
 except BaseException as exc:
  if OUT.is_dir():
   (OUT/"STOP").touch()
   rt.write(OUT/"controller_error.json",{"at":rt.now(),"type":type(exc).__name__,
      "message":rt.guard.redact(str(exc))[:650],"no_auto_retry":True})
   rt.write(P/"M13_wave_status.json",{"status":"failed_or_guarded","at":rt.now(),"directory":str(OUT)})
  raise
 finally:
  frontend=rt.read(OUT/"process.json").get("pid") if OUT.exists() else None
  alive=bool(frontend and rt.guard.alive(frontend))
  # Leave own lock if frontend still exists, to prevent simultaneous rerun.
  if not alive:
   for lock in reversed(captured):
    if rt.read(lock).get("source_sha256")==state["source_sha256"]:lock.unlink()
if __name__=="__main__":main()
