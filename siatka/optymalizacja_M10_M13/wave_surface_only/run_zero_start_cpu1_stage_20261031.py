"""Independent wave-only mesh screening. EACH distinct CGNS is initialized from zero (no transferred CFD field).
One CPU2 auxiliary at a time. Preserve M11 GPU, HF and campaign hold. Scientific gates before any inlet wave.
One-shot; never auto-retry a failed stage or launch duplicate. All outputs to E:.
"""
from pathlib import Path
import os,sys,json,csv,uuid,datetime,subprocess,shutil,hashlib,statistics,time,threading,re,math
R=Path(r"E:\ntnu_mesh_optimization_20261030")
W=R/"wave_surface_only"
P=R/"parallel_cpu_20261031"
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
sys.path.insert(0,str(P))
sys.path.insert(0,str(W))
import bounded_cpu_pilot as guard
import launch_halfdt_wave_cpu2_with_M11_guard as perf
SOURCE=W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"/"input.sim"
ROOT=W/"zero_start_matrix_20261031_13h_R2"
LOCKS=[P/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_mesh_comparison.lock"]
STATUS=W/"zero_start_12_current.json"
GIB=1024**3
MESHES={"L20":{
 "coarse":("FS_coarse",41200,0.05),
 "baseline":("FS_baseline",53200,0.025),
 "fine":("FS_fine",77200,0.0125)
},"L30":{
 "coarse":("L30/coarse",61800,0.05),
 "baseline":("L30/baseline",79800,0.025),
 "fine":("L30/fine",115800,0.0125)
}}
# 12 planned independent wave settings, 6 own-mesh calm initialization runs.
CASES=[(lam,h,grid) for lam,h in [("L20",.5),("L30",.5),("L20",.25),("L20",.75)]
 for grid in ("coarse","baseline","fine")]
def now():return datetime.datetime.now().astimezone()
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for c in iter(lambda:f.read(4*1024*1024),b""):h.update(c)
 return h.hexdigest()
def write(p,obj):
 p=Path(p); t=p.with_name(p.name+"."+uuid.uuid4().hex+".tmp")
 t.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")
 os.replace(t,p)
def read(p):
 try:return json.loads(Path(p).read_text(encoding="utf8-sig"))
 except (OSError,ValueError):return {}
def rows(p):
 try:
  with Path(p).open(encoding="utf8-sig",newline="") as f:return list(csv.DictReader(f))
 except OSError:return []
def log(event,**other):
 x=dict(at=now().isoformat(),event=event,**other)
 with (R/"attempts.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+"\n")
 print(json.dumps(x,ensure_ascii=False),flush=True)
def check_danger():
 for q in (R/"STOP_ALL",W/"STOP_ALL",P/"STOP_ALL",F/"STOP_ALL",ROOT/"STOP"):
  if q.exists():return "STOP_ALL_or_user_stop"
 if guard.free_memory()<16*GIB:return "RAM_free_below_16GiB"
 if shutil.disk_usage("C:\\").free<15*GIB:return "C_free_below_15GiB"
 if shutil.disk_usage("E:\\").free<25*GIB:return "E_free_below_25GiB"
 return None
def mesh_info(lam,tag):
 rel,n,dz=MESHES[lam][tag]
 loc=W/rel/"mesh_exact.CGNS"
 v=read(loc.parent/"mesh_exact.validation.json")
 assert loc.is_file() and v["cells"]==n and abs(v["dz_free_surface_m"]-dz)<1e-12
 assert sha(loc)==v["sha256"],"CGNS hash mismatch"
 assert v["total_volume_m3"]>40 and v["total_volume_m3"]<80
 return loc,n,v
def main_current():
 return perf.main_state()
def preflight():
 assert now().date()==datetime.date(2026,10,31)
 plan=read(R/"plan.json")
 assert sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"]
 assert plan["parallel_execution"]["authorized"] and plan["parallel_execution"]["maximum_auxiliary_solvers"]==1
 assert plan["selection"]["user_primary_CL_CD_override"]["authorized"]
 assert read(P/"current.json").get("status")=="wave_mesh_triplet_needs_review"
 assert not ROOT.exists() and not any(x.exists() for x in LOCKS)
 assert read(STATUS).get("status")=="blocked_no_auto_retry"
 assert check_danger() is None
 assert (F/"campaign_hold.json").exists(), "Existing foil-wave campaign hold must remain"
 assert SOURCE.is_file() and SOURCE.stat().st_size>30_000_000
 for macro in ("CalmZeroPerMesh_20261031.java","WaveFromOwnCalm_20261031.java"):
  assert (W/macro).is_file()
 for lam in MESHES:
  for tag in MESHES[lam]:mesh_info(lam,tag)
 main=main_current()
 assert main is not None,"M11 no longer verified as main GPU stage"
 perf.only_owned_main_star(main)
 a,baseline=perf.get_gpu_durations(main)
 assert len(a)>=200 and 0<baseline<20
 return main,baseline
def records_snapshot():
 if not ROOT.exists():return
 matrix=[]
 for lam,h,tag in CASES:
  key=f"{lam}_H{int(round(h*1000)):03d}_{tag}"
  stage=ROOT/"waves"/key
  state="not_started"
  steps=0; t=None; max_eta=None; max_cfl=None
  if stage.exists():
   complete=read(stage/"completed.json")
   hist=rows(stage/"history.csv")
   if hist:
    steps=int(float(hist[-1]["step"]))
    t=float(hist[-1]["time_s"])
    max_cfl=float(hist[-1]["max_CFL"])
   if complete:state="completed_short_pilot_not_full_propagation" if complete.get("status")=="target_reached" else complete.get("status","unknown")
   elif (stage/"macro_error.json").exists():state="failed_guard"
   else:state="active_or_incomplete"
   gs=rows(stage/"gauges.csv")
   if gs:max_eta=max(abs(float(x["eta_actual_m"])) for x in gs)
  matrix.append(dict(case=key,lambda_m=int(lam[1:]),H_m=h,mesh=tag,cells=MESHES[lam][tag][1],
                     status=state,steps=steps,time_s=t,max_CFL=max_cfl,max_abs_eta_m=max_eta))
 write(ROOT/"matrix_live.json",dict(at=now().isoformat(),results=matrix,
   planned=len(matrix),actual_completed=sum(x["status"].startswith("completed") for x in matrix),
   scientifically_validated=0,warning="Short ramp pilots alone are not complete wave-propagation validation"))
 with (ROOT/"matrix_live.csv").open("w",newline="",encoding="utf8") as f:
  wr=csv.DictWriter(f,fieldnames=matrix[0].keys());wr.writeheader();wr.writerows(matrix)
def stage(main,base,phase,name,source,macro,variables,max_wall_s=2700):
 assert main_current()==main and check_danger() is None
 assert not any(x.exists() for x in (ROOT/"STOP",))
 perf.only_owned_main_star(main)
 dest=ROOT/phase/name
 assert not dest.exists(),"No stage retry or overwriting allowed"
 dest.mkdir(parents=True,exist_ok=False)
 src_hash=sha(source)
 shutil.copy2(source,dest/"input.sim")
 assert sha(dest/"input.sim")==src_hash
 shutil.copy2(macro,dest/macro.name)
 env=dict(os.environ,**variables)
 env["NTNU_NOFOIL_OUT"]=str(dest)
 env["NTNU_NOFOIL_WAVE_OUT"]=str(dest)
 env["NTNU_NOFOIL_MESH"]=str(variables.get("NTNU_NOFOIL_MESH",""))
 write(dest/"identity.json",dict(created=now().isoformat(),phase=phase,source=str(source),source_sha256=src_hash,
    macro=str(macro),macro_sha256=sha(macro),cpu_workers=1,gpu=False,original_untouched=True))
 # Only CPU2, BELOW_NORMAL. Never set main GPU affinity or priority.
 cmd=[str(guard.STAR),*guard.saved_options(1),"-batch",str(dest/macro.name),str(dest/"input.sim")]
 start=time.monotonic();last=0;reason=None;bad_windows=0;seen=0
 prev=rows(main/"history.csv")
 start_step=int(float(prev[-1]["step"])) if prev else -1
 write(STATUS,dict(status="starting",phase=phase,case=name,at=now().isoformat(),directory=str(dest)))
 with (dest/"star.log").open("x",encoding="utf8") as f:
  p=subprocess.Popen(cmd,cwd=dest,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
    text=True,encoding="utf8",errors="replace",creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
  write(dest/"process.json",dict(pid=p.pid,at=now().isoformat(),controller=os.getpid(),workers=2))
  def drain():
   for line in p.stdout:
    f.write(guard.redact(line));f.flush()
  th=threading.Thread(target=drain,daemon=True);th.start()
  log("zero_start_stage_started",phase=phase,name=name,source=str(source),pid=p.pid,main_M11=str(main))
  while p.poll() is None:
   if time.monotonic()-last>15:
    last=time.monotonic()
    reason=reason or check_danger()
    if main_current()!=main:reason=reason or "M11_changed_or_not_progressing"
    if time.monotonic()-start>max_wall_s:reason=reason or "bounded_stage_wall_time"
    windows=perf.direct_monitor(main,start_step,base) if start_step>=0 else []
    # Independently check the monitor's arithmetic and stop the helper if it is wrong.
    for ww in windows:
     actual=100*(float(ww["median_s"])/base-1)
     if abs(actual-float(ww["slowdown_pct"]))>0.01:
      reason=reason or "M11_monitor_math_self_test_failed"
    for window in windows[seen:]:
     bad_windows=bad_windows+1 if window["slowdown_pct"]>15 else 0
     if bad_windows>=2:reason=reason or "M11_slowdown_two_windows_over_15pct"
    seen=len(windows)
    data=rows(dest/"history.csv")
    steps=int(float(data[-1]["step"])) if data else 0
    write(dest/"monitor.json",dict(at=now().isoformat(),steps=steps,main_windows=windows[-3:],
      baseline_M11_s_per_step=base,reason=reason,elapsed_wall_s=round(time.monotonic()-start,2),
      io_bytes=sum(x.stat().st_size for x in dest.glob("*") if x.is_file())))
    write(STATUS,dict(status="running" if data else "loading",phase=phase,case=name,
      at=now().isoformat(),steps=steps,main_M11=str(main),stop_reason=reason))
    if reason and not (dest/"STOP").exists(): (dest/"STOP").touch()
    records_snapshot()
   time.sleep(3)
  rc=p.wait();th.join(15)
 done=read(dest/"completed.json")
 write(dest/"stage_result.json",dict(at=now().isoformat(),phase=phase,exit_code=rc,completed=done,
    source_unchanged=(sha(source)==src_hash),controller_reason=reason,monitor=read(dest/"monitor.json")))
 log("zero_start_stage_end",phase=phase,name=name,exit_code=rc,steps=done.get("steps"),status=done.get("status"),reason=reason)
 records_snapshot()
 if reason:raise RuntimeError("Safe auxiliary stop: "+reason)
 if rc!=0 or not done or done.get("status")!="target_reached" or sha(source)!=src_hash:
  raise RuntimeError("Stage failed/unsafe "+phase+"/"+name+", no retry")
 save=dest/("calm_pilot_final.sim" if phase=="calm" else "wave_pilot_final.sim")
 assert save.is_file() and save.stat().st_size>20_000_000
 return save,dest
def verify_calm(folder,lam,tag,val):
 hist=rows(folder/"history.csv");probes=rows(folder/"gauges.csv")
 ini=read(folder/"initial_flat_audit.json");done=read(folder/"completed.json")
 assert ini.get("source_field_transfer") is False and ini.get("reinitialized_disposable_copy") is True
 assert ini.get("cells")==MESHES[lam][tag][1] and ini["GPU"]==0
 assert len(hist)>=401 and done["steps"]==400
 v_expected=val["total_volume_m3"]*.8
 assert abs(ini["initial_max_velocity_m_s"]-18)<.05
 assert abs(ini["water_volume_m3"]-v_expected)<.02
 assert abs(float(hist[-1]["water_volume_m3"])-v_expected)<.01
 assert max(float(x["max_CFL"]) for x in hist)<25
 assert max(float(x["max_speed_m_s"]) for x in hist)<22
 last_g=[x for x in probes if float(x["time_s"])>=.2]
 assert last_g and max(abs(float(x["eta_actual_m"])) for x in last_g)<.004
 # Use two non-overlapping windows for calm gauge drift, not a fixed step-count receipt.
 x1=[float(x["eta_actual_m"]) for x in probes if .2<=float(x["time_s"])<.3]
 x2=[float(x["eta_actual_m"]) for x in probes if .3<=float(x["time_s"])<=.400001]
 assert x1 and x2
 delta=abs(statistics.fmean(x1)-statistics.fmean(x2))
 assert delta<.0015
 # Detect the previous 1e9-level coarse continuity anomaly.
 z=[]
 for line in (folder/"star.log").read_text(encoding="utf8",errors="replace").splitlines():
  t=line.split()
  if len(t)>9 and t[0].isdigit():
   try:z.append(float(t[1]))
   except Exception:pass
 residual=statistics.median(z[-20:]) if len(z)>=20 else None
 assert residual is not None and math.isfinite(residual) and residual<1e4,"Anomalous pressure-continuity residual; no wave activation"
 write(folder/"calm_readiness.json",dict(at=now().isoformat(),pass_for_bounded_wave_trial=True,
  scientific_long_term_settling_certified=False,source_field_transfer=False,
  last20_continuity_residual_median=residual,water_volume_m3=float(hist[-1]["water_volume_m3"]),
  calm_gauge_mean_delta_m=delta,max_last_gauge_abs_m=max(abs(float(x["eta_actual_m"])) for x in last_g)))
def main():
 main,baseline=preflight()
 token=uuid.uuid4().hex;mine=[]
 start=now();deadline=start+datetime.timedelta(hours=3)
 try:
  for lock in LOCKS:
   with lock.open("x",encoding="utf8") as f:json.dump(dict(pid=os.getpid(),token=token,at=now().isoformat(),kind="zero_start_12_cpu2"),f)
   mine.append(lock)
  ROOT.mkdir(exist_ok=False)
  write(ROOT/"plan.json",dict(created=start.isoformat(),deadline=deadline.isoformat(),
    target_cases=12,actual_results_required=True,one_solver_max=True,workers=2,gpu=False,
    flow="independent_mesh_replace_after_CLEARED_solution => own flat water t0 => validate calm => inlet wave (never global initialize)",
    source=str(SOURCE),source_hash=sha(SOURCE),runbook_SHA=sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md"),
    main=str(main),main_baseline_s_step=baseline,preserved_campaign_hold=True,
    wave_steps_per_case=2200,calm_steps_per_mesh=400,
    note="No 12-case validation guarantee. Allow 3 hours for starts; existing started job is not killed on deadline."))
  records_snapshot()
  log("zero_start_12_matrix_created",folder=str(ROOT),cases=12,deadline=deadline.isoformat())
  for lam,h,tag in CASES:
   if now()>=deadline:log("zero_start_deadline_reached_no_new_solver");break
   if check_danger():raise RuntimeError(check_danger())
   cg,n,val=mesh_info(lam,tag)
   calm_file=ROOT/"calm"/f"{lam}_{tag}"/"calm_pilot_final.sim"
   volume=val["total_volume_m3"]*.8
   if not calm_file.is_file():
    source_out,stage_dir=stage(main,baseline,"calm",f"{lam}_{tag}",SOURCE,
     W/"CalmZeroPerMesh_20261031.java",
     dict(NTNU_NOFOIL_MESH=str(cg),NTNU_NOFOIL_CELLS=str(n),
          NTNU_NOFOIL_DT=".001",NTNU_NOFOIL_STEPS="400",
          NTNU_NOFOIL_WATER_M3=str(volume)),max_wall_s=1200)
    verify_calm(stage_dir,lam,tag,val)
   else:
    assert read(calm_file.parent/"calm_readiness.json").get("pass_for_bounded_wave_trial")
   xmin=val["bounds"][0][0];xmax=val["bounds"][1][0]
   case=f"{lam}_H{int(round(h*1000)):03d}_{tag}"
   wave_period=20/23.612 if lam=="L20" else 30/24.7
   final,folder=stage(main,baseline,"waves",case,calm_file,
       W/"WaveFromOwnCalm_20261031.java",
       dict(NTNU_NOFOIL_CELLS=str(n),NTNU_NOFOIL_WATER_M3=str(volume),
            NTNU_NOFOIL_LAMBDA=str(int(lam[1:])),NTNU_NOFOIL_H=str(h),
            NTNU_NOFOIL_XMIN=str(xmin),NTNU_NOFOIL_XMAX=str(xmax),
            NTNU_NOFOIL_WAVE_PERIOD_S=str(wave_period),
            NTNU_NOFOIL_WAVE_STEPS="2200"),max_wall_s=2700)
   log("zero_start_bounded_wave_completed_not_validated",case=case,folder=str(folder))
  write(STATUS,dict(at=now().isoformat(),status="finished_budget_or_matrix",
      folder=str(ROOT),remaining_deadline=now()<deadline,actual=read(ROOT/"matrix_live.json")))
 except BaseException as exc:
  write(STATUS,dict(at=now().isoformat(),status="blocked_no_auto_retry",reason=str(exc)[:500],
      folder=str(ROOT),actual=read(ROOT/"matrix_live.json")))
  log("zero_start_matrix_blocked_no_auto_retry",reason=str(exc)[:350])
 finally:
  # Never remove another owner's lock.
  for lock in reversed(mine):
   try:
    if read(lock).get("token")==token:lock.unlink()
   except OSError:pass
  log("zero_start_controller_finished",root=str(ROOT),auxiliary_locks_released=len(mine))
if __name__=="__main__":main()
