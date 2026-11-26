from pathlib import Path
import datetime,json,hashlib,ctypes,shutil,csv,math,re,collections,urllib.request
R=Path(r"E:\ntnu_mesh_optimization_20261030")
W=R/"wave_surface_only"
ROOT=W/"zero_start_matrix_20261031_13h_R2"
M=R/"M11_G10_M_GPU_queue_20261031_105607_91db08"
CASE=ROOT/"waves"/"L20_H500_coarse"
C=ROOT/"calm"/"L20_coarse"
def obj(p):
 try:return json.loads(p.read_text(encoding="utf8-sig"))
 except Exception as e:return {"missing_or_invalid":type(e).__name__}
def tailcsv(p,n=100):
 out=collections.deque(maxlen=n)
 try:
  with p.open(newline="",encoding="utf8-sig") as f:
   for row in csv.DictReader(f):out.append(row)
 except OSError:return []
 return list(out)
p=obj(R/"plan.json")
hashmatch=hashlib.sha256((R/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()==p["recovery_policy"]["runbook_sha256"]
w=tailcsv(CASE/"history.csv",100)
m=tailcsv(M/"history.csv",200)
g=tailcsv(CASE/"gauges.csv",500)
it=collections.deque(maxlen=180)
errs=collections.Counter()
try:
 with (CASE/"star.log").open(encoding="utf8",errors="replace") as f:
  for line in f:
   z=line.split()
   if len(z)>=10 and z[0].isdigit():
    try:it.append((int(z[0]),float(z[1]),float(z[2]),float(z[4]),float(z[7])))
    except (ValueError,IndexError):pass
   if "Non-finite value detected" in line:
    if "Maximum Velocity" in line: errs["velocity_monitor"]+=1
    elif "Fx_half" in line: errs["force_x_monitor"]+=1
    elif "Fz_half" in line: errs["force_z_monitor"]+=1
except OSError:pass
endit=[z for z in it if z[0]%10==0]
try:
 class Mem(ctypes.Structure):
  _fields_=[("dwLength",ctypes.c_ulong),("dwMemoryLoad",ctypes.c_ulong),
           ("ullTotalPhys",ctypes.c_ulonglong),("ullAvailPhys",ctypes.c_ulonglong),
           ("ullTotalPageFile",ctypes.c_ulonglong),("ullAvailPageFile",ctypes.c_ulonglong),
           ("ullTotalVirtual",ctypes.c_ulonglong),("ullAvailVirtual",ctypes.c_ulonglong),
           ("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
 mm=Mem();mm.dwLength=ctypes.sizeof(mm)
 assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mm))
 ram=round(mm.ullAvailPhys/1024**3,2)
except Exception as e:ram=str(e)
water=[float(x["water_volume_m3"]) for x in w]
forrow=lambda x: dict(first_step=int(x[0]["step"]),last_step=int(x[-1]["step"]),
     first_t=float(x[0].get("time_s",x[0].get("physical_time_s"))),last_t=float(x[-1].get("time_s",x[-1].get("physical_time_s"))),
     wall_s=float(x[-1].get("wall_s",x[-1].get("wall_seconds")))-float(x[0].get("wall_s",x[0].get("wall_seconds")))) if x else None
out={
"time":datetime.datetime.now().astimezone().isoformat(),
"hash_match":hashmatch,
"stops":{str(x):x.exists() for x in [R/"STOP_ALL",W/"STOP_ALL",ROOT/"STOP",CASE/"STOP",Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\STOP_ALL")]},
"locks":{str(x):obj(x) if x.exists() else None for x in [R/"parallel_cpu_20261031"/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_mesh_comparison.lock"]},
"queue":obj(R/"mesh_queue_state.json"),
"auxiliary":obj(W/"zero_start_12_current.json"),
"available_GiB":{"RAM":ram,"C":round(shutil.disk_usage("C:\\").free/2**30,1),"E":round(shutil.disk_usage("E:\\").free/2**30,1)},
"main":forrow(m),
"main_last":m[-1] if m else None,
"wave":forrow(w),
"wave_last":w[-1] if w else None,
"wave_recent_water_volume_range":round(max(water)-min(water),6) if water else None,
"wave_last_gauges":g[-8:],
"wave_last_18_end_iteration":endit[-18:],
"wave_recent_residuals_median":{"continuity":sorted(z[1] for z in endit[-18:])[len(endit[-18:])//2] if endit else None,"xmomentum":sorted(z[2] for z in endit[-18:])[len(endit[-18:])//2] if endit else None},
"wave_nonfinite_legacy_report_counts":dict(errs),
"wave_completion":obj(CASE/"completed.json"),
"calm_acceptance":obj(C/"calm_readiness.json"),
"matrix":obj(ROOT/"matrix_live.json").get("actual_completed"),
}
try:
 with urllib.request.urlopen("http://127.0.0.1:8771/api/mesh-study",timeout=4) as res:
  data=json.load(res)
  out["local_dashboard"]={"ok":True,"keys":list(data)[:15] if isinstance(data,dict) else str(type(data))}
except Exception as e:out["local_dashboard"]={"ok":False,"reason":type(e).__name__}
print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
