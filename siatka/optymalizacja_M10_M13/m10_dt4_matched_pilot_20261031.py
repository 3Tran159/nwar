"""Bounded matched-time M10 dt=0.2 vs 0.4 ms from SAME 0.896-s saved checkpoint.
Separate sequential one-GPU runs, no source changes. Never infer settled-time accuracy from pilot.
"""
from pathlib import Path
import os,sys,json,csv,math,time,hashlib,shutil,subprocess,threading,datetime,uuid,statistics
R=Path(r"E:\ntnu_mesh_optimization_20261030")
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
sys.path.insert(0,str(R))
import mesh_queue_control_m10_dt2_20261031 as c
sys.path.insert(0,str(F.parent/"night_20261028"))
from night_queue import STAR,saved_options,redact,free_memory
SOURCE_FOLDER=R/"M10_W01a_GPU_queue_20261031_162517_807fed"
SOURCE=SOURCE_FOLDER/"final.sim"
MACRO=B/"ContinueCalmGPULive.java"
PILOT=R/"M10_W01a_dt0004_matched_GPU_20261031"
LOCK=R/"m10_dt4_pilot.lock"
RESULT=R/"m10_dt4_pilot_result.json"
START=.896
N04=71
TARGET=START+N04*.0004
GIB=2**30
def now():return c.stamp()
def read(p):return c.read(p)
def write(p,x):return c.write(p,x)
def sha(p):return c.sha(p)
def tail(path):
 try:
  with Path(path).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
 except OSError:return []
def reserves():
 ram=free_memory()/GIB
 C=shutil.disk_usage("C:\\").free/GIB
 E=shutil.disk_usage("E:\\").free/GIB
 assert ram>=16 and C>=15 and E>=25,(ram,C,E)
 return dict(RAM_GiB=ram,C_GiB=C,E_GiB=E)
def preflight():
 assert datetime.datetime.now().astimezone().date()==datetime.date(2026,10,31)
 assert c.original_ok()
 plan=read(R/"plan.json")
 assert sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"]
 state=read(c.STATE)
 assert state.get("status")=="paused" and state.get("stage")=="M10"
 assert not c.alive(state.get("controller_pid"))
 assert state.get("directory")==str(SOURCE_FOLDER)
 assert c.PAUSE.exists()
 assert not c.LOCK.exists() and not LOCK.exists() and not PILOT.exists()
 for lk in (R/"m10_dt_pilot.lock",R/"m11_dt_pilot.lock",R/"parallel_cpu_20261031"/"auxiliary.lock",
            F/"STOP_ALL",R/"STOP_ALL",B/"gpu_live_study.lock",F/"queue.lock"):
  assert not lk.exists(),"Conflicting lock/stop: "+str(lk)
 assert read(F/"campaign_hold.json").get("active") is True
 assert read(SOURCE_FOLDER/"completed.json").get("status")=="stopped_by_marker"
 assert abs(read(SOURCE_FOLDER/"completed.json").get("time_s",-1)-START)<1e-8
 assert read(SOURCE_FOLDER/"exit.json").get("returncode")==0 and read(SOURCE_FOLDER/"exit.json").get("source_unchanged") is True
 assert read(SOURCE_FOLDER/"EXPORT_OK.json").get("time_s")==read(SOURCE_FOLDER/"completed.json")["time_s"]
 assert SOURCE.is_file() and SOURCE.stat().st_size>100_000_000
 assert MACRO.is_file() and read(B/"gpu_live_macro_receipt.json")["GPU_macro_sha256"]==sha(MACRO)
 setup=read(SOURCE_FOLDER/"pilot_config.json")
 assert setup.get("cells")==317277 and setup.get("physical_dt_s")==.0002 and setup.get("inner")==10
 c.no_other_stars()
 reserves()
 g=subprocess.run(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],
                  capture_output=True,text=True,timeout=12,creationflags=subprocess.CREATE_NO_WINDOW)
 assert g.returncode==0 and int(g.stdout.strip().splitlines()[0])>=4000
def pilot(tag,dt,N,source_sha,owner):
 assert not (R/"STOP_ALL").exists() and c.PAUSE.exists()
 assert c.read(c.STATE).get("status")=="paused"
 reserves();c.no_other_stars()
 folder=PILOT/tag
 folder.mkdir(exist_ok=False)
 shutil.copy2(SOURCE,folder/"input.sim")
 shutil.copy2(MACRO,folder/MACRO.name)
 assert sha(folder/"input.sim")==source_sha and sha(folder/MACRO.name)==sha(MACRO)
 write(folder/"source_identity.json",dict(source=str(SOURCE),sha256=source_sha,
     source_time_s=START,source_preserved=True))
 write(folder/"pilot_config.json",dict(kind="M10 timestep comparison same saved state",
     dt_s=dt,steps=N,start_s=START,target_s=TARGET,cells=317277,inner=10,gpu=1,
     no_reinitialization=True,controller_token=owner,project_acceptance=False))
 env=dict(os.environ,NTNU_STAB_OUT=str(folder),NTNU_MAP_OUT=str(folder),NTNU_STAB_DT=str(dt),
          NTNU_STAB_TARGET=str(TARGET),NTNU_STAB_INNER="10",NTNU_STAB_CELLS="317277",
          NTNU_STAB_START=str(START),NTNU_STAB_INIT="false",NTNU_STAB_ORDER="SECOND_ORDER",
          NTNU_STAB_BUDGET="1100",NTNU_STAB_PRIOR_HISTORY="",NTNU_CALM_SETTLE="false",
          NTNU_GCI_MAX_CFL="25",NTNU_GCI_INTERFACE_CFL="1")
 cmd=[str(STAR),*saved_options(1),"-gpgpu","auto:1","-batch",str(folder/MACRO.name),str(folder/"input.sim")]
 beg=time.monotonic();why=None
 with (folder/"star.log").open("x",encoding="utf-8") as f:
  process=subprocess.Popen(cmd,cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
    encoding="utf8",errors="replace",text=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.NORMAL_PRIORITY_CLASS)
  write(folder/"process.json",dict(pid=process.pid,controller_pid=os.getpid(),at=now(),one_gpu=True))
  write(PILOT/"current.json",dict(at=now(),status="pilot_running",tag=tag,dt_s=dt,pid=process.pid,
                                 directory=str(folder),other_pilot_not_started=tag=="reference_dt0002"))
  def readout():
   for ln in process.stdout:f.write(redact(ln));f.flush()
  t=threading.Thread(target=readout,daemon=True);t.start()
  while process.poll() is None:
   if (R/"STOP_ALL").exists() or (F/"STOP_ALL").exists():why=why or "STOP_ALL"
   if not c.PAUSE.exists() or c.read(c.STATE).get("status")!="paused":why=why or "queue_generation_changed"
   try:reserves()
   except Exception:why=why or "insufficient_resources"
   if time.monotonic()-beg>1350:why=why or "pilot_budget_timeout"
   if why and not (folder/"STOP").exists():(folder/"STOP").touch()
   time.sleep(4)
  rc=process.wait();t.join(20)
 done=read(folder/"completed.json")
 exitinfo=dict(at=now(),returncode=rc,reason=why,source_unchanged=sha(SOURCE)==source_sha)
 write(folder/"exit.json",exitinfo)
 write(PILOT/"current.json",dict(at=now(),status="stage_finished",tag=tag,
                                dt_s=dt,completed=done,exit_code=rc,reason=why))
 success=(rc==0 and why is None and done.get("status")=="target_reached" and
   done.get("steps")==N and abs(done.get("time_s",0)-TARGET)<1e-8 and
   read(folder/"EXPORT_OK.json").get("time_s")==done.get("time_s") and
   (folder/"final.sim").exists() and (folder/"final.sim").stat().st_size>100_000_000 and
   sha(SOURCE)==source_sha)
 if not success:raise RuntimeError("Stage failed "+tag+" return="+str(rc)+" "+repr(done)+" reason="+str(why))
 data=tail(folder/"history.csv")
 assert len(data)==N
 mx=lambda k:max(float(z[k]) for z in data)
 assert mx("interface_max_CFL")<1.00001 and mx("max_CFL")<25 and mx("max_velocity_m_s")<50
 return folder,data,dict(max_interface_CFL=mx("interface_max_CFL"),
    max_bulk_CFL=mx("max_CFL"),wall_s=float(data[-1]["wall_seconds"]),
    s_per_step=float(data[-1]["wall_seconds"])/N)
def analyze(ref,cand,refperf,candperf):
 r={round(float(x["physical_time_s"]),7):x for x in ref}
 pairs=[(x,r.get(round(float(x["physical_time_s"]),7))) for x in cand]
 assert len(pairs)==N04 and all(y is not None for x,y in pairs)
 M={}
 for key in ("CL","CD"):
  def value(row):
   return float(row["CD"]) if key=="CD" else float(row["CL_total"])-22.718189111947265/3855.6
  v=[100*(value(x)-value(y))/value(y) for x,y in pairs]
  M[key]=dict(mean_signed_pct=statistics.fmean(v),mean_abs_pct=statistics.fmean(abs(z) for z in v),
    last20_mean_abs_pct=statistics.fmean(abs(z) for z in v[-20:]),
    max_abs_pct=max(abs(z) for z in v),last_0p4_value=value(pairs[-1][0]),last_0p2_value=value(pairs[-1][1]))
 pass_for_exploration=all(M[k]["last20_mean_abs_pct"]<.15 and M[k]["max_abs_pct"]<.3 for k in ("CL","CD"))
 guard=candperf["max_interface_CFL"]<1 and candperf["max_bulk_CFL"]<25
 return dict(at=now(),status="bounded_matched_M10_0p2_vs_0p4_test_not_final_settling",
   matched_time_s=[START+.0004,TARGET],source_time_s=START,
   ref_dt_s=.0002,candidate_dt_s=.0004,
   ref_steps=2*N04,candidate_steps=N04,matched_pairs=len(pairs),forces=M,
   ref_performance=refperf,candidate_performance=candperf,
   source_preserved=True,guard_ok=guard,short_force_guard_ok=pass_for_exploration,
   preliminary_exploratory_dt4_supported=bool(guard and pass_for_exploration),
   full_temporal_validation_at_settled_state_required=True,
   caution="CFL close to interface limit; no automatic production accuracy certification.")
def run():
 preflight()
 tok=uuid.uuid4().hex
 with LOCK.open("x",encoding="utf8") as lf:json.dump(dict(token=tok,pid=os.getpid(),at=now(),kind="M10_dual_matched_GPU_dt_test"),lf)
 try:
  PILOT.mkdir(exist_ok=False)
  src_sha=sha(SOURCE)
  write(PILOT/"plan.json",dict(at=now(),source=str(SOURCE),source_sha256=src_sha,
       start_s=START,target_s=TARGET,one_gpu_sequential=True,stages=[
        dict(name="reference_dt0002",dt=.0002,steps=2*N04),
        dict(name="candidate_dt0004",dt=.0004,steps=N04)],
       existing_queue_paused=True))
  rf,rh,rp=pilot("reference_dt0002",.0002,2*N04,src_sha,tok)
  cf,ch,cp=pilot("candidate_dt0004",.0004,N04,src_sha,tok)
  result=analyze(rh,ch,rp,cp)
  write(PILOT/"comparison.json",result)
  write(RESULT,result)
  write(PILOT/"current.json",dict(at=now(),status="completed_matched_pilot",
                                 pilot_result=str(RESULT),exploratory_pass=result["preliminary_exploratory_dt4_supported"]))
  print(json.dumps(result,ensure_ascii=False),flush=True)
 except BaseException as e:
  status=dict(at=now(),status="not_accepted_no_auto_retry",error_type=type(e).__name__,reason=str(e)[:700],source_unmodified=True)
  write(RESULT,status)
  if PILOT.exists():write(PILOT/"current.json",status)
  print(json.dumps(status,ensure_ascii=False),flush=True)
 finally:
  if read(LOCK).get("token")==tok:LOCK.unlink()
if __name__=="__main__":run()
