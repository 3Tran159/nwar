"""Bounded same-source M11 dt=0.0002 vs recorded dt=0.0001 pilot. Never edits original source or M12."""
from pathlib import Path
import sys,os,json,time,uuid,datetime,hashlib,shutil,subprocess,threading,csv,statistics,math
import mesh_queue_control_20261031 as c
R=c.R;B=c.B;F=c.F
sys.path.insert(0,str(F.parent/"night_20261028"))
from night_queue import STAR,saved_options,redact,free_memory
LOCK=R/"m11_dt_pilot.lock"
SOURCE=B/"force_stabilization_20261029"/"calm_pilot_G10_M_continued_r1"/"final.sim"
REF=R/"M11_G10_M_GPU_queue_20261031_104358_b59373"
MACRO=B/"ContinueCalmGPULive.java"
DT=.0002;N=71;START=.591;TARGET=START+N*DT
def now():return c.stamp()
def write(p,v):c.write(p,v)
def preflight():
 assert now()[:10]=="2026-10-31"
 assert c.original_ok()
 assert c.sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==c.read(R/"plan.json")["recovery_policy"]["runbook_sha256"]
 q=c.read(c.STATE);assert q["stage"]=="M11" and q["status"]=="paused"
 assert not c.alive(q["controller_pid"]), "Previous M11 controller not exited"
 d=c.read(REF/"completed.json");e=c.read(REF/"exit.json")
 assert d["status"]=="stopped_by_marker" and e["returncode"]==0 and e["source_unchanged"] is True
 assert (REF/"final.sim").is_file() and (REF/"EXPORT_OK.json").is_file()
 assert abs(d["time_s"]-.6052)<1e-8
 assert not c.LOCK.exists() and not LOCK.exists()
 assert c.PAUSE.exists(), "Queue must remain paused during GPU dt pilot"
 for x in (R/"parallel_cpu_20261031"/"auxiliary.lock",F/"queue.lock",F/"STOP_ALL",R/"STOP_ALL",B/"gpu_live_study.lock"):
  assert not x.exists(), "Conflicting lock/stop "+str(x)
 c.no_other_stars()
 assert (SOURCE).stat().st_size>100_000_000
 assert c.read(B/"gpu_live_macro_receipt.json")["GPU_macro_sha256"]==c.sha(MACRO)
 with (REF/"history.csv").open(encoding="utf-8-sig",newline="") as f: h=list(csv.DictReader(f))
 assert len(h)>=2*N
 assert abs(float(h[-1]["physical_time_s"])-TARGET)<1e-8
 assert all(abs(float(x["dt_s"])-.0001)<1e-12 for x in h)
 ram=free_memory()/1024**3;dv1=shutil.disk_usage("C:\\").free/1024**3;dv2=shutil.disk_usage("E:\\").free/1024**3
 assert ram>=16 and dv1>=15 and dv2>=25
 q=subprocess.run(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=12,creationflags=subprocess.CREATE_NO_WINDOW)
 assert q.returncode==0 and int(q.stdout.strip().splitlines()[0])>=4000
 return h
def analyze(out,ref):
 with (out/"history.csv").open(encoding="utf-8-sig",newline="") as f:h=list(csv.DictReader(f))
 by={round(float(r["physical_time_s"]),8):r for r in ref}
 pairs=[(r,by[round(float(r["physical_time_s"]),8)]) for r in h if round(float(r["physical_time_s"]),8) in by]
 assert len(pairs)==N
 metrics={}
 for key in ("CL","CD"):
  def val(x):
   if key=="CD":return float(x["CD"])
   return float(x["CL_total"])-22.718189111947265/3855.6
  a=[val(x) for x,_ in pairs];b=[val(y) for _,y in pairs]
  rel=[100*(u-v)/v for u,v in zip(a,b)]
  metrics[key]={"mean_relative_signed_pct":statistics.fmean(rel),"mean_abs_relative_pct":statistics.fmean(abs(x) for x in rel),"last_20_mean_abs_relative_pct":statistics.fmean(abs(x) for x in rel[-20:]),"last_20_mean_signed_pct":statistics.fmean(rel[-20:]),"maximum_abs_relative_pct":max(abs(x) for x in rel),"pilot_endpoint":a[-1],"reference_endpoint":b[-1]}
 def values(key):return [float(x[key]) for x in h]
 maxci=max(values("interface_max_CFL"));maxbulk=max(values("max_CFL"))
 done=c.read(out/"completed.json");ex=c.read(out/"exit.json")
 report=dict(status="bounded_dt_sensitivity_only_not_settled",at=now(),reference_time_s=[START+.0002,TARGET],reference_dt_s=.0001,pilot_dt_s=DT,physical_time_steps=N,paired_samples=len(pairs),max_interface_CFL=maxci,max_bulk_CFL=maxbulk,forces=metrics,guard_ok=maxci<=1.00001 and maxbulk<=25 and max(values("max_velocity_m_s"))<50,compare_only_startup_not_final_CL_CD=True,source_preserved=ex.get("source_unchanged"),solver_complete=done.get("status")=="target_reached" and ex.get("returncode")==0,ready_for_full_dt_change=False,reason="Early-time matched force and CFL check only. Full comparison at settled time still needed before assigning accuracy.")
 write(out/"dt_pilot_comparison.json",report);write(R/"m11_dt_pilot_result.json",report)
 return report
def main():
 ref=preflight();token=uuid.uuid4().hex
 with LOCK.open("x",encoding="utf8") as f:json.dump(dict(pid=os.getpid(),token=token,at=now(),kind="M11_dt_0.0002_GPU"),f)
 try:
  folder=R/("M11_G10_M_dt0002_GPU_pilot_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+token[:6])
  folder.mkdir(exist_ok=False);src_sha=c.sha(SOURCE);shutil.copy2(SOURCE,folder/"input.sim");assert c.sha(SOURCE)==src_sha and c.sha(folder/"input.sim")==src_sha
  shutil.copy2(MACRO,folder/MACRO.name)
  assert c.sha(folder/MACRO.name)==c.sha(MACRO)
  write(folder/"source_identity.json",dict(path=str(SOURCE),sha256=src_sha,reinitialized=False))
  write(folder/"pilot_config.json",dict(dt_s=DT,steps=N,start_time_s=START,target_time_s=TARGET,case="M11",source="original t=0.591 pilot",compared_to="separately stopped 0.1ms M11 saved run",production_acceptance=False))
  env=dict(os.environ,NTNU_STAB_OUT=str(folder),NTNU_MAP_OUT=str(folder),NTNU_STAB_DT=str(DT),NTNU_STAB_TARGET=str(TARGET),NTNU_STAB_INNER="10",NTNU_STAB_CELLS="595285",NTNU_STAB_START=str(START),NTNU_STAB_INIT="false",NTNU_STAB_ORDER="SECOND_ORDER",NTNU_STAB_BUDGET="1200",NTNU_STAB_PRIOR_HISTORY="",NTNU_CALM_SETTLE="false",NTNU_GCI_MAX_CFL="25",NTNU_GCI_INTERFACE_CFL="1")
  c.no_other_stars()
  start=time.monotonic();stop_reason=None;proc=None
  with (folder/"star.log").open("x",encoding="utf8") as f:
   proc=subprocess.Popen([str(STAR),*saved_options(1),"-gpgpu","auto:1","-batch",str(folder/MACRO.name),str(folder/"input.sim")],cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding="utf8",errors="replace",text=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.NORMAL_PRIORITY_CLASS)
   write(folder/"process.json",dict(pid=proc.pid,controller_pid=os.getpid(),at=now(),gpu=True,workers=1))
   write(R/"m11_dt_pilot_current.json",dict(status="solver_launched_not_yet_steps",at=now(),directory=str(folder),pid=proc.pid))
   with (R/"attempts.jsonl").open("a",encoding="utf8") as jf:jf.write(json.dumps(dict(at=now(),event="M11_GPU_dt_double_bounded_test_launched",directory=str(folder),dt_s=DT,steps=N,original_unchanged=True,expected_CFL="interface about 0.72 predicted; unverified"),ensure_ascii=False)+"\n")
   def drain():
    for line in proc.stdout:f.write(redact(line));f.flush()
   th=threading.Thread(target=drain,daemon=True);th.start()
   while proc.poll() is None:
    if (R/"STOP_ALL").exists() or (F/"STOP_ALL").exists():stop_reason="STOP_ALL"
    if time.monotonic()-start>1450:stop_reason="pilot_time_limit"
    if free_memory()/1024**3<16 or shutil.disk_usage("E:\\").free/1024**3<25:stop_reason="resources"
    if stop_reason and not (folder/"STOP").exists():(folder/"STOP").touch()
    time.sleep(4)
   rc=proc.wait();th.join(15)
  write(folder/"exit.json",dict(returncode=rc,source_unchanged=c.sha(SOURCE)==src_sha,gpu=True,workers=1,stop_reason=stop_reason))
  done=c.read(folder/"completed.json")
  if rc or stop_reason or done.get("status")!="target_reached" or not (folder/"EXPORT_OK.json").exists():
   write(R/"m11_dt_pilot_result.json",dict(status="failed_or_not_finished",at=now(),directory=str(folder),done=done,reason=stop_reason));return
  report=analyze(folder,ref)
  print(json.dumps(report,ensure_ascii=False),flush=True)
 finally:
  if c.read(LOCK).get("token")==token:LOCK.unlink()
if __name__=="__main__":main()
