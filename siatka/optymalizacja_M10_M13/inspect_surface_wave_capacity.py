from pathlib import Path
from datetime import datetime
import json, urllib.request, subprocess, shutil, os
def j(p):
 try: return json.loads(Path(p).read_text(encoding="utf-8-sig"))
 except Exception as e: return {"read_error":str(e)[:100]}
def mini(obj, keys):
 if not isinstance(obj,dict): return str(obj)[:80]
 return {k:(str(obj[k])[:180] if isinstance(obj.get(k),(list,dict)) else obj.get(k)) for k in keys if k in obj}
o={"checked_at":datetime.now().astimezone().isoformat()}
try:
 with urllib.request.urlopen("http://127.0.0.1:8771/api/mesh-study",timeout=7) as f:
  q=json.load(f)
 o["mesh_api"]=mini(q,["status","job","message"])
except Exception as e: o["mesh_api_error"]=str(e)[:160]
base=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
m=j(base/"gpu_study_state.json")
o["mesh_state"]=mini(m,["status","job","pid","star_pid"])
if m.get("directory"):
 p=Path(m["directory"])
 try:
  with (p/"history.csv").open(encoding="utf-8") as f:
   from collections import deque
   last=deque(f,maxlen=1)
  vals=last[0].strip().split(",")
  o["mesh_history"]={"step":vals[1],"time_s":vals[3],"CD":vals[9],"CL":vals[-1]}
 except Exception as e: o["history_error"]=str(e)[:120]
o["disks"]={drive:round(shutil.disk_usage(drive+":\\").free/2**30,2) for drive in ("C","E","F") if Path(drive+":\\").exists()}
try:
 import psutil
 o["cpu_percent_1s"]=psutil.cpu_percent(interval=1)
 o["cpu_logical"]=psutil.cpu_count()
 o["free_ram_GiB"]=round(psutil.virtual_memory().available/2**30,1)
 out=[]
 for p in psutil.process_iter(["pid","name","memory_info"]):
  if any(x in (p.info["name"] or "").lower() for x in ["starccm","python","java"]):
   out.append({"pid":p.info["pid"],"name":p.info["name"],"rssGiB":round((p.info["memory_info"].rss if p.info["memory_info"] else 0)/2**30,2)})
 o["relevant_processes"]=out[:18]
except Exception as e:o["psutil_error"]=str(e)[:200]
try:
 q=subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu","--format=csv,noheader,nounits"],capture_output=True,text=True,timeout=5)
 o["gpu_telemetry"]=(q.stdout.strip().splitlines() or [q.stderr.strip()[:80]])[:2]
except Exception as e: o["gpu_error"]=str(e)[:120]
r=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
for n in ("wave24m_preparation_plan.json","wave_extension_plan.json","wave_numerical_review_current.json","wave_cycle_continuation_plan_r2.json","campaign_hold.json","mesh_selection_plan.json"):
 q=j(r/n)
 o[n]=mini(q,["status","state","scope","objective","waves","preparation","errors","prerequisites","initialization","current_wave_case","latest_execution","cases","wave_model","mass_gate","proposed_next_actions"])
o["wave_files"]=[f.name for f in r.iterdir() if f.is_file() and any(k in f.name.lower() for k in ("wave","r14","mass"))][:75]
o["wave_case_dirs"]={}
for root in (Path(r"E:\ntnu\quasi2d_waves_20261029"),Path(r"F:\ntnu\wave_depth_20261029"),Path(r"F:\ntnu\mesh_screening_20261028")):
 if root.exists():
  o["wave_case_dirs"][str(root)]=[p.name for p in root.iterdir() if p.is_dir()][:30]
print(json.dumps(o,ensure_ascii=False,indent=2)[:15000])
