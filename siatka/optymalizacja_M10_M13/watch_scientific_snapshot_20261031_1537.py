"""Read-only CFD safety/science snapshot. Writes ONLY distinct new E: report files."""
from pathlib import Path
import csv,json,math,statistics,datetime,hashlib,shutil,ctypes,subprocess
R=Path(r"E:\ntnu_mesh_optimization_20261030")
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
M11=R/"M11_G10_M_GPU_queue_20261031_105607_91db08"
M12=B/"force_stabilization_20261029"/"calm_settle_G10_F_GPU_live_r2_resume_20261030_173420_4854e1"
R4=R/"wave_surface_only"/"zero_start_matrix_R2_coarse_continuation_20261031_4"/"waves"/"L20_H500_coarse"
def j(path): return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def data(path):
 with Path(path).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def ram_gib():
 class MS(ctypes.Structure):
  _fields_=[("dwLength",ctypes.c_ulong),("dwMemoryLoad",ctypes.c_ulong),("ullTotalPhys",ctypes.c_ulonglong),("ullAvailPhys",ctypes.c_ulonglong),("ullTotalPageFile",ctypes.c_ulonglong),("ullAvailPageFile",ctypes.c_ulonglong),("ullTotalVirtual",ctypes.c_ulonglong),("ullAvailVirtual",ctypes.c_ulonglong),("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
 m=MS();m.dwLength=ctypes.sizeof(MS)
 return round(m.ullAvailPhys/1024**3,2) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) else None
def pid_alive(p):
 p=int(p);h=ctypes.windll.kernel32.OpenProcess(0x1000,False,p)
 if not h:return False
 v=ctypes.c_ulong();ok=ctypes.windll.kernel32.GetExitCodeProcess(h,ctypes.byref(v));ctypes.windll.kernel32.CloseHandle(h)
 return bool(ok and v.value==259)
def mean(x,k):return statistics.fmean(float(r[k]) for r in x)
def stat(x,k):
 v=[float(r[k]) for r in x];m=statistics.fmean(v)
 return {"mean":m,"rms_pct":100*statistics.pstdev(v)/abs(m)}
def fullwin(rows,now,s=0.2):
 return [r for r in rows if now-s+1e-9 < float(r["physical_time_s"]) <= now+1e-9]
def delta_pct(a,b):return 100*(a/b-1)
plan=j(R/"plan.json");hashok=hashlib.sha256((R/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()==plan["recovery_policy"]["runbook_sha256"]
owner=j(R/"parallel_cpu_20261031"/"auxiliary.lock")
proc=j(R4/"process.json")
m11state=j(R/"mesh_queue_state.json")
m11proc=j(M11/"process.json")
mon=j(R4/"monitor.json")
progress=j(R4/"progress.json")
setup=j(R4/"wave_setup_audit.json")
identity=j(R4/"identity.json")
rawm=data(M11/"history.csv")
last_t=float(rawm[-1]["physical_time_s"])
w1=fullwin(rawm,last_t-0.2);w2=fullwin(rawm,last_t)
f1={k:stat(w1,k) for k in ("CL","CD")}
f2={k:stat(w2,k) for k in ("CL","CD")}
dpress=(mean(w2,"pressure_drag_N")-mean(w1,"pressure_drag_N"))/3855.6
dvisc=(mean(w2,"viscous_drag_N")-mean(w1,"viscous_drag_N"))/3855.6
cd=abs(f2["CD"]["mean"])
m12last=data(M12/"history.csv")[-1]
v=[]
try:
 x=subprocess.run(["nvidia-smi","--query-gpu=temperature.gpu,utilization.gpu,memory.free,clocks_throttle_reasons.active","--format=csv,noheader,nounits"],timeout=7,capture_output=True,text=True)
 v=x.stdout.strip().splitlines()[:2] if x.returncode==0 else [x.stderr.strip()[:200]]
except Exception as e:v=[str(e)[:120]]
m11p=int(m11proc.get("star_pid",m11state.get("star_pid",0)))
report={
 "at":datetime.datetime.now().astimezone().isoformat(),
 "runbook_hash_ok":hashok,
 "STOP_ALL":(R/"STOP_ALL").exists() or Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\STOP_ALL").exists(),
 "campaign_hold":Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\campaign_hold.json").exists(),
 "ram_available_GiB":ram_gib(),
 "C_free_GiB":round(shutil.disk_usage("C:\\").free/1024**3,2),
 "E_free_GiB":round(shutil.disk_usage("E:\\").free/1024**3,2),
 "gpu_query":v,
 "M11":{"steps":int(rawm[-1]["step"]),"t_s":last_t,"dt_s":float(rawm[-1]["dt_s"]),
  "CL_instant":float(rawm[-1]["CL"]),"CD_instant":float(rawm[-1]["CD"]),"alive":pid_alive(m11p),
  "previous_window":f1,"latest_window":f2,"mean_shift_pct":{k:delta_pct(f2[k]["mean"],f1[k]["mean"]) for k in ("CL","CD")},
  "component_delta_over_totalCD_pct":{"pressure":100*abs(dpress)/cd,"viscous":100*abs(dvisc)/cd,"sum_moduli":100*(abs(dpress)+abs(dvisc))/cd,"opposite_signs":dpress*dvisc<0},
  "one_diagnostic_pair_pass":all(abs(delta_pct(f2[k]["mean"],f1[k]["mean"]))<.5 and f1[k]["rms_pct"]<.5 and f2[k]["rms_pct"]<.5 for k in ("CL","CD")),
  "two_successive_formal_checks_verified":False},
 "M12":{"saved_paused":True,"last_t_s":float(m12last["physical_time_s"]),"CL_instant":float(m12last["CL"]),"CD_instant":float(m12last["CD"])},
 "R4":{"owner_pid":owner.get("pid"),"owner_alive":pid_alive(owner.get("pid",0)),"star_pid":proc.get("pid"),"star_alive":pid_alive(proc.get("pid",0)),
  "owner_pid_match":owner.get("pid")==proc.get("controller"),
  "dt_s":setup.get("dt_s"),"source_t_s":setup.get("source_t_s"),"reinitialized":setup.get("initialization_performed"),
  "progress":progress,"monitor":mon,"source_identity":identity,
  "slowdown_exceeds_twice":sum(z.get("slowdown_pct",0)>15 for z in mon.get("main_windows",[])[-2:])==2,
  "not_wave_accepted":True}
}
out=R/"watch_scientific_snapshot_20261031_1537.json"
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:report[k] for k in ["at","runbook_hash_ok","STOP_ALL","campaign_hold","ram_available_GiB","C_free_GiB","E_free_GiB","gpu_query","M11","R4"]},ensure_ascii=False,indent=2)[:10500])
