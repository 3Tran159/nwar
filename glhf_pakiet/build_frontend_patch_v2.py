from pathlib import Path
import json,shutil,hashlib
ROOT=Path('E:/NWAR_portable_20261103');OLD=ROOT/'NWAR_GLHF_UI_hotfix';PATCH=ROOT/'NWAR_GLHF_UI_hotfix_v2'
if PATCH.exists():raise ValueError('Existing patch preserved')
shutil.copytree(OLD,PATCH,ignore=shutil.ignore_patterns('__pycache__','QA_summary.json'))
p=PATCH/'payload/wave_view.js';s=p.read_text(encoding='utf8')
a=s.index('// Display-only compatibility');b=s.index('async function refresh(force=false){',a)
helper='''// Display-only observation: advancing history is independent of controller status.
const observedTimes=new Map();
document.documentElement.dataset.nwarUi='20261103-ui2';
function compatibleView(data){
 if(data.empty)return data;
 const jobs=[...(latestState?.jobs||[]),...(latestState?.external||[])];
 const run=jobs.find(j=>j.id===data.run_id)||jobs.find(j=>j.case_id===data.case_id&&j.id===latestState?.current_run?.id);
 const key=data.run_id||data.case_id,current=data.time_s,prior=observedTimes.get(key),now=Date.now();
 const advancing=Number.isFinite(current)&&prior&&current>prior.time;
 const activityAt=advancing?now:(prior?.activityAt||0);
 observedTimes.set(key,{time:current,activityAt});
 const nativeActive=run?.solver_alive===true||run?.solver_active===true||run?.native_active===true||run?.live?.solver_alive===true;
 const fresh=Number.isFinite(run?.live?.age_s)&&run.live.age_s<180;
 const observed=(activityAt>0&&now-activityAt<45000)||(nativeActive&&fresh);
 const unattended=latestState?.worker_alive===false||['interrupted','needs_attention','failed'].includes(run?.observed_status||run?.status);
 if(data.cycle_progress&&data.status==='running'&&!unattended)return data;
 if(!observed&&data.status!=='running')return data;
 const last=data.cycles?.at(-1),start=last?.end??data.first_cycle_progress?.cycle_start_s,T=last?.T||data.period_s;
 if(!Number.isFinite(start)||!Number.isFinite(T)||T<=0)return data;
 const history=run?.live?.history_segments?.flatMap(s=>s.points)||run?.live?.series||[];
 const points=history.filter(p=>p?.length>=3&&p.every(Number.isFinite)&&p[0]>=start&&p[0]<=current).sort((a,b)=>a[0]-b[0]);
 const end=points.at(-1)?.[0],target=start+T,remaining=Math.max(0,target-current),cost=run?.live?.s_per_step;
 const progress={percent:Math.min(99,Math.max(0,100*(current-start)/T)),state:current<target?'recording':'awaiting_crossing',complete:false,cycle_number:data.cycle_count+1,completed_cycles:data.cycle_count,current_time_s:current,cycle_start_s:start,target_time_s:target,period_s:T,period_basis:last?'measured_cycles':'configured_wave',estimated:true,remaining_physical_s:remaining,eta_wall_s:remaining>0&&Number.isFinite(cost)?remaining/.0004*cost:null};
 const partial=points.length>1?{number:data.cycle_count+1,start,end,T,complete:false,provisional:true,phase_estimated:true,phase:points.map(p=>(p[0]-start)/T),time_s:points.map(p=>p[0]),CL:points.map(p=>p[2]),CD:points.map(p=>p[1])}:null;
 return {...data,cycle_progress:progress,in_progress_cycle:partial,ui_history_advancing:observed,ui_controller_attention:unattended};
}

'''
s=s[:a]+helper+s[b:]
s=s.replace("$('view-status').textContent=payload.display_id", "$('view-status').textContent='UI 20261103.2 · '+payload.display_id")
s=s.replace(" const status=payload.project_accepted?", " const status=payload.ui_controller_attention?'Solver history advancing · controller requires attention':payload.project_accepted?")
s=s.replace("$('view-cycle-progress-note').textContent+=' A remaining-time estimate requires fresh samples from a running solver.';", "$('view-cycle-progress-note').textContent+=' A remaining-time estimate requires fresh samples from a running solver.';\n if(payload?.ui_controller_attention)$('view-cycle-progress-note').textContent+=' Controller attention: this is a browser estimate from recorded samples. Automatic finalization and the next wave are not confirmed.';")
p.write_text(s,encoding='utf8')
index=PATCH/'payload/index.html';html=index.read_text(encoding='utf8')
for name in ['app.js','wave_view.js','history_chart.js','convergence_chart.js','style.css']:
 html=html.replace('"/'+name+'"','"/'+name+'?ui=20261103.2"')
index.write_text(html,encoding='utf8')
manifest=json.loads((PATCH/'frontend_manifest.json').read_text())
manifest['id']='GLHF_static_UI_hotfix_20261103_v2'
for item in manifest['files']:
 item['allowed_before_sha256'].append(hashlib.sha256((OLD/'payload'/item['name']).read_bytes()).hexdigest())
 raw=(PATCH/'payload'/item['name']).read_bytes();item.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
(PATCH/'frontend_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
for name in ['Apply UI patch.cmd','CZYTAJ_UI.txt']:
 f=PATCH/name;f.write_text(f.read_text(encoding='utf8').replace('NWAR_GLHF_UI_hotfix','NWAR_GLHF_UI_hotfix_v2'),encoding='utf8')
with (PATCH/'CZYTAJ_UI.txt').open('a',encoding='utf8') as f:f.write('''
Wersja UI 20261103.2: pokazuje otwarty cykl także gdy kontroler jest martwy,
ale historia rośnie. Rozpoznanie przyrostu może wymagać dwóch odświeżeń
(około 8–16 s). Nie oznacza to odzyskania nadzoru kontrolera.
Wiersz nad wykresami musi zawierać UI 20261103.2; jeśli go brak, oglądasz
inny folder/usługę lub starą kartę. Wykonaj Ctrl+F5 i sprawdź log instalatora.
Diagnose dashboard.cmd zapisuje tylko raport o stanie, bez napraw i restartów.
''')
print(json.dumps(dict(patch=str(PATCH),version='20261103.2')))
