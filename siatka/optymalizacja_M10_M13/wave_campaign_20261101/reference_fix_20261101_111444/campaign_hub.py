"""Current CFD campaign and one provenance-preserving result catalog.
Read solver artifacts only. Write ONLY derived dashboard assets/catalog exports.
Completed runs are archived logically, never moved, renamed or deleted.
"""
from pathlib import Path
from datetime import datetime,timezone
import csv,ctypes,hashlib,io,json,math,os,re,statistics,time,uuid
HERE=Path(__file__).resolve().parent
E=Path(r'E:\ntnu_mesh_optimization_20261030')
W=E/'wave_surface_only'
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
Q2=F.parent/'quasi2d_012_20261029'
STUDY=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030')
PUBLIC=F.parent/'dashboard_work_20261030'
CATALOG=E/'results_catalog'
VERSION='campaign-hub-v1-20261031'
OFFSET=22.718189111947265/3855.6
SKIP={'__pycache__','deps311','node_modules','plots','qa_browser_profile'}

def read(p,default=None):
 try:
  p=Path(p)
  if p.stat().st_size>12_000_000:return default if default is not None else {}
  return json.loads(p.read_text(encoding='utf-8-sig'))
 except (OSError,ValueError,TypeError):return default if default is not None else {}
def num(v):
 try:
  f=float(v);return f if math.isfinite(f) else None
 except (ValueError,TypeError):return None
def timestamp(p):
 try:return Path(p).stat().st_mtime
 except OSError:return 0
def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat() if t else None
def digest_id(p):return hashlib.sha256(str(p).casefold().encode()).hexdigest()[:16]
def alive(pid):
 if not isinstance(pid,int) or pid<1:return False
 try:
  k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p;k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
  k.CloseHandle.argtypes=[ctypes.c_void_p];k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
  h=k.OpenProcess(0x1000,False,pid)
  if not h:return False
  try:
   code=ctypes.c_ulong();return bool(k.GetExitCodeProcess(h,ctypes.byref(code))) and code.value==259
  finally:k.CloseHandle(h)
 except (OSError,AttributeError):return False

def csv_tail(p,limit=1400000):
 try:
  with Path(p).open('rb') as f:
   header=f.readline().decode('utf-8-sig',errors='replace').strip();start=f.tell()
   f.seek(0,2);size=f.tell();f.seek(max(start,size-limit))
   if size-limit>start:f.readline()
   text=f.read().decode('utf-8',errors='replace')
  if not header:return []
  return [r for r in csv.DictReader(io.StringIO(header+'\n'+text)) if None not in r]
 except (OSError,ValueError,csv.Error):return []

def keys_match(row):
 return num(row.get('physical_time_s',row.get('time_s')))
def cl_value(r,known_baseline):
 if num(r.get('CL_dynamic')) is not None:return num(r['CL_dynamic'])
 if num(r.get('CL')) is not None:return num(r['CL'])
 t=num(r.get('CL_total'))
 return t-OFFSET if t is not None and known_baseline else None

def history_data(folder,foil=False,legacy=False,setup=None):
 setup=setup or {};rows=csv_tail(folder/'history.csv');valid=[r for r in rows if keys_match(r) is not None]
 if not valid:return {'t_s':None,'step':None,'dt_s':None,'s_per_step':None,'CL':None,'CD':None,'mean_CL':None,'mean_CD':None,'mean_window':None,'series':[],'rows':[]}
 known=legacy or (abs((num(setup.get('reference_area_m2')) or 0)-.0238)<1e-9 and abs((num(setup.get('span_m')) or 0)-.02)<1e-9)
 last=valid[-1];t=keys_match(last);dt=num(last.get('dt_s')) or num(setup.get('dt_s'))
 costs=[];points=[]
 for i,r in enumerate(valid):
  wall=num(r.get('wall_seconds',r.get('wall_s')));step=num(r.get('step'))
  cost=None
  if i:
   prev=valid[i-1];w0=num(prev.get('wall_seconds',prev.get('wall_s')));s0=num(prev.get('step'))
   if wall is not None and w0 is not None and step is not None and s0 is not None and step-s0==1 and wall>w0:
    cost=wall-w0;costs.append(cost)
  points.append([keys_match(r),num(r.get('CD')),cl_value(r,known),cost])
 sample=valid[-1];window=[r for r in valid if keys_match(r)>t-.2+1e-9 and keys_match(r)<=t+1e-9]
 complete=bool(dt and valid[0] and keys_match(valid[0])<=t-.2+dt*1.1 and len(window)>=max(2,round(.2/dt)-1))
 def mean(key):
  vals=[cl_value(r,known) if key=='CL' else num(r.get(key)) for r in window]
  return statistics.fmean(vals) if complete and vals and all(v is not None for v in vals) else None
 stride=max(1,math.ceil(len(points)/750));thin=points[::stride]
 if thin and thin[-1]!=points[-1]:thin.append(points[-1])
 return {'t_s':t,'step':int(num(last.get('step')) or 0),'dt_s':dt,'CL':cl_value(last,known),'CD':num(last.get('CD')),
  'mean_CL':mean('CL'),'mean_CD':mean('CD'),'mean_window':[t-.2,t] if complete else None,
  's_per_step':statistics.median(costs[-100:]) if len(costs)>3 else None,
  'interface_CFL':num(last.get('interface_max_CFL',last.get('interface_CFL'))),'CFL':num(last.get('max_CFL')),
  'series':thin,'rows':valid,'cl_convention':'hydrodynamic' if known or 'CL' in last else 'unknown'}

def primary_checks(p):
 checks=[]
 try:
  for line in (p/'settling_checks.jsonl').read_text(encoding='utf-8-sig').splitlines()[-30:]:
   try:checks.append(json.loads(line))
   except ValueError:pass
 except OSError:pass
 single=read(p/'settling_check.json')
 if single and (not checks or single.get('time_s')!=checks[-1].get('time_s')):checks.append(single)
 out=[];npass=0
 for c in checks:
  q=[]
  for key in ('CL','CD'):
   a=c.get(key,{})
   q.extend([num(a.get('mean_change_pct')),num(a.get('previous_RMS_pct')),num(a.get('latest_RMS_pct'))])
  passed=all(v is not None and v<.5 for v in q)
  npass=npass+1 if passed else 0
  out.append({'t_s':num(c.get('time_s')),'CL':num(c.get('CL',{}).get('mean_change_pct')),'CD':num(c.get('CD',{}).get('mean_change_pct')),
   'CL_rms':num(c.get('CL',{}).get('latest_RMS_pct')),'CD_rms':num(c.get('CD',{}).get('latest_RMS_pct')),'primary_pass':passed})
 explicit=read(p/'queue_stage_result.json');ev=read(p/'project_primary_evidence.json')
 accepted=explicit.get('project_primary_pass') is True or (len(ev.get('checks_s',[]))>=2 and ev.get('raw_independently_recomputed') is True)
 return {'pass_count':min(npass,2),'accepted_record':accepted,'qualifies':npass>=2,'last':out[-1] if out else None,'history':out,'legacy_pass':single.get('pass')}

def discover(root,depth=3,foil=False):
 found=[]
 if not root.exists():return found
 for path,dirs,files in os.walk(root,followlinks=False):
  p=Path(path);d=len(p.relative_to(root).parts)
  dirs[:]=[s for s in dirs if s not in SKIP and not s.startswith(('compiled','backup','policy_before','recovery_before'))]
  if d>=depth:dirs[:]=[]
  if any(n in files for n in ('history.csv','completed.json','stage_result.json','macro_error.txt','macro_error.json')):
   if foil and not re.search(r'M\d\d|G10_[MF]|W01a|calm_',str(p.relative_to(root))):continue
   found.append(p)
 return found

def infer_wave(p):
 s=str(p)
 m=re.search(r'L(10|20|30)(?:_H(\d{3}))?_(coarse|baseline|fine)',s)
 if not m:return None
 lam=int(m[1]);h=int(m[2])/1000 if m[2] else None
 if m[2] and m[2] in ('025','050','075'):h=int(m[2])/100
 return lam,h,m[3]

def checkpoint(p):
 q=read(p/'latest_checkpoint.json');candidate=q.get('path',q.get('file'))
 if candidate and Path(candidate).is_file():return {'path':candidate,'t_s':num(q.get('time_s')),'exists':True}
 for name in ('final.sim','wave_pilot_final.sim','calm_pilot_final.sim'):
  f=p/name
  if f.is_file():return {'path':str(f),'t_s':num(read(p/'completed.json').get('time_s')),'exists':True}
 return None

def get_record(p,kind,queue):
 setup=read(p/'setup.json') or read(p/'pilot_config.json') or {}
 identity=read(p/'identity.json');done=read(p/'completed.json');stage=read(p/'stage_result.json');runresult=read(p/'pilot_result.json')
 proc=read(p/'process.json');prog=read(p/'progress.json');h=history_data(p,kind=='foil',False,setup)
 if not h['dt_s']:
  h['dt_s']=num(setup.get('dt_s'))
  rr=h['rows']
  if len(rr)>2:h['dt_s']=keys_match(rr[-1])-keys_match(rr[-2])
 stamp=max(timestamp(p/n) for n in ('history.csv','completed.json','setup.json','process.json','stage_result.json','macro_error.txt','macro_error.json'))
 age=time.time()-timestamp(p/'history.csv') if (p/'history.csv').exists() else None
 qdir=queue.get('directory')
 is_main=bool(qdir and str(p.resolve()).casefold()==str(Path(qdir).resolve()).casefold())
 pid=queue.get('star_pid') if is_main else proc.get('pid',proc.get('star_pid'))
 running=not done and alive(pid) and (age is not None and age<120)
 loading=not done and alive(pid) and age is None and time.time()-timestamp(p/'process.json')<900
 result=str(done.get('status',''))
 errors=(p/'macro_error.txt').is_file() or (p/'macro_error.json').is_file() or stage.get('exit_code',0) not in (0,None) or runresult.get('returncode',0) not in (0,None)
 status='running' if running else 'loading' if loading else 'unknown'
 if not running and not loading:
  if errors or 'guard' in result.lower() or result in ('failed','unstable'):status='failed'
  elif result=='target_reached':status='pilot_complete'
  elif result=='stabilized':status='solver_stabilized'
  elif result in ('stopped_by_marker','wall_budget'):status='saved_stop' if checkpoint(p) else 'stopped'
  elif done:status='recorded'
  elif h['t_s'] is not None:status='incomplete'
 checks=primary_checks(p) if kind=='foil' else {}
 if kind=='foil' and done and (checks.get('accepted_record') or (checks.get('qualifies') and result in ('stopped_by_marker','stabilized','target_reached'))):status='primary_accepted'
 wf=infer_wave(p) if kind=='wave' else None
 mesh=re.search(r'M\d\d',p.name) or re.search(r'M\d\d',p.parent.name)
 mesh=mesh[0] if mesh else 'M12' if 'G10_F' in p.name else 'M11' if 'G10_M' in p.name else 'M10' if 'W01a' in p.name else p.name.split('_')[0]
 phase='calm' if kind=='foil' else 'wave' if ('waves' in p.parts or any(x in str(done.get('stage','')).lower() for x in ('inlet','incident','propagation')) or identity.get('phase')=='waves' or 'inlet_wave' in p.name or 'halfdt' in p.name) else 'calm' if 'calm' in str(p).lower() else 'setup'
 validation=read(p/'propagation_validation.json') or read(p/'wave_validation.json')
 verified=bool(kind=='wave' and phase=='wave' and (validation.get('pass') is True or validation.get('status') in ('accepted','verified')) and (validation.get('verified_raw_gauges') is True or (num(validation.get('raw_gauge_rows')) or 0)>=25))
 if verified:status='wave_verified'
 cells=num(setup.get('cells',setup.get('source_built_cells')))
 lam=H=grid=None
 if wf:
  lam,H,grid=wf;mesh=f'L{lam} {grid}'
  if not cells:cells={20:{'coarse':41200,'baseline':53200,'fine':77200},30:{'coarse':61800,'baseline':79800,'fine':115800},10:{'coarse':41200,'baseline':53200,'fine':77200}}[lam][grid]
 source=read(p/'source_identity.json').get('path') or identity.get('source')
 rec={'id':digest_id(p.resolve()),'kind':kind,'phase':phase,'mesh':mesh,'run':p.name,'path':str(p),'status':status,
  'active':running or loading,'t_s':h['t_s'] if h['t_s'] is not None else num(done.get('time_s')),'step':h['step'],
  'cells':int(cells) if cells else None,'dt_s':h['dt_s'],'order':setup.get('order'),'inner':setup.get('inner_iterations',setup.get('inner')),
  'CL':h['CL'],'CD':h['CD'],'mean_CL':h['mean_CL'],'mean_CD':h['mean_CD'],'mean_window':h['mean_window'],
  's_per_step':h['s_per_step'],'CFL':h.get('CFL'),'interface_CFL':h.get('interface_CFL'),
  'primary':checks,'checkpoint':checkpoint(p),'updated_at':iso(stamp),'age_s':age,'source':source,
  'cohort':'W01a / current foil family' if kind=='foil' else 'Independent wave-only experiments',
  'lambda_m':lam,'H_m':H,'grid':grid,'wave_verified':verified,'wave_metrics':validation.get('metrics',{}),
  'termination':result or None,'cl_convention':h.get('cl_convention'),'geometry_only':False,
  'reason':('Numerical/initialization guard or execution error; see original evidence' if errors or 'guard' in result else runresult.get('reason')),
  'evidence':[str(p/n) for n in ('setup.json','completed.json','history.csv','stage_result.json','project_primary_evidence.json','queue_stage_result.json') if (p/n).exists()]}
 if rec['active']:
  rec['series']=h['series']
  if kind=='foil':
   try:
    import mesh_live_focus_v4 as v
    rec['drift']=v.mean_drift_from_rows(h['rows'])
   except (ValueError,KeyError,TypeError):rec['drift']={}
 return rec

def historic_records():
 out=[];summ=read(F/'mesh_convergence.json').get('settled_results',[])
 for r in summ:
  ident=r.get('id');p=F/'mesh_convergence.json'
  if not re.fullmatch(r'M\d\d',ident or ''):continue
  out.append({'id':'legacy-summary-'+ident,'kind':'legacy','phase':'calm','mesh':ident,'run':ident+' initial force screen','path':str(F),
   'status':'historical_screen','active':False,'cells':r.get('cells'),'t_s':r.get('time_s'),'dt_s':.001,'order':'FIRST_ORDER','inner':20,
   'CL':None,'CD':None,'mean_CL':num(r.get('CL_dynamic')),'mean_CD':num(r.get('CD')),'mean_window':[r.get('window_start_s'),r.get('time_s')],
   's_per_step':r.get('wall_s_per_step_median'),'cohort':'Initial screen / original domain / first order',
   'updated_at':iso(timestamp(p)),'evidence':[str(p)],'cl_convention':'hydrodynamic recorded','geometry_only':False,
   'notes':'Historical mean-shift criterion; not the later CL/CD RMS acceptance rule.',
   'quality':r.get('yplus',{}).get('latest',{}),'checkpoint':None})
 matched=read(F/'matched_endpoint_results.json')
 for r in matched.get('results',[]):
  means=r.get('means',{});total=num(means.get('CL_total'))
  out.append({'id':'legacy-matched-'+str(r.get('mesh')),'kind':'legacy','phase':'calm','mesh':r.get('mesh'),'run':r.get('id'),'path':str(Path(r.get('source_sim',str(F))).parent),
   'status':'historical_matched','active':False,'cells':r.get('cells'),'t_s':r.get('window',[None,None])[-1],'dt_s':r.get('dt_s'),'order':r.get('order'),'inner':r.get('inner_iterations'),
   'mean_CL':total-OFFSET if total is not None else None,'mean_CD':num(means.get('CD')),'mean_window':r.get('window'),
   'cohort':'Matched M07-M09 / original domain / second order','updated_at':iso(timestamp(F/'matched_endpoint_results.json')),
   'evidence':[str(F/'matched_endpoint_results.json'),r.get('combined_history')],'cl_convention':'hydrodynamic, known legacy normalization',
   'checkpoint':{'path':r.get('source_sim'),'exists':Path(r.get('source_sim','')).is_file(),'t_s':matched.get('target_s')},'geometry_only':False})
 # Include M01 and every original mesh configuration, including unsuccessful M04 variants.
 for p in sorted(Q2.glob('M*/measurement.json')):
  r=read(p);m=r.get('metrics',{});ident=p.parent.name
  out.append({'id':'mesh-'+digest_id(p),'kind':'geometry','phase':'mesh','mesh':ident,'run':ident+' geometry audit','path':str(p.parent),
   'status':'geometry_only','active':False,'cells':m.get('cell_count'),'t_s':None,'dt_s':None,'mean_CL':None,'mean_CD':None,'mean_window':None,
   'cohort':'Original geometry generation and mesh audits','updated_at':iso(timestamp(p)),'quality':m,'notes':r.get('notes',[]),
   'evidence':[str(p)],'geometry_only':True,'checkpoint':None})
 # Preserve original individual attempts in addition to their summary, not silently replace them.
 for job in read(F/'queue.json',[]):
  if not re.fullmatch(r'M\d\d_[A-Za-z0-9_]+',job.get('id','')):continue
  p=F/job['id']
  if not p.is_dir() or not (p/'history.csv').exists():continue
  h=history_data(p,True,True,{'dt_s':job.get('dt')});done=read(p/'completed.json')
  out.append({'id':digest_id(p.resolve()),'kind':'legacy','phase':'calm','mesh':job['id'][:3],'run':job['id'],'path':str(p),
   'status':'legacy_attempt','active':False,'cells':job.get('cells'),'t_s':h['t_s'],'dt_s':h['dt_s'],'mean_CL':h['mean_CL'],'mean_CD':h['mean_CD'],
   'mean_window':h['mean_window'],'CL':h['CL'],'CD':h['CD'],'order':job.get('order'),'inner':job.get('inner'),'s_per_step':h['s_per_step'],
   'cohort':'Initial screen / original domain','updated_at':iso(timestamp(p/'history.csv')),'checkpoint':checkpoint(p),'termination':done.get('status'),
   'evidence':[str(F/'queue.json'),str(p/'history.csv'),str(p/'completed.json')],'geometry_only':False})
 return out

def collect():
 start=time.perf_counter();queue=read(E/'mesh_queue_state.json');records=historic_records();paths={}
 for p in discover(STUDY/'force_stabilization_20261029',1,True)+discover(E,3,True):
  if W in p.parents:continue
  if not re.search(r'M1[0-5]|G10_[MF]|W01a',str(p.relative_to(E)) if p.is_relative_to(E) else p.name):continue
  if not (p/'setup.json').exists():continue
  paths[str(p.resolve()).casefold()]=p
 for p in paths.values():records.append(get_record(p,'foil',queue))
 for p in discover(W,4):
  if infer_wave(p) and not any(x.startswith(('compiled','audit_saved','resume_coarse_r')) for x in p.relative_to(W).parts):
   records.append(get_record(p,'wave',{}))
 # Deduplicate junctions; distinct temporal tests and continuations remain distinct.
 dedup={r['id']:r for r in records}
 for old in read(CATALOG/'results.json').get('records',[]):
  if old.get('id') not in dedup:
   old=dict(old,active=False,source_unavailable=True,status='source_unavailable',notes='Retained catalog record; original source not present in this scan. Last known values only.');dedup[old['id']]=old
 records=list(dedup.values());records.sort(key=lambda r:r.get('updated_at') or '',reverse=True)
 live_foils=[r for r in records if r['kind']=='foil' and r['active']]
 live_waves=[r for r in records if r['kind']=='wave' and r['active']]
 active=live_foils[0] if live_foils else None
 wave=live_waves[0] if live_waves else None
 stages=[]
 for mesh in ('M12','M11','M10','M13','M14','M15'):
  rs=[r for r in records if r['kind']=='foil' and r['mesh']==mesh]
  best=next((r for r in rs if r['active']),None) or next((r for r in rs if r['status']=='primary_accepted'),None) or (rs[0] if rs else None)
  if best:stages.append({k:best.get(k) for k in ('id','mesh','cells','status','t_s','dt_s','mean_CL','mean_CD','s_per_step','primary','checkpoint','cohort')})
 geom=read(W/'geometry_matrix_manifest.json').get('records',[])
 matrix=read(W/'zero_start_matrix_20261031_13h_R2'/'matrix_live.json').get('results',[])
 wave_cases=[]
 for c in matrix:
  lam=c.get('lambda_m');H=c.get('H_m');grid=c.get('mesh')
  trials=[r for r in records if r['kind']=='wave' and r['lambda_m']==lam and r['H_m']==H and r['grid']==grid and r['phase']=='wave' and ('zero_start_matrix' in r['path'] or 'wave_cpu1_resource_pilot' in r['path'])]
  latest=next((r for r in trials if r['active']),None) or (trials[0] if trials else None)
  g=next((a for a in geom if a.get('lambda_m')==lam and a.get('name')==grid),{})
  wave_cases.append({'key':c['case'],'lambda_m':lam,'H_m':H,'mesh':grid,'cells':c.get('cells'),'dx_m':g.get('dx_m'),'dz_m':g.get('dz_m'),
   'status':latest['status'] if latest else 'planned','t_s':latest.get('t_s') if latest else None,'dt_s':latest.get('dt_s') if latest else .001,
   's_per_step':latest.get('s_per_step') if latest else None,'attempts':len(trials),'id':latest['id'] if latest else None,
   'verified':any(r['wave_verified'] for r in trials),'mean_metrics':latest.get('wave_metrics',{}) if latest else {}})
 catalog_only=[{k:v for k,v in r.items() if k not in ('series','drift')} for r in records]
 import mesh_comparison
 comparison=mesh_comparison.collect(records)
 return {'version':VERSION,'sampled_at':datetime.now(timezone.utc).isoformat(),'current_foil':active,'current_wave':wave,
  'latest_wave':next((r for r in records if r['kind']=='wave' and r['phase']=='wave'),None),'stages':stages,
  'records':catalog_only,'wave_cases':wave_cases,'geometries':geom,'comparison':comparison,
  'counts':{'records':len(records),'archived':sum(not r['active'] for r in records),'active':sum(r['active'] for r in records),
   'wave_planned':len(wave_cases),'wave_started':sum(c['attempts']>0 for c in wave_cases),'wave_verified':sum(c['verified'] for c in wave_cases)},
  'criterion':'CL and total CD: mean change and RMS below 0.5% in adjacent 0.2 s windows; two checks. Pressure/viscous terms diagnostic. Project rule, not ITTC.',
  'catalog_path':str(CATALOG),'collection_s':round(time.perf_counter()-start,3),
  'comparison_note':'Keep original-domain M01-M09 separate from W01a M10-M12. Different time steps and acceptance rules are shown explicitly. No automatic claim of grid independence.'}

def atomic(p,text):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(text,encoding='utf-8');os.replace(tmp,p)
def publish(data):
 # No original simulation or source file is modified. Canonical index is recoverable from sources.
 stripped={k:v for k,v in data.items() if k not in ('current_foil','current_wave')}
 atomic(CATALOG/'results.json',json.dumps(stripped,ensure_ascii=False,allow_nan=False,indent=2))
 fields=['id','kind','mesh','run','status','active','cells','t_s','dt_s','mean_CL','mean_CD','s_per_step','cohort','updated_at','path']
 output=io.StringIO();wr=csv.DictWriter(output,fieldnames=fields,extrasaction='ignore');wr.writeheader()
 for r in data['records']:wr.writerow(r)
 atomic(CATALOG/'results.csv',output.getvalue())
 atomic(CATALOG/'mesh_comparison.json',json.dumps(data.get('comparison',{}),ensure_ascii=False,allow_nan=False,indent=2))
 payload=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
 atomic(PUBLIC/'campaign_hub_snapshot.js','window.ntnuCampaignSnapshot&&window.ntnuCampaignSnapshot('+payload+');')
 atomic(CATALOG/'README.txt','Derived CFD results catalog. Updated by the local dashboard. Original .sim and raw logs remain at their original paths.\nOne record per run or explicitly labeled historical summary; source paths and differing criteria are retained.\nJSON: results.json\nCSV: results.csv\n')
 return payload

def render_page(legacy_page):
 data=collect()
 import importlib,campaign_visuals
 importlib.reload(campaign_visuals)
 campaign_visuals.enrich(data)
 import campaign_wave_live
 data['wave_lab']=campaign_wave_live.collect()
 foil_ui=Path(r'E:\ntnu_mesh_optimization_20261030\foil_live_dashboard_20261031')
 foil_spec=importlib.util.spec_from_file_location('foil_live_dashboard_current',foil_ui/'foil_live.py')
 foil_module=importlib.util.module_from_spec(foil_spec);foil_spec.loader.exec_module(foil_module)
 data['foil_live']=foil_module.collect()
 wave_campaign_ui=Path(r'E:\ntnu_mesh_optimization_20261030\wave_campaign_20261101')
 campaign_spec=importlib.util.spec_from_file_location('m13_wave_campaign_current',wave_campaign_ui/'campaign.py')
 campaign_module=importlib.util.module_from_spec(campaign_spec);campaign_spec.loader.exec_module(campaign_module)
 reference_spec=importlib.util.spec_from_file_location('m13_C01_reference_policy',wave_campaign_ui/'reference_policy.py')
 reference_module=importlib.util.module_from_spec(reference_spec);reference_spec.loader.exec_module(reference_module)
 reference_module.enforce(data)
 data['wave_campaign']=campaign_module.enrich(data)
 payload=publish(data)
 # Preserve full previous evidence and controls in a separate allowed archive URL.
 archived=PUBLIC/'archive_runs'/'legacy_dashboard.html'
 if not archived.exists():atomic(archived,legacy_page)
 css=(HERE/'campaign_hub.css').read_text(encoding='utf-8');js=(HERE/'mesh_comparison.js').read_text(encoding='utf-8')+'\n'+(HERE/'campaign_hub.js').read_text(encoding='utf-8')
 css+='\n'+(HERE/'campaign_compare.css').read_text(encoding='utf-8')
 js+='\n'+(HERE/'campaign_visuals.js').read_text(encoding='utf-8')
 css+='\n'+(HERE/'campaign_wave_live.css').read_text(encoding='utf-8')
 js+='\n'+(HERE/'campaign_wave_live.js').read_text(encoding='utf-8')
 css+='\n'+(foil_ui/'foil_live.css').read_text(encoding='utf-8')
 js+='\n'+(foil_ui/'foil_live.js').read_text(encoding='utf-8')
 css+='\n'+(wave_campaign_ui/'campaign.css').read_text(encoding='utf-8')
 js+='\n'+(wave_campaign_ui/'campaign.js').read_text(encoding='utf-8')
 # Preserve the existing generation-checked queue controls unchanged and folded away.
 import importlib.util
 spec=importlib.util.spec_from_file_location('hub_existing_queue_panel',F/'mesh_study_control_panel.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 controls=module.panel()
 body='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NTNU CFD · Current campaign & results</title><style>'''+css+'''</style></head><body><main><header><div><div class="eyebrow">NTNU · HYDROFOIL CFD</div><h1>Campaign workspace</h1><p>Current calculations first. Every finished attempt, one results archive.</p></div><div id="freshness"></div></header><nav aria-label="Dashboard sections"><button data-tab="live" class="selected">Current campaign</button><button data-tab="compare">Mesh comparison</button><button data-tab="archive">Results archive <span id="archive-count"></span></button><a href="/archive_runs/legacy_dashboard.html" target="_blank" rel="noopener">Earlier detailed view ↗</a></nav><section id="view-live"><div id="campaign-stages"></div><div id="live-pulse"></div><div id="live-foil"></div><div id="live-wave"></div><div id="wave-matrix"></div><div id="campaign-notes"></div></section><section id="view-compare" hidden><div id="mesh-comparison"></div></section><section id="view-archive" hidden><div class="archive-heading"><div><div class="eyebrow">PERSISTENT RESULTS</div><h2>One record of the experiments</h2><p>Initial meshes, force studies, time-step pilots and independent wave trials.</p></div><div class="exports"><button id="export-csv">Export CSV</button><button id="export-json">Export JSON</button></div></div><div class="toolbar"><input id="search" type="search" placeholder="Search mesh, run, status or source…" aria-label="Search archive"><select id="kind" aria-label="Filter experiment group"><option value="all">All groups</option><option value="foil">Current foil family</option><option value="wave">Wave-only trials</option><option value="legacy">Initial force studies</option><option value="geometry">Initial geometry / audits</option></select><select id="result-filter" aria-label="Filter outcome"><option value="all">All outcomes</option><option value="accepted">Accepted primary / historical screen</option><option value="failed">Failed / interrupted</option><option value="finished">Saved / completed pilots</option></select></div><p id="archive-note" class="note"></p><div id="archive-table"></div><div id="record-detail"></div></section><footer><span>Read-only telemetry. Archiving changes presentation, not source files or solver queues.</span><span id="catalog-path"></span></footer></main><script>window.CAMPAIGN_INITIAL='''+payload+''';</script><script>'''+js+'''</script></body></html>'''
 body=body.replace('<div id="campaign-notes"></div>','<div id="campaign-notes"></div><details class="details" id="queue-controls"><summary>Calculation controls · pause / save / resume the existing queue</summary>'+controls+'</details>',1)
 return body

if __name__=='__main__':
 d=collect();print(json.dumps({'counts':d['counts'],'foil':{k:d['current_foil'].get(k) for k in ('mesh','status','t_s','dt_s')} if d['current_foil'] else None,'stages':[{k:r.get(k) for k in ('mesh','status','t_s')} for r in d['stages']],'wave':d['current_wave']['run'] if d['current_wave'] else None,'collection_s':d['collection_s']},ensure_ascii=False))
