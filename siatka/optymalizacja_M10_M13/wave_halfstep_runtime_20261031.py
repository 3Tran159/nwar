"""Bounded NEW experiment runner. Never changes an existing solver or queue.
Credentials are obtained from the existing launcher only at runtime and redacted.
"""
from pathlib import Path
from datetime import datetime
import sys,os,json,uuid,hashlib,shutil,subprocess,threading,time,csv,statistics,ctypes
ROOT=Path(r'E:\ntnu_mesh_optimization_20261030');W=ROOT/'wave_surface_only'
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
sys.path.insert(0,str(ROOT/'parallel_cpu_20261031'))
import bounded_cpu_pilot as guard
GIB=2**30
def now():return datetime.now().astimezone().isoformat()
def read(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def write(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 t.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');os.replace(t,p)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 try:
  with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 except OSError:return []
def resource_problem():
 if any(p.exists() for p in (ROOT/'STOP_ALL',W/'STOP_ALL',F/'STOP_ALL',ROOT/'parallel_cpu_20261031/STOP_ALL')):return 'STOP_ALL'
 if guard.free_memory()<16*GIB:return 'RAM_below16GiB'
 if shutil.disk_usage('C:/').free<15*GIB or shutil.disk_usage(str(ROOT)).free<25*GIB:return 'disk_guard'
 return None
def set_owned_affinity(mask):
 k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p
 k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
 k.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
 assert k.SetProcessAffinityMask(k.GetCurrentProcess(),mask),'Own CPU affinity failed'
 assert k.SetPriorityClass(k.GetCurrentProcess(),0x4000),'Own priority failed'
def main_cost():
 q=read(ROOT/'mesh_queue_state.json')
 if q.get('status')!='running' or not guard.alive(q.get('star_pid')):return None
 p=Path(q.get('directory',''));rr=rows(p/'history.csv')
 if len(rr)<201:return None
 vals=[float(b['wall_seconds'])-float(a['wall_seconds']) for a,b in zip(rr[-201:-1],rr[-200:]) if int(b['step'])-int(a['step'])==1]
 if len(vals)<180 or min(vals)<=0:return None
 return {'path':str(p),'pid':q['star_pid'],'last_step':int(rr[-1]['step']),'cost':statistics.median(vals)}
def check_slowdown(baseline,laststep):
 if not baseline:return laststep,None,None
 q=read(ROOT/'mesh_queue_state.json')
 if q.get('status')!='running':return laststep,None,None
 if q.get('directory')!=baseline['path']:return laststep,None,'primary_stage_changed'
 p=Path(baseline['path'])/'history.csv'
 if time.time()-p.stat().st_mtime>120:return laststep,None,'main_history_stale'
 rr=[r for r in rows(p) if int(r['step'])>laststep]
 if len(rr)<31:return laststep,None,None
 rr=rr[:31];vals=[float(b['wall_seconds'])-float(a['wall_seconds']) for a,b in zip(rr,rr[1:])]
 if len(vals)!=30 or min(vals)<=0:return laststep,None,'invalid_main_timing'
 cost=statistics.median(vals)
 return int(rr[-1]['step']),{'at':now(),'s_per_step':cost,'slowdown_pct':100*(cost/baseline['cost']-1)},None

def stage(folder,source,macro,env=None,workers=1,gpu=False,mask=None,budget_s=2400,protect_main=False,phase='mesh'):
 folder,source,macro=Path(folder),Path(source),Path(macro)
 assert folder.resolve().is_relative_to(ROOT.resolve())
 assert not (folder/'star.log').exists(),'Existing attempt preserved'
 assert source.is_file() and macro.is_file()
 assert resource_problem() is None,resource_problem()
 folder.mkdir(parents=True,exist_ok=True)
 if mask is not None:set_owned_affinity(mask)
 digest=sha(source);inputpath=folder/'input.sim'
 assert not inputpath.exists(),'Existing input preserved'
 shutil.copy2(source,inputpath);assert sha(inputpath)==digest
 localmacro=folder/macro.name
 if localmacro.resolve()!=macro.resolve():
  assert not localmacro.exists();shutil.copy2(macro,localmacro)
 baseline=main_cost() if protect_main else None
 last=baseline['last_step'] if baseline else -1;bad=0;reason=None;measurements=[]
 actual_env=dict(os.environ,**(env or {}));actual_env['PYTHONUTF8']='1'
 options=guard.saved_options(workers)
 if gpu:options+=['-gpgpu','auto:1']
 args=[str(guard.STAR),*options,'-batch',str(localmacro),str(inputpath)]
 write(folder/'source_identity.json',{'path':str(source),'sha256':digest,'original_preserved':True})
 write(folder/'identity.json',{'phase':phase,'source':str(source),'source_sha256':digest,'macro_sha256':sha(macro),'workers':workers,'cpu_workers':workers,'gpu':gpu,'created':now()})
 started=time.monotonic()
 with (folder/'star.log').open('x',encoding='utf-8') as log:
  proc=subprocess.Popen(args,cwd=folder,env=actual_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
  write(folder/'process.json',{'pid':proc.pid,'controller_pid':os.getpid(),'workers':workers,'gpu':gpu,'at':now(),'mask':mask})
  print(json.dumps({'event':'owned_stage_started','folder':str(folder),'phase':phase,'pid':proc.pid,'workers':workers,'gpu':gpu}),flush=True)
  def drain():
   for line in proc.stdout:log.write(guard.redact(line));log.flush()
  thread=threading.Thread(target=drain,daemon=True);thread.start();lastcheck=0
  while proc.poll() is None:
   if time.monotonic()-lastcheck>=12:
    lastcheck=time.monotonic();reason=reason or resource_problem()
    if time.monotonic()-started>budget_s:reason=reason or 'wall_budget'
    if protect_main:
     last,m,problem=check_slowdown(baseline,last);reason=reason or problem
     if m:
      measurements.append(m);bad=bad+1 if m['slowdown_pct']>15 else 0
      if bad>=2:reason=reason or 'main_slowdown_over15pct_two_windows'
    if (folder.parent/'STOP').exists():reason=reason or 'user_stop'
    if (folder/'macro_error.json').exists():
     failure=read(folder/'macro_error.json')
     reason=reason or 'macro_error'
     lost='Connection reset' in str(failure.get('error',''))
     hist=folder/'history.csv'
     stale=hist.exists() and time.time()-hist.stat().st_mtime>120
     saving=any(time.time()-f.stat().st_mtime<90 for f in folder.glob('*.sim'))
     if lost and stale and not saving:
      write(folder/'failed_client_shutdown.json',{'at':now(),'pid':proc.pid,'reason':'Lost server, stale steps, no save in progress; own process only'})
      subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    if reason:(folder/'STOP').touch()
    rr=rows(folder/'history.csv');lastrow=rr[-1] if rr else {}
    write(folder/'monitor.json',{'at':now(),'phase':phase,'status':'stop_requested' if reason else 'running' if rr else 'loading','reason':reason,'pid':proc.pid,'last_step':lastrow.get('step'),'time_s':lastrow.get('physical_time_s',lastrow.get('time_s')),'elapsed_wall_s':time.monotonic()-started,'main_timing':measurements[-4:]})
   time.sleep(3)
  thread.join(20)
 unchanged=sha(source)==digest
 result={'exit_code':proc.returncode,'source_unchanged':unchanged,'controller_reason':reason,'completed':read(folder/'completed.json'),'phase':phase,'at':now(),'wall_s':time.monotonic()-started,'timing':measurements}
 write(folder/'stage_result.json',result)
 assert proc.returncode==0 and unchanged,'Stage failed; original evidence preserved'
 assert reason is None,'Bounded stage stopped: '+str(reason)
 return folder,result
