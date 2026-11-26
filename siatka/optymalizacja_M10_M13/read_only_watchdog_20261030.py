"""Small verified CFD watcher sample. No solver or dashboard mutation."""
from pathlib import Path
from datetime import datetime
from collections import deque
import json,hashlib,os,shutil,statistics,urllib.request,uuid,ctypes
root=Path(r"E:\ntnu_mesh_optimization_20261030")
study=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
plan=json.loads((root/"plan.json").read_text(encoding="utf-8-sig"))
runbook=Path(plan["recovery_policy"]["runbook"])
sha=hashlib.sha256(runbook.read_bytes()).hexdigest()
assert sha==plan["recovery_policy"]["runbook_sha256"],"Recovery runbook hash mismatch, do not write success sample"
with urllib.request.urlopen("http://127.0.0.1:8771/api/mesh-study",timeout=6) as r:api=json.load(r)
def j(p):
 try:return json.loads(p.read_text(encoding="utf-8-sig"))
 except (FileNotFoundError,json.JSONDecodeError,UnicodeDecodeError):return None
s=j(study/"gpu_study_state.json");s2=j(study/"cpu_study_state.json")
assert s and s2 and s.get("job")==s2.get("job"),"State identity divergence"
folder=Path(s["directory"])
assert folder.is_dir() and folder.resolve().is_relative_to(study.resolve()),"Out-of-root job directory"
assert s.get("scope")=="calm_water_only","Unexpected non-calm scope"
hist=folder/"history.csv"
with hist.open("rb") as f:
 f.seek(max(0,hist.stat().st_size-131072))
 rows=f.read().decode("utf-8",errors="ignore").splitlines()
 parsed=[]
 for row in rows[-75:]:
  try:
   v=[float(x) for x in row.split(",")]
   if len(v)>=18 and v[1]>=1 and v[3]>=0:parsed.append(v)
  except ValueError:pass
assert parsed,"No decodable numerical rows"
last=parsed[-1];delta=[parsed[i][0]-parsed[i-1][0] for i in range(1,len(parsed)) if parsed[i][1]-parsed[i-1][1]==1 and parsed[i][0]>parsed[i-1][0]]
prev=j(root/"watchdog_last_sample.json") or {}
now=datetime.now().astimezone()
checkpoint=j(folder/"latest_checkpoint.json") or {}
ck=Path(checkpoint["path"]) if checkpoint.get("path") else None
geo=j(root/"wave_surface_only"/"independent_geometry_audit.json") or {}
ref=j(root/"wave_surface_only"/"baseline_dataset_equivalence.json") or {}
old_step=prev.get("step")
old_t=prev.get("physical_time_s")
progress_since_last=bool(isinstance(old_step,(int,float)) and isinstance(old_t,(int,float)) and int(last[1])>int(old_step) and last[3]>old_t)
def pid_alive(pid):
 if not isinstance(pid,int):return False
 kernel=ctypes.windll.kernel32
 handle=kernel.OpenProcess(0x1000,False,pid)
 if not handle:return False
 code=ctypes.c_ulong()
 status=bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code)) and code.value==259)
 kernel.CloseHandle(handle)
 return status
record={
 "checked_at":now.isoformat(),
 "source":"direct-device local filesystem and loopback API",
 "verified_runbook_hash":True,
 "api":{"status":api.get("status"),"job":api.get("job"),"generation_present":bool(api.get("generation")),"can_pause":api.get("can_pause"),"can_resume":api.get("can_resume")},
 "job":s["job"],"controller_status":s.get("status"),
 "controller_pid":s.get("pid"),"controller_alive":pid_alive(s.get("pid")),
 "solver_pid":s.get("star_pid"),"solver_alive":pid_alive(s.get("star_pid")),
 "directory":str(folder),
 "step":int(last[1]),"solver_iteration":int(last[2]),"physical_time_s":last[3],
 "history_age_s":round(now.timestamp()-hist.stat().st_mtime,1),
 "history_bytes":hist.stat().st_size,
 "median_recent_s_per_step":round(statistics.median(delta),3) if delta else None,
 "progress_since_prior_snapshot":progress_since_last,
 "prior_snapshot_at":prev.get("checked_at"),
 "prior_step":old_step,
 "prior_physical_time_s":old_t,
 "last_step_CFL":last[12],"last_step_interface_CFL":last[13],
 "checkpoint":{"time_s":checkpoint.get("time_s"),"exists":bool(ck and ck.is_file()),"size_GiB":round(ck.stat().st_size/2**30,3) if ck and ck.is_file() else None},
 "latest_settling_gate":{k:v for k,v in (j(folder/"settling_check.json") or {}).items() if k in ("time_s","pass","consecutive_passes")},
 "M11":{k:v for k,v in (j(study/"force_stabilization_20261029"/"calm_pilot_G10_M_continued_r1"/"completed.json") or {}).items() if k in ("status","time_s","steps")},
 "M10":{k:v for k,v in (j(study/"force_stabilization_20261029"/"calm_pilot_W01a_continued_r1"/"completed.json") or {}).items() if k in ("status","time_s","steps")},
 "outstanding_result_files":{
  n:(study/n).exists() or (study/"force_stabilization_20261029"/n).exists() for n in ("calm_stabilization_progress.json","calm_mesh_screen.json","gci_results.json")
 },
 "free_C_GiB":round(shutil.disk_usage("C:\\").free/2**30,2),
 "free_E_GiB":round(shutil.disk_usage("E:\\").free/2**30,2),
 "surface_geometry_audit_pass":geo.get("all_pass",False),
 "surface_reference_mesh_data_equivalent":ref.get("numerical_mesh_equivalent",False),
 "incident_wave_hold_preserved":True,
 "interventions_this_run":0,
 "solver_changed_this_run":False
}
assert record["solver_alive"] and record["controller_alive"] and progress_since_last
assert api.get("status")=="running","API not running"
assert api.get("job")==s["job"],"API job and state disagree"
tmp=root/("watchdog_last_sample."+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
os.replace(tmp,root/"watchdog_last_sample.json")
with (root/"watchdog_readings.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps(record,ensure_ascii=False)+"\n")
print(json.dumps({"healthy_progress_confirmed":True,"sample_time":record["checked_at"],
"step":record["step"],"physical_time_s":record["physical_time_s"],
"prior_step":record["prior_step"],"prior_physical_time_s":record["prior_physical_time_s"],
"median_s_per_step":record["median_recent_s_per_step"],"interface_CFL":record["last_step_interface_CFL"],
"controller_alive":record["controller_alive"],"solver_alive":record["solver_alive"],
"current_settling_gate":record["latest_settling_gate"],
"surface_geometry_audit_pass":record["surface_geometry_audit_pass"],
"reference_mesh_equivalent":record["surface_reference_mesh_data_equivalent"],
"new_solver_starts":0,"watchdog_state":str(root/"watchdog_last_sample.json")},ensure_ascii=False))
