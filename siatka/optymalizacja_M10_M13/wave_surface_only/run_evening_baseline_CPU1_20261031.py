"""Authorized isolated wave-only baseline test, CPU1, from its own saved calm state.
Never edits main GPU, original simulation, old C01 hold or existing controllers.
"""
from pathlib import Path
from datetime import datetime
import os,sys,json,csv,math,time,statistics,subprocess,threading,shutil,uuid,hashlib
R=Path(r'E:\ntnu_mesh_optimization_20261030');W=R/'wave_surface_only';P=R/'parallel_cpu_20261031'
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
sys.path[:0]=[str(P),str(W)]
import bounded_cpu_pilot as guard
import launch_halfdt_wave_cpu2_with_M11_guard as perf
SOURCE=W/'WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c'
MACRO=W/'WaveFromOwnCalm_20261031.java'
LOCKS=[P/'auxiliary.lock',W/'wave_inlet.lock',W/'wave_mesh_comparison.lock']
TOKEN=uuid.uuid4().hex
ROOT=W/('zero_start_matrix_evening_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+TOKEN[:6])
OUT=ROOT/'waves'/'L20_H500_baseline'
def read(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 tmp.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8');os.replace(tmp,p)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 try:
  with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 except OSError:return []
def now():return datetime.now().astimezone().isoformat()
def danger():
 if any(p.exists() for p in [R/'STOP_ALL',W/'STOP_ALL',P/'STOP_ALL',F/'STOP_ALL',ROOT/'STOP']):return 'user_stop'
 if guard.free_memory()<16*1024**3:return 'RAM_below16GiB'
 if shutil.disk_usage('C:/').free<15*1024**3 or shutil.disk_usage('E:/').free<25*1024**3:return 'disk_reserve'
 return None
def main():
 assert datetime.now().date().isoformat()=='2026-10-31'
 plan=read(R/'plan.json');assert plan['parallel_execution']['authorized']
 assert sha(R/'AUTONOMOUS_RECOVERY_PROMPT.md')==plan['recovery_policy']['runbook_sha256']
 assert not any(p.exists() for p in LOCKS),'Another auxiliary owns resources'
 assert danger() is None
 done=read(SOURCE/'completed.json');result=read(SOURCE/'pilot_result.json');ini=read(SOURCE/'initial_flat_audit.json')
 assert done.get('status')=='target_reached' and done.get('steps')==400 and abs(done['time_s']-.4)<1e-8
 assert result.get('returncode')==0 and result.get('original_source_unchanged') is True
 assert ini.get('cells')==53200 and ini.get('reinitialized_disposable_copy') is True
 assert abs(ini.get('initial_max_velocity_m_s',0)-18)<.001
 hist=rows(SOURCE/'history.csv');gauges=rows(SOURCE/'gauges.csv')
 assert len(hist)>=401 and abs(float(hist[-1]['time_s'])-.4)<1e-8
 assert 38.39<float(hist[-1]['water_volume_m3'])<38.41 and 17.5<float(hist[-1]['max_speed_m_s'])<18.5
 late=[x for x in gauges if float(x['time_s'])>=.2]
 assert late and max(abs(float(x['eta_actual_m'])) for x in late)<.002
 prev=[float(x['eta_actual_m']) for x in late if float(x['time_s'])<.3]
 curr=[float(x['eta_actual_m']) for x in late if float(x['time_s'])>=.3]
 assert prev and curr and abs(statistics.fmean(prev)-statistics.fmean(curr))<.0015
 assert read(F/'campaign_hold.json').get('active') is True
 q=read(R/'mesh_queue_state.json');mainpath=Path(q['directory']) if q.get('directory') else None
 main_active=q.get('status')=='running' and guard.alive(q.get('star_pid'))
 if main_active:perf.only_owned_main_star(mainpath)
 elif any(name.lower() in ('starccm+.exe','star-ccm+.exe') for _,name in guard.processes().values()):raise RuntimeError('Unidentified STAR process; no duplicate launch')
 mainrows=rows(mainpath/'history.csv') if mainpath else []
 durations=[float(b['wall_seconds'])-float(a['wall_seconds']) for a,b in zip(mainrows[-201:],mainrows[-200:]) if int(b['step'])==int(a['step'])+1]
 baseline=statistics.median(durations) if len(durations)>=100 else None
 assert not main_active or (baseline is not None and baseline>0)
 frozen_source=SOURCE/'calm_pilot_final.sim';assert frozen_source.stat().st_size>20_000_000
 srcsha=sha(frozen_source);macrosha=sha(MACRO)
 acquired=[];proc=None
 try:
  for lk in LOCKS:
   with lk.open('x',encoding='utf8') as f:json.dump({'pid':os.getpid(),'token':TOKEN,'kind':'evening_baseline_wave_CPU1','at':now()},f)
   acquired.append(lk)
  OUT.mkdir(parents=True,exist_ok=False)
  shutil.copy2(frozen_source,OUT/'input.sim');shutil.copy2(MACRO,OUT/MACRO.name)
  assert sha(OUT/'input.sim')==srcsha and sha(OUT/MACRO.name)==macrosha
  write(OUT/'identity.json',{'created':now(),'phase':'waves','source':str(frozen_source),'source_sha256':srcsha,'macro_sha256':macrosha,'cpu_workers':1,'gpu':False,'original_untouched':True})
  write(OUT/'pilot_config.json',{'stage':'inlet_wave','cells':53200,'lambda_m':20,'H_m':.5,'dt_s':.001,'CPU_workers':1,'inner':10,'steps':5000,'own_calm_checkpoint_t_s':.4,'no_reinitialization':True})
  write(ROOT/'plan.json',{'at':now(),'authorization':'User explicitly requested waves in parallel while M10 completes and M13 is prepared','main_at_start':str(mainpath),'main_baseline_s_step':baseline,'wave_target':{'lambda_m':20,'H_m':.5,'mesh':'baseline'},'source_calm_validated_from_gauges':True,'initialization_performed':False,'old_C01_hold_unchanged':True,'one_auxiliary_CPU':True})
  env=dict(os.environ,NTNU_NOFOIL_WAVE_OUT=str(OUT),NTNU_NOFOIL_OUT=str(OUT),NTNU_NOFOIL_CELLS='53200',NTNU_NOFOIL_WATER_M3='38.4',NTNU_NOFOIL_LAMBDA='20',NTNU_NOFOIL_H='.5',NTNU_NOFOIL_XMIN='-35',NTNU_NOFOIL_XMAX='45',NTNU_NOFOIL_WAVE_PERIOD_S=str(20/23.612),NTNU_NOFOIL_WAVE_STEPS='5000')
  guard.MASK=1<<20
  assert guard.k.SetProcessAffinityMask(guard.k.GetCurrentProcess(),guard.MASK)
  assert guard.k.SetPriorityClass(guard.k.GetCurrentProcess(),guard.BELOW_NORMAL)
  options=guard.saved_options(1);assert '-gpgpu' not in options
  started=time.monotonic();reason=None;lastcheck=0;seen=0;bad=0
  startstep=int(mainrows[-1]['step']) if mainrows else -1
  with (OUT/'star.log').open('x',encoding='utf8') as log:
   proc=subprocess.Popen([str(guard.STAR),*options,'-batch',str(OUT/MACRO.name),str(OUT/'input.sim')],cwd=OUT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   write(OUT/'process.json',{'pid':proc.pid,'controller_pid':os.getpid(),'at':now(),'workers':1,'gpu':False})
   def drain():
    for line in proc.stdout:log.write(guard.redact(line));log.flush()
   th=threading.Thread(target=drain,daemon=True);th.start()
   print(json.dumps({'launched':True,'directory':str(OUT),'pid':proc.pid,'stage':'wave from saved flat water','dt_s':.001,'workers':1}),flush=True)
   while proc.poll() is None:
    if time.monotonic()-lastcheck>15:
     lastcheck=time.monotonic();reason=reason or danger()
     qnew=read(R/'mesh_queue_state.json')
     # Main completion is allowed, never a reason to kill its independent wave test.
     if main_active and qnew.get('status') in ('paused','needs_review'):reason=reason or 'main_paused_or_error'
     new_active=qnew.get('status')=='running' and guard.alive(qnew.get('star_pid'))
     if new_active and qnew.get('directory')!=str(mainpath):reason=reason or 'new_main_requires_solo_performance_baseline'
     wins=perf.direct_monitor(mainpath,startstep,baseline) if main_active and new_active and baseline else []
     for win in wins[seen:]:
      bad=bad+1 if win['slowdown_pct']>15 else 0
      if bad>=2:reason=reason or 'primary_slowdown_two_windows_over15pct'
     seen=len(wins)
     if time.monotonic()-started>2700:reason=reason or 'bounded_wall_budget'
     if reason and not (OUT/'STOP').exists():(OUT/'STOP').touch()
     h=rows(OUT/'history.csv');tail=h[-1] if h else {}
     state={'at':now(),'status':'stop_requested' if reason else 'running' if h else 'loading','phase':'waves','case':'L20_H500_baseline','directory':str(OUT),'pid':proc.pid,'steps':int(tail.get('step',0)),'time_s':float(tail['time_s']) if tail else None,'reason':reason,'main_windows':wins[-3:]}
     write(OUT/'monitor.json',state);write(W/'evening_wave_current.json',state)
    time.sleep(4)
   rc=proc.wait();th.join(20)
  complete=read(OUT/'completed.json')
  result={'at':now(),'phase':'waves','exit_code':rc,'completed':complete,'source_unchanged':sha(frozen_source)==srcsha,'controller_reason':reason,'no_propagation_acceptance_claim':True}
  write(OUT/'stage_result.json',result);write(W/'evening_wave_current.json',dict(result,status='saved_for_review' if rc==0 else 'failed',directory=str(OUT)))
  print(json.dumps(result,ensure_ascii=False),flush=True)
 finally:
  # Keep ownership if solver survives an unexpected controller exception.
  if proc is None or proc.poll() is not None:
   for lk in reversed(acquired):
    if read(lk).get('token')==TOKEN:lk.unlink()
if __name__=='__main__':main()
