"""GPU continuation of the authorized calm-water mesh campaign; reuse immutable CPU checkpoints."""
from pathlib import Path
import os,sys,json,time,datetime,ctypes,shutil,subprocess,threading,statistics,math
import cpu_study as runner
import calm_analysis as a
O=Path(__file__).resolve().parent
BASE=O/'force_stabilization_20261029'
LEVELS=['W01a','G10_M','G10_F'];RUN_ORDER=['G10_F','G10_M','W01a']
WORKERS=1;AFFINITY=16777212
read,write,sha=runner.read,runner.write,runner.sha
def alive(pid):
 if not pid:return False
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.OpenProcess.restype=ctypes.c_void_p;k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
 k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];k.CloseHandle.argtypes=[ctypes.c_void_p]
 h=k.OpenProcess(0x1000,False,int(pid))
 if not h:return False
 try:
  code=ctypes.c_ulong();return bool(k.GetExitCodeProcess(h,ctypes.byref(code))) and code.value==259
 finally:k.CloseHandle(h)
def state(status,**kw):
 value=dict(status=status,pid=os.getpid(),updated_at=datetime.datetime.now().astimezone().isoformat(),scope='calm_water_only',workers=WORKERS,gpu=True,gpu_count=1,GPU_wave_untouched=True,**kw)
 write(O/'gpu_study_state.json',value);write(O/'cpu_study_state.json',value);print(status,kw,flush=True)
def pin():
 k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p;k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
 if not k.SetProcessAffinityMask(k.GetCurrentProcess(),AFFINITY):raise RuntimeError('Cannot reserve CPUs 0 and 1 for the other campaign')
def gpu_memory_free():
 p=subprocess.run(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise RuntimeError('GPU unavailable')
 return float(p.stdout.strip().splitlines()[0])
def job(name,source,envs):
 out=BASE/name
 if out.exists():raise RuntimeError('Existing attempt preserved '+name)
 if runner.stop():raise RuntimeError('Stop marker')
 if runner.free_memory()<16*1024**3 or shutil.disk_usage(O).free<15*1024**3:raise RuntimeError('Insufficient free RAM or storage')
 if gpu_memory_free()<4000:raise RuntimeError('Less than 4 GB free GPU memory; other workloads preserved')
 out.mkdir();before=sha(source);shutil.copy2(source,out/'input.sim')
 if sha(out/'input.sim')!=before:raise RuntimeError('Copied checkpoint mismatch')
 write(out/'source_identity.json',dict(path=str(source),sha256=before,gpu_continuation=True,reinitialized=False))
 macro=O/'ContinueCalmGPULive.java';receipt=read(O/'gpu_live_macro_receipt.json')
 if receipt['status']!='javac_passed' or sha(macro)!=receipt['GPU_macro_sha256']:raise RuntimeError('GPU macro identity mismatch')
 prior=envs.get('NTNU_STAB_PRIOR_HISTORY')
 if prior:
  shutil.copy2(prior,out/'prior_history.csv');envs=dict(envs,NTNU_STAB_PRIOR_HISTORY=str(out/'prior_history.csv'))
 env=dict(os.environ,**envs,NTNU_STAB_OUT=str(out),NTNU_MAP_OUT=str(out))
 pin();start=time.monotonic();reason=None
 with (out/'star.log').open('x',encoding='utf-8') as log:
  p=subprocess.Popen([str(runner.STAR),*runner.saved_options(WORKERS),'-gpgpu','auto:1','-batch',str(macro),str(out/'input.sim')],cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.NORMAL_PRIORITY_CLASS)
  write(out/'process.json',dict(pid=p.pid,workers=WORKERS,CPU_affinity_mask=AFFINITY,gpu=True,gpu_count=1))
  state('GPU_job_running',job=name,star_pid=p.pid,directory=str(out))
  def drain():
   for line in p.stdout:log.write(runner.redact(line));log.flush()
  th=threading.Thread(target=drain,daemon=True);th.start()
  try:
   while p.poll() is None:
    if runner.stop() or runner.free_memory()<8*1024**3 or shutil.disk_usage(O).free<6*1024**3 or time.monotonic()-start>345600:
     (out/'STOP').touch();reason=reason or time.monotonic()
    if reason and time.monotonic()-reason>600:
     subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);break
    time.sleep(3)
  except BaseException:
   (out/'STOP').touch()
   try:p.wait(timeout=600)
   except subprocess.TimeoutExpired:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
   raise
  rc=p.wait();th.join(30)
 unchanged=sha(source)==before
 write(out/'exit.json',dict(returncode=rc,source_unchanged=unchanged,wall_s=time.monotonic()-start,gpu=True,workers=WORKERS))
 if rc or not unchanged or reason:raise RuntimeError('Owned GPU job stopped or failed '+name)
 return out
def flow(name,source,start,target,dt,inner,cells,settle=False,pilot=False,prior=None):
 env={'NTNU_STAB_DT':str(dt),'NTNU_STAB_TARGET':str(target),'NTNU_STAB_INNER':str(inner),'NTNU_STAB_CELLS':str(cells),'NTNU_STAB_START':str(start),'NTNU_STAB_INIT':'false','NTNU_STAB_ORDER':'SECOND_ORDER','NTNU_STAB_BUDGET':'345000','NTNU_STAB_PRIOR_HISTORY':str(prior) if prior else '','NTNU_CALM_SETTLE':'true' if settle else 'false','NTNU_GCI_MAX_CFL':'25','NTNU_GCI_INTERFACE_CFL':'1'}
 out=job(name+'_GPU_live_r2',source,env)
 done=read(out/'completed.json');setup=read(out/'setup.json');calm=read(out/'calm_audit.json')
 if setup['gpu_count']!=1 or calm['reinitialized'] or calm['incident_wave_height_m']!=0 or calm['type']!='FlatVofWave':raise RuntimeError('GPU/calm identity failed')
 if done['status'] not in ['target_reached','stabilized'] or not (out/'EXPORT_OK.json').exists():raise RuntimeError('Flow gate failed '+name+' '+str(done))
 if done['status']=='target_reached' and abs(done['time_s']-target)>1.1*dt:raise RuntimeError('Incorrect final time')
 history=runner.rawrows(out/'history.csv');sub=runner.rawrows(out/'vof_substeps.csv')
 if not history or len(history)!=len(sub):raise RuntimeError('Incomplete force/CFL history')
 d={'max_CFL':max(r['max_CFL'] for r in history),'interface_CFL':max(r['interface_max_CFL'] for r in history),'effective_VOF_CFL':max(r['flow_CFL_divided_by_substeps'] for r in sub),'max_yplus':max(r['max_yplus'] for r in history),'time_s':done['time_s']}
 write(out/'flow_diagnostics.json',d)
 if d['max_CFL']>25 or d['interface_CFL']>1.00001 or d['effective_VOF_CFL']>1.00001:raise RuntimeError('GPU CFL screening failed')
 if settle:
  check=read(out/'settling_check.json') if (out/'settling_check.json').exists() else {}
  if done['status']!='stabilized' or not check.get('pass') or check.get('consecutive_passes',0)<2:raise RuntimeError('0.5 percent stabilization not reached; preserve fields for review')
 return out,d
def compare_hardware(cpu,gpu):
 cpu=a.coefficients(cpu);gpu=a.coefficients(gpu);matched={round(r['physical_time_s'],9):r for r in cpu}
 if len(gpu)<20:raise RuntimeError('CPU/GPU comparison needs 20 saved matched steps')
 diffs={}
 for key in a.KEYS:
  values=[]
  for g in gpu:
   c=matched.get(round(g['physical_time_s'],9))
   if c is None or abs(c['dt_s']-g['dt_s'])>1e-12:raise RuntimeError('Unmatched CPU/GPU time step')
   if not all(math.isfinite(r[key]) and abs(r[key])>1e-8 for r in [c,g]):raise RuntimeError('Unresolved CPU/GPU coefficient')
   values.append(100*abs(g[key]-c[key])/abs(c[key]))
  diffs[key]={'max_relative_difference_pct':max(values),'pass':max(values)<.05}
 def cost(rs):
  # Omit first five steps, which may include GPU kernels/caches being initialized.
  delta=[rs[i]['wall_seconds']-rs[i-1]['wall_seconds'] for i in range(5,len(rs))]
  return statistics.median(delta)
 ct=cost([matched[round(r['physical_time_s'],9)] for r in gpu]);gt=cost(gpu)
 return dict(pass_check=all(v['pass'] for v in diffs.values()),threshold_pct=.05,threshold_purpose='Project hardware-equivalence screen, ten times tighter than force settling; not a mesh uncertainty estimate',matched_steps=len(gpu),quantities=diffs,cpu_seconds_per_step=ct,gpu_seconds_per_step=gt,speedup=ct/gt,dt_s=gpu[-1]['dt_s'],inner=10)
def main():
 request=read(O/'gpu_live_transition.json');old=Path(request['source_case'])
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
 paths={m:[] for m in LEVELS};paths['G10_F']=[old/'history.csv'];summaries={}
 for m in RUN_ORDER:
  t=start_times[m]
  out,d=flow('calm_settle_'+m,sources[m],t,t+3,dt,10,cells[m],settle=True,prior=old/'history.csv' if m=='G10_F' else None)
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
  write(O/'gci_results.json',dict(status='calm_mesh_screen_completed_GCI_not_resolved',cells=cells,dt_s=dt,summaries=summaries,spatial_noise=noise,GCI=estimates,controls_run=False,reason='No quantity has a resolved plausible monotonic grid trend with sufficiently small settling uncertainty; additional time-step controls would not establish GCI.',scope='Calm water only; no wave accuracy claim',source=original,gpu=True))
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
 write(O/'gci_results.json',dict(status='calm_GPU_checks_completed',cells=cells,dt_s=dt,summaries=summaries,controls=controls,nuisance_gates=gates,spatial_noise=noise,GCI=estimates,scope='Numerical in-plane mesh convergence of CL and total/pressure/viscous CD in calm water on W01a domain. Does not establish wave-response discretization uncertainty or experimental validation.',wave_GCI_planned=False,local_yplus_exceptions_allowed=True,source=original,gpu=True,workers=WORKERS,lightest_mesh_preferred=True))
 state('calm_GPU_GCI_checks_completed',verified_quantities=[k for k,v in estimates.items() if v['status']=='calm_spatial_uncertainty_estimated'])

if __name__=='__main__':
 lock=O/'gpu_live_study.lock';owned=False
 try:
  with lock.open('x') as f:json.dump({'pid':os.getpid()},f)
  owned=True
  ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
  main()
 except BaseException as e:
  if owned:state('needs_review',error=runner.redact(str(e)))
  raise
 finally:
  ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
  if owned and lock.exists() and read(lock).get('pid')==os.getpid():lock.unlink()
