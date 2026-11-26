"""Read-only hourly M13 verification; never starts a solver or mutates originals."""
from pathlib import Path
from datetime import datetime
import csv,json,hashlib,shutil,subprocess,statistics,sys,os
R=Path(r'E:\ntnu_mesh_optimization_20261030')
P=R/'M13_wave_direct_20261031'
D=P/'M13_GPU_W20_H050_continuation_R3V_20261101'
def js(p):
 try:return json.loads(p.read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 with p.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def num(v):
 try:return float(v)
 except:return None
data={'observed':datetime.now().astimezone().isoformat()}
plan=js(R/'plan.json')
data['runbook_verified']=sha(R/'AUTONOMOUS_RECOVERY_PROMPT.md')==plan['recovery_policy']['runbook_sha256']
for name,p in [('E_STOP',R/'STOP_ALL'),('F_STOP',Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\STOP_ALL')),('R3V_STOP',D/'STOP'),('GPU_LOCK',R/'m13_wave_gpu.lock'),('R3V_LOCK',P/'M13_wave_gpu_pilot.lock'),('WAVE_LOCK',R/'wave_surface_only'/'wave_inlet.lock')]:
 data[name]={'exists':p.exists(),'contents':js(p) if p.suffix=='.lock' else None}
data['hold_active']=js(Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\campaign_hold.json')).get('active')
h=rows(D/'history.csv');last=h[-1]
data['samples']=len(h);data['history_tail']={k:last.get(k) for k in ('time_s','step','CL_hydrodynamic','CD_total','max_CFL','max_speed_m_s','water_volume_m3','alpha_min','alpha_max','p_min_Pa','p_max_Pa','target_H_m')}
data['first_data_time']=h[0].get('time_s')
data['receipt']=js(D/'completed.json');data['stage']=js(D/'stage_result.json')
data['final_sim']={'exists':(D/'wave_pilot_final.sim').exists(),'size_bytes':(D/'wave_pilot_final.sim').stat().st_size if (D/'wave_pilot_final.sim').exists() else 0}
data['recent_CL']={'min':min(float(r['CL_hydrodynamic']) for r in h[-501:]),'max':max(float(r['CL_hydrodynamic']) for r in h[-501:]),'mean':statistics.fmean(float(r['CL_hydrodynamic']) for r in h[-501:])}
data['recent_CD']={'min':min(float(r['CD_total']) for r in h[-501:]),'max':max(float(r['CD_total']) for r in h[-501:]),'mean':statistics.fmean(float(r['CD_total']) for r in h[-501:])}
g=rows(D/'gauges.csv')
from collections import defaultdict
gp=defaultdict(list)
for row in g:
 x=num(row.get('x_m'));t=num(row.get('time_s'));e=num(row.get('eta_actual_m'))
 if None not in (x,t,e):gp[str(x)].append((t,e))
data['gauges']={x:{'count':len(a),'last':a[-1],'min_last300':min(e for t,e in a[-300:]),'max_last300':max(e for t,e in a[-300:])} for x,a in gp.items() if a}
frame=js(D/'live_foil_wave_frame.json');jpg=D/frame.get('image','')
data['frame']={'time_s':frame.get('time_s'),'interface_CFL':frame.get('interface_CFL'),'bytes_verified':bool(jpg.is_file() and sha(jpg)==frame.get('sha256'))}
data['latest_checkpoints']=[{'name':x.name,'bytes':x.stat().st_size} for x in sorted(D.glob('checkpoint_*.sim'),key=lambda x:x.stat().st_mtime)[-3:]]
try:
 import psutil
 data['processes']=[{'pid':p.pid,'name':p.name(),'start':datetime.fromtimestamp(p.create_time()).astimezone().isoformat()} for p in psutil.process_iter() if p.name().lower().startswith(('starccm','star-ccm','mpiexec'))]
 data['ram_free_gib']=round(psutil.virtual_memory().available/2**30,2)
except Exception as e:data['process_error']=str(e)
data['disk_free_gib']={d:round(shutil.disk_usage(d+':/').free/2**30,2) for d in ('C','E')}
try:
 q=subprocess.run(['nvidia-smi','--query-gpu=memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8)
 data['gpu_status']=q.stdout.strip() if q.returncode==0 else 'unavailable'
except Exception as e:data['gpu_status']=str(e)
try:
 sys.path.insert(0,str(R/'foil_live_dashboard_20261031'))
 import foil_live
 runs=foil_live.collect().get('runs',[])
 data['dashboard_runs']=[{'id':a.get('id'),'status':a.get('status'),'last':a.get('last'),'cycles':a.get('phase_cycles'),'frame':bool(a.get('frame'))} for a in runs if 'R3V' in a.get('id','')]
 for a in data['dashboard_runs']:
  if a['cycles'] is not None:
   c=a['cycles'];a['cycles']={k:v for k,v in c.items() if k!='overlays'}
except Exception as e:data['dashboard_error']=str(e)
out=P/'WATCH_R3V_20261101_0333.json'
out.write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
print(json.dumps(data,ensure_ascii=False,default=str))
