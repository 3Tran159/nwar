"""One auxiliary CPU2 STAR at a time: matched no-foil wave meshes, independent from M11 GPU.
Protocol: verified baseline calm t=.4 -> map (if needed) -> 200 calm steps to .6
 -> 800 incident wave steps dt=.001 with same upstream ramp and gauges.
No original .sim or existing C01/HF changed. One owner token/atomic locks.
"""
from pathlib import Path
import os,sys,time,json,csv,uuid,datetime,subprocess,shutil,hashlib,statistics,math,threading
R=Path(r"E:\ntnu_mesh_optimization_20261030")
W=R/"wave_surface_only"
PAR=R/"parallel_cpu_20261031"
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
sys.path.insert(0,str(W));sys.path.insert(0,str(PAR))
import bounded_cpu_pilot as guard
import launch_halfdt_wave_cpu2_with_M11_guard as perf
GIB=1024**3
ORIG=W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"
SOURCE=ORIG/"calm_pilot_final.sim"
LOCKS=[PAR/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_mesh_comparison.lock"]
CURRENT=W/"wave_mesh_comparison_current.json"
BASE=W/"wave_mesh_triplet_20261031"
CASES=[("coarse",41200,.05),("baseline",53200,.025),("fine",77200,.0125)]
def now():return datetime.datetime.now().astimezone().isoformat()
def write(path,obj):
 p=Path(path);tmp=p.with_name(p.name+"."+uuid.uuid4().hex+".tmp")
 tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8");os.replace(tmp,p)
def read(p):
 try:return json.loads(Path(p).read_text(encoding="utf8-sig"))
 except (ValueError,OSError):return {}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
 return h.hexdigest()
def log(event,**kw):
 data=dict(at=now(),event=event,**kw)
 with (R/"attempts.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(data,ensure_ascii=False,allow_nan=False)+"\n");f.flush()
 print(json.dumps(data,ensure_ascii=False,allow_nan=False),flush=True)
def raw(p):
 try:
  with Path(p).open(newline="",encoding="utf8-sig") as f:return list(csv.DictReader(f))
 except OSError:return []
def danger():
 if any(p.exists() for p in (F/"STOP_ALL",R/"STOP_ALL",W/"STOP_ALL",PAR/"STOP_ALL", BASE/"STOP_ALL")):return "STOP_ALL"
 if guard.free_memory()<16*GIB:return "RAM_less16GiB"
 if shutil.disk_usage("C:\\").free<15*GIB:return "C_less15GiB"
 if shutil.disk_usage("E:\\").free<25*GIB:return "E_less25GiB"
 return None
def main_path():
 return perf.main_state()
def preflight():
 t=datetime.datetime.now().astimezone()
 assert t.date()==datetime.date(2026,10,31) and t.hour<23
 plan=read(R/"plan.json")
 assert sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"],"Runbook SHA mismatch"
 assert plan["parallel_execution"]["authorized"] and plan["parallel_execution"]["maximum_auxiliary_solvers"]==1
 assert plan["selection"]["user_primary_CL_CD_override"]["authorized"]
 assert read(PAR/"current.json").get("status")=="completed_diagnostic"
 assert all(not p.exists() for p in LOCKS)
 assert not BASE.exists(), "Previous triplet exists, do not run duplicate"
 assert danger() is None
 p=main_path();assert p is not None,"M11 healthy GPU stage needed for bounded simultaneous CPU pilot"
 perf.only_owned_main_star(p)
 a,baseline=perf.get_gpu_durations(p)
 assert len(a)>=200 and 0<baseline<20
 assert read(ORIG/"pilot_result.json").get("status")=="calm_pilot_completed"
 assert read(ORIG/"completed.json").get("status")=="target_reached" and abs(read(ORIG/"completed.json")["time_s"]-.4)<1e-8
 ini=read(ORIG/"initial_flat_audit.json")
 assert abs(ini["initial_max_velocity_m_s"]-18)<.05 and abs(ini["water_volume_m3"]-38.4)<.02
 assert SOURCE.stat().st_size>50_000_000
 allpass=read(W/"matrix_independent_geometry_audit.json")
 assert allpass and read(W/"plan.json")["geometry_validation"]["topology_geometry_pass"]
 for tag,n,dz in CASES:
  mesh=W/("FS_"+tag)/"mesh_exact.CGNS"
  val=read(mesh.parent/"mesh_exact.validation.json")
  assert mesh.is_file() and val["cells"]==n and abs(val["dz_free_surface_m"]-dz)<1e-12 and sha(mesh)==val["sha256"]
 for macro in ("NoFoilFlatMeshMapper.java","ContinueMappedNoFoilFlat.java","WaveTriplet_Coarse.java","WaveTriplet_Baseline.java","WaveTriplet_Fine.java"):
  assert (W/macro).is_file()
 assert (F/"STOP_ALL").exists()==False
 return p,baseline
def score(main,baseline,start):
 # Non-overlapping sets of 30 completed steps; ignore startup if insufficient.
 return perf.direct_monitor(main,start,baseline)
def guard_stars(main,folder,proc):
 # Check only main and own STAR have explicit tracked roots; avoid secondary untracked STAR.
 q=read(R/"mesh_queue_state.json")
 assert q["status"]=="running" and q["directory"]==str(main)
 snap=guard.processes(); ids={q["star_pid"],proc.pid}
 for _ in range(14):
  ids|={pid for pid,(parent,_) in snap.items() if parent in ids}
 others={pid for pid,(_,name) in snap.items() if name.lower() in ("starccm+.exe","star-ccm+.exe") and pid not in ids}
 if others:
  # STAR can spawn MPI worker server through detached launchers. Do not treat
  # such STAR worker as foreign until encoded source identity was inspected.
  import base64,re
  query="Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'starccm+.exe' -or $_.Name -eq 'star-ccm+.exe' } | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
  z=subprocess.run(["powershell","-NoProfile","-Command",query],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
  if z.returncode!=0:raise RuntimeError("Cannot verify STAR ownership")
  obj=json.loads(z.stdout or "[]"); obj=obj if isinstance(obj,list) else [obj]
  x={int(k["ProcessId"]):str(k.get("CommandLine") or "") for k in obj}
  for pid in others:
   cmd=x.get(pid,"")
   match=re.search(r"-xencoded-session\s+([^\s]+)",cmd)
   decoded=""
   if match:
    try:decoded=base64.b64decode(match.group(1)).decode("utf8",errors="replace")
    except Exception:pass
   if all(t not in cmd and t not in decoded for t in (main.name,folder.name)):
    raise RuntimeError("Unidentified STAR solver "+str(pid))
def execute_stage(token,jobname,src,macro,envs,expected_output,main,baseline,substep):
 if main_path()!=main or danger():raise RuntimeError("Main M11 stage changed or resource block")
 perf.only_owned_main_star(main)
 folder=BASE/jobname
 assert not folder.exists()
 folder.mkdir(exist_ok=False)
 original=sha(src)
 shutil.copy2(src,folder/"input.sim")
 assert sha(folder/"input.sim")==original and sha(src)==original
 m=Path(macro);mdigest=sha(m)
 shutil.copy2(m,folder/m.name);assert sha(folder/m.name)==mdigest
 env=dict(os.environ,**envs)
 for k in ("NTNU_MAP_OUT","NTNU_NOFOIL_OUT","NTNU_NOFOIL_WAVE_OUT"):env[k]=str(folder)
 start=time.monotonic();reason=None;low_windows=0;windows_seen=0;monitor_start=None;baseline_start_step=None
 list_before=raw(main/"history.csv")
 baseline_start_step=int(list_before[-1]["step"]) if list_before else None
 write(folder/"identity.json",dict(source=str(src),source_sha256=original,macro=str(m),macro_sha256=mdigest,at=now(),stage=jobname,inputs_copied=True,secondary_GPU_used=False))
 assert guard.k.SetProcessAffinityMask(guard.k.GetCurrentProcess(),guard.MASK)
 assert guard.k.SetPriorityClass(guard.k.GetCurrentProcess(),guard.BELOW_NORMAL)
 cmd=[str(guard.STAR),*guard.saved_options(2),"-batch",str(folder/m.name),str(folder/"input.sim")]
 with (folder/"star.log").open("x",encoding="utf8") as logf:
  proc=subprocess.Popen(cmd,cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
    text=True,encoding="utf8",errors="replace",
    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
  write(folder/"process.json",dict(pid=proc.pid,controller_pid=os.getpid(),started_at=now(),cpu_workers=2,gpu=False))
  write(CURRENT,dict(status="stage_started",job=jobname,folder=str(folder),at=now(),token=token,star_pid=proc.pid,steps_confirmed=0))
  log("wave_mesh_triplet_stage_started",stage=jobname,folder=str(folder),source_sha256=original,main_M11=str(main))
  def drain():
   for line in proc.stdout:logf.write(guard.redact(line));logf.flush()
  th=threading.Thread(target=drain,daemon=True);th.start()
  last_monitor=0
  while proc.poll() is None:
   if time.monotonic()-last_monitor>15:
    last_monitor=time.monotonic()
    reason=reason or danger()
    if main_path()!=main:reason=reason or "main_M11_stage_changed"
    if time.monotonic()-start>2700:reason=reason or "bounded_stage_wall"
    if baseline_start_step is not None:
     windows=score(main,baseline,baseline_start_step)
     for w in windows[windows_seen:]:
      low_windows=low_windows+1 if w["slowdown_pct"]>15 else 0
      if low_windows>=2:reason=reason or "M11_2_independent_windows_slowdown_above_15pct"
     windows_seen=len(windows)
    else:windows=[]
    try:
     guard_stars(main,folder,proc)
    except Exception as e:reason=reason or ("STAR_owner_conflict_"+type(e).__name__)
    simrows=raw(folder/"history.csv")
    steps=int(float(simrows[-1].get("step",0))) if simrows else 0
    io_bytes=sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    monitor=dict(at=now(),step=steps,main_windows=windows[-4:] if baseline_start_step is not None else [],baseline_M11_s_per_step=baseline,io_bytes=io_bytes,stop_reason=reason)
    write(folder/"monitor.json",monitor)
    write(CURRENT,dict(status="running" if steps else "initializing",job=jobname,folder=str(folder),at=now(),token=token,steps_confirmed=steps,stop_reason=reason,main_M11=str(main)))
    if reason and not (folder/"STOP").exists():
     (folder/"STOP").touch()
   time.sleep(3)
  rc=proc.wait();th.join(20)
 done=read(folder/"completed.json")
 proof=folder/expected_output
 out=dict(stage=jobname,at=now(),exit_code=rc,completed=done,source_unchanged=sha(src)==original,stop_reason=reason,receipt_present=proof.is_file(),receipt_bytes=proof.stat().st_size if proof.is_file() else 0,monitor=read(folder/"monitor.json"))
 write(folder/"stage_result.json",out)
 log("wave_mesh_triplet_stage_finished",stage=jobname,exit_code=rc,done=done,stop_reason=reason,source_unchanged=out["source_unchanged"])
 if reason:raise RuntimeError("STOPPED: "+reason)
 if rc!=0 or not out["source_unchanged"] or not proof.is_file():raise RuntimeError("Stage failure "+jobname+" exit="+str(rc))
 if done and done.get("status")!="target_reached":raise RuntimeError("Stage numeric guard "+jobname+":"+str(done))
 return proof,folder
def verify_calm(p,folder,n):
 complete=read(folder/"completed.json");ini=read(folder/"initial_flat_audit.json")
 assert complete.get("status")=="target_reached" and complete.get("steps")==200 and abs(complete.get("time_s",0)-.6)<1e-7
 assert ini.get("cells")==n and ini.get("reinitialized_disposable_copy") is False and ini.get("GPU")==0
 assert ini.get("initial_max_velocity_m_s") and abs(ini["initial_max_velocity_m_s"]-18)<.5
 data=raw(folder/"history.csv");gauges=raw(folder/"gauges.csv")
 assert len(data)>=201 and len(gauges)>80
 max_eta=max(abs(float(v["eta_actual_m"])) for v in gauges)
 first=float(data[0]["water_volume_m3"]);last=float(data[-1]["water_volume_m3"])
 assert max_eta<.005 and abs(last-first)<.005 and max(float(z["max_CFL"]) for z in data)<25
 write(folder/"calm_acceptance_diagnostic.json",dict(status="numerically_flat_calming_200_steps",max_gauge_eta_m=max_eta,water_volume_delta_m3=last-first,cells=n,source_time_s=.4,final_time_s=.6,does_not_prove_infinite_time_settling=True))
def audit_map(folder,expected):
 info=read(folder/"mapping_audit.json")
 assert info.get("pass") is True and info.get("cells")==expected and abs(info.get("time_s",-1)-.4)<1e-7
 assert info["mass_relative_change"]<.002 and info["water_relative_change"]<.002
def wave_samples(folder):
 a=raw(folder/"history.csv");g=raw(folder/"gauges.csv")
 done=read(folder/"completed.json")
 assert done.get("status")=="target_reached" and done.get("steps")==800
 assert abs(done.get("time_s",0)-1.4)<1e-7
 assert len(a)==801 and len(g)>500
 return a,g
def compare():
 ref=None;rows=[];g_by={}
 for tag,n,dz in CASES:
  p=BASE/("wave_"+tag)
  if not (p/"completed.json").exists():continue
  try:h,g=wave_samples(p)
  except Exception:continue
  g_by[tag]=g
  vals=[float(x["interface_CFL"]) for x in h if x.get("interface_CFL") and x["interface_CFL"].lower() not in ("nan","null") and math.isfinite(float(x["interface_CFL"]))]
  wall=float(h[-1]["wall_s"]);water=[float(x["water_volume_m3"]) for x in h]
  row=dict(mesh=tag,cells=n,dz_m=dz,dt_s=.001,steps=800,final_physical_s=1.4,
    measured_max_interface_CFL=max(vals) if vals else None,
    water_volume_range_m3=max(water)-min(water),solver_wall_s=wall,
    mean_s_per_step=wall/800,full_wave_arrival_validated=False,
    wave_stage="upstream_ramp_800_steps_only")
  rows.append(row)
 if "baseline" in g_by:
  base={(round(float(x["time_s"]),5),round(float(x["x_m"]),2)):float(x["eta_actual_m"]) for x in g_by["baseline"]}
  for row in rows:
   matched=[(float(x["eta_actual_m"]),base[(round(float(x["time_s"]),5),round(float(x["x_m"]),2))]) for x in g_by[row["mesh"]] if (round(float(x["time_s"]),5),round(float(x["x_m"]),2)) in base]
   if matched:
    row["gauge_matched"]=len(matched)
    row["gauge_mean_abs_diff_mm_vs_baseline"]=1000*statistics.fmean(abs(a-b) for a,b in matched)
    row["gauge_max_abs_diff_mm_vs_baseline"]=1000*max(abs(a-b) for a,b in matched)
   else:row["gauge_matched"]=0
 data=dict(at=now(),status="partial_matched_wave_startup_comparison_not_propagation_validation",parameters=dict(H_target_m=.5,lambda_m=20,U_m_s=18,dt_s=.001,ramp_duration_s=1.6945346413782258,calm_end_s=.6,steps=800),results=rows,missing=[x[0] for x in CASES if x[0] not in g_by])
 write(BASE/"wave_grid_comparison_latest.json",data)
 with (BASE/"wave_grid_comparison_latest.csv").open("w",encoding="utf8",newline="") as f:
  keys=sorted(set().union(*(x.keys() for x in rows))) if rows else ["mesh"]
  wr=csv.DictWriter(f,fieldnames=keys);wr.writeheader();wr.writerows(rows)
 return data
def main():
 main,baseline=preflight();token=uuid.uuid4().hex;owned=[]
 try:
  for p in LOCKS:
   with p.open("x",encoding="utf8") as f:json.dump(dict(pid=os.getpid(),token=token,at=now(),kind="wave_mesh_triplet_CPU2"),f)
   owned.append(p)
  BASE.mkdir(exist_ok=False)
  write(BASE/"plan.json",dict(started=now(),runbook_SHA=sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md"),matrix=CASES,source_calm=str(SOURCE),source_calm_sha256=sha(SOURCE),M11_main=str(main),M11_baseline_s_per_step=baseline,CPU_workers=2,priority="BELOW_NORMAL",wave_control_scope="separate no-foil only",C01_hold_unchanged=True,HF_untouched=True,do_not_conclude_wave_GCI=True))
  write(PAR/"current.json",dict(status="wave_mesh_triplet_CPU2",at=now(),directory=str(BASE),controller_pid=os.getpid(),token=token,main_M11=str(main)))
  for tag,n,dz in CASES:
   if danger() or main_path()!=main:raise RuntimeError("Main changed or resource guard")
   if tag=="baseline":
    mapped=SOURCE
   else:
    mesh=W/("FS_"+tag)/"mesh_exact.CGNS"
    mapped,folder=execute_stage(token,"map_"+tag,SOURCE,W/"NoFoilFlatMeshMapper.java",
       dict(NTNU_MAP_MESH=str(mesh),NTNU_MAP_CELLS=str(n),NTNU_MAP_EXPECTED_START="0.4"),
       "mapped.sim",main,baseline,False)
    audit_map(folder,n)
   calm,cf=execute_stage(token,"calm_"+tag,mapped,W/"ContinueMappedNoFoilFlat.java",
      dict(NTNU_NOFOIL_DT=".001",NTNU_NOFOIL_STEPS="200",NTNU_NOFOIL_CELLS=str(n)),
      "calm_pilot_final.sim",main,baseline,True)
   verify_calm(calm,cf,n)
   wave,wf=execute_stage(token,"wave_"+tag,calm,W/("WaveTriplet_"+tag.title()+".java"),
      dict(NTNU_NOFOIL_WAVE_STEPS="800"),
      "wave_pilot_final.sim",main,baseline,True)
   wave_samples(wf)
   compare()
  write(CURRENT,dict(status="triplet_completed_startup_only",at=now(),directory=str(BASE),comparison=str(BASE/"wave_grid_comparison_latest.json"),token=token))
  write(PAR/"current.json",dict(status="wave_mesh_triplet_completed_startup_only",at=now(),directory=str(BASE),comparison=str(BASE/"wave_grid_comparison_latest.json")))
  log("wave_mesh_triplet_finished",folder=str(BASE),full_propagation_validation=False)
 except BaseException as e:
  write(CURRENT,dict(status="needs_review_no_auto_retry",at=now(),directory=str(BASE),error_type=type(e).__name__,reason=str(e)[:300],token=token))
  write(PAR/"current.json",dict(status="wave_mesh_triplet_needs_review",at=now(),directory=str(BASE),reason=str(e)[:300]))
  log("wave_mesh_triplet_blocker",error_type=type(e).__name__,reason=str(e)[:300])
 finally:
  for p in reversed(owned):
   if read(p).get("token")==token:p.unlink()
if __name__=="__main__":main()
