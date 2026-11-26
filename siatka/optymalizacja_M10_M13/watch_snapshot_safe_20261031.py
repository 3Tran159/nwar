from pathlib import Path
import json,hashlib,datetime,shutil,subprocess,urllib.request
root=Path(r"E:\ntnu_mesh_optimization_20261030")
def read(p):
 try:return json.loads(p.read_text(encoding="utf-8-sig"))
 except Exception:return {}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ps(cmd):
 try:
  x=subprocess.run(["powershell","-NoProfile","-Command",cmd],text=True,capture_output=True,timeout=12)
  return x.stdout.strip() if x.returncode==0 else ""
 except Exception:return ""
plan=read(root/"plan.json")
sha_ok=(sha(root/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan.get("recovery_policy",{}).get("runbook_sha256"))
state=read(root/"mesh_queue_state.json")
directory=Path(state.get("directory") or "Q:\\absent")
progress=read(directory/"progress.json")
proc=read(directory/"process.json")
ids=[int(v) for k,v in proc.items() if k.endswith("_pid") and isinstance(v,int)]
pids=",".join(map(str,ids))
procinfo=ps(f"Get-CimInstance Win32_Process | Where-Object {{$_.ProcessId -in @({pids})}} | Select-Object ProcessId,ParentProcessId,Name,CreationDate | ConvertTo-Json -Compress") if ids else ""
osinfo=ps("Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize | ConvertTo-Json -Compress")
try:osobj=json.loads(osinfo); ram=round(osobj["FreePhysicalMemory"]/1048576,2)
except Exception:ram=None
r={"at":datetime.datetime.now().astimezone().isoformat(),"runbook_hash_ok":sha_ok,"active_stage":state.get("stage"),"queue_token":state.get("token"),"steps":progress.get("steps"),"physical_time_s":progress.get("time_s"),"dt_s":0.0002,"CL":progress.get("CL"),"CD":progress.get("CD"),"max_interface_CFL":progress.get("interface_CFL"),"CFL":progress.get("CFL"),"processes":json.loads(procinfo) if procinfo else "not_read","ram_available_GiB":ram,"C_free_GiB":round(shutil.disk_usage("C:\\").free/2**30,2),"E_free_GiB":round(shutil.disk_usage("E:\\").free/2**30,2),"STOP_ALL":Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\STOP_ALL").exists(),"auxiliary":read(root/"parallel_cpu_20261031"/"current.json").get("status"),"auxiliary_lock":(root/"parallel_cpu_20261031"/"auxiliary.lock").exists()}
try:
 with urllib.request.urlopen("http://127.0.0.1:8771/api/mesh-study",timeout=3) as x:
  payload=json.load(x)
  r["api_http"]=x.status
  r["api_fields"]={k:payload.get(k) for k in ("status","current_job","queue_status") if k in payload}
except Exception as e:r["api_error"]=str(e)[:200]
try:
 v=subprocess.run(["nvidia-smi","--query-gpu=temperature.gpu,memory.used,memory.free,utilization.gpu","--format=csv,noheader,nounits"],text=True,capture_output=True,timeout=6)
 r["gpu_metrics"]=v.stdout.strip()[:300] if v.returncode==0 else "unavailable"
except Exception as e:r["gpu_metrics"]=type(e).__name__
journal=root/"watch_status_20261031.jsonl"
with journal.open("a",encoding="utf8") as f:f.write(json.dumps(r,ensure_ascii=False)+"\n")
print(json.dumps(r,ensure_ascii=False))
