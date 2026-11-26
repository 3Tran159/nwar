from pathlib import Path
import json,zipfile,shutil,hashlib,datetime
ROOT=Path('E:/NWAR_portable_20261103');QA=ROOT/'QA_frontend';PATCH=ROOT/'NWAR_GLHF_UI_hotfix'
NAMES=['index.html','style.css','app.js','wave_view.js','history_chart.js','convergence_chart.js']
def sha(data):return hashlib.sha256(data).hexdigest()
def put(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data if isinstance(data,str) else json.dumps(data,indent=2),encoding='utf8')
if PATCH.exists():raise ValueError('Existing frontend patch preserved')
QA.mkdir(exist_ok=True)
original={}
with zipfile.ZipFile(ROOT/'NWAR_Windows_2602_2606.zip') as z:
 for name in NAMES:original[name]=z.read('NWAR_Windows_2602_2606/app/'+name)
records=[]
for name in NAMES:
 data=(ROOT/'QA_v3/candidate/app'/name).read_text(encoding='utf8')
 if name=='index.html':
  data=data.replace('Q = mean wave CD over complete cycles 2-5 (cycle 1 excluded) − mean C01 CD.','Q = mean wave CD over the installed backend averaging window − mean C01 CD.')
  data=data.replace('Four-cycle means at x = 0:','Accepted cycle means at x = 0:')
 if name=='app.js':
  data=data.replace('Records 5 complete measured cycles. Cycle 1 is excluded; cycles 2-5 must pass repeatability before acceptance.','Run limits and acceptance follow the installed controller. This UI does not change calculation settings.')
  data=data.replace('To cycle 5','Controller estimate')
 if name=='wave_view.js':
  data=data.replace('Cycles 2–5 appear below; cycle 1 is excluded. Acceptance is checked separately.', 'Displayed cycle windows follow the installed backend. Acceptance is checked separately.')
  old="'Cycles 2-5: '+payload.cycles.length+' complete measured cycles (cycle 1 excluded)'"
  new="(payload.cycle_policy_id?'Cycles 2-5: '+payload.cycles.length+' complete measured cycles (cycle 1 excluded)':payload.cycles.length+' complete measured cycles supplied by the installed backend')"
  assert old in data;data=data.replace(old,new)
  old="' Target: 5 complete cycles; cycle 1 is startup and excluded from means, repeatability and Q. Force timing and cycle mean offsets are preserved. An incomplete cycle does not count toward acceptance.'"
  new="(payload.cycle_policy_id?' Target: 5 complete cycles; cycle 1 is excluded from analysis.':' Run limits, analysis and Q remain those of the installed backend.')+' Force timing and cycle mean offsets are preserved. An incomplete cycle does not count toward acceptance.'"
  assert old in data;data=data.replace(old,new)
  data=data.replace('payload=data;render();','payload=compatibleView(data);render();')
  helper='''// Display-only compatibility with the first portable backend. No requests mutate data.
function compatibleView(data){
 if(data.empty||data.cycle_progress||data.status!=='running')return data;
 const last=data.cycles?.at(-1),start=last?.end??data.first_cycle_progress?.cycle_start_s,T=last?.T||data.period_s;
 if(!Number.isFinite(start)||!Number.isFinite(T)||T<=0)return data;
 const jobs=[...(latestState?.jobs||[]),...(latestState?.external||[])],run=jobs.find(j=>j.id===data.run_id);
 const history=run?.live?.history_segments?.flatMap(s=>s.points)||run?.live?.series||[];
 const points=history.filter(p=>p?.length>=3&&p.every(Number.isFinite)&&p[0]>=start&&p[0]<=data.time_s).sort((a,b)=>a[0]-b[0]);
 const current=data.time_s,end=points.at(-1)?.[0],target=start+T,remaining=Math.max(0,target-current),cost=run?.live?.s_per_step;
 const progress={percent:Math.min(99,Math.max(0,100*(current-start)/T)),state:current<target?'recording':'awaiting_crossing',complete:false,cycle_number:data.cycle_count+1,completed_cycles:data.cycle_count,current_time_s:current,cycle_start_s:start,target_time_s:target,period_s:T,period_basis:last?'measured_cycles':'configured_wave',estimated:true,remaining_physical_s:remaining,eta_wall_s:remaining>0&&Number.isFinite(cost)?remaining/.0004*cost:null};
 const partial=points.length>1?{number:data.cycle_count+1,start,end,T,complete:false,provisional:true,phase_estimated:true,phase:points.map(p=>(p[0]-start)/T),time_s:points.map(p=>p[0]),CL:points.map(p=>p[2]),CD:points.map(p=>p[1])}:null;
 return {...data,cycle_progress:progress,in_progress_cycle:partial};
}

'''
  data=data.replace('async function refresh(force=false){',helper+'async function refresh(force=false){')
 put(PATCH/'payload'/name,data);raw=(PATCH/'payload'/name).read_bytes()
 allowed=[sha(original[name])]
 for folder in ['QA_v2/patch_candidate/app','QA_v3/candidate/app']:
  path=ROOT/folder/name
  if path.exists():allowed.append(sha(path.read_bytes()))
 records.append(dict(name=name,sha256=sha(raw),bytes=len(raw),allowed_before_sha256=list(dict.fromkeys(allowed))))
put(PATCH/'frontend_manifest.json',dict(id='GLHF_static_UI_hotfix_20261103',created=datetime.datetime.now().astimezone().isoformat(),frontend_only=True,files=records))
shutil.copy2(Path(__file__).parent/'templates/apply_frontend_patch.py',PATCH/'apply_frontend_patch.py')
put(PATCH/'Apply UI patch.cmd','''@echo off
setlocal
if not exist "%~dp0..\\runtime\\python.exe" (
 echo Extract NWAR_GLHF_UI_hotfix inside the NWAR folder, beside app, assets and runtime.
 pause
 exit /b 1
)
set "PYTHONHOME=%~dp0..\\runtime"
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
"%~dp0..\\runtime\\python.exe" "%~dp0apply_frontend_patch.py"
set "UI_PATCH_EXIT=%ERRORLEVEL%"
pause
exit /b %UI_PATCH_EXIT%
''')
put(PATCH/'CZYTAJ_UI.txt','''GLHF — wyłącznie frontend, aktualizacja podczas obliczeń

1. Rozpakuj NWAR_GLHF_UI_hotfix wewnątrz istniejącej paczki NWAR,
   obok app, assets i runtime.
2. Uruchom NWAR_GLHF_UI_hotfix\\Apply UI patch.cmd.
3. Po komunikacie sukcesu odśwież kartę dashboardu przez Ctrl+F5.

Nie zamykaj dashboardu, nie pauzuj solvera ani nie restartuj usługi.
Patch podmienia tylko index.html, style.css oraz cztery pliki JavaScript.
Aktualizuje też sumy kontrolne tych sześciu plików w spisie paczki.
Nie uruchamia i nie zatrzymuje procesów. Nie edytuje plików Python,
makr Java, kolejki, ustawień, CSV, wyników, C01/PRE ani plików .sim.
RAM, liczba cykli, kryteria akceptacji i analiza Q pozostają bez zmian.

Nowy wygląd: interaktywne nakładanie cykli, dorysowywanie bieżącego
cyklu i odliczanie, dwie sondy z ręcznym przesunięciem fazy. Dla starszego
backendu odliczanie i otwarty wykres są tylko estymacją w przeglądarce
z już zapisanych punktów; zamknięcie cyklu i zaliczenie ustala backend.
W szczególności ten patch NIE zmienia czterech cykli na pięć i nie zmienia
zasady pomijania pierwszego cyklu w analizie.

Obsługuje oryginalną paczkę, patch v2 i pełny patch v3, wersje 2602/2606.
Aktualizuje paczkę i istniejące foldery wyników z launcher.json oraz
workspaces/2602 i workspaces/2606. Dodatkowy katalog można wskazać:
runtime\\python.exe NWAR_GLHF_UI_hotfix\\apply_frontend_patch.py --workspace-root "D:\\wyniki"
Opcja --check nie zapisuje plików. Kopie UI są w .nwar_frontend_backups.
Lokalne, nierozpoznane zmiany wyglądu są chronione przed nadpisaniem.
Nie łącz instalacji tego hotfixu z instalacją innego patcha w tym samym czasie.
''')
print(json.dumps(dict(patch=str(PATCH),static_files=len(records),payload_bytes=sum(x['bytes'] for x in records))))
