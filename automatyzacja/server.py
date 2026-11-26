"""Loopback-only calculation console. Explicit authenticated POSTs own all queue changes."""
from common import *
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,unquote,parse_qs
import threading,subprocess,secrets,mimetypes,statistics,webbrowser,argparse
from history_view import history_view,run_chain
from report_selection import final_report_root
from project_results import force_difference_rows
from english import localize
TOKEN=secrets.token_urlsafe(32)
PORT=8782
ACTION_LOCK=threading.RLock()
TELEMETRY={}
LEGACY_QUEUE_WAIT='Waiting: resources occupied by an existing run.'
def spawn(script,*args):
 log=DATA/(script.replace('.py','')+'.service.log')
 with log.open('a',encoding='utf8') as f:
  p=subprocess.Popen([str(PYTHON),str(HERE/script),*args],cwd=HERE,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 return p.pid
def ensure_worker():
 owner=read(DATA/'worker.lock')
 if owner.get('birth') and owner['birth']==birth(owner.get('pid')):return owner['pid']
 return spawn('worker.py')

def current_resume(jj, preparation, external):
 """Expose the most recently used run, never an older abandoned pause."""
 if any(j['status'] in ('running','preflight','pausing') for j in jj) or any(j['status']=='running' for j in external):return None
 if preparation and preparation['active']:return None
 candidates=[(j.get('updated') or j.get('created') or '', 'wave', j) for j in jj if not j['spec'].get('smoke') and j['status'] not in ('queued','deferred','cancelled','preflight_blocked')]
 if preparation:candidates.append((preparation.get('updated_at',''),'preparation',preparation))
 if not candidates:return None
 _,kind,run=max(candidates,key=lambda x:x[0])
 if kind=='preparation':
  info=run['resume_info']
  if run['phase'] not in ('paused','needs_review'):return None
  return dict(kind=kind,id='PRE_W04',case_id='PRE W04',folder=run['folder'],time_s=info['time_s'],available=info['available'],reason=info['reason'])
 if (run['case_id']=='W08' and run['status']=='failed' and run['spec'].get('mode')=='resume'
     and not (Path(run['folder'])/'process.json').exists()):
  run=next((j for j in jj if j['id']==run['spec'].get('parent_id') and j['can_resume']),run)
 if run['status']!='paused':return None
 return dict(kind=kind,id=run['id'],case_id=run['case_id'],folder=run['folder'],time_s=run['live'].get('time_s'),available=run['can_resume'],reason=None if run['can_resume'] else 'This pause already has a continuation or needs checkpoint review.')

def current_run(jj, preparation, external):
 """Display the active or latest run, independently of whether it can resume."""
 waves=jj+external
 active=next((j for j in waves if j['status'] in ('running','preflight','pausing') and not j.get('observed_status')),None)
 if active:return dict(kind='wave',id=active['id'])
 if preparation and preparation.get('active'):return dict(kind='preparation',id='PRE_W04')
 candidates=[(j.get('updated') or j.get('created') or '',dict(kind='wave',id=j['id'])) for j in waves
             if not j.get('spec',{}).get('smoke') and j['status'] not in ('queued','deferred','cancelled','preflight_blocked')]
 if preparation and (preparation.get('live',{}).get('history_samples') or preparation.get('error')):
  candidates.append((preparation.get('updated_at',''),dict(kind='preparation',id='PRE_W04')))
 return max(candidates,key=lambda x:x[0])[1] if candidates else None

def enable_report_updates():
 write(DATA/'live_report_refresh.json',dict(enabled=final_report_root() is None,interval_s=300,at=now(),last_requested_epoch=0))

def refresh_live_report():
 if final_report_root() is not None:return
 config=read(DATA/'live_report_refresh.json')
 if not config.get('enabled') or time.time()-config.get('last_requested_epoch',0)<300:return
 lock=read(HERE/'report.lock')
 if lock.get('birth') and lock['birth']==birth(lock.get('pid')):return
 from pre_w04 import PRE,calm_folders
 owner=read(PRE/'state.json');folders=[]
 if owner.get('birth') and owner['birth']==birth(owner.get('pid')) and owner.get('status')=='calm_running':folders.append(calm_folders()[-1])
 folders += [Path(j['folder']) for j in jobs() if j['status']=='running' and j.get('controller_birth') and j['controller_birth']==birth(j.get('controller_pid'))]
 signature=[]
 for folder in folders:
  hist=tail(folder/'history.csv')
  if hist:signature.append([str(folder),hist[-1].get('time_s')])
 if not signature or signature==config.get('signature'):return
 spawn('report.py');config.update(last_requested_epoch=time.time(),signature=signature);write(DATA/'live_report_refresh.json',config)

def report_refresh_loop():
 while True:
  try:
   with ACTION_LOCK:
    from custom_waves import release_next
    if release_next():ensure_worker();enable_report_updates()
    refresh_live_report()
  except Exception as ex:write(DATA/'report_error.json',dict(at=now(),error=str(ex)))
  time.sleep(15)
def hardware_loop():
 global TELEMETRY
 while True:
  info=dict(sampled_at=now(),sampled_epoch=time.time())
  try:
   p=subprocess.run(['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
   if p.returncode==0:
    vals=[v.strip() for v in p.stdout.splitlines()[0].split(',')]
    info['gpu']=dict(name=vals[0],percent=number(vals[1]),used_mb=number(vals[2]),total_mb=number(vals[3]),temperature_c=number(vals[4]),power_W=number(vals[5]))
   class MEMORY(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ('total','free','page_total','page_free','virtual_total','virtual_free','extended')]
   m=MEMORY();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
   info['memory']=dict(percent=m.load,used_gb=(m.total-m.free)/2**30,total_gb=m.total/2**30)
   import shutil
   info['disk_free_gb']=shutil.disk_usage(ROOT).free/2**30
   waiting=next((j for j in jobs() if j['status']=='queued' and j['message']==LEGACY_QUEUE_WAIT),None)
   if waiting and not (DATA/'PAUSE').exists():
    from worker import queue_wait_reason
    reason=queue_wait_reason(waiting['spec'])
    if reason:info['queue_wait']=dict(id=waiting['id'],reason=reason)
  except Exception as ex:info['error']=str(ex)
  TELEMETRY=info;time.sleep(10)
def live(folder,spec=None,external=False,entry=None):
 p=Path(folder);hist=tail(p/'history.csv');prog=read(p/'progress.json');mon=read(p/'monitor.json');done=read(p/'completed.json')
 rr=hist[-300:];last=rr[-1] if rr else {}
 costs=[]
 for a,b in zip(rr[:-1],rr[1:]):
  wa,wb=number(a.get('wall_s')),number(b.get('wall_s'))
  sa,sb=number(a.get('step')),number(b.get('step'))
  if None not in (wa,wb,sa,sb) and sb>sa and wb>wa:costs.append((wb-wa)/(sb-sa))
 cost=statistics.median(costs) if costs else None
 t=number(last.get('time_s')) or prog.get('t_s') or number(mon.get('time_s'))
 n=number(last.get('step'));goal=None
 if n is None and spec and spec.get('native_production') and t is not None:
  n=max(0,round((t-spec['source_time'])/spec['dt']))
 if spec:
  if spec.get('mode')!='fresh' and spec.get('stop_kind') not in ('four_cycles','five_cycles'):goal=spec.get('extra_steps')
  elif spec.get('smoke'):goal=spec['smoke']
  else:
   T=period(spec['L']);distance=spec.get('mesh_profile',{}).get('probe_distance_m',34.5)
   origin=spec.get('mesh_profile',{}).get('wave_origin_s',T0)
   end=read(p/'native_plan.json').get('target_s',origin+2*T+distance*T/spec['L']+6*T)
   if prog.get('last_cycle_end_s') is not None:end=prog['last_cycle_end_s']+max(0,5-prog.get('complete_cycles',0))*(prog.get('last_cycle_period_s') or T)
   goal=max(1,math.ceil((end-spec.get('source_time',origin))/.0004))
 else:goal=prog.get('extra_steps_goal');n=prog.get('extra_steps',n)
 pct=min(100,100*n/goal) if n is not None and goal else None
 remaining=max(0,goal-n)*cost if goal and n is not None and cost else None
 age=time.time()-(p/'history.csv').stat().st_mtime if (p/'history.csv').exists() else None
 try:history=history_view(run_chain(entry) if entry else [p])
 except (ValueError,KeyError) as ex:
  history=history_view([p]);history['history_warnings'].insert(0,'Could not load earlier history: '+str(ex))
 return dict(time_s=t,step=n,CL=number(last.get('CL_hydrodynamic')),CD=number(last.get('CD_total')),CFL=number(last.get('max_CFL')),interface_CFL=number(last.get('interface_CFL')),speed=number(last.get('max_speed_m_s')),s_per_step=cost,percent=pct,eta_s=remaining,goal_steps=goal,progress_label='Additional segment' if external or (spec and spec.get('mode')!='fresh') else 'Estimated completion of cycle 5',age_s=age,stale=bool(age is not None and age>180),complete_cycles=prog.get('complete_cycles'),**history,history_label='Full saved wave history',error=read(p/'macro_error.json').get('error'),completed=done,checkpoint=read(p/'latest_checkpoint.json'),wall_s=mon.get('elapsed_wall_s'))
def externals():
 out=[]
 for p in NIGHT.glob('W0*_resume*'):
  pre=read(p/'resume_preflight.json')
  if not pre:continue
  case=pre.get('case');proc=read(p/'process.json');stage=read(p/'stage_result.json')
  if case not in EXISTING:continue
  active=bool(birth(proc.get('controller_pid')) or birth(proc.get('pid')))
  status='running' if active else 'failed' if read(p/'macro_error.json') or stage.get('exit_code',0)!=0 else 'completed' if stage.get('exit_code')==0 and read(p/'completed.json') else 'interrupted'
  entry=dict(id=p.name,case_id=case,external=True,status=status,folder=str(p),updated=stage.get('at') or read(p/'progress.json').get('sampled_at') or '')
  entry['live']=live(p,external=True,entry=entry);out.append(entry)
 from glhf_import import imported_entries
 for entry in imported_entries():
  entry['live']=live(entry['folder'],entry=entry)
  entry['live'].update(complete_cycles=entry['import_recorded_cycles'],
                       history_label='Imported GLHF wave history')
  out.append(entry)
 return out
def snapshot():
 from pre_w04 import snapshot as preparation_snapshot
 from report_selection import active_entries
 from calm_reference import local_reference_enabled,REFERENCE_ID
 jj=active_entries(jobs())
 from bichromatic import case as bichromatic_case
 current_bichromatic=bichromatic_case()
 waiting=TELEMETRY.get('queue_wait',{})
 for j in jj:
  if j['status']=='queued' and j['message']==LEGACY_QUEUE_WAIT and j['id']==waiting.get('id') and not (DATA/'PAUSE').exists():
   j['message']='Waiting: '+waiting['reason']
  j['live']=live(j['folder'],j['spec'],entry=j)
  j['validation']=read(DATA/'validations'/(j['id']+'.json'))
  if j['status'] in ('running','preflight','pausing') and j.get('controller_birth')!=birth(j.get('controller_pid')):
   j['observed_status']='interrupted'
  has_resume=any(x['spec'].get('parent_id')==j['id'] and x['spec'].get('mode')=='resume' and x['status'] not in ('failed','cancelled','interrupted','preflight_blocked') for x in jj)
  j['can_resume']=j['status']=='paused' and not has_resume and j['live']['checkpoint'].get('healthy') is True
  if j['case_id']=='W08' and j['spec'].get('components')!=(current_bichromatic or {}).get('components'):
   j['can_resume']=False
 latest=read(HERE/'latest_report.json')
 summ=read(Path(latest['directory'])/'audit.json') if latest else {}
 if local_reference_enabled() and summ.get('C01',{}).get('reference_id')!=REFERENCE_ID:summ={}
 sources=[]
 for c in catalog():
  results=[r for r in summ.get('results',[]) if r.get('case')==c['id'] and not r.get('smoke') and 'error' not in r]
  cr=max(results,key=lambda r:r.get('time_s') or -1) if results else {}
  diagnostic=summ.get('w08bi_snapshot') if c['id']=='W08' and c.get('diagnostic_only') else None
  if diagnostic and diagnostic.get('final'):
   sources.append(dict(c,result=dict(time_s=diagnostic['time_s'],CL=diagnostic['CL_wave'],CD=diagnostic['CD_wave'],
                    cycles=None,repeatable=None,hash_verified=True,diagnostic_completed=True),validation={}))
   continue
  validation_id=cr.get('id',c['id'])
  validation=cr.get('validation',{})
  if validation.get('verification_kind') not in ('glhf_saved_state','glhf_verified_final_save'):
   validation={} if local_reference_enabled() and not cr else read(DATA/'validations'/(validation_id+'.json'))
  sources.append(dict(c,display_id=cr.get('display_id',c.get('display_id',c['id'])),result=dict(time_s=cr.get('time_s'),cycles=cr.get('cycles',{}).get('count'),repeatable=cr.get('cycles',{}).get('repeatable'),CL=cr.get('cycles',{}).get('CL_mean'),CD=cr.get('cycles',{}).get('CD_mean'),hash_verified=cr.get('saved_hash_verified')),validation_id=validation_id,validation=validation,force_wave_plot=cr.get('force_wave_plot')))
 owner=read(DATA/'worker.lock');preparation=preparation_snapshot();external=active_entries(externals())
 if preparation:
  from pre_w04 import PRE
  from pre_resume import checkpoint_info
  preparation['updated_at']=read(PRE/'state.json').get('at','');preparation['resume_info']=checkpoint_info()
  if preparation['resume_info']['starting']:
   preparation.update(active=True,status='preflight',label='Loading the saved checkpoint')
 drag_differences,lift_differences=force_difference_rows(summ)
 return dict(sampled_at=now(),preparation=preparation,current_run=current_run(jj,preparation,external),current_resume=current_resume(jj,preparation,external),live_report_refresh=read(DATA/'live_report_refresh.json'),catalog=sources,jobs=jj,external=external,hardware=TELEMETRY,paused=(DATA/'PAUSE').exists(),stops=[str(p) for p in STOPS if p.exists()],worker_alive=bool(owner.get('birth') and owner['birth']==birth(owner.get('pid'))),report=latest,report_busy=bool(read(HERE/'report.lock').get('birth') and read(HERE/'report.lock')['birth']==birth(read(HERE/'report.lock').get('pid'))),audit=dict(C01=summ.get('C01'),missing=summ.get('missing',[]),mesh=summ.get('mesh',[])),report_error=read(DATA/'report_error.json'),selftest=read(HERE/'selftest.json'),Q_data=summ.get('Q_data',[]),drag_differences=drag_differences,lift_differences=lift_differences,project_policy=summ.get('project_policy',{}))
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def valid_host(self):
  return self.headers.get('Host') in ('127.0.0.1:'+str(PORT),'localhost:'+str(PORT))
 def send(self,obj,status=200):
  body=json.dumps(localize(obj),ensure_ascii=False,allow_nan=False).encode()
  self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def file(self,p,replace_token=False):
  if not p.is_file():return self.send({'error':'File not found.'},404)
  body=p.read_bytes()
  if replace_token:body=body.replace(b'__TOKEN__',TOKEN.encode())
  self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if not self.valid_host():return self.send({'error':'Invalid host.'},403)
  path=unquote(urlparse(self.path).path)
  try:
   if path=='/api/status':return self.send(snapshot())
   if path=='/api/wave-view':
    from wave_view import wave_view
    case_id=parse_qs(urlparse(self.path).query).get('case',[''])[0]
    if case_id not in {c['id'] for c in catalog()}:return self.send({'error':'Unknown wave case'},400)
    return self.send(wave_view(case_id,externals()))
   if path in ('/','/index.html'):return self.file(HERE/'index.html',True)
   if path in ('/app.js','/history_chart.js','/convergence_chart.js','/wave_view.js','/style.css','/instrukcja.html'):return self.file(HERE/path[1:])
   if path.startswith('/pre-w04/'):
    from pre_w04 import PRE
    name=path.removeprefix('/pre-w04/')
    if name not in ('PRE_W04_history.png','PRE_W04_convergence.png','convergence.csv','history.csv','calm_receipt.json'):return self.send({'error':'Path not allowed.'},403)
    return self.file(PRE/name)
   if path.startswith('/validations/'):
    target=(DATA/path[1:]).resolve()
    if not target.is_relative_to((DATA/'validations').resolve()) or target.suffix!='.json':return self.send({'error':'Path not allowed.'},403)
    if not target.is_file() and target.stem.startswith('GLHF_'):
     from glhf_import import imported_entries
     entry=next((j for j in imported_entries() if j['id']==target.stem and j['validation']),None)
     if entry:return self.send(entry['validation'])
    return self.file(target)
   if path=='/report':
    latest=read(HERE/'latest_report.json')
    if not latest:return self.send({'error':'Preparing report.'},404)
    self.send_response(302);self.send_header('Location','/'+latest['relative']+'/report.html');self.end_headers();return
   if path.startswith('/reports/final/'):
    root=final_report_root()
    if root is None:return self.send({'error':'Final report archive is unavailable.'},404)
    root=root.resolve()
    target=(root/path.removeprefix('/reports/final/')).resolve()
    if (not target.is_relative_to(root) or target.parent.parent!=root or not target.parent.name.startswith('final_')
        or read(target.parent/'report_generation.json').get('kind')!='NWAR consolidated final report'):
     return self.send({'error':'Path not allowed.'},403)
    return self.file(target)
   if path.startswith('/reports/'):
    target=(HERE/path[1:]).resolve()
    if not target.is_relative_to((HERE/'reports').resolve()):return self.send({'error':'Path not allowed.'},403)
    return self.file(target)
   return self.send({'error':'Address not found.'},404)
  except Exception as ex:return self.send({'error':str(ex)},500)
 def do_POST(self):
  try:size=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.send({'error':'Invalid request size.'},400)
  if not 0<size<=12000:return self.send({'error':'Invalid request size.'},413)
  payload=self.rfile.read(size)
  if not self.valid_host() or not secrets.compare_digest(self.headers.get('X-NWAR-Token',''),TOKEN):return self.send({'error':'Refresh the dashboard before sending a request.'},403)
  origin=self.headers.get('Origin')
  if origin and origin not in ('http://127.0.0.1:'+str(PORT),'http://localhost:'+str(PORT)):return self.send({'error':'Origin not allowed.'},403)
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=12000:raise ValueError('Invalid request size.')
   data=json.loads(payload)
   with ACTION_LOCK:
    if self.path=='/api/enqueue':
     selected=data.get('cases',[])
     if not isinstance(selected,list) or not 1<=len(selected)<=7 or len(set(selected))!=len(selected):raise ValueError('Select at least one wave.')
     case_map={c['id']:c for c in catalog()}
     if data.get('mode')=='extend' and any(x['case_id'] in selected and x['status']=='running' for x in externals()):
      raise ValueError('This wave has an active continuation. Request extra cycles after it saves to use the latest checkpoint.')
     if any(c not in case_map or not case_map[c]['ready'] for c in selected):raise ValueError('The selected wave requires review.')
     # Validate the whole selection before committing individual idempotent requests.
     active={j['case_id'] for j in jobs() if j['status'] in ('queued','running','preflight','pausing')}
     key=data.get('request_key')
     if not isinstance(key,str) or not 8<=len(key)<=100:raise ValueError('Missing request identifier.')
     existing_keys={j['request_key'] for j in jobs()}
     if any(c in active and key+'_'+c not in existing_keys for c in selected):raise ValueError('A selected wave is already queued.')
     with connection() as conn:
      conn.execute('BEGIN IMMEDIATE')
      ids=[enqueue(c,mode=data.get('mode','fresh'),extra_cycles=data.get('extra_cycles',1),request_key=key+'_'+c,conn=conn) for c in selected]
     if any(job(id)['status']=='queued' for id in ids):ensure_worker()
     return self.send(dict(ids=ids,paused=(DATA/'PAUSE').exists()),202)
    if self.path=='/api/custom-wave':
     from custom_waves import submit
     id=submit(data.get('H'),data.get('L'),data.get('request_key'))
     return self.send(dict(id=id,case_id=job(id)['case_id'],message='Custom wave queued. It starts after the local campaign is accepted and the solver is free.'),202)
    if self.path=='/api/pause':
     from pre_w04 import PRE, calm_folders, snapshot as preparation_snapshot
     preparation=preparation_snapshot()
     marker=dict(origin='user',at=now())
     if preparation and preparation['active'] and preparation['phase']=='calm_running':
      folder=calm_folders()[-1];marker.update(kind='pre_dashboard_pause',folder=str(folder))
      if not (PRE/'STOP').exists():write(PRE/'STOP',marker)
      if not (folder/'STOP').exists():write(folder/'STOP',marker)
     if not (DATA/'PAUSE').exists():write(DATA/'PAUSE',marker)
     for j in jobs():
      if j['status'] in ('running','preflight'):
       p=Path(j['folder'])
       if p.exists():(p/'STOP').touch()
       update(j['id'],status='pausing',message='Pause requested: waiting for a safe checkpoint.')
     return self.send({'message':'Queue paused. The active owned run will finish its step and save a checkpoint.'})
    if self.path=='/api/continue':
     (DATA/'PAUSE').unlink(missing_ok=True);ensure_worker()
     return self.send({'message':'Queue continued. Saved pauses have a separate Resume checkpoint button.'})
    if self.path=='/api/resume':
     parent=job(data['id'])
     if parent['status']!='paused':raise ValueError('Only a verified saved pause can be resumed.')
     id=enqueue(parent['case_id'],'resume',parent_id=parent['id'],request_key=data['request_key'])
     (DATA/'PAUSE').unlink(missing_ok=True);ensure_worker();enable_report_updates();return self.send({'id':id},202)
    if self.path=='/api/resume-current':
     target=snapshot().get('current_resume')
     if not target or any(data.get(k)!=target[k] for k in ('kind','id','folder')):raise ValueError('The current run changed. Refresh the dashboard before resuming.')
     if not target['available']:raise ValueError(target['reason'] or 'The checkpoint is not ready to resume.')
     if target['kind']=='preparation':
      from pre_resume import resume
      result=resume(target['folder'],data.get('request_key'),spawn)
     else:
      from worker import native
      if native() or any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS):raise ValueError('Wait for the previous solver to exit and release its resources.')
      id=enqueue(target['case_id'],'resume',parent_id=target['id'],request_key=data.get('request_key'))
      (DATA/'PAUSE').unlink(missing_ok=True);ensure_worker()
      result=dict(id=id,message='Resuming '+target['case_id']+' from its saved checkpoint. Live charts and report updates are enabled.')
     enable_report_updates();return self.send(result,202)
    if self.path=='/api/cancel':
     j=job(data['id'])
     if j['status'] not in ('queued','deferred'):raise ValueError('Only queued jobs can be cancelled. Save an active run first.')
     update(j['id'],status='cancelled',message='Removed from queue; results remain preserved.');return self.send({'ok':True})
    if self.path=='/api/report':
     state=read(HERE/'report.lock')
     if not (state.get('birth') and state['birth']==birth(state.get('pid'))):spawn('report.py')
     return self.send({'message':'Report generation started.'},202)
    if self.path=='/api/validate':
     from validation import lookup
     entry=lookup(data['id'])
     if not (Path(entry['folder'])/'completed.json').exists():raise ValueError('Full verification is available after the final save. Numerical guards remain active during calculation.')
     spawn('validation.py','--id',entry['id'])
     return self.send({'message':'Run verification started. The checklist will refresh automatically.'},202)
    return self.send({'error':'Unknown operation.'},404)
  except (ValueError,KeyError,TypeError) as ex:return self.send({'error':str(ex)},400)
  except Exception as ex:return self.send({'error':str(ex)},500)
def main():
 p=argparse.ArgumentParser();p.add_argument('--open',action='store_true');a=p.parse_args()
 DATA.mkdir(exist_ok=True,parents=True)
 try:server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
 except OSError:
  if a.open:webbrowser.open('http://127.0.0.1:'+str(PORT))
  return
 write(DATA/'server.json',dict(pid=os.getpid(),birth=birth(os.getpid()),url='http://127.0.0.1:'+str(PORT),at=now()))
 threading.Thread(target=hardware_loop,daemon=True).start()
 threading.Thread(target=report_refresh_loop,daemon=True).start()
 if a.open:webbrowser.open('http://127.0.0.1:'+str(PORT))
 print('NWAR panel: http://127.0.0.1:'+str(PORT),flush=True)
 server.serve_forever()
if __name__=='__main__':main()
