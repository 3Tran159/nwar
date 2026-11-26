"""Serial owned solver worker with bounded recovery for W04b transport failures."""
from common import *
import subprocess,shutil,traceback,argparse,re
from cpu_coexistence import ActiveSolverError
sys.path.insert(0,str(ROOT))
import owned_experiment_runtime_20261031 as rt
from resource_limits import owned_resource_problem,minimum_free_ram_gib
_original_resource_problem=rt.resource_problem
rt.resource_problem=lambda:owned_resource_problem(_original_resource_problem,rt.guard.free_memory)
MACRO=HERE/'NwarWave.java'
OWNER=DATA/'worker.lock'
WAVE_CPU_MASK=sum(1 << cpu for cpu in (0,1,10,11,4,5,6,7,8,9,14,15))
W04B_CPU_MASK=1 << 11  # Windows CPU set 11 is an unparked P core on this host.
W04B_STAR_2606=Path('E:/Program Files/Siemens/21.04.009-R8/STAR-CCM+21.04.009-R8/star/lib/win64/clang20.1vc14.2-r8/lib/starccm+.exe')
W04B_ISOLATED_PORT=48743
W04B_MAX_RETRIES_WITHOUT_CHECKPOINT=3
def native():
 return [(pid,name) for pid,(_,name) in rt.guard.processes().items() if name.lower().startswith(('starccm+','star-ccm+','mpiexec'))]

def resource_processes(spec,launch=False):
 if spec.get('resource_scope')=='owned_gpu_cpu11':
  from cpu_coexistence import snapshot
  processes=snapshot()
  p=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
  if p.returncode:raise ActiveSolverError('GPU compute inventory is unavailable.')
  gpu={int(line.strip()) for line in p.stdout.splitlines() if line.strip().isdigit()}
  native=[r for r in processes.values() if r['name'].lower().startswith(('starccm+','star-ccm+','mpiexec'))]
  if any(r['gpu_flag'] or r['pid'] in gpu for r in native):raise ActiveSolverError('A GPU solver is still active.')
 elif spec.get('short_wave_diagnostic'):
  p=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],
                   capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
  if p.returncode:raise ActiveSolverError('GPU compute inventory is unavailable.')
  if any(line.strip().isdigit() for line in p.stdout.splitlines()):
   raise ActiveSolverError('A GPU compute process is still active.')
 elif spec.get('allow_approved_cpu'):
  from cpu_coexistence import check
  check(launch=launch)
 elif native():raise ValueError('Another STAR/MPI solver is active.')

def reservation_paths(spec):
 if spec.get('short_wave_diagnostic'):
  return SOLVER_LOCKS+[p for p in OTHER_LOCKS if p.name!='auxiliary.lock']
 return SOLVER_LOCKS+OTHER_LOCKS

def short_wave_solver_alive(folder):
 log=folder/'star.log'
 if not log.exists():return False
 launch=read(folder/'launch_audit.json')
 client=read(folder/'process.json').get('pid')
 if not launch.get('at') or not client:return True
 stage=read(folder/'stage_result.json')
 if not stage.get('at'):return True
 def filetime(iso):return int(datetime.fromisoformat(iso).timestamp()*10_000_000)+116444736000000000
 started,finished=filetime(launch['at']),filetime(stage['at'])
 with log.open(encoding='utf-8') as stream:header=stream.read(65536)
 ranks={int(pid) for pid in re.findall(r'(?m)^(?:Serial process|Process rank \d+ \S+)\s+(\d+)\s*$',header)}
 tree=rt.guard.processes()
 # Process IDs in the launch record are scoped by creation time and image name.
 for pid,(parent,name) in tree.items():
  if pid in ranks:
   if not name.lower().startswith(('star-ccm+','starccm+')):continue
  elif pid!=client and parent!=client:continue
  elif not name.lower().startswith(('star-ccm+','starccm+','mpiexec','hydra','python','cmd')):continue
  created=birth(pid)
  if created and started<=int(created)<=finished:return True
 return False

def queue_wait_reason(spec):
 try:resource_processes(spec)
 except (ValueError,RuntimeError) as exc:return rt.guard.redact(str(exc))
 for path in reservation_paths(spec):
  if path.exists():return 'Solver reservation present: '+path.name
 try:problem=rt.resource_problem()
 except OSError:return 'Could not check available RAM or disk space.'
 if problem=='disk_guard':return 'Disk reserve below 15 GiB on C: or 25 GiB on the simulation drive.'
 if problem and problem.startswith('RAM_below'):return 'Less than '+format(minimum_free_ram_gib(),'g')+' GiB of free RAM.'
 return problem

def pause_after_limit(j):
 """Only an exclusively created automatic marker may later be auto-cleared."""
 marker=DATA/'PAUSE'
 try:
  with marker.open('x',encoding='utf8') as f:f.write('')
 except FileExistsError:return
 stat=marker.stat()
 write(Path(j['folder'])/'automatic_pause.json',dict(reason='wall_budget',job_id=j['id'],at=now(),marker=str(marker),mtime_ns=stat.st_mtime_ns,sha256=sha(marker)))
def preflight(j):
 spec=j['spec']
 if spec.get('imported_native_continuation'):
  from imported_native_resume import verify
  verify(spec)
 if spec.get('wave_kind')=='bichromatic':
  from advance_wave_queue import choose_case
  plan=read(HERE/'campaign_followup.json')
  from bichromatic import approved_manual_resume,approved_manual_start,followup
  manual=approved_manual_start(j,plan) or approved_manual_resume(j,plan)
  if not manual and j.get('request_key')!=plan['id']+'_W08_bichromatic_20261103':raise ValueError('W08 requires an approved diagnostic launch or a verified continuation.')
  entries=[v for v in jobs() if v['spec'].get('campaign_id')==plan['id']]
  def proof(v):return read(DATA/'validations'/(v['id']+'.json')),read(Path(v['folder'])/'independent_cycle_review.json')
  if choose_case(['W04','W06'],entries,proof)['status']!='complete':raise ValueError('W08 requires accepted W04 and W06.')
  # Keep the pinned request_key check above and recheck the time budget at launch.
  if not manual:
   if followup(plan,budget_only=True)['status']!='ready':raise ValueError('Insufficient verified overnight time for W08.')
 if type(spec.get('mpi_processes',1))!=int or spec.get('mpi_processes',1) not in (1,2):raise ValueError('Invalid GPU process count.')
 if spec.get('short_wave_diagnostic') and spec.get('mpi_processes',1)!=1:
  raise ValueError('W04b requires one solver process and one P core.')
 if spec.get('checkpoint_recovery'):
  from checkpoint_recovery import verify
  recovered=verify(spec['checkpoint_recovery'],parent_id=spec.get('parent_id'))
  if Path(spec['source']).resolve()!=Path(recovered['checkpoint']).resolve() or spec['source_sha']!=recovered['checkpoint_sha256'] or abs(spec['source_time']-recovered['time_s'])>1e-7:raise ValueError('Recovery request differs from verified checkpoint.')
 if spec.get('native_recovery'):
  from native_production import recovery_checkpoint,surface_rule_checkpoint
  receipt=spec['native_recovery'];parent=job(receipt['parent_id'])
  verify=surface_rule_checkpoint if receipt.get('surface_rule') else recovery_checkpoint
  if (j['case_id']!=parent['case_id'] or not spec.get('native_production') or spec['mode']!='resume'
      or receipt!=verify(parent) or spec['source']!=receipt['checkpoint']
      or spec['source_sha']!=receipt['sha256'] or spec['source_time']!=receipt['time_s']):
   raise ValueError('The native continuation differs from its verified checkpoint.')
 if any(p.exists() for p in STOPS):raise ValueError('External STOP: '+str(next(p for p in STOPS if p.exists())))
 if (DATA/'PAUSE').exists():raise ValueError('The queue is paused.')
 resource_processes(spec,launch=True)
 if any(p.exists() for p in reservation_paths(spec)):raise ValueError('Resources are reserved by another campaign.')
 problem=rt.resource_problem()
 if problem:raise ValueError(problem)
 review=read(CALM/'C01_final_acceptance_20261101.json')
 if review.get('project_primary_settled') is not True or sha(SOURCE)!=SOURCE_SHA:raise ValueError('Invalid C01 reference.')
 from calm_reference import reference_for
 if not reference_for(j,verify=True).get('project_primary_settled'):raise ValueError('Run reference has not been accepted.')
 cr=read(HERE/'compile_receipt.json')
 if cr.get('ok') is not True or cr.get('macro_sha256')!=sha(MACRO):raise ValueError('The macro differs from the verified build.')
 src=Path(spec['source'])
 if sha(src)!=spec['source_sha']:raise ValueError('The checkpoint changed after the request.')
 if spec.get('parent_folder') in map(str,EXISTING.values()):
  folder=Path(spec['parent_folder'])
  old=read(NIGHT/'W01_four_cycle_review.json') if j['case_id']=='W01' else read(folder/'four_cycle_independent_review.json')
  if old.get('final_sim_SHA256')!=spec['source_sha'] or not old.get('saved_and_valid'):raise ValueError('Source differs from the accepted checkpoint.')
 if spec.get('mesh_profile'):
  from wave_profiles import verify_spec
  verify_spec(j['case_id'],spec)
 elif not (.25<=spec['H']<=.5 and 19<=spec['L']<=30 and spec['dt']==.0004):raise ValueError('Parameters are outside the reviewed range.')
 p=subprocess.run(['nvidia-smi','--query-gpu=memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise ValueError('Could not read GPU status.')
 free,load,temp=[float(x.strip()) for x in p.stdout.splitlines()[0].split(',')]
 if free<4000 or load>=45 or temp>=85:raise ValueError('GPU busy or insufficient free memory.')
 return dict(at=now(),source=str(src),source_sha256=spec['source_sha'],C01_sha256=SOURCE_SHA,macro_sha256=sha(MACRO),gpu_free_MiB=free,gpu_percent=load,gpu_temperature_C=temp,dt_s=.0004,inner=10,case=j['case_id'],H_m=spec['H'],lambda_m=spec['L'],no_reinitialize=True)
def owned_lock(path,token,role):
 with path.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid(),birth=birth(os.getpid()),token=token,role=role,at=now()),f)

def release_w04b_rank(folder):
 if not short_wave_solver_alive(folder):return
 with (folder/'star.log').open(encoding='utf-8') as stream:
  match=re.search(r'(?m)^Serial process (\d+)\s*$',stream.read(65536))
 if not match:raise ValueError('W04b rank could not be identified.')
 pid=int(match[1]);created=birth(pid)
 if not created:raise ValueError('W04b client is still active.')
 command=(f'Get-NetTCPConnection -LocalPort {W04B_ISOLATED_PORT} -State Listen '
          '-ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess')
 listener=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,
                         timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
 if set(listener.stdout.split())!={str(pid)} or birth(pid)!=created:
  raise ValueError('W04b rank no longer owns its assigned STAR listener.')
 tree=rt.guard.processes()
 if tree.get(pid,(None,''))[1].lower()!='star-ccm+.exe':raise ValueError('Unexpected W04b rank image.')
 # Verify that the orphan is the same native rank from this run before terminating it.
 launch=read(folder/'launch_audit.json');stage=read(folder/'stage_result.json')
 def filetime(iso):return int(datetime.fromisoformat(iso).timestamp()*10_000_000)+116444736000000000
 started,finished=filetime(launch['at']),filetime(stage['at'])
 if not started<=int(created)<=finished:raise ValueError('W04b rank is outside the original launch window.')
 owned={pid:created};parent=tree[pid][0]
 while parent in tree and tree[parent][1].lower() in ('python.exe','cmd.exe','starccm+.exe'):
  parent_birth=birth(parent)
  if not parent_birth or not started<=int(parent_birth)<int(owned[next(reversed(owned))]):break
  owned[parent]=parent_birth;parent=tree[parent][0]
 kernel=ctypes.windll.kernel32
 kernel.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
 kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
 for owned_pid,identity in owned.items():
  if birth(owned_pid)!=identity:continue
  handle=kernel.OpenProcess(0x101001,False,owned_pid)
  if not handle:raise OSError('Cannot open the failed W04b process.')
  try:
   times=[ctypes.c_ulonglong() for _ in range(4)]
   if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in times)) or str(times[0].value)!=identity:
    raise ValueError('W04b process identity changed during cleanup.')
   kernel.TerminateProcess(handle,1)
   if kernel.WaitForSingleObject(handle,5000)!=0:raise OSError('W04b process did not exit.')
  finally:kernel.CloseHandle(handle)
 write(folder/'owned_solver_cleanup.json',dict(at=now(),dead_owned_process_births=owned,reason='transport_reset'))

def retry_w04b(j):
 from checkpoint_recovery import auto_authorization,prepare
 id=j['id'];spec=j['spec'];folder=Path(j['folder'])
 ck=read(folder/'latest_checkpoint.json')
 advanced=ck.get('healthy') is True and ck.get('step',0)>0 and ck.get('time_s',0)>spec['source_time']
 count=0 if advanced else spec.get('transport_retries_without_checkpoint',0)+1
 if count>W04B_MAX_RETRIES_WITHOUT_CHECKPOINT:raise ValueError('Automatic W04b retry limit reached without a newer checkpoint.')
 receipt=spec.get('checkpoint_recovery');mode=spec['mode'];parent_id=spec.get('parent_id')
 if advanced:
  checkpoint=(folder/ck['file']).resolve()
  if checkpoint.parent!=folder.resolve() or not checkpoint.name.startswith('checkpoint_t'):
   raise ValueError('Unexpected W04b checkpoint location.')
  auth=auto_authorization(id);auth.parent.mkdir(parents=True,exist_ok=True)
  record=dict(parent_id=id,source_time_s=ck['time_s'],checkpoint_sha256=sha(checkpoint),
              error=read(folder/'macro_error.json').get('error'))
  if auth.exists() and read(auth)!=record:raise ValueError('W04b recovery authorization changed.')
  if not auth.exists():write(auth,record)
  receipt=prepare(job(id));mode='resume';parent_id=id
 with connection() as conn:
  conn.execute('BEGIN IMMEDIATE')
  retry=enqueue('W04b',mode,extra_cycles=spec['extra_cycles'],parent_id=parent_id,
                request_key='w04b_transport_retry_'+id,smoke=spec.get('smoke',0),conn=conn,
                recovery_receipt=receipt,mpi_processes=1)
  new=json.loads(conn.execute('SELECT spec FROM jobs WHERE id=?',(retry,)).fetchone()[0])
  if not advanced and any(new[k]!=spec[k] for k in ('source','source_sha','source_time')):
   raise ValueError('W04b retry would change the pinned source.')
  new.update(retry_star_release='2606',retry_serial_gpu=True,retry_of=id,
             transport_retries_without_checkpoint=count)
  new.update({key:spec[key] for key in ('scan_id','scan_order','w04b_loopback') if key in spec})
  conn.execute('UPDATE jobs SET spec=? WHERE id=?',(json.dumps(new),retry))
 event('transport_retry_queued',id=id,retry_id=retry,source_time=new['source_time'])
 return retry

def process(j):
 id=j['id'];spec=j['spec'];folder=Path(j['folder']);locks=[];token=uuid.uuid4().hex
 deferred=False;recover_transport=False;retry=None
 night=bool(spec.get('overnight_queue'))
 with connection() as c:
  c.execute('BEGIN IMMEDIATE')
  claimed=c.execute("UPDATE jobs SET status='preflight',updated=?,controller_pid=?,controller_birth=?,message=? WHERE id=? AND status='queued'",(now(),os.getpid(),birth(os.getpid()),'Checking source, compilation and resources',id)).rowcount
 if not claimed:return
 try:
  pre=preflight(j)
  macro=MACRO
  if spec.get('imported_native_continuation'):
   from imported_native_resume import verify
   verify(spec)
   macro=Path(spec['imported_native_continuation']['macro'])
  if spec.get('wave_kind')=='bichromatic':
   proof=read(HERE/'bichromatic_w08.json');macro=HERE/'NwarBichromatic.java'
   if not proof.get('compiled') or sha(macro)!=proof.get('macro_sha256'):raise ValueError('Bichromatic generator differs from its verified build.')
  for p in SOLVER_LOCKS:owned_lock(p,token,'nwar_wave');locks.append(p)
  resource_processes(spec,launch=True)
  if (DATA/'PAUSE').exists():
   update(id,status='queued',message='Queue paused before solver start.');return
  folder.mkdir(parents=True,exist_ok=False)
  mask=W04B_CPU_MASK if spec.get('short_wave_diagnostic') or night else WAVE_CPU_MASK
  star=W04B_STAR_2606 if j['case_id']=='W04b' and spec.get('retry_star_release')=='2606' else rt.guard.STAR
  if j['case_id']=='W04f' and spec.get('imported_native_continuation'):
   star=W04B_STAR_2606
  if not star.is_file():raise ValueError('The selected STAR installation is missing.')
  intel_mpi=j['case_id']=='W04b' and spec.get('retry_intel_mpi') is True
  serial=j['case_id']=='W04b' and spec.get('retry_serial_gpu') is True
  loopback=serial and spec.get('w04b_loopback') is True
  launch_audit=dict(pre,cpu_affinity_mask=mask,star_executable=str(star))
  if intel_mpi:
   launch_audit.update(mpi='intel',server_port=W04B_ISOLATED_PORT,server_port_range=1)
  if serial:
   launch_audit.update(mpi='none',server_port=W04B_ISOLATED_PORT,server_port_range=1)
  if loopback:
   launch_audit['batch_client_host']='127.0.0.1'
  write(folder/'request.json',spec);write(folder/'launch_audit.json',launch_audit)
  if spec['mode']!='fresh' and not spec.get('native_recovery'):
   from analysis import merge_segments,segment_chain,numeric_rows
   chain=segment_chain(job(id))[:-1]
   prior,evidence=merge_segments(chain)
   if abs(float(prior['time_s'][-1])-spec['source_time'])>1e-7:raise ValueError('History endpoint does not match the checkpoint time.')
   with (folder/'prior_history.csv').open('w',newline='',encoding='utf8') as f:
    w=csv.writer(f);w.writerow(prior);w.writerows(zip(*prior.values()))
   last={}
   with (folder/'prior_gauges.csv').open('w',newline='',encoding='utf8') as f:
    w=csv.writer(f);w.writerow(['time_s','x_m','eta_actual_m'])
    for source_folder in chain:
     gauges=numeric_rows(source_folder/'gauges.csv')
     if not gauges:continue
     for t,x,eta in zip(gauges['time_s'],gauges['x_m'],gauges['eta_actual_m']):
      if t>last.get(x,-1e30)+1e-8 and t<=spec['source_time']+1e-8:w.writerow([t,x,eta]);last[x]=t
   write(folder/'prior_history_provenance.json',evidence)
  env={'NTNU_M13_WAVE_OUT':str(folder),'NTNU_M13_WAVE_DT':'.0004','NTNU_M13_WAVE_STEPS':'24000','NTNU_M13_WAVE_INNER':'10','NTNU_M13_WAVE_BUDGET':str(spec['budget_s']-60),
       'NWAR_MPI_PROCESSES':str(spec.get('mpi_processes',1)),
       'NWAR_H':str(spec['H']),'NWAR_L':str(spec['L']),'NWAR_RESUME':'0' if spec['mode']=='fresh' else '1','NWAR_ALLOW_EARLY':'0','NWAR_SOURCE_TIME':str(spec['source_time']),'NWAR_EXTRA_STEPS':str(spec.get('extra_steps',0)),'NWAR_SMOKE_STEPS':str(spec.get('smoke',0)),'NWAR_MAX_CYCLES':'5'}
  update(id,status='running',message='Loading and calculating in STAR-CCM+')
  profile=spec.get('mesh_profile')
  if profile:env.update(NWAR_PROFILE=profile['id'],NWAR_CASE=j['case_id'],NWAR_WAVE_ORIGIN=str(profile['wave_origin_s']))
  if night:env['NWAR_NIGHT_CHECKPOINTS']='1'
  event('solver_start',id=id,case=j['case_id'],mode=spec['mode'])
  original_star=rt.guard.STAR
  original_options=rt.guard.saved_options
  def isolated_options(workers):
   options=original_options(workers)
   if any(flag in options for flag in ('-host','-port','-on','-machinefile','-assignport','-portrange','-hostregexpr','-mpi')):
    raise ValueError('Saved STAR options conflict with the isolated W04b launch.')
   if serial:
    # Keep -cpubind off so STAR does not override the inherited Windows CPU mask.
    index=options.index('-np')
    del options[index:index+2]
   else:
    options.extend(('-mpi','intel'))
   return [*options,'-assignport',str(W04B_ISOLATED_PORT),'-portrange','1']
  try:
   if spec.get('native_production'):
    from native_production import run_case
    rt.guard.STAR=star
    native_options=original_options(1)
    if j['case_id'] in ('W04h','W04f','W04k') and spec.get('native_mpi')=='intel':
     if '-mpi' in native_options:raise ValueError('Conflicting saved MPI options.')
     native_options.extend(('-mpi','intel'))
     write(folder/'native_transport.json',dict(mpi='intel',workers=1,reason='Isolate the owned GPU wave from independent MS MPI CPU experiments.'))
    run_case(folder,Path(spec['source']),macro,env,executable=star,options=native_options,
             mask=mask,budget=spec['budget_s'],redact=rt.guard.redact,free_memory=rt.guard.free_memory,
             recovery=spec.get('native_recovery'))
   elif serial or night:
    from w04b_controller import run
    options=isolated_options(1) if serial else original_options(1)
    run(folder,Path(spec['source']),macro,executable=star,options=options,env=env,
        mask=mask,budget=spec['budget_s'],redact=rt.guard.redact,free_memory=rt.guard.free_memory,
        loopback_port=W04B_ISOLATED_PORT if loopback else None,phase='NWAR_'+j['case_id'],watch_progress=night)
   else:
    rt.guard.STAR=star
    if intel_mpi:rt.guard.saved_options=isolated_options
    rt.stage(folder,Path(spec['source']),macro,env=env,workers=spec.get('mpi_processes',1),gpu=True,mask=mask,budget_s=spec['budget_s'],protect_main=False,phase='NWAR_'+j['case_id'])
  except AssertionError:
   # The existing runtime raises also on requested, safely saved pauses/budgets.
   stage=read(folder/'stage_result.json');done=read(folder/'completed.json')
   if not (stage.get('exit_code')==0 and stage.get('source_unchanged') is True and done.get('status') in ('paused_saved','wall_budget')):raise
  finally:
   rt.guard.STAR=original_star
   rt.guard.saved_options=original_options
  stage=read(folder/'stage_result.json');done=read(folder/'completed.json')
  if sha(Path(spec['source']))!=spec['source_sha']:raise ValueError('Source identity changed after calculation.')
  native_complete=False
  if spec.get('native_production'):
   from native_production import native_completion_verified
   native_complete=native_completion_verified(folder)
  if (stage.get('exit_code')!=0 and not native_complete) or not stage.get('source_unchanged') or read(folder/'macro_error.json'):raise ValueError('Solver failed; results preserved for diagnosis.')
  ck=folder/'wave_pilot_final.sim'
  if not ck.is_file() or ck.stat().st_size<400_000_000:raise ValueError('No complete final checkpoint.')
  write(folder/'final_integrity.json',dict(sha256=sha(ck),bytes=ck.stat().st_size,time_s=done['time_s'],source_unchanged=True))
  diagnostic=spec.get('wave_kind')=='bichromatic' and done['status']=='bichromatic_diagnostic_saved'
  if diagnostic:
   from analysis import analyze,segment_chain
   result,_,_=analyze(dict(spec,id=j['case_id']),segment_chain(job(id)))
   write(folder/'independent_cycle_review.json',result)
   if not result['health']['ok']:raise ValueError('Bichromatic diagnostic failed independent numerical health review.')
   state='completed';msg='Bichromatic diagnostic saved; numerical health verified.'
  elif done['status']=='paused_saved':state='paused';msg='Pause saved. Ready to resume.'
  elif done['status'] in ('five_cycles_repeated','five_cycles_recorded','four_cycles_repeated','requested_extension_saved','smoke_test_saved'):state='completed';msg='Result saved; preparing report.'
  else:state='needs_review';msg='Diagnostic limit reached; result saved for review.'
  update(id,status=state,message=msg)
  from validation import validate
  verification=validate(job(id))
  if not diagnostic and verification['run_verification']=='failed' and state=='completed':
   update(id,status='needs_review',message='Checklist detected a mismatch. Open run validation.')
   if not night:(DATA/'PAUSE').touch()
  if state in ('paused','needs_review'):
   if done['status']=='wall_budget':pause_after_limit(j)
   elif done['status']!='native_review':(DATA/'PAUSE').touch()
  if state=='completed' and not diagnostic and not spec.get('smoke'):
   from analysis import analyze,segment_chain
   result,_,_=analyze(dict(spec,id=j['case_id']),segment_chain(job(id)))
   write(folder/'independent_cycle_review.json',result)
   if not result['health']['ok'] or not __import__('cycle_policy').accepted_cycles(result['cycles']):
    update(id,status='needs_review',message='Result saved; independent verification of cycles 2–5 requires review.')
    if not night:(DATA/'PAUSE').touch()
 except ActiveSolverError as exc:
  # These resource checks run before creating the run folder or starting STAR.
  deferred=True
  update(id,status='queued',message='Waiting: '+str(exc))
  event('preflight_waiting_for_solver',id=id,reason=str(exc))
 except Exception as e:
  error=rt.guard.redact(str(e))[:900]
  update(id,status='failed',message=error);write(folder/'controller_failure.json',dict(at=now(),error=error))
  if j['case_id']=='W04b' and spec.get('retry_serial_gpu'):
   from checkpoint_recovery import transport_failure
   try:recover_transport=transport_failure(folder)
   except OSError:pass
  stage=read(folder/'stage_result.json')
  continue_night=(night and stage.get('ownership')=='windows_job_closed'
                  and stage.get('source_unchanged') is True
                  and (stage.get('exit_code')!=0 or spec.get('native_production') is True)
                  and stage.get('controller_reason') in (None,'night_progress_timeout')
                  and not any(p.exists() for p in STOPS+[DATA/'STOP',DATA/'PAUSE'])
                  and (not (folder/'STOP').exists() or stage.get('controller_reason')=='night_progress_timeout'))
  if continue_night:
   update(id,message='Night queue: failed segment preserved. Next verified case will run after resource release.')
   event('night_failed_case_skipped',id=id,case=j['case_id'])
  elif not recover_transport:(DATA/'PAUSE').touch()
  event('failed',id=id,error=error)
 finally:
  released=deferred
  if recover_transport and read(folder/'stage_result.json').get('ownership')!='windows_job_closed':
   try:release_w04b_rank(folder)
   except (ValueError,RuntimeError,OSError) as exc:
    recover_transport=False;(DATA/'PAUSE').touch()
    event('transport_recovery_hold',id=id,reason=str(exc))
  if not deferred:
   for _ in range(15):
    try:
     if read(folder/'stage_result.json').get('ownership')=='windows_job_closed':
      released=True
     elif spec.get('short_wave_diagnostic'):
      released=not short_wave_solver_alive(folder)
     else:
      resource_processes(spec);released=True
     if released:break
    except (ValueError,RuntimeError,OSError):pass
    time.sleep(1)
  if released:
   for p in reversed(locks):
    if read(p).get('token')==token:p.unlink()
  elif locks:
   (DATA/'PAUSE').touch()
   update(id,status='needs_attention',message='The solver process is still active. Queue stopped; resource locks preserved.')
  if released and recover_transport and not (DATA/'PAUSE').exists() and not any(p.exists() for p in STOPS):
   try:retry=retry_w04b(j)
   except Exception as exc:
    (DATA/'PAUSE').touch()
    reason=rt.guard.redact(str(exc))
    update(id,message='W04b automatic recovery on HOLD. '+reason)
    event('transport_recovery_hold',id=id,reason=reason)
  if deferred:
   time.sleep(15)
  elif retry:
   event('job_finished',id=id,status='failed')
  else:
   try:
    from report_selection import final_report_root
    completed=job(id)['status']=='completed'
    if final_report_root() is None or (completed and not spec.get('smoke')):
     import report
     report.build_report()
     if completed:update(id,message='Done: result, checklist and report saved.')
    elif completed:update(id,message='Done: result and checklist saved.')
   except Exception as e:
    event('report_failed',id=id,error=str(e));write(DATA/'report_error.json',dict(at=now(),error=str(e)))
   event('job_finished',id=id,status=job(id)['status'])
 return retry
def main(only=None,night=None):
 DATA.mkdir(parents=True,exist_ok=True)
 token=uuid.uuid4().hex
 if OWNER.exists():
  prev=read(OWNER)
  if prev.get('birth') and birth(prev.get('pid'))==prev['birth']:return
  if not prev.get('birth') or not isinstance(prev.get('pid'),int):return
  OWNER.rename(OWNER.with_name('worker.stale.'+uuid.uuid4().hex+'.json'))
 owned_lock(OWNER,token,'nwar_queue')
 try:
  # Crash recovery is explicit: no invisible restart or PID-only assumptions.
  for j in jobs():
   if j['status'] in ('running','preflight','pausing'):
    if j.get('controller_birth')!=birth(j.get('controller_pid')):
     update(j['id'],status='interrupted',message='Controller interrupted. Review the checkpoint before restarting.')
     (DATA/'PAUSE').touch()
  while not (DATA/'PAUSE').exists():
   pending=[j for j in jobs()[::-1] if j['status']=='queued' and (only is None or j['id']==only)
            and (night is None or j['spec'].get('overnight_queue')==night)]
   pending.sort(key=lambda j:j['spec']['overnight_order'] if night else j['spec'].get('mode')!='resume')
   if not pending:break
   reason=queue_wait_reason(pending[0]['spec'])
   if reason:
    message='Waiting: '+reason
    if pending[0]['message']!=message:update(pending[0]['id'],message=message)
    time.sleep(15);continue
   retry=process(pending[0])
   if only and retry:only=retry
 finally:
  if read(OWNER).get('token')==token:OWNER.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--smoke',choices=['fresh','extend']);p.add_argument('--parent');p.add_argument('--only');p.add_argument('--night');a=p.parse_args()
 if a.smoke:
  id=enqueue('W03',a.smoke,parent_id=a.parent,smoke=10)
  print(json.dumps(dict(job=id)),flush=True)
 main(a.only,a.night)
