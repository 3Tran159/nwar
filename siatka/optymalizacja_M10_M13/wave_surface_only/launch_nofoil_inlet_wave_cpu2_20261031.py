"""Guarded independent no-foil FifthOrder inlet-wave startup from verified t=0.4s calm throughflow.
It does not resume held C01/foil-wave, change M12, or certify propagation.
Only one CPU2 solver, own E: output, atomic auxiliary/wave locks and STOP.
"""
import os,sys,time,math,json,hashlib,datetime,uuid,subprocess,threading,shutil,csv,statistics,urllib.request
from pathlib import Path
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030")
WAVE=ROOT/"wave_surface_only"
PAR=ROOT/"parallel_cpu_20261031"
STUDY=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
CALM=WAVE/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"
MACRO=WAVE/"NoFoilInletWavePilot.java"
sys.path.insert(0,str(PAR))
import bounded_cpu_pilot as guard
DATE=datetime.date(2026,10,31)
DT=.001
STEPS=500
def now():return datetime.datetime.now().astimezone().isoformat()
def read(p):return guard.read(p)
def write(p,x):return guard.write(p,x)
def sha(p):return guard.sha(p)
def log(msg,**details):print(json.dumps({"at":now(),"event":msg,**details},ensure_ascii=False),flush=True)
def journal(name,obj):
 obj={"at":now(),**obj}
 with (ROOT/name).open("a",encoding="utf8") as f:
  f.write(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n")
  f.flush();os.fsync(f.fileno())
def check_resources():
 if (WAVE/"STOP_ALL").exists() or (ROOT/"STOP_ALL").exists() or (PAR/"STOP_ALL").exists():
  return "scope_STOP_ALL"
 if (Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")/"STOP_ALL").exists():
  return "global_STOP_ALL"
 if guard.free_memory()<16*guard.GIB:return "RAM_below_16GiB"
 if shutil.disk_usage("C:/").free<15*guard.GIB:return "C_below_15GiB"
 if shutil.disk_usage(WAVE).free<25*guard.GIB:return "E_below_25GiB"
 state=read(STUDY/"gpu_study_state.json")
 if state.get("status") not in ("pause_save_finished","paused"):
  return "main_campaign_stage_or_pause_changed"
 if guard.alive(state.get("star_pid")):return "main_solver_active_unexpected"
 return None
def safe_local_api():
 with urllib.request.urlopen("http://127.0.0.1:8771/api/mesh-study",timeout=5) as response:
  assert response.status==200
  data=json.load(response)
  return data.get("status")
def hist_guard():
 p=CALM/"history.csv"
 with p.open(newline="",encoding="utf-8-sig") as f:
  rows=list(csv.DictReader(f))
 assert len(rows)>=401,"Missing full flat throughflow history"
 last=rows[-1]
 assert int(float(last["step"]))==400
 assert abs(float(last["time_s"])-.4)<1e-9
 assert abs(float(last["max_speed_m_s"])-18)<.05
 assert abs(float(last["water_volume_m3"])-38.4)<.005
 assert float(last["max_CFL"])<1
 with (CALM/"gauges.csv").open(newline="",encoding="utf-8-sig") as f:
  gauges=list(csv.DictReader(f))
 assert len(gauges)>=200
 assert max(abs(float(g["eta_actual_m"])) for g in gauges)<.002
 return {"last":last,"max_abs_eta_m":max(abs(float(g["eta_actual_m"])) for g in gauges),"gauge_rows":len(gauges)}
def active_solving():
 # The GUI-only STAR launcher is not a running solver. A second STAR solver is a conflict.
 ps=guard.processes()
 return sorted([{"pid":pid,"name":name} for pid,(_,name) in ps.items()
  if name.lower() in {"star-ccm+.exe","starccm+.exe"}],key=lambda row:row["pid"])
def owned_star_pids(folder):
 """Identity-based STAR client/server check, including server detached by .bat shell."""
 name=folder.name
 assert name.startswith("WS_L20_H050_baseline_inlet_wave_CPU2_") and all(c.isalnum() or c=="_" for c in name)
 ps=(
  "$needle='"+name+"';"
  "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'starccm+.exe' -or $_.Name -eq 'star-ccm+.exe' } | ForEach-Object {"
  "$c=[string]$_.CommandLine;"
  r"$m=[regex]::Match($c,'-xencoded-session\s+([^\s]+)');"
  "$decoded='';if($m.Success){try{$decoded=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($m.Groups[1].Value))}catch{}};"
  "if($c.Contains($needle) -or $decoded.Contains($needle)){Write-Output $_.ProcessId}"
  "}"
 )
 result=subprocess.run(["powershell.exe","-NoProfile","-Command",ps],
  stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=15)
 if result.returncode!=0:raise RuntimeError("STAR ownership CIM query failed")
 return {int(x.strip()) for x in result.stdout.splitlines() if x.strip().isdigit()}
def main():
 plan=read(ROOT/"plan.json")
 assert sha(ROOT/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"],"Runbook hash mismatch"
 p=plan["parallel_execution"]
 assert p["authorized"] and p["maximum_auxiliary_solvers"]==1
 assert datetime.datetime.now().astimezone().date()==DATE
 assert datetime.datetime.now().hour<12,"No new wave launch at/after noon without scope review"
 assert read(WAVE/"plan.json")["geometry_validation"]["topology_geometry_pass"]
 assert read(WAVE/"baseline_dataset_equivalence.json")["numerical_mesh_equivalent"]
 assert not active_solving(), "An unexpected STAR CFD solver process is active"
 assert check_resources() is None,check_resources()
 assert safe_local_api()=="paused","Main paused state not confirmed by read-only API"
 previous=read(PAR/"current.json")
 assert previous.get("status") in ("calm_pilot_completed","wave_controller_error_saved_stop_verified",
  "wave_ramp_pilot_stopped_or_failed"),"Unknown auxiliary ownership/status"
 if previous.get("status")=="wave_ramp_pilot_stopped_or_failed":
  # Exactly one retry after a verified EXTERNAL resource conflict; never retry
  # numerical divergence, licence loss, user pause, or ambiguous STAR ownership.
  assert previous.get("reason")=="another_STAR_solver_started"
  assert previous.get("exit_code")==0 and previous.get("source_unchanged") is True
  assert previous.get("final_sim_exists") is True
  assert previous.get("completed",{}).get("status")=="stopped_by_marker"
  assert previous.get("completed",{}).get("steps")==0
  prior_folder=Path(previous["directory"])
  assert prior_folder.resolve().parent==WAVE.resolve()
  assert not (PAR/"auxiliary.lock").exists() and not (WAVE/"wave_inlet.lock").exists()
  prior_starts=[q for q in WAVE.iterdir()
   if q.is_dir() and q.name.startswith("WS_L20_H050_baseline_inlet_wave_CPU2_")]
  assert len(prior_starts)==3,"No further automatic wave restart after this final process-lineage correction"
  log("single_retry_after_foreign_STAR_conflict",verified_prior_stop=True)
 assert read(CALM/"pilot_result.json")["status"]=="calm_pilot_completed"
 assert read(CALM/"pilot_result.json")["returncode"]==0
 assert read(CALM/"pilot_result.json")["source_unchanged"] if "source_unchanged" in read(CALM/"pilot_result.json") else read(CALM/"pilot_result.json")["original_source_unchanged"]
 assert read(CALM/"completed.json")["status"]=="target_reached"
 assert read(CALM/"initial_flat_audit.json")["throughflow_current_target_m_s"]==18.0
 assert abs(read(CALM/"initial_flat_audit.json")["initial_max_velocity_m_s"]-18)<.05
 assert hist_guard()["max_abs_eta_m"]<.002
 src=CALM/"calm_pilot_final.sim"
 assert src.is_file() and src.stat().st_size>60_000_000
 assert MACRO.is_file() and MACRO.stat().st_size>8000
 source_sha=sha(src);macro_sha=sha(MACRO)
 assert source_sha and macro_sha
 assert not (PAR/"auxiliary.lock").exists() and not (WAVE/"wave_inlet.lock").exists(),"Existing lock: do not launch"
 # Locks are both atomic; if the second is blocked, release only our first acquired one.
 first=PAR/"auxiliary.lock";second=WAVE/"wave_inlet.lock";token=uuid.uuid4().hex
 with first.open("x",encoding="utf-8") as f:json.dump({"owner":"independent_nofoil_wave","token":token,"pid":os.getpid(),"at":now()},f)
 try:
  with second.open("x",encoding="utf-8") as f:json.dump({"owner":"independent_nofoil_wave","token":token,"pid":os.getpid(),"at":now()},f)
 except BaseException:
  if read(first).get("token")==token:first.unlink()
  raise
 proc=None;folder=None;stop_reason=None
 try:
  assert check_resources() is None
  assert not active_solving()
  folder=WAVE/("WS_L20_H050_baseline_inlet_wave_CPU2_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+token[:6])
  folder.mkdir(exist_ok=False)
  shutil.copy2(src,folder/"input.sim")
  assert sha(folder/"input.sim")==source_sha
  shutil.copy2(MACRO,folder/MACRO.name)
  assert sha(folder/MACRO.name)==macro_sha
  cfg={"stage":"nofoil_inlet_wave_ramp","started_at":now(),"source":str(src),
   "source_sha256":source_sha,"macro_sha256":macro_sha,"source_time_s":.4,
   "lambda_m":20,"H_m":.5,"cells":53200,"dt_s":DT,"steps":STEPS,"inner":10,
   "CPU_workers":2,"CPU_mask":guard.MASK,"gpu":False,"status":"startup_preflight",
   "no_clear_or_initialize":True,"previous_flat_current_verified":True,
   "expected_height_ramp_duration_s":1.6945346413782258,
   "no_full_wave_validation_claim":True,"C01_hold_unchanged":True,"M12_paused_unchanged":True,
   "diagnostic_only":"500-step wave ramp, record gauges/phase/VOF, not full propagation validation"}
  write(folder/"pilot_config.json",cfg)
  write(PAR/"current.json",{"status":"preparing_inlet_wave","directory":str(folder),"at":now(),"controller_pid":os.getpid(),**cfg})
  assert guard.k.SetProcessAffinityMask(guard.k.GetCurrentProcess(),guard.MASK)
  assert guard.k.SetPriorityClass(guard.k.GetCurrentProcess(),guard.BELOW_NORMAL)
  opts=guard.saved_options(2)
  assert "-gpgpu" not in opts, "Unexpected GPU allocation in CPU solver"
  cmd=[str(guard.STAR),*opts,"-batch",str(folder/MACRO.name),str(folder/"input.sim")]
  env=dict(os.environ,NTNU_NOFOIL_WAVE_OUT=str(folder),NTNU_NOFOIL_WAVE_STEPS=str(STEPS))
  started=time.monotonic();request_time=None;last_progress=-1
  with (folder/"star.log").open("x",encoding="utf-8") as stream:
   proc=subprocess.Popen(cmd,cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
    text=True,encoding="utf-8",errors="replace",
    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   write(folder/"process.json",{"pid":proc.pid,"controller_pid":os.getpid(),"started_at":now(),
    "source_hash":source_sha,"macro_hash":macro_sha,"gpu":False,"CPU_workers":2})
   journal("attempts.jsonl",{"event":"launch_independent_nofoil_inlet_wave_CPU2","directory":str(folder),
    "source_sha256":source_sha,"macro_sha256":macro_sha,
    "dt_s":DT,"steps_budget":STEPS,"C01_wave_hold_unchanged":True,
    "initialization_performed":False,"source_calm_time_s":.4,
    "planned_status":"bounded_wave_ramp_diagnostic_only","M12_not_restarted":True})
   log("wave_startup_launched",folder=str(folder),pid=proc.pid,dt_s=DT,steps_budget=STEPS)
   def drain():
    for line in proc.stdout:stream.write(guard.redact(line));stream.flush()
   reader=threading.Thread(target=drain,daemon=True);reader.start()
   last_owned_check=0.0
   while proc.poll() is None:
    danger=check_resources()
    if time.monotonic()-last_owned_check>20:
     try:
      current_star={p["pid"] for p in active_solving()}
      explicit_owners=owned_star_pids(folder)
      # STAR 2602 spawns MPI workers via intermediate launchers. Their own
      # command lines do not always repeat the source .sim path; classify
      # actual descendants of source-matched STAR roots by Windows PID graph.
      # Do not classify arbitrary system or unrelated STAR roots as ours.
      snapshot=guard.processes()
      belonging=set(explicit_owners)
      for _ in range(12):
       belonging|={pid for pid,(parent,_) in snapshot.items() if parent in belonging}
      if proc.pid not in explicit_owners or not explicit_owners:
       danger=danger or "own_STAR_identity_not_verifiable"
      elif current_star-belonging:
       danger=danger or "another_STAR_solver_started"
     except Exception as ownership_error:
      danger=danger or "STAR_ownership_check_error"
      log("wave_ownership_verification_error",type=type(ownership_error).__name__)
     last_owned_check=time.monotonic()
    if time.monotonic()-started>1500:danger=danger or "wave_wall_budget"
    if danger and stop_reason is None:
     stop_reason=danger;request_time=time.monotonic()
     (folder/"STOP").touch()
     log("wave_stop_requested",reason=stop_reason)
    progress=read(folder/"progress.json")
    n=progress.get("steps",0)
    state={"status":"stop_requested" if stop_reason else
       "running_wave" if isinstance(n,int) and n>0 else "loading_wave",
      "at":now(),"directory":str(folder),"controller_pid":os.getpid(),
      "auxiliary_pid":proc.pid,"auxiliary_steps":n,
      "auxiliary_time_s":progress.get("time_s"),
      "wave_height_m":progress.get("wave_height_m"),
      "max_abs_eta_m":progress.get("max_abs_gauge_eta_m"),
      "max_CFL":progress.get("max_CFL"),
      "interface_CFL":progress.get("interface_CFL"),
      "reason":stop_reason,"source_calm_verified":True}
    write(folder/"monitor.json",state)
    write(PAR/"current.json",state)
    if request_time and time.monotonic()-request_time>600:
     write(PAR/"current.json",{"status":"unresolved_wave_graceful_stop","at":now(),
      "directory":str(folder),"auxiliary_pid":proc.pid,"reason":stop_reason,
      "manual_review_required":True})
     return # Intentionally preserve locks and process; never force-kill a possibly saving solver.
    time.sleep(5)
   code=proc.wait(timeout=60)
   reader.join(timeout=20)
  completed=read(folder/"completed.json")
  final=folder/"wave_pilot_final.sim"
  outcome={"status":"wave_ramp_pilot_completed" if code==0 and completed.get("status")=="target_reached"
   and final.is_file() and final.stat().st_size>50_000_000 and not stop_reason
   else "wave_ramp_pilot_stopped_or_failed",
    "at":now(),"directory":str(folder),"exit_code":code,"reason":stop_reason,
    "completed":completed,"source_unchanged":sha(src)==source_sha,
    "final_sim_exists":final.is_file(),"propagation_verified":False,
    "C01_hold_unchanged":True,"M12_not_restarted":True}
  write(folder/"pilot_result.json",outcome)
  write(PAR/"current.json",outcome)
  journal("decisions.jsonl",{"event":"nofoil_wave_ramp_pilot_finished",
   "status":outcome["status"],"folder":str(folder),
   "solver_steps":completed.get("steps"),"time_s":completed.get("time_s"),
   "returncode":code,"wave_not_fully_validated":True,
   "next":"Review finite CFL, VOF, wave gauge amplitude and period, inlet/outlet before longer propagation."})
  log("wave_result",status=outcome["status"],steps=completed.get("steps"),time_s=completed.get("time_s"))
 except BaseException as exc:
  message=guard.redact(str(exc))
  log("wave_controller_error",message=message)
  if folder:
   write(folder/"controller_error.json",{"at":now(),"error":message,"source_preserved":True,"main_untouched":True})
  if proc and proc.poll() is None:
   (folder/"STOP").touch()
   # Remain attached and keep draining STAR output while it gently saves and stops.
   deadline=time.monotonic()+600
   while proc.poll() is None and time.monotonic()<deadline:
    time.sleep(5)
   if proc.poll() is None:
    write(PAR/"current.json",{"status":"unresolved_wave_controller_stop","at":now(),
     "directory":str(folder),"auxiliary_pid":proc.pid,"reason":message,
     "manual_review_required":True,"STOP_present":True})
    return # Preserve both locks; never force-kill a STAR process.
  if folder:
   write(PAR/"current.json",{"status":"wave_controller_error_process_exited","at":now(),
    "directory":str(folder),"reason":message,"no_unverified_result_accepted":True})
  raise
 finally:
  if proc is None or proc.poll() is not None:
   for lock in (second,first):
    if read(lock).get("token")==token:lock.unlink()
if __name__=="__main__":main()
