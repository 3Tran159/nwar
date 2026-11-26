"""CPU-only GCI family; read completed W01a GPU checkpoints without controlling that run."""
from pathlib import Path
import os,sys,json,time,datetime,hashlib,shutil,subprocess,threading,ctypes,csv,math
O=Path(__file__).resolve().parent;H=O.parent
sys.path.insert(0,str(H/'.deps'))
import numpy as np
import wave_analysis as a
R=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
W=Path(r'E:\ntnu\quasi2d_waves_20261029\W01a_W20L4_M10_inlet_wave_r1')
sys.path.insert(0,str(R.parent/'night_20261028'))
from night_queue import STAR,saved_options,redact,free_memory
LEVELS=['W01a','G10_M','G10_F'];PRIMARY=['CD_mean','CD_amplitude','CL_total_mean','CL_total_amplitude']
WORKERS=22;AFFINITY=16777212 # CPUs 2-23 for this study; CPUs 0-1 reserved for C01.
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def state(status,**kw):
 write(O/'cpu_study_state.json',dict(status=status,pid=os.getpid(),updated_at=datetime.datetime.now().astimezone().isoformat(),workers=WORKERS,gpu=False,**kw));print(status,kw,flush=True)
def stop():return (O/'STOP').exists() or (R/'STOP_ALL').exists()
def wait_resources():
 while free_memory()<20*1024**3:
  if stop():raise RuntimeError('Stop marker')
  state('waiting_for_CPU_memory');time.sleep(30)
 if shutil.disk_usage(str(O)).free<15*1024**3:raise RuntimeError('Less than 15 GiB free study storage')
def pin():
 k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p;k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
 if not k.SetProcessAffinityMask(k.GetCurrentProcess(),AFFINITY):raise RuntimeError('CPU affinity assignment failed')
def job(name,source,macro,envs):
 out=O/'force_stabilization_20261029'/name
 if out.exists():raise RuntimeError('Existing attempt preserved '+name)
 out.mkdir(parents=True);wait_resources();before=sha(source);shutil.copy2(source,out/'input.sim')
 assert sha(out/'input.sim')==before
 write(out/'source_identity.json',dict(path=str(source),sha256=before))
 env=os.environ.copy();env.update(envs);env.update(NTNU_STAB_OUT=str(out),NTNU_MAP_OUT=str(out))
 pin();start=time.time();reason=None
 with (out/'star.log').open('x',encoding='utf-8') as log:
  # Deliberately no -gpgpu option. Every mesh level and numerical control uses CPU22.
  p=subprocess.Popen([str(STAR),*saved_options(WORKERS),'-batch',str(macro),str(out/'input.sim')],cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.NORMAL_PRIORITY_CLASS)
  write(out/'process.json',dict(pid=p.pid,workers=WORKERS,CPU_affinity_mask=AFFINITY,gpu=False))
  state('CPU_job_running',job=name,star_pid=p.pid,directory=str(out))
  def drain():
   for line in p.stdout:log.write(redact(line));log.flush()
  th=threading.Thread(target=drain);th.start()
  while p.poll() is None:
   if stop() or free_memory()<8*1024**3 or shutil.disk_usage(str(O)).free<6*1024**3 or time.time()-start>345600:
    (out/'STOP').touch();reason=reason or time.time()
   if free_memory()<4*1024**3 or (reason and time.time()-reason>600):
    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);break
   time.sleep(5)
  rc=p.wait();th.join(30)
 unchanged=sha(source)==before;write(out/'exit.json',dict(returncode=rc,source_unchanged=unchanged,wall_s=time.time()-start,gpu=False,workers=WORKERS))
 if rc or not unchanged or reason:raise RuntimeError('Owned CPU job stopped or failed '+name)
 return out
def rawrows(path):
 with path.open(encoding='utf-8-sig') as f:return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
def flow(name,source,start,target,dt,inner,cells,period,pilot=False):
 env={'NTNU_STAB_DT':str(dt),'NTNU_STAB_TARGET':str(target),'NTNU_STAB_INNER':str(inner),'NTNU_STAB_CELLS':str(cells),'NTNU_STAB_START':str(start),'NTNU_STAB_INIT':'false','NTNU_STAB_ORDER':'SECOND_ORDER','NTNU_STAB_BUDGET':'345000','NTNU_STAB_PRIOR_HISTORY':'','NTNU_GCI_WAVE_PERIOD':str(period),'NTNU_GCI_MAX_CFL':'1e8' if pilot else '25','NTNU_GCI_INTERFACE_CFL':'1e8' if pilot else '1'}
 out=job(name,source,O/'ContinueWaveGCI.java',env);done=read(out/'completed.json')
 if done['status']!='target_reached' or abs(done['time_s']-target)>dt*1.1 or not (out/'EXPORT_OK.json').exists():raise RuntimeError('Flow/CFL gate failed '+name+' '+str(done))
 setup=read(out/'setup.json')
 if setup['gpu_count']!=0:raise RuntimeError('CPU-only execution violated')
 wave=read(out/'wave_audit.json')
 if wave['reinitialized'] or abs(wave['period_s']/period-1)>1e-6:raise RuntimeError('Wave clock changed')
 history=rawrows(out/'history.csv');sub=rawrows(out/'vof_substeps.csv')
 d={'max_CFL':max(r['max_CFL'] for r in history),'interface_CFL':max(r['interface_max_CFL'] for r in history),'effective_VOF_CFL':max(r['flow_CFL_divided_by_substeps'] for r in sub),'max_yplus':max(r['max_yplus'] for r in history),'time_s':done['time_s']}
 write(out/'flow_diagnostics.json',d)
 if not pilot and d['effective_VOF_CFL']>1.00001:raise RuntimeError('VOF CFL exceeded study screening limit')
 return out,d
def select_source():
 global W
 state('waiting_for_completed_full_height_W01a_checkpoint',GPU_run_untouched=True)
 while True:
  if stop():raise RuntimeError('Stop marker')
  runtime=read(R/'wave_foil_run_state.json') if (R/'wave_foil_run_state.json').exists() else {}
  candidate=Path(runtime.get('directory',str(W)))
  allowed=Path(r'E:\ntnu\quasi2d_waves_20261029').resolve()
  if candidate.resolve().parent!=allowed or not candidate.name.startswith('W01a_'):raise RuntimeError('Current wave runtime is outside the requested W01a scope')
  W=candidate
  if (W/'completed.json').exists():
   done=read(W/'completed.json')
   if done['status'] not in ['target_reached','stopped_by_marker','wall_budget']:raise RuntimeError('W01a source run failed its guards')
  if (W/'wave_activation.json').exists() and (W/'latest_checkpoint.json').exists():
   act=read(W/'wave_activation.json');cp=read(W/'latest_checkpoint.json')
   p=Path(cp.get('file',cp.get('path','')))
   if cp.get('completed_save') and p.is_file() and cp.get('time_s',0)>=max(act['ramp_end_time_s']+.2*act['planning_full_height_period_s'],act['activation_time_s']+act['planning_full_height_period_s']):
    bind=read(W/'inlet_wave_binding.json')
    if bind['initial_conditions_unchanged']!=True or bind['global_initialization']!=False or bind['forcing_zone_x_m']!=[-35,-15] or bind['damping_zone_x_m']!=[25,45]:raise RuntimeError('W01a source configuration differs')
    if read(W/'setup.json')['cells']!=317277:raise RuntimeError('Wrong coarse mesh')
    out=O/'wave_source';out.mkdir()
    digest=sha(p);shutil.copy2(p,out/'reference.sim')
    if sha(p)!=digest or sha(out/'reference.sim')!=digest:raise RuntimeError('Completed source checkpoint changed while copying')
    spec=dict(original=str(p),sha256=digest,time_s=cp['time_s'],period_s=act['planning_full_height_period_s'],activation=act,binding=bind,original_preserved=True)
    write(out/'source_identity.json',spec);return out/'reference.sim',spec
  time.sleep(30)
def main():
 state('waiting_for_W01a_geometry_audit',GPU_run_untouched=True)
 while not (O/'verified_starting_states.json').exists():
  if stop():raise RuntimeError('Stop marker')
  if (O/'study_state.json').exists() and read(O/'study_state.json')['status']=='needs_review':raise RuntimeError('Geometry/mapping preparation needs review')
  time.sleep(20)
 fam=read(O/'family_audit/family_audit.json')
 if not all(fam['gates'].values()):raise RuntimeError('Actual mesh family audit failed')
 cells={m:fam['meshes'][m]['cells'] for m in LEVELS};area={m:fam['meshes'][m]['total_fluid_section_area_m2'] for m in LEVELS}
 reference,spec=select_source();start=spec['time_s'];period=spec['period_s'];sources={'W01a':reference}
 for m in LEVELS[1:]:
  out=job('wave_map_'+m,reference,O/'MapW01Solution.java',{'NTNU_MAP_MESH':str(O/(m+'_raw')/'mesh_exact.CGNS'),'NTNU_MAP_CELLS':str(cells[m]),'NTNU_MAP_EXPECTED_START':str(start)})
  if not read(out/'mapping_audit.json')['pass'] or not (out/'mapped.sim').exists():raise RuntimeError('Wave-field mapping failed '+m)
  sources[m]=out/'mapped.sim'
 dt=.0001
 for attempt in range(4):
  pilots={};ratios=[]
  for m in LEVELS:
   out,d=flow('pilot_'+m+'_r'+str(attempt+1),sources[m],start,start+.02,dt,10,cells[m],period,True);pilots[m]=out
   ratios += [d['max_CFL']/25,d['interface_CFL'],d['effective_VOF_CFL']]
  worst=max(ratios)
  if worst<=1:break
  dt/=2**max(1,math.ceil(math.log2(1.1*worst)))
 else:raise RuntimeError('No acceptable common dt after four CPU pilots')
 write(O/'accepted_timestep.json',dict(dt_s=dt,flow_max_CFL_limit=25,interface_max_CFL_limit=1,effective_VOF_max_CFL_limit=1,gpu=False,workers=WORKERS,interpretation='Project screening for implicit URANS/VOF; dt/2 controls required for temporal accuracy. Not a universal explicit CFL bound.'))
 source_time={m:read(pilots[m]/'completed.json')['time_s'] for m in LEVELS};sources={m:pilots[m]/'final.sim' for m in LEVELS};paths={m:[] for m in LEVELS}
 target=start+6*period
 for roundno in range(5):
  for m in LEVELS:
   out,d=flow('study_'+m+'_r'+str(roundno+1),sources[m],source_time[m],target,dt,10,cells[m],period);paths[m].append(out/'history.csv');sources[m]=out/'final.sim';source_time[m]=d['time_s']
  summaries={m:a.summarize(a.load_history(paths[m]),target,period) for m in LEVELS};flat={m:a.flat_metrics(summaries[m]) for m in LEVELS}
  deltas={k:min(abs(flat[LEVELS[j]][k]-flat[LEVELS[j+1]][k]) for j in [0,1]) for k in flat['W01a']}
  shifts={}
  for k in flat['W01a']:
   field,metric=k.rsplit('_',1);shifts[k]=max(summaries[m][field][metric+'_cycle_shift_abs'] for m in LEVELS)
  stable={k:shifts[k]<=.1*deltas[k] and all(summaries[m][k.rsplit('_',1)[0]][k.rsplit('_',1)[1]+'_cycle_shift_pct']<=.2 for m in LEVELS) for k in PRIMARY}
  estimates={k:a.gci([flat[m][k] for m in LEVELS],area,cells) for k in flat['W01a']}
  write(O/'spatial_progress.json',dict(window_s=[target-3*period,target],summaries=summaries,smallest_pair_differences=deltas,cycle_shifts=shifts,stability=stable,GCI=estimates))
  if all(stable.values()):break
  target+=3*period
 else:raise RuntimeError('Periodic drift not small relative to mesh differences; GCI withheld after 18 cycles')
 control_start=source_time['G10_F'];control_end=control_start+4*period;common=sources['G10_F'];controls={}
 for label,testdt,inner in [('baseline',dt,10),('dt_half',dt/2,10),('inner_twice',dt,20)]:
  out,d=flow('control_'+label,common,control_start,control_end,testdt,inner,cells['G10_F'],period)
  controls[label]=a.summarize(a.load_history([out/'history.csv']),control_end,period)
 cflat={k:a.flat_metrics(v) for k,v in controls.items()};gates={}
 for k in estimates:
  base=cflat['baseline'][k];field,metric=k.rsplit('_',1)
  effects={'dt_half':abs(cflat['dt_half'][k]-base),'inner_twice':abs(cflat['inner_twice'][k]-base),'later_window':abs(flat['G10_F'][k]-base),'cycle_drift':max(controls[v][field][metric+'_cycle_shift_abs'] for v in controls)}
  passed=max(effects.values())<=.1*deltas[k];gates[k]={'effects':effects,'allowed_abs':.1*deltas[k],'pass':passed}
  if 'GCI_fine_abs' in estimates[k]:estimates[k]['status']='spatial_uncertainty_estimated' if passed and not estimates[k]['order_caution'] else 'not_verified_nuisance_or_order_review_required'
 phase={key:{m:a.phase_difference(summaries[m][key]['full']['phase_deg'],summaries['G10_F'][key]['full']['phase_deg']) for m in LEVELS} for key in summaries['W01a']}
 write(O/'gci_results.json',dict(status='CPU_checks_completed',cells=cells,dt_s=dt,period_s=period,averaging_window_s=[target-3*period,target],means_and_harmonics=summaries,phase_difference_vs_fine_deg=phase,controls=controls,nuisance_gates=gates,GCI=estimates,local_yplus_exceptions_allowed=True,scope='Numerical in-plane spatial uncertainty of current W01a. Separate phase-conservation audit, wave-domain validation and experimental validation are not certified by GCI.',source=spec,gpu=False,workers=WORKERS))
 state('CPU_GCI_checks_completed',verified_quantities=[k for k,v in estimates.items() if v['status']=='spatial_uncertainty_estimated'])
if __name__=='__main__':
 raise RuntimeError('Wave GCI superseded by user: use cpu_calm_study.py for calm-only CPU verification')
 lock=O/'cpu_study.lock'
 try:
  with lock.open('x') as f:json.dump({'pid':os.getpid()},f)
  ctypes.windll.kernel32.SetThreadExecutionState(0x80000001);main()
 except BaseException as e:state('needs_review',error=str(e));raise
 finally:
  ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
  if lock.exists() and read(lock).get('pid')==os.getpid():lock.unlink()
