import subprocess,json,urllib.request
from pathlib import Path
ps='''$p=(Get-NetTCPConnection -LocalPort 8771 -State Listen -ErrorAction SilentlyContinue).OwningProcess;Get-CimInstance Win32_Process | Where-Object {$_.ProcessId -eq $p} | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Compress'''
r=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=20)
print('LISTENER',r.stdout[:500],r.stderr[:300])
p=Path(r'E:\ntnu_mesh_optimization_20261030')
print('M11_LAUNCH_FILES',[x.name for x in p.glob('launch_M11*')])
for name in ('m11_current.json','m11_main.lock','queue_main.lock'):
 f=p/name;print(name,f.exists(),f.stat().st_size if f.exists() else None)
try:
 a=json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/mesh-study',timeout=5))
 print('API',json.dumps(a,ensure_ascii=False)[:1000])
except Exception as e:print('API_ERROR',type(e).__name__,str(e)[:200])
