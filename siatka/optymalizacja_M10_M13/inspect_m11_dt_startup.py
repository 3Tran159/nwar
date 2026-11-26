import subprocess,json,os,time
from pathlib import Path
r=Path(r"E:\ntnu_mesh_optimization_20261030")
p=r/"M11_G10_M_dt0002_GPU_pilot_20261031_105103_6e9452"
ps='$names=@("starccm+.exe","starccmw.exe","mpiexec.exe","smpd.exe","python.exe","pythonw.exe"); Get-CimInstance Win32_Process | Where-Object {$names -contains $_.Name} | Select-Object ProcessId,ParentProcessId,Name,CreationDate,KernelModeTime,UserModeTime,WorkingSetSize | ConvertTo-Json -Compress'
res=subprocess.run(["powershell","-NoProfile","-Command",ps],capture_output=True,text=True,timeout=25)
print("TIME",time.strftime("%Y-%m-%d %H:%M:%S"))
print("PROCESSES",res.stdout[:4000],"ERR",res.stderr[:200])
for n in ("star.log","setup.json","history.csv","completed.json","macro_error.txt"):
 f=p/n;print(n,f.exists(),f.stat().st_size if f.exists() else None,f.stat().st_mtime if f.exists() else None)
