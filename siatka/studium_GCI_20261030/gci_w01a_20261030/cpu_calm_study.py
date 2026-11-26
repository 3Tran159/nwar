"""CPU-only calm-water verification; main W01a GPU wave case is never controlled."""
from pathlib import Path
import os,sys,json,time,datetime,ctypes,shutil
import cpu_study as runner
import calm_analysis as a
O=Path(__file__).resolve().parent
LEVELS=['W01a','G10_M','G10_F']
RUN_ORDER=['G10_F','G10_M','W01a'] # Fine reference first; keep mathematical GCI ordering coarse/medium/fine.
WORKERS=runner.WORKERS
read,write,sha=runner.read,runner.write,runner.sha
def state(status,**kw):
 write(O/'cpu_study_state.json',dict(status=status,pid=os.getpid(),updated_at=datetime.datetime.now().astimezone().isoformat(),scope='calm_water_only',workers=WORKERS,gpu=False,GPU_wave_untouched=True,**kw));print(status,kw,flush=True)
runner.state=state
def flow(name,source,start,target,dt,inner,cells,settle=False,pilot=False):
 env={'NTNU_STAB_DT':str(dt),'NTNU_STAB_TARGET':str(target),'NTNU_STAB_INNER':str(inner),'NTNU_STAB_CELLS':str(cells),'NTNU_STAB_START':str(start),'NTNU_STAB_INIT':'false','NTNU_STAB_ORDER':'SECOND_ORDER','NTNU_STAB_BUDGET':'345000','NTNU_STAB_PRIOR_HISTORY':'','NTNU_CALM_SETTLE':'true' if settle else 'false','NTNU_GCI_MAX_CFL':'1e8' if pilot else '25','NTNU_GCI_INTERFACE_CFL':'1e8' if pilot else '1'}
 out=runner.job(name,source,O/'ContinueCalmGCI.java',env)
 done=read(out/'completed.json');setup=read(out/'setup.json');calm=read(out/'calm_audit.json')
 if setup['gpu_count']!=0 or calm['reinitialized'] or calm['incident_wave_height_m']!=0 or calm['type']!='FlatVofWave':raise RuntimeError('CPU/calm identity failed')
 if done['status'] not in ['target_reached','stabilized'] or not (out/'EXPORT_OK.json').exists():raise RuntimeError('Flow gate failed '+name+' '+str(done))
 if done['status']=='target_reached' and abs(done['time_s']-target)>1.1*dt:raise RuntimeError('Incorrect final time')
 history=runner.rawrows(out/'history.csv');sub=runner.rawrows(out/'vof_substeps.csv')
 d={'max_CFL':max(r['max_CFL'] for r in history),'interface_CFL':max(r['interface_max_CFL'] for r in history),'effective_VOF_CFL':max(r['flow_CFL_divided_by_substeps'] for r in sub),'max_yplus':max(r['max_yplus'] for r in history),'time_s':done['time_s']}
 write(out/'flow_diagnostics.json',d)
 if not pilot and d['effective_VOF_CFL']>1.00001:raise RuntimeError('Effective VOF CFL limit exceeded')
 if settle and done['status']!='stabilized':raise RuntimeError('0.5 percent stabilization not reached within three additional seconds; preserve fields for review')
 if settle:
  check=read(out/'settling_check.json')
  if not check['pass'] or check['consecutive_passes']<2:raise RuntimeError('Incomplete stabilization confirmation')
 return out,d
def main():
 if not read(O/'calm_cpu_smoke_result.json')['pass_check']:raise RuntimeError('Calm CPU preflight did not pass')
 state('waiting_for_calm_geometry_and_mapping_audit')
 while not (O/'verified_starting_states.json').exists():
  if runner.stop():raise RuntimeError('Stop marker')
  if (O/'study_state.json').exists() and read(O/'study_state.json')['status']=='needs_review':raise RuntimeError('Geometry/mapping needs review')
  time.sleep(20)
 verified=read(O/'verified_starting_states.json')
 if verified['status']!='calm_geometry_and_mapping_verified':raise RuntimeError('Wrong source scope')
 fam=read(O/'family_audit/family_audit.json')
 if not all(fam['gates'].values()):raise RuntimeError('Mesh family audit failed')
 cells={m:fam['meshes'][m]['cells'] for m in LEVELS}
 area={m:fam['meshes'][m]['total_fluid_section_area_m2'] for m in LEVELS}
 sources={m:Path(verified['sources'][m]) for m in LEVELS}
 original=read(O/'calm_source_identity.json')
 if sha(sources['W01a'])!=original['sha256']:raise RuntimeError('Calm source identity changed')
 start=verified['source_checkpoint_time_s'];dt=.0001
 start_times={m:start for m in LEVELS}
 warm=read(O/'calm_warm_restart.json')
 sources['G10_F']=Path(warm['source']);start_times['G10_F']=warm['time_s']
 if not sources['G10_F'].is_file():raise RuntimeError('Saved warm fine reference missing')
 for attempt in range(4):
  pilots={};ratios=[]
  for m in RUN_ORDER:
   out,d=flow('calm_pilot_'+m+'_continued_r'+str(attempt+1),sources[m],start_times[m],start_times[m]+.004,dt,10,cells[m],pilot=True)
   pilots[m]=out;ratios.extend([d['max_CFL']/25,d['interface_CFL'],d['effective_VOF_CFL']])
  worst=max(ratios)
  if worst<=1:break
  import math
  dt/=2**max(1,math.ceil(math.log2(1.1*worst)))
  # Keep all computed relaxation fields when reducing dt; calm-water comparisons need stationarity, not a common wave phase.
  for m in LEVELS:
   sources[m]=pilots[m]/'final.sim';start_times[m]=read(pilots[m]/'completed.json')['time_s']
 else:raise RuntimeError('Common CPU timestep pilots failed')
 write(O/'accepted_timestep.json',dict(dt_s=dt,flow_max_CFL_limit=25,interface_max_CFL_limit=1,effective_VOF_max_CFL_limit=1,workers=WORKERS,gpu=False,scope='calm water',interpretation='Project screening limits for implicit URANS/VOF; temporal and inner iteration controls are still required for GCI.'))
 paths={m:[] for m in LEVELS};summaries={}
 for m in RUN_ORDER:
  p=pilots[m];t=read(p/'completed.json')['time_s']
  out,d=flow('calm_settle_'+m,p/'final.sim',t,t+3,dt,10,cells[m],settle=True)
  paths[m].append(out/'history.csv');sources[m]=out/'final.sim';summaries[m]=a.summarize(a.load_history(paths[m]))
  if not summaries[m]['pass_stabilization']:raise RuntimeError('Independent four-coefficient stabilization check failed')
  write(O/'calm_stabilization_progress.json',dict(summaries=summaries,threshold_pct=.5,completed_meshes=list(summaries),scope='calm water only'))
 estimates,noise=a.estimate(summaries,area,cells)
 # Save the user's fast 0.5% screening result before the stricter GCI nuisance controls.
 write(O/'calm_mesh_screen.json',dict(status='all_three_stabilized_below_0.5_percent',cells=cells,dt_s=dt,summaries=summaries,GCI_pending=estimates,nuisance_screen=noise,scope='Calm water only; no wave GCI planned',light_mesh_objective=True))
 # If settling uncertainty exceeds a tenth of the mesh difference, one later window per level can distinguish slow drift.
 for refinement in range(2):
  if all(v['pass'] for v in noise.values()):break
  for m in RUN_ORDER:
   t=summaries[m]['time_s']
   out,d=flow('calm_later_'+m+'_r'+str(refinement+1),sources[m],t,t+.4,dt,10,cells[m])
   paths[m].append(out/'history.csv');sources[m]=out/'final.sim';summaries[m]=a.summarize(a.load_history(paths[m]))
  estimates,noise=a.estimate(summaries,area,cells)
  write(O/'calm_spatial_progress.json',dict(summaries=summaries,GCI=estimates,nuisance_screen=noise))
 if not any('GCI_fine_abs' in estimates[k] and noise[k]['pass'] and not estimates[k]['order_caution'] for k in a.KEYS):
  for k in estimates:
   if 'GCI_fine_abs' in estimates[k]:estimates[k]['status']='not_verified_spatial_noise_or_order_review_required'
  write(O/'gci_results.json',dict(status='calm_mesh_screen_completed_GCI_not_resolved',cells=cells,dt_s=dt,summaries=summaries,spatial_noise=noise,GCI=estimates,controls_run=False,reason='No quantity has a resolved plausible monotonic grid trend with sufficiently small settling uncertainty; additional time-step controls would not establish GCI.',scope='Calm water only; no wave accuracy claim',source=original,gpu=False))
  state('calm_mesh_screen_completed_GCI_needs_review',verified_quantities=[],controls_skipped_to_avoid_uninformative_cost=True);return
 control_start=summaries['G10_F']['time_s'];common=sources['G10_F'];controls={}
 for label,testdt,inner in [('baseline',dt,10),('dt_half',dt/2,10),('inner_twice',dt,20)]:
  out,d=flow('calm_control_'+label,common,control_start,control_start+.6,testdt,inner,cells['G10_F'])
  controls[label]=a.summarize(a.load_history([out/'history.csv']))
 gates={}
 for k in a.KEYS:
  base=controls['baseline']['quantities'][k]['mean']
  effects={'dt_half':abs(controls['dt_half']['quantities'][k]['mean']-base),'inner_twice':abs(controls['inner_twice']['quantities'][k]['mean']-base),'later_window':abs(summaries['G10_F']['quantities'][k]['mean']-base)}
  for label,summary in controls.items():
   q=summary['quantities'][k];effects[label+'_repeat_window_shift']=q['mean_change_abs'];effects[label+'_RMS']=max(q['RMS_abs'])
  allowed=min(.005*abs(base),noise[k]['allowed_abs'])
  stable=all(v['quantities'][k]['pass_stabilization'] for v in list(summaries.values())+list(controls.values()))
  passed=noise[k]['pass'] and stable and max(effects.values())<=allowed
  gates[k]={'effects':effects,'allowed_abs':allowed,'pass':passed}
  if 'GCI_fine_abs' in estimates[k]:estimates[k]['status']='calm_spatial_uncertainty_estimated' if passed and not estimates[k]['order_caution'] else 'not_verified_nuisance_or_order_review_required'
 write(O/'gci_results.json',dict(status='calm_CPU_checks_completed',cells=cells,dt_s=dt,summaries=summaries,controls=controls,nuisance_gates=gates,spatial_noise=noise,GCI=estimates,scope='Numerical in-plane mesh convergence of CL and total/pressure/viscous CD in calm water on W01a domain. Does not establish wave-response discretization uncertainty or experimental validation.',wave_GCI_planned=False,local_yplus_exceptions_allowed=True,source=original,gpu=False,workers=WORKERS,lightest_mesh_preferred=True))
 state('calm_CPU_GCI_checks_completed',verified_quantities=[k for k,v in estimates.items() if v['status']=='calm_spatial_uncertainty_estimated'])
if __name__=='__main__':
 lock=O/'cpu_calm_study.lock'
 try:
  with lock.open('x') as f:json.dump({'pid':os.getpid()},f)
  ctypes.windll.kernel32.SetThreadExecutionState(0x80000001);main()
 except BaseException as e:state('needs_review',error=str(e));raise
 finally:
  ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
  if lock.exists() and read(lock).get('pid')==os.getpid():lock.unlink()
