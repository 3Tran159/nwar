"""Isolated W04k native continuation using the existing GLHF runtime/settings.

No installed queue, application file, license file or other process is changed.
"""
from pathlib import Path
from datetime import datetime
import argparse,ctypes,hashlib,json,math,os,re,shutil,subprocess,sys,time,uuid,webbrowser,msvcrt,ntpath
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread

PATCH=Path(__file__).resolve().parent

def read(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def write(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf8');tmp.replace(p)
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def root_folder():
 for p in PATCH.parents:
  if all((p/n).is_file()for n in('launcher.json','start_nwar.py','runtime/python.exe')):return p
 raise ValueError('Extract the W04k patch inside the existing NWAR GLHF main folder (beside Start NWAR.cmd).')

def license_key(root):
 if os.environ.get('NWAR_POD_KEY'):return
 # Reuse only an existing user-provided private NWAR launcher, without printing it.
 patterns=[r'set\s+"?NWAR_POD_KEY=([^"\r\n]+)',r'os\.environ\[.[Nn][Ww][Aa][Rr]_[Pp][Oo][Dd]_[Kk][Ee][Yy].\]\s*=\s*[\'"]([^\'"\r\n]+)']
 for base in (root,PATCH):
  for p in list(base.glob('*.cmd'))+list(base.glob('*private*.py')):
   content=p.read_text(encoding='utf-8-sig',errors='replace')
   for pattern in patterns:
    match=re.search(pattern,content,re.I)
    if match and re.fullmatch(r'[A-Za-z0-9_-]{12,100}',match[1].strip()):
     os.environ['NWAR_POD_KEY']=match[1].strip();return
 import tkinter as tk
 from tkinter.simpledialog import askstring
 ui=tk.Tk();ui.withdraw()
 key=askstring('NWAR W04k','Power-on-Demand key for this session',show='*',parent=ui);ui.destroy()
 if not key:raise ValueError('License key was not supplied. Nothing started.')
 os.environ['NWAR_POD_KEY']=key.strip()

def start():
 root=root_folder();config=read(root/'launcher.json')
 if config.get('release')!='2606':raise ValueError('Select STAR-CCM+ 2606 in the existing GLHF installation first.')
 if config.get('license_mode')=='pod':license_key(root)
 env=dict(os.environ,NWAR_PACKAGE_ROOT=str(root),NWAR_WORKSPACE=str(Path(config['workspace_root'])/'2606'),
          NWAR_STAR_RELEASE='2606',NWAR_TRANSFER_ROOT=str(PATCH),PYTHONHOME=str(root/'runtime'),PYTHONNOUSERSITE='1',
          PYTHONPATH=os.pathsep.join((str(PATCH/'engine'),str(root/'lib'))),PYTHONUTF8='1')
 return subprocess.call([str(root/'runtime/python.exe'),str(PATCH/'w04k_transfer.py'),'--run'],cwd=PATCH,env=env)

PAGE='''<!doctype html><meta charset="utf-8"><title>NWAR W04k continuation</title>
<style>body{font:18px system-ui;max-width:1000px;margin:45px auto;background:#f2f6f6;color:#16333b}section{background:white;padding:28px;border-radius:12px;margin:16px 0}progress{width:100%;height:26px}button,a{font:inherit;padding:9px}pre{white-space:pre-wrap}small{color:#526a70}</style>
<h1>W04k · H = 0.25 m · λ = 15 m</h1><section><h2 id="status">Loading status</h2><progress id="progress" max="100" value="0"></progress><p id="time"></p><p id="detail"></p><small>Native STAR-CCM+ 2606 · one GPU process · fields and saved phase preserved</small></section>
<section><b>Target: five complete measured cycles</b><p>Cycle 1 is excluded. Cycles 2–5 must pass the existing numerical health and repeatability checks. A saved diagnostic is not automatically accepted.</p><button onclick="pause()">Pause at a saved checkpoint</button> <a href="/files">Saved results</a><pre id="review"></pre></section>
<script>const token='TOKEN';async function poll(){let s=await(await fetch('/api/status')).json();document.getElementById('status').textContent=s.state;let t=Number(s.time_s||s.source_time_s);document.getElementById('time').textContent='Physical time: '+t.toFixed(4)+' s · target '+s.target_s.toFixed(4)+' s';document.getElementById('progress').value=100*Math.max(0,Math.min(1,(t-s.source_time_s)/(s.target_s-s.source_time_s)));document.getElementById('detail').textContent=s.message||'';document.getElementById('review').textContent=s.cycles==null?'':s.cycles+' complete cycles recorded · accepted cycles 2–5: '+s.cycles_accepted;}async function pause(){await fetch('/api/pause',{method:'POST',headers:{'X-NWAR-Token':token}});poll()}poll();setInterval(poll,4000)</script>'''

def serve(status,token):
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*a):pass
  def reply(self,body,kind='text/html'):
   self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body.encode())
  def do_GET(self):
   if self.path=='/':return self.reply(PAGE.replace('TOKEN',token))
   if self.path=='/api/status':return self.reply(json.dumps(status()),'application/json')
   if self.path=='/files':
    import html
    folder=PATCH/'work';paths=[str(p.relative_to(PATCH))for p in folder.rglob('*')if p.is_file()and p.suffix in('.csv','.json','.sim','.simh')]
    return self.reply('<meta charset="utf-8"><h1>Saved W04k results</h1><p>Folder: '+html.escape(str(folder))+'</p><pre>'+html.escape('\n'.join(paths))+'</pre>')
   self.send_error(404)
  def do_POST(self):
   if self.path!='/api/pause'or self.headers.get('X-NWAR-Token')!=token:return self.send_error(403)
   write(PATCH/'state/PAUSE',{'origin':'user','action':'pause_W04k_only','at':time.time()});self.reply('{}','application/json')
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);Thread(target=server.serve_forever,daemon=True).start()
 return server,'http://127.0.0.1:'+str(server.server_port)

def verify_payload():
 m=read(PATCH/'manifest.json')
 if m.get('case_id')!='W04k'or (m.get('H_m'),m.get('lambda_m'))!=(.25,15.):raise ValueError('Unexpected W04k transfer identity.')
 for name,info in m['files'].items():
  p=(PATCH/name).resolve()
  if not p.is_relative_to(PATCH)or not p.is_file()or p.stat().st_size!=info['bytes']or sha(p)!=info['sha256']:
   raise ValueError('Transfer checksum failed: '+name)
 return m

DESKTOP_GPU_APPS={'explorer.exe','photos.exe','dwm.exe','applicationframehost.exe','shellexperiencehost.exe',
 'startmenuexperiencehost.exe','searchhost.exe','searchapp.exe','textinputhost.exe','chrome.exe','msedge.exe',
 'msedgewebview2.exe','firefox.exe','codex.exe','chatgpt.exe','widgets.exe','widgetservice.exe','shellhost.exe',
 'runtimebroker.exe','lockapp.exe','windowsTerminal.exe'.lower(),'taskmgr.exe','phoneexperiencehost.exe',
 'nvidia overlay.exe','nvidia share.exe','nvdisplay.container.exe','nvidia app.exe',
 # WDDM reports these ordinary GLHF desktop applications as C+G as well.
 'steamwebhelper.exe','crossdeviceresume.exe','icue.exe','msteams.exe','ledkeeper2.exe',
 'systemsettings.exe','storagemonitor.exe','icloudhome.exe','logonui.exe','adskaccessuihost.exe',
 'tabtip.exe','lghub_system_tray.exe','epicwebhelper.exe','epicgameslauncher.exe',
 'whatsapp.root.exe','overwolfbrowser.exe','overwolf.exe','rtkuwp.exe','widgetboard.exe',
 'remoting_desktop.exe'}

def gpu_conflicts(output,table):
 return [int(line.strip())for line in output.splitlines()if line.strip().isdigit()
         and ntpath.basename(table.get(int(line.strip()),(None,''))[1]).lower()not in DESKTOP_GPU_APPS]

def parse_gpu_xml(content,table):
 tree=ET.fromstring(content)
 if not tree.findall('gpu'):raise ValueError('NVIDIA diagnostic contains no GPU.')
 records=[]
 for item in tree.findall('.//process_info'):
  pid=(item.findtext('pid')or'').strip()
  if not pid.isdigit():continue
  pid=int(pid);kind=(item.findtext('type')or'unknown').strip()
  name=ntpath.basename(table.get(pid,(None,''))[1]or(item.findtext('process_name')or'unknown'))
  graphics_only=kind.upper()=='G'
  record=dict(pid=pid,name=name,type=kind,blocks=not graphics_only and name.lower()not in DESKTOP_GPU_APPS)
  records.append(record)
 return records

def gpu_preflight(wait_s=25):
 from transfer_runtime import processes
 nvidia=shutil.which('nvidia-smi')
 if not nvidia:raise ValueError('NVIDIA diagnostic utility is unavailable; GPU state cannot be checked.')
 deadline=time.monotonic()+wait_s;clear=0;last={}
 while True:
  try:
   probe=subprocess.run([nvidia,'-q','-x'],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
   if probe.returncode:raise ValueError('NVIDIA diagnostic failed: '+(probe.stderr or probe.stdout).strip()[:220])
   records=parse_gpu_xml(probe.stdout,processes());blocked=[v for v in records if v['blocks']]
   last=dict(at=datetime.now().astimezone().isoformat(),records=records,blocking=blocked,query_passed=True)
  except (OSError,subprocess.TimeoutExpired,ET.ParseError,ValueError)as e:
   blocked=[dict(pid=None,name='GPU diagnostic unavailable',type='unknown',blocks=True)]
   last=dict(query_passed=False,error=str(e),blocking=blocked)
  write(PATCH/'state/gpu_preflight.json',last)
  if not blocked:
   clear+=1
   if clear>=2:return last
  else:clear=0
  if time.monotonic()>=deadline:
   if not last['query_passed']:raise ValueError(last['error']+' Details saved in state/gpu_preflight.json.')
   names='; '.join('PID '+str(v['pid'])+' '+v['name']+' ['+v['type']+']'for v in blocked)
   raise ValueError('GPU compute process still present: '+names+'. Nothing was stopped. Details: state/gpu_preflight.json.')
  if blocked and last['query_passed']:print('Waiting for GPU release: '+'; '.join(str(v['pid'])+' '+v['name']for v in blocked),flush=True)
  time.sleep(2)

def calculate(m,folder,options,installed,mask):
 from common import now,write as atomic_write
 from transfer_controller import run
 from transfer_native import saved_header,prepare_history
 from analysis import analyze
 from cycle_policy import accepted_cycles
 from transfer_runtime import redact,free_memory
 source=PATCH/'seed/checkpoint.sim';plan=m['plan'];source_step,source_time,scenes=saved_header(source)
 if (source_step!=m['checkpoint_step'] or abs(source_time-m['time_s'])>1e-7 or scenes!=30):raise ValueError('Checkpoint native time or scene count differs.')
 folder.mkdir(parents=True,exist_ok=False)
 for name in ('wave_setup_audit.json','stopping_policy.json','native_C01_rho_readback.json','wave_density_audit.json'):
  shutil.copy2(PATCH/'seed'/name,folder/name)
 write(folder/'native_plan.json',plan)
 write(folder/'source_identity.json',dict(path=str(source),sha256=m['checkpoint_sha256'],original_preserved=True))
 kw=dict(executable=installed['executable'],options=options,mask=mask,budget=129600,redact=redact,free_memory=free_memory,watch_progress=True)
 filename='wake_'+uuid.uuid4().hex[:16]+'.simh'
 run(folder,source,PATCH/'engine/NwarNativeResume.java',env={
  'NWAR_NATIVE_RESUME_OUT':str(folder),'NWAR_NATIVE_RESUME_TIME':str(source_time),'NWAR_NATIVE_RESUME_TARGET':str(plan['target_s']),
  'NWAR_NATIVE_RESUME_DT':str(plan['dt_s']),'NWAR_NATIVE_RESUME_STRIDE':str(plan['wake_stride']),
  'NWAR_NATIVE_RESUME_START':str(math.ceil(plan['wake_start_s']/plan['dt_s'])),'NWAR_NATIVE_RESUME_WAKE':filename},phase='W04k_zero_step_prepare',**kw)
 proof=read(folder/'native_resume_prepared.json');prepared=folder/'native_ready.sim'
 if proof.get('passed')is not True or proof.get('steps_advanced')!=0 or saved_header(prepared)!=(source_step,source_time,30):raise ValueError('Zero-step preparation failed.')
 begin=m['initial_step'];dt=plan['dt_s'];target=begin+round((plan['target_s']-plan['start_s'])/dt)
 def csv_export(directory,step):
  times={k:plan['start_s']+(k-begin)*dt for k in range(begin+1,step+1)}
  prepare_history(folder,directory,times,begin,plan)
 csv_export(folder/'seed_monitors',source_step)
 solve=folder/'native_solve';solve.mkdir();reason=None
 try:
  run(solve,prepared,PATCH/'engine/NwarNativeResume.java',env={},native_batch=True,phase='W04k_native_solve',status_dir=folder,
      native_initial_step=source_step,native_initial_time=source_time,native_dt=dt,native_target_step=target,**kw)
 except AssertionError:
  reason=read(solve/'stage_result.json').get('controller_reason')
  if reason not in('user_stop','wall_budget'):raise
 stage=read(solve/'stage_result.json')
 if stage.get('source_unchanged')is not True or stage.get('ownership')!='windows_job_closed':raise ValueError('Native solver ownership or source changed.')
 candidates=[]
 for p in solve.glob('*.sim'):
  if p.name=='input.sim'or p.stat().st_size<400_000_000:continue
  step,t,count=saved_header(p)
  if count==30 and source_step<step<=target and abs(t-(plan['start_s']+(step-begin)*dt))<1e-7:candidates.append((step,p))
 if not candidates:raise ValueError('No new complete saved checkpoint; original seed preserved.')
 step,checkpoint=max(candidates,key=lambda v:(v[0],v[1].stat().st_mtime_ns));end=plan['start_s']+(step-begin)*dt
 if not reason and step!=target:raise ValueError('Native solver stopped before the target. HOLD; no automatic retry.')
 # Pause requests stay recorded, but must not interrupt the read-only final export.
 export=folder/'native_export';export.mkdir();exported=folder/'native_monitors'
 export_kwargs=dict(kw,watch_progress=False)
 import transfer_controller
 original_stop=transfer_controller._stop_reason
 def export_stop(path,started,budget,mem):
  from resource_limits import memory_reason
  return memory_reason(mem)
 transfer_controller._stop_reason=export_stop
 try:run(export,checkpoint,PATCH/'engine/NwarNativeExport.java',env={'NWAR_NATIVE_EXPORT':str(exported)},phase='W04k_saved_monitor_export',**export_kwargs)
 finally:transfer_controller._stop_reason=original_stop
 if abs(float((exported/'final_time.txt').read_text())-end)>1e-7:raise ValueError('Native export time differs.')
 csv_export(exported,step)
 review,_,_=analyze(dict(id='W04k',H=.25,L=15.),[folder]);write(folder/'independent_cycle_review.json',review)
 if not review['health']['ok']:raise ValueError('Saved numerical history is unhealthy. HOLD; no automatic retry.')
 final=folder/'wave_pilot_final.sim';shutil.copy2(checkpoint,final);digest=sha(final)
 write(folder/'latest_checkpoint.json',dict(file=final.name,step=step-begin,time_s=end,healthy=True,sha256=digest))
 write(folder/'final_integrity.json',dict(sha256=digest,bytes=final.stat().st_size,time_s=end,source_unchanged=sha(source)==m['checkpoint_sha256']))
 wake=folder/filename
 if wake.is_file():write(folder/'field_history_segments.json',dict(segments=[dict(file=filename,start_s=source_time,valid_through_s=end)],prior_segments=m['archived_field_history']))
 passed=step==target and accepted_cycles(review['cycles'])
 state='five_cycles_recorded'if passed else'paused_saved'if reason else'needs_review'
 write(folder/'completed.json',dict(status=state,time_s=end,steps=step-begin,complete_cycles=review['cycles']['count'],cycles_accepted=passed,project_accepted=False))
 return state,review

def run_main():
 sys.path.insert(0,str(PATCH/'engine'))
 from common import birth,now
 from transfer_runtime import processes,free_memory,launch_settings,redact
 owner=read(PATCH/'state/owner.json')
 if owner.get('birth')and birth(owner.get('pid'))==owner['birth']:
  print('W04k is already open: '+owner['url'],flush=True);webbrowser.open(owner['url']);return 0
 global _INSTANCE
 (PATCH/'state').mkdir(exist_ok=True)
 _INSTANCE=(PATCH/'state/instance.lock').open('a+b');_INSTANCE.seek(0);_INSTANCE.write(b'1');_INSTANCE.flush();_INSTANCE.seek(0)
 try:msvcrt.locking(_INSTANCE.fileno(),msvcrt.LK_NBLCK,1)
 except OSError:raise ValueError('W04k is already starting. Wait for its verification and panel; no duplicate is started.')
 if (PATCH/'state/run_state.json').is_file():raise ValueError('This transfer was already attempted. Its saved state is preserved; do not launch a duplicate.')
 m=verify_payload()
 if any(n.lower().startswith(('starccm+','star-ccm+','mpiexec'))for _,n in processes().values()):raise ValueError('Another STAR/MPI run is still active. Save it and let it exit first.')
 gpu_preflight()
 host=Path(os.environ['NWAR_PACKAGE_ROOT']);work=Path(os.environ['NWAR_WORKSPACE'])
 if any(p.exists()for p in(host/'STOP_ALL',work/'data/STOP',work/'data/STOP_ALL')):raise ValueError('A global manual GLHF STOP is present; preserved.')
 if free_memory()<8*2**30:raise ValueError('At least 8 GiB free RAM is required.')
 if shutil.disk_usage(PATCH).free<25*2**30:raise ValueError('At least 25 GiB free patch-drive storage is required.')
 installed,options=launch_settings()
 if (PATCH/'STOP').exists()or(PATCH/'state/PAUSE').exists():raise ValueError('A manual W04k stop/pause marker is present; preserved.')
 state=dict(state='Preparing saved fields',time_s=m['time_s'],source_time_s=m['time_s'],target_s=m['plan']['target_s'])
 folder=PATCH/'work/W04k'
 def current():
  result=dict(state);mon=read(folder/'monitor.json');result.update({k:mon[k]for k in('time_s','phase','reason')if k in mon})
  if state['state']not in('HOLD','five_cycles_recorded','paused_saved','needs_review'):result['message']=mon.get('phase','Preparing saved state; no simulation steps are advanced.')
  return result
 server,url=serve(current,uuid.uuid4().hex);write(PATCH/'state/owner.json',dict(pid=os.getpid(),birth=birth(os.getpid()),url=url,at=now()))
 write(PATCH/'state/run_state.json',dict(state,at=now(),url=url));webbrowser.open(url)
 print('W04k dashboard: '+url+'\nNative continuation from '+format(m['time_s'],'.4f')+' s. Check fresh physical-time samples.',flush=True)
 try:
  state['state']='Native continuation';status,review=calculate(m,folder,options,installed,1<<max(0,min(2,(os.cpu_count()or 1)-1)))
  state.update(state=status,time_s=review['time_s'],cycles=review['cycles']['count'],cycles_accepted=read(folder/'completed.json')['cycles_accepted'],message='Saved result retained. No further wave is started.')
 except Exception as e:
  state.update(state='HOLD',message=redact(str(e)));write(PATCH/'state/error.json',dict(state,at=now()));print('HOLD: '+state['message'],flush=True)
 finally:write(PATCH/'state/run_state.json',dict(state,at=now()))
 print(state['state']+'. Saved files: '+str(folder)+'\nThe GPU solver has exited. Close this console when finished.',flush=True)
 while True:time.sleep(2) # Only the lightweight read-only panel remains after solve.

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--gpu-diagnostics',action='store_true');args=parser.parse_args()
 try:
  if args.gpu_diagnostics:
   sys.path.insert(0,str(PATCH/'engine'));print(json.dumps(gpu_preflight(),indent=2));raise SystemExit(0)
  raise SystemExit(run_main()if args.run else start())
 except Exception as e:print('HOLD: '+str(e),flush=True);raise SystemExit(1)
