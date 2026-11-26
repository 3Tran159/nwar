"""Generation-checked M10 dt2 queue control, distinct from active original queue control."""
from pathlib import Path
import datetime, json, os, shutil, subprocess, sys, uuid, ctypes, hashlib, urllib.request
R=Path(r"E:\ntnu_mesh_optimization_20261030")
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
STATE=R/"mesh_queue_state.json"
LOCK=R/"mesh_queue_launch.lock"
PAUSE=R/"mesh_queue_PAUSE"
WORKER=R/"mesh_queue_worker_M10_dt2_20261031.py"
MAIN_PAUSE=B/"dashboard_control"/"pause.json"
def stamp():return datetime.datetime.now().astimezone().isoformat()
def read(path):
 try:return json.loads(Path(path).read_text(encoding="utf-8-sig"))
 except (ValueError,OSError):return {}
def write(path,v):
 p=Path(path); tmp=p.with_name(p.name+"."+uuid.uuid4().hex+".tmp")
 tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8");os.replace(tmp,p)
def alive(pid):
 if not isinstance(pid,int) or pid<1:return False
 k=ctypes.windll.kernel32
 k.OpenProcess.restype=ctypes.c_void_p
 h=k.OpenProcess(0x1000,False,pid)
 if not h:return False
 try:
  val=ctypes.c_ulong()
  return bool(k.GetExitCodeProcess(h,ctypes.byref(val))) and val.value==259
 finally:k.CloseHandle(h)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(4*1024**2),b""):h.update(b)
 return h.hexdigest()
def original_ok():
 plan=read(R/"plan.json"); old=read(MAIN_PAUSE)
 if sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")!=plan.get("recovery_policy",{}).get("runbook_sha256"):return False
 if not plan.get("selection",{}).get("user_primary_CL_CD_override",{}).get("authorized"):return False
 if "G10_F" not in old.get("job","") or not old.get("id"):return False
 if not (B/"STOP").is_file() or (B/"STOP").read_text(encoding="utf8")!=old["id"]:return False
 if alive(old.get("controller_pid")) or alive(old.get("star_pid")):return False
 folder=Path(old["directory"])
 if read(folder/"completed.json").get("status")!="stopped_by_marker":return False
 if read(folder/"exit.json").get("returncode")!=0:return False
 if not (folder/"final.sim").is_file() or not (folder/"EXPORT_OK.json").is_file():return False
 if abs(read(folder/"completed.json").get("time_s",0)-3.3314)>0.0002:return False
 audit=read(R/"project_primary_independent_audit_20261031_0930.json")
 # The original scientific acceptance was independently audited; never promote legacy four-way.
 if audit.get("consecutive_primary_checks",0)<2 or not audit.get("source_sim_sha_verified") or not audit.get("runbook_sha_verified") or not (R/"project_primary_saved_stop_request_result_20261031_0930.json").exists():return False
 return True
def snapshot():
 pilot=read(R/"m11_dt_pilot.lock")
 if pilot and alive(pilot.get("pid")):
  return dict(status="testing_dt",can_pause=False,can_resume=False,generation=pilot.get("token",""),job="M11 Δt comparison",message="Controlled timestep pilot in progress; the saved M11 queue is protected from duplicate restart.",scope="M11 only; M12 saved, waves separate.")
 s=read(STATE)
 if not s:
  if original_ok():
   old=read(MAIN_PAUSE)
   return dict(status="paused",can_pause=False,can_resume=True,generation="queue_initial_"+old["id"],job="Next: M11 / G10_M",message="M12 saved (project CL/CD). Resume continues the queue: M11, then M10. M12 will NOT restart.",scope="Mesh queue only, HF and C01 hold unchanged.")
  return dict(status="needs_review",can_pause=False,can_resume=False,generation="",job=None,message="M12 save/project acceptance not verified; queue resume blocked.")
 status=s.get("status","needs_review"); token=s.get("token","")
 running= status in ("starting","running","saving") and alive(s.get("controller_pid"))
 stage=s.get("stage","M11")
 if running:
  return dict(status="running" if status=="running" else status,can_pause=status=="running",can_resume=False,generation=token,job=stage,message="Queue "+stage+": "+("solver active" if status=="running" else status)+". M12 preserved.",scope="M11 then M10; independent wave diagnostics unaffected.",directory=s.get("directory"))
 if status in ("paused","ready_next"):
  return dict(status="paused",can_pause=False,can_resume=True,generation=token,job="Next: "+stage,message="Saved queue position. Resume continues "+stage+", not M12.",scope="Mesh queue M11 then M10.")
 if status=="done":
  return dict(status="completed",can_pause=False,can_resume=False,generation=token,job="M11/M10",message="Queue finished; check independent CL/CD and mesh agreement.",scope="Calm-water mesh campaign.")
 return dict(status="needs_review",can_pause=False,can_resume=False,generation=token,job=stage,message="Queue needs review. No automatic duplicate start.",scope="Mesh queue only.")
def no_other_stars():
 s='Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "starccm+.exe" } | Select-Object -ExpandProperty ProcessId'
 p=subprocess.run(["powershell","-NoProfile","-Command",s],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise ValueError("Cannot inspect active STAR processes")
 if [x for x in p.stdout.split() if x.isdigit()]:raise ValueError("Another STAR solver is active; queue launch withheld")
def resume(data):
 st=snapshot()
 if set(data)!={"generation"} or not st["can_resume"] or data["generation"]!=st["generation"]:raise ValueError("Queue state changed; refresh. No restart performed.")
 if LOCK.exists() or (R/"m11_dt_pilot.lock").exists() or (R/"m10_dt_pilot.lock").exists():raise ValueError("Queue or timestep pilot lock exists; no duplicate GPU launch")
 sel=read(R/"m10_dt_selection.json")
 if not sel.get("approved_for_continuation_pilot") or not sel.get("pilot_CFL_guard_pass") or not sel.get("force_short_pilot_guard_pass"):
  raise ValueError("M10 dt2 selection has not been approved by bounded matched-time test")
 if not original_ok():raise ValueError("Previous M12 saved receipt or project acceptance not verified")
 for x in (F/"STOP_ALL",R/"STOP_ALL",B/"gpu_live_study.lock",F/"queue.lock",R/"parallel_cpu_20261031"/"auxiliary.lock"):
  if x.exists():raise ValueError("Control hold/resource conflict: "+x.name)
 if PAUSE.exists() and st["status"]!="paused":raise ValueError("Unresolved queue pause")
 no_other_stars()
 osstats=shutil.disk_usage("E:\\").free/1024**3
 if osstats<25 or shutil.disk_usage("C:\\").free/1024**3<15:raise ValueError("Insufficient disk reserve")
 if not WORKER.is_file():raise ValueError("Queue worker missing")
 s=read(STATE);token=uuid.uuid4().hex
 with LOCK.open("x",encoding="utf8") as f:json.dump(dict(token=token,started=stamp(),stage=s.get("stage","M11")),f)
 if PAUSE.exists():PAUSE.unlink() # own marker only, after a verified paused state
 req=R/("mesh_queue_request_"+token+".json")
 write(req,dict(token=token,created=stamp(),resume_from=st["status"],stage=s.get("stage","M11"),prior=s))
 write(STATE,dict(status="starting",token=token,stage=s.get("stage","M11"),stage_index=s.get("stage_index",0),directory=s.get("directory"),at=stamp()))
 try:
  out=(R/("mesh_queue_"+token+".stdout.log")).open("x",encoding="utf8");err=(R/("mesh_queue_"+token+".stderr.log")).open("x",encoding="utf8")
  try:
   p=subprocess.Popen([r"C:\Python315\python.exe",str(WORKER),"--worker",str(req)],cwd=R,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
  finally:out.close();err.close()
  write(STATE,dict(status="starting",token=token,stage=s.get("stage","M11"),stage_index=s.get("stage_index",0),directory=s.get("directory"),controller_pid=p.pid,at=stamp()))
  return dict(message="Queue resumed: "+s.get("stage","M11")+", then M10. M12 remains saved.",pid=p.pid)
 except BaseException:
  write(STATE,dict(status="needs_review",token=token,stage=s.get("stage","M11"),at=stamp(),reason="launcher_exception"))
  raise
def pause(data):
 st=snapshot()
 if set(data)!={"generation"} or not st["can_pause"] or st["generation"]!=data["generation"]:raise ValueError("No matching running queue job")
 q=read(STATE)
 with PAUSE.open("x",encoding="utf8") as f:json.dump(dict(token=q["token"],at=stamp(),stage=q["stage"]),f)
 if q.get("directory"):
  output=Path(q["directory"])
  if output.parent==R and output.is_dir(): (output/"STOP").touch()
 return dict(message="Queue pause requested; only the owned stage will save and stop. M12, HF and C01 are untouched.")
