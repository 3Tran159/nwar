"""One authorized CPU2 no-foil wave time-step sensitivity pilot alongside M11 GPU.
Waits for >=200 measured M11 steps; never touches the main GPU, HF or held C01.
"""
from pathlib import Path
import os,sys,time,json,csv,math,statistics,uuid,datetime,subprocess,threading,hashlib,shutil,ctypes
R=Path(r"E:\ntnu_mesh_optimization_20261030")
W=R/"wave_surface_only";PAR=R/"parallel_cpu_20261031"
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
sys.path.insert(0,str(PAR))
import bounded_cpu_pilot as guard
from pathlib import Path
CALM=W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"
OLD=W/"WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0"
MACRO=W/"NoFoilInletWaveHalfDtPilot.java"
LOCKS=[PAR/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_halfdt.lock"]
GIB=1024**3
def now():return datetime.datetime.now().astimezone().isoformat()
def read(p):
 try:return json.loads(Path(p).read_text(encoding="utf8-sig"))
 except (OSError,ValueError):return {}
def atomic(p,x):
 p=Path(p);tmp=p.with_name(p.name+"."+uuid.uuid4().hex+".tmp")
 tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8");os.replace(tmp,p)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
def hist(p):
 try:
  with Path(p).open(encoding="utf8-sig",newline="") as f:return list(csv.DictReader(f))
 except OSError:return []
def resources():
 if any(x.exists() for x in (F/"STOP_ALL",R/"STOP_ALL",W/"STOP_ALL",PAR/"STOP_ALL")):return "STOP_ALL"
 if guard.free_memory()<16*GIB:return "RAM_below16GiB"
 if shutil.disk_usage("C:\\").free<15*GIB:return "C_below15GiB"
 if shutil.disk_usage("E:\\").free<25*GIB:return "E_below25GiB"
 return None
def main_state():
 q=read(R/"mesh_queue_state.json")
 p=Path(q.get("directory",""))
 if q.get("status")!="running" or q.get("stage")!="M11" or q.get("star_pid") is None:return None
 if not guard.alive(q.get("controller_pid")) or not guard.alive(q.get("star_pid")):return None
 if p.parent!=R or not p.name.startswith("M11_G10_M_GPU_queue_"):return None
 cfg=read(p/"setup.json")
 if cfg and (cfg.get("gpu_count")!=1 or abs(cfg.get("dt_s",0)-.0002)>1e-10):return None
 return p
def get_gpu_durations(path):
 a=hist(path/"history.csv")
 times=[float(x["physical_time_s"]) for x in a]
 steps=[int(x["step"]) for x in a]
 if len(a)<201 or any(steps[i]!=steps[i-1]+1 for i in range(1,len(a))):return None
 walls=[float(x["wall_seconds"]) for x in a]
 deltas=[walls[i]-walls[i-1] for i in range(21,len(walls))]
 if len(deltas)<180 or any(x<=0 for x in deltas):return None
 return a,statistics.median(deltas[:180])
def preflight():
 assert now()[:10]=="2026-10-31"
 plan=read(R/"plan.json")
 assert sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"]
 assert plan["parallel_execution"]["maximum_auxiliary_solvers"]==1 and plan["parallel_execution"]["authorized"]
 assert read(PAR/"current.json").get("status")=="wave_ramp_pilot_completed"
 assert read(OLD/"pilot_result.json").get("exit_code")==0
 assert read(OLD/"completed.json").get("status")=="target_reached"
 assert read(OLD/"completed.json").get("steps")==500
 assert read(CALM/"pilot_result.json").get("status")=="calm_pilot_completed"
 assert read(CALM/"completed.json").get("status")=="target_reached"
 init=read(CALM/"initial_flat_audit.json")
 assert abs(init["initial_max_velocity_m_s"]-18)<.05
 assert CALM.joinpath("calm_pilot_final.sim").stat().st_size>50_000_000
 assert MACRO.is_file()
 assert resources() is None
 assert not any(x.exists() for x in LOCKS)
 assert main_state() is not None
 only_owned_main_star(main_state())
def only_owned_main_star(mainpath):
 import base64,re
 q=read(R/"mesh_queue_state.json")
 primary=q.get("star_pid")
 assert guard.alive(primary)
 rows=guard.processes()
 ids={primary}
 for _ in range(15):
  ids|={pid for pid,(parent,_) in rows.items() if parent in ids}
 unknown=[pid for pid,(_,name) in rows.items() if name.lower() in ("starccm+.exe","star-ccm+.exe") and pid not in ids]
 if not unknown:return
 ps="Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'starccm+.exe' -or $_.Name -eq 'star-ccm+.exe' } | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
 proc=subprocess.run(["powershell","-NoProfile","-Command",ps],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
 if proc.returncode:raise RuntimeError("Cannot verify STAR process ownership")
 items=json.loads(proc.stdout or "[]");items=items if isinstance(items,list) else [items]
 by={int(x["ProcessId"]):x.get("CommandLine","") or "" for x in items}
 for pid in unknown:
  cmd=by.get(pid,"")
  match=re.search(r"-xencoded-session\s+([^\s]+)",cmd)
  decoded=""
  if match:
   try:decoded=base64.b64decode(match.group(1)).decode("utf8",errors="replace")
   except Exception:pass
  if mainpath.name not in cmd and mainpath.name not in decoded:
   raise RuntimeError("Unidentified STAR solver exists; no auxiliary wave launch")
def direct_monitor(mainpath,startstep,baseline):
 a=hist(mainpath/"history.csv")
 r=[x for x in a if int(x["step"])>startstep]
 windows=[]
 for i in range(0,len(r)-29,30):
  w=r[i:i+30]
  if int(w[-1]["step"])-int(w[0]["step"])!=29:continue
  vals=[float(w[j]["wall_seconds"])-float(w[j-1]["wall_seconds"]) for j in range(1,len(w))]
  if vals and all(z>0 for z in vals):windows.append(dict(start=int(w[0]["step"]),end=int(w[-1]["step"]),median_s=statistics.median(vals),slowdown_pct=100*(statistics.median(vals)/baseline-1)))
 return windows
def gauges_compare(out):
 a=hist(OLD/"gauges.csv");b=hist(out/"gauges.csv")
 base={(round(float(x["time_s"]),6),round(float(x["x_m"]),2)):float(x["eta_actual_m"]) for x in a}
 pairs=[]
 for x in b:
  key=(round(float(x["time_s"]),6),round(float(x["x_m"]),2))
  if key in base:pairs.append((float(x["eta_actual_m"]),base[key],key))
 if not pairs:return dict(matched=0,phase_validated=False)
 dif=[x-y for x,y,_ in pairs]
 return dict(matched=len(pairs),max_absolute_difference_mm=1000*max(abs(x) for x in dif),mean_absolute_difference_mm=1000*statistics.fmean(abs(x) for x in dif),start_to_end_physical_s=[.4,.6],full_wave_arrival_validated=False,remarks="Initial inlet ramp only; do not infer full wave grid/phase accuracy.")
def main():
 preflight();token=uuid.uuid4().hex
 acquired=[]
 try:
  for p in LOCKS:
   with p.open("x",encoding="utf8") as f:json.dump(dict(pid=os.getpid(),token=token,at=now(),kind="bounded_nofoil_halfdt_CPU2"),f)
   acquired.append(p)
  wait_start=time.monotonic();mainpath=None;baseline=None;readings=None
  while time.monotonic()-wait_start<1200:
   if resources() is not None:raise RuntimeError("Resource stop while waiting for primary baseline")
   mainpath=main_state()
   if mainpath is None:raise RuntimeError("M11 stage is no longer active; cancel auxiliary")
   measurements=get_gpu_durations(mainpath)
   if measurements:
    readings,baseline=measurements;break
   atomic(W/"wave_halfdt_pending.json",dict(status="waiting_for_M11_200_step_baseline",at=now(),elapsed_wait_s=round(time.monotonic()-wait_start),main_M11=str(mainpath)))
   time.sleep(15)
  if baseline is None:raise RuntimeError("No M11 200-step baseline obtained within 20min")
  assert main_state()==mainpath and resources() is None
  startstep=int(readings[-1]["step"])
  folder=W/("WS_L20_H050_baseline_halfdt_CPU2_20261031_"+datetime.datetime.now().strftime("%H%M%S")+"_"+token[:6])
  folder.mkdir(exist_ok=False)
  source=CALM/"calm_pilot_final.sim";digest=sha(source)
  shutil.copy2(source,folder/"input.sim");assert sha(source)==digest and sha(folder/"input.sim")==digest
  shutil.copy2(MACRO,folder/MACRO.name);assert sha(folder/MACRO.name)==sha(MACRO)
  atomic(folder/"source_identity.json",dict(path=str(source),sha256=digest,source_time_s=.4,reinitialized=False))
  atomic(folder/"pilot_config.json",dict(dt_s=.0005,steps=400,target_time_s=.6,primary_M11=str(mainpath),baseline_M11_steps=len(readings),baseline_median_wall_s_per_step=baseline,CPU_workers=2,priority="BELOW_NORMAL",affinity_mask=guard.MASK,affinity_CPU20_21=True,gpu_used=False,source_unchanged=True))
  assert resources() is None and main_state()==mainpath
  only_owned_main_star(mainpath)
  assert guard.k.SetProcessAffinityMask(guard.k.GetCurrentProcess(),guard.MASK)
  assert guard.k.SetPriorityClass(guard.k.GetCurrentProcess(),guard.BELOW_NORMAL)
  t0=time.monotonic();stop_reason=None;lastcheck=0;window_prev=0;bad=0
  cmd=[str(guard.STAR),*guard.saved_options(2),"-batch",str(folder/MACRO.name),str(folder/"input.sim")]
  env=dict(os.environ,NTNU_NOFOIL_WAVE_OUT=str(folder),NTNU_NOFOIL_WAVE_STEPS="400")
  with (folder/"star.log").open("x",encoding="utf8") as log:
   proc=subprocess.Popen(cmd,cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding="utf8",errors="replace",text=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   atomic(folder/"process.json",dict(pid=proc.pid,controller_pid=os.getpid(),at=now(),gpu=False,CPU_workers=2))
   atomic(PAR/"current.json",dict(status="wave_halfdt_running",at=now(),directory=str(folder),pid=proc.pid,main_M11=str(mainpath)))
   with (R/"attempts.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(dict(at=now(),event="independent_nofoil_0p5ms_CPU2_wave_pilot_launch",folder=str(folder),baseline_steps=len(readings),main_baseline_s_per_step=baseline,no_second_gpu=True),ensure_ascii=False)+"\n")
   def drain():
    for line in proc.stdout:log.write(guard.redact(line));log.flush()
   reader=threading.Thread(target=drain,daemon=True);reader.start()
   while proc.poll() is None:
    if time.monotonic()-lastcheck>15:
     lastcheck=time.monotonic()
     if resources() is not None:stop_reason=stop_reason or resources()
     if main_state()!=mainpath:stop_reason=stop_reason or "main_M11_stage_changed_or_paused"
     if time.monotonic()-t0>1300:stop_reason=stop_reason or "bounded_wave_wall_budget"
     windows=direct_monitor(mainpath,startstep,baseline)
     for w in windows[window_prev:]:
      bad=bad+1 if w["slowdown_pct"]>15 else 0
      if bad>=2:stop_reason=stop_reason or "M11_two_windows_over_15pct"
     window_prev=len(windows)
     io=sum(x.stat().st_size for x in folder.rglob("*") if x.is_file())
     atomic(folder/"monitor.json",dict(at=now(),main_baseline_s=baseline,main_monitor_windows=windows[-5:],aux_output_bytes=io,stop_reason=stop_reason,confirmed_wave_steps=len(hist(folder/"history.csv"))-1))
     if stop_reason and not (folder/"STOP").exists():(folder/"STOP").touch()
    time.sleep(4)
   rc=proc.wait();reader.join(20)
  d=read(folder/"completed.json")
  success=rc==0 and d.get("status")=="target_reached" and d.get("steps")==400 and abs(d.get("time_s",0)-.6)<1e-7 and stop_reason is None
  result=dict(at=now(),directory=str(folder),status="completed_diagnostic" if success else "incomplete_or_safely_stopped",exit_code=rc,completed=d,stop_reason=stop_reason,source_unchanged=sha(source)==digest,baseline_M11_s_per_step=baseline,gauge_comparison=gauges_compare(folder) if success else None,not_full_wave_validation=True)
  atomic(folder/"pilot_result.json",result)
  atomic(PAR/"current.json",result)
  with (R/"decisions.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(dict(at=now(),event="nofoil_halfdt_CPU2_wave_test_result",status=result["status"],folder=str(folder),stop_reason=stop_reason,full_propagation_accepted=False),ensure_ascii=False)+"\n")
  print(json.dumps(result,ensure_ascii=False),flush=True)
 except BaseException as ex:
  atomic(W/"wave_halfdt_pending.json",dict(status="needs_review_no_automatic_retry",at=now(),error_type=type(ex).__name__,reason=str(ex)[:300]))
  print("BLOCKER",type(ex).__name__,str(ex)[:200],flush=True)
 finally:
  for p in reversed(acquired):
   if read(p).get("token")==token:p.unlink()
if __name__=="__main__":main()
