from pathlib import Path
from datetime import datetime
import json, os, time, ctypes
from ctypes import wintypes
def j(p):
 try:return json.loads(Path(p).read_text(encoding="utf-8-sig"))
 except Exception: return None
def mem_gib():
 class MEM(ctypes.Structure):
  _fields_=[("dwLength",wintypes.DWORD),("dwMemoryLoad",wintypes.DWORD),("ullTotalPhys",ctypes.c_ulonglong),("ullAvailPhys",ctypes.c_ulonglong),("ullTotalPageFile",ctypes.c_ulonglong),("ullAvailPageFile",ctypes.c_ulonglong),("ullTotalVirtual",ctypes.c_ulonglong),("ullAvailVirtual",ctypes.c_ulonglong),("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
 x=MEM();x.dwLength=ctypes.sizeof(x);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(x));return (round(x.ullAvailPhys/2**30,2),x.dwMemoryLoad)
def cpu_pct():
 class FT(ctypes.Structure):
  _fields_=[("low",wintypes.DWORD),("high",wintypes.DWORD)]
  def value(self):return self.low+self.high*2**32
 def snap():
  i,k,u=FT(),FT(),FT()
  ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i),ctypes.byref(k),ctypes.byref(u))
  return i.value(),k.value(),u.value()
 a=snap();time.sleep(1.5);b=snap()
 idle=b[0]-a[0]; total=b[1]+b[2]-a[1]-a[2]
 return round(100*(1-idle/total),1) if total>0 else None
o={"time":datetime.now().astimezone().isoformat(),"available_RAM_GiB":mem_gib()[0],"memory_load_pct":mem_gib()[1],"logical_CPUs":os.cpu_count(),"cpu_load_pct_1p5s":cpu_pct()}
r=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
w=j(r/"wave24m_preparation_plan.json") or {}
o["wave24m_keys"]=list(w)[:45]
o["wave24m_workflow"]={k:str(v)[:450] for k,v in w.items() if k in ["objective","status","scope","current_execution","conditions_for_start","wave_model","meshes","source","mesh","geometry","propagation","run","errors","run_status"]}
w=j(r/"wave_numerical_review_current.json") or {}
o["numerical_review_keys"]=list(w)[:40]
for k,v in w.items():
 if any(s in k.lower() for s in ("mass","gate","r14","wave","resolution")):
  o["numerical_"+k]=str(v)[:350]
for folder in [Path(r"E:\ntnu\quasi2d_waves_20261029\W20_H24_X4_CPUprop_dt1ms_r1"),Path(r"E:\ntnu\quasi2d_waves_20261029\W20_H24_X4_CPUprop_dt1ms_r2"),Path(r"E:\ntnu\quasi2d_waves_20261029\W20_H24_X4_CPUprop_r2_field_audit_r1")]:
 if not folder.is_dir():continue
 o[folder.name+"_files"]=[(x.name,round(x.stat().st_size/1024**2,2)) for x in folder.iterdir() if x.is_file()][:28]
 for file in folder.glob("*.json"):
  if any(s in file.name.lower() for s in ("completed","summary","result","audit","diagnostic","mass","propagation","progress","setup","config")):
   q=j(file)
   o[folder.name+"/"+file.name]=str(q)[:430]
print(json.dumps(o,ensure_ascii=False,indent=2)[:13000])
