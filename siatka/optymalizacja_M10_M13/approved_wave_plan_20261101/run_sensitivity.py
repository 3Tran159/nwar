"""Guarded matched M13 calm/wave dt0.2ms tests. A new approved experiment, not a retry loop."""
from pathlib import Path
from datetime import datetime
import os,sys,json,uuid,math,subprocess,argparse,statistics
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'approved_wave_plan_20261101';P=R/'M13_wave_direct_20261031';W=R/'wave_surface_only'
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029');sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
CASES={'calm':{'source':R/'M13_farfield15_20261031'/'M13_GPU_calm_dt0004'/'final.sim','macro':D/'M13CalmDt02.java','folder':P/'M13_GPU_sensitivity_calm_dt0002_20261101','wall':6000},'wave':{'source':P/'M13_GPU_W20_H050_continuation_R4V_20261101'/'wave_pilot_final.sim','macro':D/'M13WaveDt02.java','folder':P/'M13_GPU_W20_H050_sensitivity_dt0002_20261101','wall':27000}}
LOCKS=[D/'sensitivity.lock',R/'m13_wave_gpu.lock',P/'M13_wave_gpu_pilot.lock',W/'wave_inlet.lock']

def preflight(name):
 c=CASES[name];now=datetime.now().astimezone();deadline=datetime.fromisoformat(rt.read(D/'authorization.json')['until_local'])
 assert now<deadline and (deadline-now).total_seconds()>c['wall']+300,'Insufficient authorized bounded time'
 plan=rt.read(R/'plan.json');assert rt.sha(R/'AUTONOMOUS_RECOVERY_PROMPT.md')==plan['recovery_policy']['runbook_sha256']
 assert rt.resource_problem() is None,rt.resource_problem()
 assert not c['folder'].exists(),'Attempt exists; read results instead of repeating'
 assert not any(k.exists() for k in [*LOCKS,D/'forcing_audit.lock',R/'parallel_cpu_20261031'/'auxiliary.lock']), 'Another audit/solver owns resources'
 assert not any(n.lower().startswith(('starccm+','star-ccm+')) for _,n in rt.guard.processes().values()),'STAR execution process remains'
 assert rt.read(F/'campaign_hold.json').get('active') is True
 review=rt.read(D/'forcing_review.json')
 assert review.get('ready_for_matched_sensitivity') is True,'Read-only forcing/calm-wave audit not yet reviewed'
 assert review.get('sources_unchanged') is True and review.get('forcing_at_foil_excluded_or_quantified') is True
 compiled=rt.read(D/'sensitivity_compile_receipt.json');assert compiled.get('status')=='javac_pass'
 assert rt.sha(c['macro'])==compiled['macros'][c['macro'].name]
 assert (D/'compiled_sensitivity'/'macro'/c['macro'].with_suffix('.class').name).exists()
 src=c['source'];assert src.exists() and src.stat().st_size>400000000
 stage=rt.read(src.parent/'stage_result.json');done=rt.read(src.parent/'completed.json')
 assert stage.get('exit_code')==0 and stage.get('source_unchanged') is True and done
 if name=='wave':
  assert rt.read(D/'calm_dt02_result.json').get('project_primary_pass') is True,'Matched calm0.2ms not accepted'
  assert done.get('time_s')>13 and done.get('global_initialization') is False
 else:
  assert rt.read(src.parent/'project_primary_evidence.json').get('raw_independently_recomputed') is True
 gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
 assert gpu.returncode==0 and int(gpu.stdout.splitlines()[0].split(',')[0])>=4000,'GPU reserve unavailable'
 assert int(gpu.stdout.splitlines()[0].split(',')[1])<45,'GPU unexpectedly busy'
 return dict(c,source_sha256=rt.sha(src),start_time=float(done['time_s']),macro_sha256=rt.sha(c['macro']),checked_at=rt.now())

def assess_calm(folder):
 rows=rt.rows(folder/'history.csv');checks=[json.loads(x) for x in (folder/'settling_checks.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
 assert len(checks)>=2 and len(rows)>=3000,'Not enough complete dt0.2ms windows'
 selected=checks[-2:];assert abs(selected[1]['time_s']-selected[0]['time_s']-.2)<1e-8
 recalculated=[]
 for check in selected:
  t=check['time_s'];window=[]
  for a,b in ((t-.4,t-.2),(t-.2,t)):
   q=[r for r in rows if a+1e-8<float(r['physical_time_s'])<=b+1e-8]
   assert len(q)==1000 and all(abs(float(r['dt_s'])-.0002)<1e-12 for r in q)
   window.append({key:(statistics.fmean(float(r[key]) for r in q),statistics.pstdev(float(r[key]) for r in q)) for key in ('CL','CD')})
  metrics={}
  for key in ('CL','CD'):
   (m0,s0),(m1,s1)=window[0][key],window[1][key]
   change=100*abs(m1-m0)/abs(m1);r0=100*s0/abs(m0);r1=100*s1/abs(m1)
   metrics[key]={'mean_shift_pct':change,'RMS_previous_pct':r0,'RMS_latest_pct':r1,'mean':m1}
   assert max(change,r0,r1)<.5,'Raw primary settling check failed'
  recalculated.append({'time_s':t,'metrics':metrics})
 return {'at':rt.now(),'project_primary_pass':True,'legacy_four_way_claim':False,'raw_recomputed':True,'checks':recalculated,'source':str(folder),'dt_s':.0002,'CL':recalculated[-1]['metrics']['CL']['mean'],'CD':recalculated[-1]['metrics']['CD']['mean']}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',choices=CASES,required=True);ap.add_argument('--preflight-only',action='store_true');ap.add_argument('--run',action='store_true');args=ap.parse_args();c=preflight(args.case)
 if args.preflight_only:print(json.dumps({'preflight':'PASS','case':args.case,'at':rt.now(),'source_sha256':c['source_sha256'],'no_solver_started':True}));return
 assert args.run,'Explicit --run required';owned=[];token=uuid.uuid4().hex;folder=c['folder']
 try:
  for lock in LOCKS:
   with lock.open('x',encoding='utf8') as f:json.dump({'pid':os.getpid(),'at':rt.now(),'token':token,'case':args.case},f)
   owned.append(lock)
  folder.mkdir()
  rt.write(folder/'approved_experiment.json',{'at':rt.now(),'case':args.case,'source':str(c['source']),'source_sha256':c['source_sha256'],'macro_sha256':c['macro_sha256'],'dt_s':.0002,'only_numerical_change':'dt0.4ms to0.2ms','old_F_hold_unchanged':True,'new_user_authorization':str(D/'authorization.json'),'no_automatic_retry':True})
  if args.case=='calm':
   env={'NTNU_STAB_OUT':str(folder),'NTNU_STAB_DT':'.0002','NTNU_STAB_TARGET':str(c['start_time']+1.0),'NTNU_STAB_START':str(c['start_time']),'NTNU_STAB_INNER':'10','NTNU_STAB_CELLS':'309441','NTNU_STAB_INIT':'false','NTNU_STAB_ORDER':'SECOND_ORDER','NTNU_STAB_BUDGET':'5700','NTNU_CALM_SETTLE':'true','NTNU_STAB_PRIOR_HISTORY':'','NTNU_GCI_MAX_CFL':'25','NTNU_GCI_INTERFACE_CFL':'2.5'}
  else:
   env={'NTNU_M13_WAVE_OUT':str(folder),'NTNU_M13_WAVE_DT':'.0002','NTNU_M13_WAVE_STEPS':'26000','NTNU_M13_WAVE_INNER':'10','NTNU_M13_WAVE_BUDGET':'26700','NTNU_M13_WAVE_START_T':str(c['start_time'])}
  rt.write(D/'sensitivity_state.json',{'at':rt.now(),'status':'starting','case':args.case,'directory':str(folder)})
  with (R/'attempts.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps({'at':rt.now(),'event':'approved_dt_sensitivity_launch','case':args.case,'directory':str(folder),'source_sha256':c['source_sha256']})+'\n')
  _,result=rt.stage(folder,c['source'],c['macro'],env=env,workers=1,gpu=True,mask=240,budget_s=c['wall'],protect_main=False,phase='M13_dt_sensitivity_'+args.case)
  done=rt.read(folder/'completed.json');assert not (folder/'macro_error.json').exists() and not (folder/'macro_error.txt').exists()
  if args.case=='calm':
   assert done.get('status')=='stabilized' and (folder/'final.sim').exists() and (folder/'EXPORT_OK.json').exists()
   summary=assess_calm(folder);rt.write(D/'calm_dt02_result.json',summary)
  else:
   assert done.get('status') in ('target_reached','wall_budget') and (folder/'wave_pilot_final.sim').exists()
   summary={'at':rt.now(),'saved':True,'case':args.case,'time_s':done['time_s'],'steps':done['steps'],'scientific_review_required':True,'not_automatically_validated':True};rt.write(D/'wave_dt02_result.json',summary)
  rt.write(D/'sensitivity_state.json',{'at':rt.now(),'status':'saved_requires_scientific_review' if args.case=='wave' else 'calm_primary_pass_wave_next','case':args.case,'directory':str(folder),'source_unchanged':result.get('source_unchanged')})
  print(json.dumps({'event':'sensitivity_saved','case':args.case,'time_s':done.get('time_s'),'steps':done.get('steps')}),flush=True)
 except BaseException as ex:
  if folder.exists():rt.write(folder/'experiment_error.json',{'at':rt.now(),'error':rt.guard.redact(str(ex))[:600],'no_retry':True})
  rt.write(D/'sensitivity_state.json',{'at':rt.now(),'status':'requires_review','case':args.case,'directory':str(folder)});raise
 finally:
  pid=rt.read(folder/'process.json').get('pid') if folder.exists() else None
  if not pid or not rt.guard.alive(pid):
   for lock in reversed(owned):
    if rt.read(lock).get('token')==token:lock.unlink()
if __name__=='__main__':main()
