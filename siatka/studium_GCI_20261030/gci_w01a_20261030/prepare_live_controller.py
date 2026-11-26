from pathlib import Path
import ast,json,datetime
O=Path(__file__).resolve().parent
s=(O/'gpu_calm_study.py').read_text()
s=s.replace("macro=O/'ContinueCalmGPU.java';receipt=read(O/'gpu_macro_receipt.json')","macro=O/'ContinueCalmGPULive.java';receipt=read(O/'gpu_live_macro_receipt.json')")
s=s.replace("env=dict(os.environ,**envs,", """prior=envs.get('NTNU_STAB_PRIOR_HISTORY')
 if prior:
  shutil.copy2(prior,out/'prior_history.csv');envs=dict(envs,NTNU_STAB_PRIOR_HISTORY=str(out/'prior_history.csv'))
 env=dict(os.environ,**envs,""",1)
s=s.replace('def flow(name,source,start,target,dt,inner,cells,settle=False,pilot=False):','def flow(name,source,start,target,dt,inner,cells,settle=False,pilot=False,prior=None):')
s=s.replace("'NTNU_STAB_PRIOR_HISTORY':''","'NTNU_STAB_PRIOR_HISTORY':str(prior) if prior else ''")
s=s.replace("out=job(name+'_GPU_r1'","out=job(name+'_GPU_live_r2'")
begin=s.index(" request=read(O/'gpu_transition_request.json')")
end=s.index(" paths={m:[] for m in LEVELS};summaries={}",begin)
s=s[:begin]+""" request=read(O/'gpu_live_transition.json');old=Path(request['source_case'])
 deadline=time.monotonic()+1800
 while alive(request['controller_pid']) or alive(request['launcher_pid']):
  if time.monotonic()>deadline:raise RuntimeError('Previous GPU save still active')
  time.sleep(3)
 if (O/'gpu_calm_study.lock').exists():raise RuntimeError('Previous GPU controller lock remains')
 done=read(old/'completed.json');exit_info=read(old/'exit.json')
 if done['status']!='stopped_by_marker' or exit_info['returncode']!=0 or not exit_info['source_unchanged'] or not (old/'EXPORT_OK.json').exists():raise RuntimeError('Previous GPU fields not safely saved')
 fam=read(O/'family_audit/family_audit.json')
 if not all(fam['gates'].values()):raise RuntimeError('Mesh family audit failed')
 cells={m:fam['meshes'][m]['cells'] for m in LEVELS};area={m:fam['meshes'][m]['total_fluid_section_area_m2'] for m in LEVELS}
 original=read(O/'calm_source_identity.json');dt=read(O/'accepted_timestep.json')['dt_s']
 # Re-evaluate the already calculated matched CPU/GPU probe for hydrodynamic CL.
 hardware=read(O/'gpu_equivalence_check.json')
 comparison=compare_hardware(runner.rawrows(Path(hardware['cpu_case'])/'history.csv'),runner.rawrows(Path(hardware['gpu_case'])/'history.csv'))
 comparison.update({k:hardware[k] for k in ['source','cpu_case','gpu_case','scope','gpu']})
 comparison['lift_convention']='hydrodynamic_lift_v1'
 write(O/'gpu_equivalence_check_hydrodynamic.json',comparison)
 if not comparison['pass_check'] or comparison['speedup']<=1:raise RuntimeError('Saved hardware equivalence failed after lift correction')
 sources={'G10_F':old/'final.sim'};start_times={'G10_F':done['time_s']}
 for m in ['G10_M','W01a']:
  pilot=BASE/('calm_pilot_'+m+'_continued_r1');previous=read(pilot/'completed.json')
  if previous['status']!='target_reached':raise RuntimeError('Saved pilot not complete '+m)
  sources[m]=pilot/'final.sim';start_times[m]=previous['time_s']
 write(O/'gpu_campaign_sources_live.json',dict(sources={m:str(p) for m,p in sources.items()},start_times=start_times,dt_s=dt,gpu=True,reinitialized=False,lift_convention='hydrodynamic_lift_v1',prior_history=str(old/'history.csv')))
""" +s[end:]
s=s.replace("paths={m:[] for m in LEVELS};summaries={}","paths={m:[] for m in LEVELS};paths['G10_F']=[old/'history.csv'];summaries={}")
s=s.replace("10,cells[m],settle=True)","10,cells[m],settle=True,prior=old/'history.csv' if m=='G10_F' else None)")
s=s.replace("lock=O/'gpu_calm_study.lock'","lock=O/'gpu_live_study.lock'")
ast.parse(s)
(O/'gpu_calm_study_live.py').write_text(s)
print('New continuation controller prepared; saved hardware test and fine-grid progress will be reused.')
