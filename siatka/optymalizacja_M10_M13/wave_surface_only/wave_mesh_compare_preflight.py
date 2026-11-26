from pathlib import Path
import os,json,hashlib,datetime,sys,ctypes,shutil,subprocess,re
root=Path(r"E:\ntnu_mesh_optimization_20261030")
wave=root/"wave_surface_only"
study=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
def js(p):
 try:return json.loads(Path(p).read_text(encoding="utf8-sig"))
 except (ValueError,OSError):return {}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
p=js(root/"plan.json")
print("NOW",datetime.datetime.now().astimezone().isoformat(),"HASH_OK",p["recovery_policy"]["runbook_sha256"]==sha(root/"AUTONOMOUS_RECOVERY_PROMPT.md"))
for folder in [root/"parallel_cpu_20261031",wave,root]:
 for name in ("auxiliary.lock","wave_inlet.lock","wave_halfdt.lock","wave_mesh_comparison.lock","STOP_ALL","recovery.lock"):
  f=folder/name
  if f.exists():print("CONTROL",f, f.read_text(encoding="utf8-sig",errors="replace")[:200] if f.stat().st_size<2000 else f.stat().st_size)
print("PAR_CURRENT",js(root/"parallel_cpu_20261031"/"current.json").get("status"))
print("MAIN",js(root/"mesh_queue_state.json"))
for d in ("C:\\","E:\\"):print("FREE_GiB",d,round(shutil.disk_usage(d).free/1024**3,2))
print("SOURCE",js(wave/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"/"completed.json"))
for name in ("FS_coarse","FS_baseline","FS_fine"):
 f=wave/name/"mesh_exact.CGNS"
 print("GRID",name, f.stat().st_size,sha(f)==js(wave/name/"mesh_exact.validation.json").get("sha256"),js(wave/name/"mesh_exact.validation.json").get("cells"))
for f in wave.glob("*.py"):
 try:
  s=f.read_text(encoding="utf8-sig")
  match=[str((i+1,ln.strip()[:200])) for i,ln in enumerate(s.splitlines()) if "javac" in ln or "Java" in ln and "compile" in ln]
  if match:print("COMPILE_REF",f.name,match[:4])
 except Exception:pass
res=subprocess.run(["powershell","-NoProfile","-Command","Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('starccm+.exe','starccmw.exe','python.exe') } | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress"],capture_output=True,text=True,timeout=20)
print("PROCESSES",res.stdout[:2200])
