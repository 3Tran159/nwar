"""Release ONLY a verified failed independent wave client after lost server and stale history."""
from pathlib import Path
import sys,json,time,subprocess,os
R=Path(r'E:\ntnu_mesh_optimization_20261030');sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
S=R/'wave_surface_only/evening_wave_current.json'
s=rt.read(S);p=Path(s['directory']);pid=s.get('pid')
assert p==R/'wave_surface_only/zero_start_matrix_evening_20261031_182305_689cb9/waves/L20_H500_baseline'
assert pid==27088
error=rt.read(p/'macro_error.json');assert 'Connection reset' in error.get('error','')
log=(p/'star.log').read_text(encoding='utf-8',errors='replace')
assert 'floating point error' in log and 'Non-finite value detected' in log
assert not (p/'completed.json').exists()
assert time.time()-(p/'history.csv').stat().st_mtime>90,'History may still progress'
rows=rt.rows(p/'history.csv');assert rows and int(rows[-1]['step'])==18
assert abs(float(rows[-1]['time_s'])-.418)<1e-8
assert all(time.time()-f.stat().st_mtime>60 for f in p.glob('*.sim')),'A save might still be active'
ident=rt.read(p/'identity.json');source=Path(ident['source'])
assert source.is_file() and rt.sha(source)==ident['source_sha256']
ps="Get-CimInstance Win32_Process | Where-Object {$_.ProcessId -eq 27088} | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
x=subprocess.run(['powershell.exe','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
assert x.returncode==0
proc=json.loads(x.stdout);assert proc['ProcessId']==pid and 'starccm' in proc['Name'].lower()
assert p.name in proc['CommandLine'] and 'zero_start_matrix_evening_20261031_182305_689cb9' in proc['CommandLine']
assert proc['ParentProcessId']==22592,'Unexpected process owner'
# Never touch M13's independently started mesh/client process.
processes=rt.guard.processes();ids={pid}
for _ in range(15):ids|={i for i,(par,_) in processes.items() if par in ids}
assert 32232 not in ids and 8360 not in ids
(p/'STOP').touch()
receipt={'at':rt.now(),'reason':'Confirmed lost STAR server after non-finite numerical failure; no further history, no save in progress','verified_failed_client_pid':pid,'source_unchanged':True,'last_saved_history_time_s':.418,'last_step':18,'M13_untouched':True}
rt.write(p/'verified_failed_frontend_shutdown.json',receipt)
result=subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
receipt['taskkill_returncode']=result.returncode;rt.write(p/'verified_failed_frontend_shutdown.json',receipt)
print(json.dumps(receipt))
