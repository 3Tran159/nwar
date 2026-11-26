"""Read-only comparison of convergence normalizations and averaging windows."""
from pathlib import Path
from datetime import datetime
import csv,json,math,statistics,os,uuid
ROOT=Path(r'E:\ntnu_mesh_optimization_20261030')
S=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030')
state=json.loads((S/'gpu_study_state.json').read_text(encoding='utf-8-sig'));case=Path(state['directory'])
rows=[]
with (case/'history.csv').open(newline='',encoding='utf-8-sig') as f:
 for row in csv.DictReader(f):
  try:
   a={k:float(row[k]) for k in ('physical_time_s','wall_seconds','step','dt_s','CL_total','CD','pressure_drag_N','viscous_drag_N')}
   if not all(math.isfinite(v) for v in a.values()):continue
   a['CL']=a['CL_total']-22.718189111947265/3855.6;a['CDp']=a['pressure_drag_N']/3855.6;a['CDv']=a['viscous_drag_N']/3855.6;rows.append(a)
  except (KeyError,TypeError,ValueError):pass
assert len(rows)>10000
last=rows[-1];t=last['physical_time_s'];dt=last['dt_s'];windows={}
for window in (.2,.5,1.):
 n=round(window/dt)
 if len(rows)<2*n:continue
 a=rows[-2*n:-n];b=rows[-n:]
 assert abs(a[-1]['physical_time_s']-a[0]['physical_time_s']-(n-1)*dt)<1e-8
 assert abs(b[-1]['physical_time_s']-a[-1]['physical_time_s']-window)<1e-8
 meanD=statistics.mean(r['CD'] for r in b);res={}
 for key in ('CL','CD','CDp','CDv'):
  va=[r[key] for r in a];vb=[r[key] for r in b];ma=statistics.mean(va);mb=statistics.mean(vb)
  res[key]={'mean_old':ma,'mean_new':mb,'mean_shift_own_pct':100*abs(mb-ma)/abs(mb),'rms_old_own_pct':100*statistics.pstdev(va)/abs(ma),'rms_new_own_pct':100*statistics.pstdev(vb)/abs(mb),'absolute_shift':mb-ma,'shift_total_CD_pct':100*abs(mb-ma)/abs(meanD) if key!='CL' else None}
 res['component_sum_modulus_total_pct']=sum(res[k]['shift_total_CD_pct'] for k in ('CDp','CDv'))
 windows[str(window)]=res
formal=json.loads((case/'settling_check.json').read_text(encoding='utf-8'));p=formal['CD_pressure'];v=formal['CD_viscous'];d=formal['CD']['latest_mean']
formal_norm={'formal_t_s':formal['time_s'],'pressure_own_pct':p['mean_change_pct'],'pressure_fraction_pct':100*p['latest_mean']/d,'pressure_drift_of_total_pct':100*abs(p['latest_mean']-p['previous_mean'])/abs(d),'viscous_drift_of_total_pct':100*abs(v['latest_mean']-v['previous_mean'])/abs(d),'own_pressure_threshold_equivalent_total_pct':.5*abs(p['latest_mean'])/abs(d),'total_to_pressure_ratio':abs(d/p['latest_mean'])}
cost=[b['wall_seconds']-a['wall_seconds'] for a,b in zip(rows[-301:-1],rows[-300:]) if b['step']==a['step']+1 and b['wall_seconds']>a['wall_seconds']]
report={'read_at':datetime.now().astimezone().isoformat(),'time_s':t,'step':last['step'],'instantaneous':{k:last[k] for k in ('CL','CD','CDp','CDv')},'median_300_step_s':statistics.median(cost),'formal':formal_norm,'rolling_windows':windows,'caution':'Window shifts are NOT a bound on remaining asymptotic error. This is diagnostic only; original controller and acceptance flags unchanged.','reference_sources':['https://www.ittc.info/media/11950/75-03-01-01.pdf','https://www.ittc.info/media/11958/75-03-02-03.pdf','https://www.ittc.info/media/11960/75-03-02-04.pdf']}
dest=ROOT/'criteria_review_latest.json';tmp=dest.with_name(dest.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));os.replace(tmp,dest)
print(json.dumps({'read_at':report['read_at'],'time_s':t,'median_300_step_s':report['median_300_step_s'],'formal':formal_norm,'rolling':{w:{k:round(vv['mean_shift_own_pct'],6) for k,vv in vals.items() if isinstance(vv,dict)} for w,vals in windows.items()},'report':str(dest)},ensure_ascii=False))
