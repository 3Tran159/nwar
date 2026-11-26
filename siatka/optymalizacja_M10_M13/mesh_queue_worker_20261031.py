"""Sequential guarded M11->M10 GPU campaign, independent from historical saved M12."""
from pathlib import Path
import sys,os,json,csv,math,time,hashlib,datetime,uuid,shutil,subprocess,threading,statistics,ctypes
import mesh_queue_control_20261031 as ctrl
R=ctrl.R;B=ctrl.B;F=ctrl.F
sys.path.insert(0,str(F.parent/"night_20261028"))
from night_queue import STAR,saved_options,redact,free_memory
ROOT=B/"force_stabilization_20261029"
STAGES=[("M11","G10_M",595285,"calm_pilot_G10_M_continued_r1"),("M10","W01a",317277,"calm_pilot_W01a_continued_r1")]
DT=0.0001
PILOT_SELECTION=R/'m11_dt_selection.json'
def now():return ctrl.stamp()
def write(p,o):ctrl.write(p,o)
def journal(event,**kw):
 with (R/"attempts.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(dict(at=now(),event=event,**kw),ensure_ascii=False)+"\n")
def state(token,status,stage,index,directory=None,**kw):
 x=dict(token=token,status=status,stage=stage,stage_index=index,directory=str(directory) if directory else None,controller_pid=os.getpid(),at=now(),**kw)
 write(ctrl.STATE,x)
 return x
def check_res():
 ram=free_memory()/1024**3
 c=shutil.disk_usage("C:\\").free/1024**3
 e=shutil.disk_usage("E:\\").free/1024**3
 g=ctrl.read(R/"plan.json").get("selection",{}).get("user_primary_CL_CD_override",{}).get("authorized")
 gpu=subprocess.run(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
 gpu_free=int(gpu.stdout.strip().splitlines()[0]) if gpu.returncode==0 else 0
 assert g and ram>=16 and c>=15 and e>=25 and gpu_free>=4000,("Insufficient memory/disk/GPU",ram,c,e,gpu_free)
 return ram,c,e
def read_rows(path):
 with Path(path).open(encoding="utf-8-sig",newline="") as f:
  return list(csv.DictReader(f))
def verify_input(stage):
 name,internal,cells,pilot=stage
 origin=ROOT/pilot;d=ctrl.read(origin/"completed.json");ex=ctrl.read(origin/"exit.json")
 setup=ctrl.read(origin/"setup.json");receipt=ctrl.read(origin/"EXPORT_OK.json")
 assert d.get("status")=="target_reached" and abs(d.get("time_s",0)-.591)<1e-8
 assert ex.get("returncode")==0 and ex.get("source_unchanged") is True
 assert setup.get("cells")==cells and abs(setup.get("dt_s",0)-.0001)<1e-12 and setup.get("inner_iterations")==10
 assert receipt.get("status")=="target_reached" and receipt.get("cells")==cells
 assert (origin/"final.sim").stat().st_size>100_000_000
 data=read_rows(origin/"history.csv");assert data and abs(float(data[-1]["physical_time_s"])-.591)<1e-8
 return origin
def source_for(stage,previous):
 origin=verify_input(stage)
 selection=ctrl.read(PILOT_SELECTION)
 if stage[0]=="M11" and selection.get("approved_for_continuation_pilot") is True:
  p=Path(selection["directory"])
  assert p.parent==R and p.name.startswith("M11_G10_M_dt0002_GPU_pilot_")
  assert ctrl.sha(p/"final.sim")==selection["final_sim_sha256"]
  done=ctrl.read(p/"completed.json");exit=ctrl.read(p/"exit.json")
  assert done["status"]=="target_reached" and exit["returncode"]==0 and exit["source_unchanged"] is True
  assert abs(done["time_s"]-.6052)<1e-8
  rows=read_rows(p/"history.csv")
  assert len(rows)==71 and all(abs(float(x["dt_s"])-.0002)<1e-12 for x in rows)
  return p/"final.sim",rows,done["time_s"]
 if previous.get("directory") and previous.get("status")=="paused" and previous.get("stage")==stage[0]:
  p=Path(previous["directory"])
  d=ctrl.read(p/"completed.json");ex=ctrl.read(p/"exit.json");receipt=ctrl.read(p/"EXPORT_OK.json")
  assert p.parent==R and d.get("status") in ("stopped_by_marker","target_reached") and ex.get("returncode")==0
  assert ex.get("source_unchanged") is True and receipt.get("time_s")==d.get("time_s")
  assert (p/"final.sim").is_file()
  result=[*read_rows(p/"prior_history.csv"),*read_rows(p/"history.csv")]
  times=[float(x["physical_time_s"]) for x in result]
  assert len(set(round(x,8) for x in times))==len(times)
  assert abs(times[-1]-d["time_s"])<1e-8
  return p/"final.sim",result,d["time_s"]
 return origin/"final.sim",read_rows(origin/"history.csv"),.591
def project_check(out,baseline_rows):
 path=out/"settling_checks.jsonl"
 if not path.exists():return None
 try:
  checks=[json.loads(s) for s in path.read_text(encoding="utf8").splitlines() if s.strip()]
  if len(checks)<2:return None
  chosen=checks[-2:]
  if abs(chosen[1]["time_s"]-chosen[0]["time_s"]-.2)>1e-7:return None
  rows=read_rows(out/"history.csv")
  allrows=baseline_rows+rows
  n=int(round(.2/DT))
  if len(allrows)<2*n:return None
  keys={round(float(r["physical_time_s"]),7):r for r in allrows}
  for ch in chosen:
   t=ch["time_s"]
   prev=[keys.get(round(t-.4+(i+1)*DT,7)) for i in range(n)]
   curr=[keys.get(round(t-.2+(i+1)*DT,7)) for i in range(n)]
   if None in prev or None in curr:return None
   for k in ("CL","CD"):
    v=ch.get(k,{})
    if not(v.get("relative_test_resolved") and v.get("mean_change_pct",100)<.5 and v.get("previous_RMS_pct",100)<.5 and v.get("latest_RMS_pct",100)<.5):return None
    a=[float(r["CL_total"])-22.718189111947265/3855.6 if k=="CL" else float(r[k]) for r in prev]
    b=[float(r["CL_total"])-22.718189111947265/3855.6 if k=="CL" else float(r[k]) for r in curr]
    am=statistics.fmean(a);bm=statistics.fmean(b)
    if min(abs(am),abs(bm))<1e-8 or not all(math.isfinite(x) for x in (am,bm)):return None
    if max(100*abs(bm-am)/abs(bm),100*statistics.pstdev(a)/abs(am),100*statistics.pstdev(b)/abs(bm))>=.5:return None
    if abs(v["latest_mean"]-bm)>1e-6:return None
  if not rows:return None
  tail=rows[-100:]
  for r in tail:
   if not all(math.isfinite(float(r[k])) for k in ("max_CFL","interface_max_CFL","max_velocity_m_s","CD","CL_total")):return None
  if max(float(r["interface_max_CFL"]) for r in tail)>1.00001 or max(float(r["max_CFL"]) for r in tail)>25:return None
  if max(float(r["max_velocity_m_s"]) for r in tail)>50:return None
  cd=chosen[-1]["CD"];p=chosen[-1]["CD_pressure"];v=chosen[-1]["CD_viscous"]
  denom=abs(cd["latest_mean"]);assert denom>1e-8
  dp=100*abs(p["latest_mean"]-p["previous_mean"])/denom
  dv=100*abs(v["latest_mean"]-v["previous_mean"])/denom
  opp=(p["latest_mean"]-p["previous_mean"])*(v["latest_mean"]-v["previous_mean"])<0
  if opp and dp+dv>1: return None # Mark concerning compensation for review, not automatic acceptance.
  # Conservation data is supplementary: mass balance and phase volume must be finite.
  cons=out/"conservation.csv"
  if not cons.is_file():return None
  budgets=read_rows(cons)[-5:]
  if not budgets:return None
  if any(not math.isfinite(float(x[k])) for x in budgets for k in ("mass_kg","water_volume_m3","net_outward_mass_kg_s")):return None
  if any(float(x["water_volume_m3"])<=0 for x in budgets):return None
  return dict(criterion="project primary CL/CD only (not legacy 4-way, not ITTC)",checks_s=[r["time_s"] for r in chosen],CL_shift_pct=chosen[-1]["CL"]["mean_change_pct"],CD_shift_pct=cd["mean_change_pct"],CL_rms_pct=chosen[-1]["CL"]["latest_RMS_pct"],CD_rms_pct=cd["latest_RMS_pct"],CDp_abs_shift_vs_totalCD_pct=dp,CDv_abs_shift_vs_totalCD_pct=dv,sum_abs_components_vs_totalCD_pct=dp+dv,opposing_sign=opp,raw_independently_recomputed=True)
 except (OSError,ValueError,KeyError,AssertionError,ZeroDivisionError,TypeError):return None
def run_stage(token,stage,index,prior):
 global DT
 name,internal,cells,_=stage
 DT=.0002 if name=="M11" and ctrl.read(PILOT_SELECTION).get("approved_for_continuation_pilot") is True else .0001
 source,baseline,src_t=source_for(stage,prior)
 if ctrl.PAUSE.exists():return "paused",None
 assert 0<src_t<3.591 and abs(round(src_t/DT)*DT-src_t)<1e-7 or (name=="M11" and abs(src_t-.6052)<1e-8 and abs(DT-.0002)<1e-12)
 assert (B/"STOP").is_file() and ctrl.original_ok()
 check_res()
 if ctrl.no_other_stars():raise RuntimeError("Unknown STAR")
 tag=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
 out=R/(name+"_"+internal+"_GPU_queue_"+tag+"_"+token[:6]);out.mkdir(exist_ok=False)
 digest=ctrl.sha(source)
 shutil.copy2(source,out/"input.sim");assert ctrl.sha(source)==digest and ctrl.sha(out/"input.sim")==digest
 macro=B/"ContinueCalmGPULive.java"
 receipt=ctrl.read(B/"gpu_live_macro_receipt.json")
 assert receipt.get("status")=="javac_passed" and receipt.get("GPU_macro_sha256")==ctrl.sha(macro)
 shutil.copy2(macro,out/macro.name);assert ctrl.sha(macro)==ctrl.sha(out/macro.name)
 with (out/"prior_history.csv").open("x",encoding="utf8",newline="") as f:
  head=list(baseline[0])
  w=csv.DictWriter(f,fieldnames=head);w.writeheader();w.writerows(baseline)
 write(out/"source_identity.json",dict(path=str(source),sha256=digest,source_time_s=src_t,source_original_preserved=True))
 write(out/"pilot_config.json",dict(stage=name,cells=cells,physical_dt_s=DT,target_time_s=3.591,start_time_s=src_t,inner=10,gpu=True,workers=1,no_reinitialization=True,project_primary_diagnostic_only=True,legacy_macro_unchanged=True))
 env=dict(os.environ,NTNU_STAB_OUT=str(out),NTNU_MAP_OUT=str(out),NTNU_STAB_DT=str(DT),NTNU_STAB_TARGET="3.591",NTNU_STAB_INNER="10",NTNU_STAB_CELLS=str(cells),NTNU_STAB_START=str(src_t),NTNU_STAB_INIT="false",NTNU_STAB_ORDER="SECOND_ORDER",NTNU_STAB_BUDGET="47000",NTNU_STAB_PRIOR_HISTORY=str(out/"prior_history.csv"),NTNU_CALM_SETTLE="true",NTNU_GCI_MAX_CFL="25",NTNU_GCI_INTERFACE_CFL="1")
 if ctrl.PAUSE.exists():return "paused",None
 check_res()
 state(token,"starting",name,index,out)
 began=time.monotonic();marked=None;stop_reason=None
 with (out/"star.log").open("x",encoding="utf8") as log:
  p=subprocess.Popen([str(STAR),*saved_options(1),"-gpgpu","auto:1","-batch",str(out/macro.name),str(out/"input.sim")],cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf8",errors="replace",creationflags=subprocess.CREATE_NO_WINDOW|subprocess.NORMAL_PRIORITY_CLASS)
  write(out/"process.json",dict(star_pid=p.pid,controller_pid=os.getpid(),started_at=now(),gpu=True,workers=1))
  state(token,"running",name,index,out,star_pid=p.pid)
  journal("M11_or_M10_queue_stage_launched",stage=name,directory=str(out),star_pid=p.pid,source_sha256=digest,confirmed_steps=False)
  def drain():
   for line in p.stdout: log.write(redact(line));log.flush()
  reader=threading.Thread(target=drain,daemon=True);reader.start()
  last_check=0
  while p.poll() is None:
   if ctrl.PAUSE.exists():stop_reason=stop_reason or "user_queue_pause"
   if (F/"STOP_ALL").exists() or (R/"STOP_ALL").exists():stop_reason=stop_reason or "STOP_ALL"
   if time.monotonic()-last_check>20:
    last_check=time.monotonic()
    ram=free_memory()/1024**3
    c=shutil.disk_usage("C:\\").free/1024**3
    e=shutil.disk_usage("E:\\").free/1024**3
    if ram<16 or c<15 or e<25:stop_reason=stop_reason or "resource_threshold"
    if not marked and not stop_reason:
     result=project_check(out,baseline)
     if result:
      write(out/"project_primary_evidence.json",result);marked=now()
      stop_reason="project_primary_two_passes"
      journal("project_primary_two_passes_request_own_graceful_stop",stage=name,directory=str(out),two_checks=result["checks_s"])
   if stop_reason and not (out/"STOP").exists():
    (out/"STOP").touch();state(token,"saving",name,index,out,reason=stop_reason,star_pid=p.pid)
   time.sleep(3)
  code=p.wait();reader.join(30)
 exitinfo=dict(returncode=code,source_unchanged=ctrl.sha(source)==digest,wall_s=time.monotonic()-began,gpu=True,workers=1,at=now())
 write(out/"exit.json",exitinfo)
 done=ctrl.read(out/"completed.json");export=ctrl.read(out/"EXPORT_OK.json")
 acceptable= code==0 and exitinfo["source_unchanged"] and done.get("status") in ("stopped_by_marker","target_reached","stabilized") and export.get("time_s")==done.get("time_s") and (out/"final.sim").exists()
 if not acceptable:raise RuntimeError("M11/M10 saved receipt not complete or numerical failure: "+repr(done))
 result=project_check(out,baseline)
 if result:write(out/"project_primary_evidence.json",result)
 final=dict(stage=name,output=str(out),done=done,project_primary_pass=bool(result),two_primary_checks=result,stop_reason=stop_reason,at=now(),source_preserved=exitinfo["source_unchanged"])
 write(out/"queue_stage_result.json",final)
 journal("queue_stage_saved_result",stage=name,directory=str(out),physical_time_s=done["time_s"],solver_steps=done.get("steps"),project_primary_pass=bool(result),reason=stop_reason,returncode=code)
 if ctrl.PAUSE.exists() or stop_reason=="user_queue_pause":return "paused",out
 if not result:return "needs_review",out
 return "accepted",out
def run(request):
 req=ctrl.read(request);token=req["token"];owner=ctrl.read(ctrl.LOCK)
 assert owner.get("token")==token and ctrl.original_ok(),"Queue lock or original M12 audit mismatch"
 assert ctrl.sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==ctrl.read(R/"plan.json")["recovery_policy"]["runbook_sha256"]
 ctrl.no_other_stars()
 stage_name=req.get("stage","M11");start=0 if stage_name=="M11" else 1
 previous=req.get("prior",{});assert start in (0,1)
 journal("queue_resume_accepted",from_stage=stage_name,token=token[:8],previous_m12_untouched=True)
 try:
  for idx in range(start,2):
   if datetime.datetime.now().astimezone().date()!=datetime.date(2026,10,31):
    state(token,"ready_next",STAGES[idx][0],idx,reason="end_of_authorized_day");return
   if ctrl.PAUSE.exists():
    state(token,"paused",STAGES[idx][0],idx,previous.get("directory"));return
   stage=STAGES[idx]
   status,out=run_stage(token,stage,idx,previous)
   if status=="paused":
    state(token,"paused",stage[0],idx,out,reason="saved_user_pause");return
   if status!="accepted":
    state(token,"needs_review",stage[0],idx,out,reason="settling_or_safety_not_verified");return
   if idx==0:
    write(R/"mesh_queue_completed_M11.json",ctrl.read(out/"queue_stage_result.json"))
    state(token,"ready_next","M10",1)
    previous={}
   else:
    write(R/"mesh_queue_completed_M10.json",ctrl.read(out/"queue_stage_result.json"))
  state(token,"done","M10",2,reason="M11_M10_project_primary_saved")
 except BaseException as e:
  current=ctrl.read(ctrl.STATE)
  state(token,"needs_review",current.get("stage",stage_name),current.get("stage_index",start),current.get("directory"),reason=str(e)[:300])
  journal("queue_controller_blocker",error_type=type(e).__name__,reason=str(e)[:300])
  raise
 finally:
  if ctrl.read(ctrl.LOCK).get("token")==token:ctrl.LOCK.unlink()
if __name__=="__main__":
 if len(sys.argv)!=3 or sys.argv[1]!="--worker":raise SystemExit("Use verified queue resume control")
 ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
 try:run(Path(sys.argv[2]))
 finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
