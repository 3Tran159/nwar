from pathlib import Path
from datetime import datetime
import csv,hashlib,json,math,os,sqlite3,sys,uuid,ctypes,time,threading
from english import text as english_text
HERE=Path(__file__).resolve().parent
WORKSPACE=HERE.parent
ROOT=Path('E:/ntnu_mesh_optimization_20261030')
CLEAN=ROOT/'clean_c01_campaign_20261101'
NIGHT=CLEAN/'night_wave_queue_20261101'
DATA=ROOT/'nwar_automation_20261102'
RUNS=DATA/'runs'
CALM=CLEAN/'C01_warm_M13_steady_rho1000_air1p2_20261101'
SOURCE=CALM/'final.sim'
SOURCE_SHA='9af4857b948e0494088b5421f8ede100e66344fc2631cc00030406640d7cc295'
T0=4.699199999999548
PYTHON=Path('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
DEP=WORKSPACE/'mesh_study_20261030/.deps'
sys.path.insert(0,str(DEP))
os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
EXISTING={
 'W01':CLEAN/'W01_rho1000_air1p2_r2_20261101',
 'W02':NIGHT/'W02_rho1000_air1p2_from_C01_20261101',
 'W03':NIGHT/'W03_rho1000_air1p2_from_C01_20261101'}
F=Path('F:/ntnu/mesh_screening_20261028/force_stabilization_20261029')
STOPS=[ROOT/'STOP_ALL',CLEAN/'STOP',CLEAN/'STOP_ALL',ROOT/'wave_surface_only/STOP_ALL',F/'STOP_ALL']
SOLVER_LOCKS=[CLEAN/'campaign.lock',ROOT/'m13_wave_gpu.lock',ROOT/'M13_wave_direct_20261031/M13_wave_gpu_pilot.lock',ROOT/'wave_surface_only/wave_inlet.lock']
OTHER_LOCKS=[ROOT/'approved_wave_plan_20261101/h0_control.lock',ROOT/'approved_wave_plan_20261101/forcing_audit.lock',ROOT/'approved_wave_plan_20261101/sensitivity.lock',ROOT/'parallel_cpu_20261031/auxiliary.lock',ROOT/'wave_surface_only/wave_mesh_comparison.lock',NIGHT/'night_queue_owner.lock']
def now():return datetime.now().astimezone().isoformat()
def read(p,default=None):
 try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {} if default is None else default
def write(p,obj):
 p=Path(p);p.parent.mkdir(exist_ok=True,parents=True)
 tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');os.replace(tmp,p)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 try:
  with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 except OSError:return []
def number(v):
 try:
  f=float(v);return f if math.isfinite(f) else None
 except (ValueError,TypeError):return None
def tail(p):
 try:
  with Path(p).open('rb') as f:
   head=f.readline();pos=f.tell();f.seek(0,2);size=f.tell()
   f.seek(max(pos,size-120000))
   if size-120000>pos:f.readline()
   body=f.read().decode('utf8',errors='replace')
  import io
  return [r for r in csv.DictReader(io.StringIO(head.decode('utf-8-sig')+body)) if None not in r]
 except OSError:return []
def birth(pid):
 if type(pid)!=int or pid<=0:return None
 k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p
 k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
 k.CloseHandle.argtypes=[ctypes.c_void_p]
 k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
 k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
 h=k.OpenProcess(0x1000,False,pid)
 if not h:return None
 try:
  code=ctypes.c_ulong()
  if not k.GetExitCodeProcess(h,ctypes.byref(code)) or code.value!=259:return None
  a,b,c,d=(ctypes.c_ulonglong() for _ in range(4))
  if not k.GetProcessTimes(h,ctypes.byref(a),ctypes.byref(b),ctypes.byref(c),ctypes.byref(d)):return None
  return str(a.value)
 finally:k.CloseHandle(h)
def period(L):return L/(18+math.sqrt(9.81*L/(2*math.pi)*math.tanh(2*math.pi*24/L)))
def catalog():
 source=read(ROOT/'wave_campaign_20261101/campaign.json')
 overrides=read(HERE/'wave_plan.json').get('cases',{})
 out=[]
 for c in source.get('cases',[]):
  if c.get('kind')!='wave':continue
  id=c['id'];H=c['H_regular_m'];L=c['lambda_linear_m']
  override=overrides.get(id,{})
  H=override.get('H',H);L=override.get('L',L)
  ready=id in (*EXISTING,'W05')
  reason=None if ready else ('Mesh and wave-zone review required for H=1.5 m.' if id=='W04' else 'Domain and damping review required for λ≈47 m.' if id=='W06' else 'Wave-crest coverage review required for H=0.8 m.' if id=='W07' else 'New variant: settings and propagation review required; no completed run.')
  ready=override.get('ready',ready);reason=override.get('blocker',reason)
  if id in ('W04','W05','W06','W07'):
   from wave_profiles import approved_profile
   if approved_profile(id):ready=True;reason=None
  from calm_reference import local_reference_enabled
  out.append(dict(id=id,title=override.get('title',english_text(c['title'])),H=H,L=L,T=period(L),ready=ready,blocker=reason,existing=str(EXISTING[id]) if id in EXISTING and not local_reference_enabled() else None,scientific='diagnostic',dt=.0004))
 from custom_waves import catalog_entries
 from bichromatic import case as bichromatic_case
 diagnostic=bichromatic_case()
 out=[c for c in out if c['id']!='W08'] if diagnostic else out
 return out+catalog_entries()+([diagnostic] if diagnostic else [])
class ClosingConnection(sqlite3.Connection):
 def __exit__(self,*exc):
  try:return super().__exit__(*exc)
  finally:self.close()
_DATABASE_SETUP_LOCK=threading.RLock()
def connection():
 DATA.mkdir(parents=True,exist_ok=True);RUNS.mkdir(exist_ok=True)
 with _DATABASE_SETUP_LOCK:
  c=sqlite3.connect(DATA/'queue.sqlite',timeout=30,factory=ClosingConnection);c.row_factory=sqlite3.Row
  try:
   if c.execute('PRAGMA journal_mode').fetchone()[0].lower()!='wal':c.execute('PRAGMA journal_mode=WAL')
   c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created TEXT, updated TEXT, status TEXT, case_id TEXT, spec TEXT, folder TEXT, message TEXT, controller_pid INTEGER, controller_birth TEXT, request_key TEXT UNIQUE)')
   return c
  except BaseException:
   c.close();raise
def jobs():
 with connection() as c:return [dict(r, spec=json.loads(r['spec'])) for r in c.execute('SELECT * FROM jobs ORDER BY created DESC')]
def job(id):
 with connection() as c:
  r=c.execute('SELECT * FROM jobs WHERE id=?',(id,)).fetchone()
  if not r:raise ValueError('Run not found.')
  return dict(r,spec=json.loads(r['spec']))
def update(id,**kw):
 kw['updated']=now()
 with connection() as c:c.execute('UPDATE jobs SET '+','.join(k+'=?' for k in kw)+' WHERE id=?',[*kw.values(),id])
def event(kind,**kw):
 DATA.mkdir(exist_ok=True,parents=True)
 with (DATA/'events.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(at=now(),event=kind,**kw),ensure_ascii=False)+'\n')

def external_checkpoint(case_id):
 """Read completed external extensions; never adopt an active or partial save."""
 candidates=[]
 for folder in NIGHT.glob(case_id+'_resume*'):
  pre=read(folder/'resume_preflight.json');done=read(folder/'completed.json');stage=read(folder/'stage_result.json')
  setup=read(folder/'continuation_setup.json');src=folder/'wave_pilot_extended_final.sim'
  if pre.get('case')!=case_id or stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True:continue
  if done.get('status') not in ('one_additional_period_saved','user_stop_saved_partial','wall_budget_saved_partial') or done.get('global_initialization') is not False or read(folder/'macro_error.json'):continue
  if setup.get('no_initialize') is not True or not src.is_file() or src.stat().st_size<400_000_000:continue
  original=EXISTING.get(case_id)
  if not original or Path(pre.get('source','')).resolve()!=(original/'wave_pilot_final.sim').resolve():continue
  end=number(done.get('time_s'))
  if end is None:continue
  candidates.append(dict(folder=folder,source=src,time_s=end,segments=[original,folder],pre=pre,setup=setup))
 return max(candidates,key=lambda x:x['time_s']) if candidates else None
def enqueue(case_id,mode='fresh',extra_cycles=1,parent_id=None,request_key=None,smoke=0,conn=None,recovery_receipt=None,mpi_processes=None,release_scan_hold=False):
 choices={x['id']:x for x in catalog()}
 if case_id not in choices or not choices[case_id]['ready']:raise ValueError('This wave still requires mesh or wave-zone review.')
 if mode not in ('fresh','extend','resume'):raise ValueError('Unknown mode.')
 if type(extra_cycles)!=int or not 1<=extra_cycles<=4:raise ValueError('Select between 1 and 4 additional cycles.')
 external=None
 if recovery_receipt and (mode!='resume' or not parent_id):raise ValueError('Recovery requires an explicitly authorized parent.')
 if mpi_processes is not None and (type(mpi_processes)!=int or mpi_processes not in (1,2)):raise ValueError('Reviewed GPU process count is 1 or 2.')
 if mode=='extend' and parent_id is None:
  external=external_checkpoint(case_id)
  recent=[j for j in jobs() if j['case_id']==case_id and j['status'] in ('completed','needs_review') and not j['spec'].get('smoke') and (Path(j['folder'])/'final_integrity.json').exists()]
  recent.sort(key=lambda j:read(Path(j['folder'])/'completed.json').get('time_s',-1),reverse=True)
  if recent and (not external or read(Path(recent[0]['folder'])/'completed.json').get('time_s',-1)>=external['time_s']):parent_id=recent[0]['id'];external=None
 case=choices[case_id];spec=dict(case,mode=mode,stop_kind='four_cycles' if mode=='fresh' else 'steps',extra_cycles=extra_cycles,smoke=smoke,source=str(SOURCE),source_sha=SOURCE_SHA,source_time=T0,parent_id=None,parent_folder=None,budget_s=43200)
 if case_id=='W04b':spec.update(retry_star_release='2606',retry_serial_gpu=True)
 if mpi_processes is not None:spec['mpi_processes']=mpi_processes
 from calm_reference import local_reference_enabled,REFERENCE_ID
 if case_id in ('W04','W04c','W04e','W04g','W04h','W04k','W05','W06','W07','W08') or case.get('custom') or case.get('short_wave_diagnostic') or local_reference_enabled():
  from wave_profiles import approved_profile
  profile=approved_profile(case_id,verify=True)
  if not profile:raise ValueError('PRE W04 has not passed the calm/C01 gate.')
  spec.update(mesh_profile=profile,source=profile['source'],source_sha=profile['source_sha'],source_time=profile['source_time'])
  if profile.get('reference_id'):spec['reference_id']=profile['reference_id']
 plan=read(HERE/'campaign_followup.json')
 if case_id=='W08' and request_key==plan.get('id','')+'_W08_manual_20261105_W01_W06':
  spec['budget_s']=129600
 if plan.get('enabled'):
  spec['campaign_id']=plan['id']
  if plan.get('allow_approved_cpu'):spec['allow_approved_cpu']=True
 if case.get('custom'):
  if mpi_processes not in (None,1):raise ValueError('Custom waves use one GPU solver process.')
  spec.update(mpi_processes=1,campaign_id='custom-waves-original',wait_for_campaign_id=plan.get('id'))
 if mode!='fresh':
  if parent_id:
   p=job(parent_id)
   if p['case_id']!=case_id or (p['status'] not in ('completed','paused','needs_review') and not recovery_receipt):raise ValueError('The continuation source has not completed or saved.')
   if p['spec'].get('reference_id')!=spec.get('reference_id'):raise ValueError('Archived run belongs to a different calm reference. Start a fresh run in the active series.')
   if case.get('wave_kind')=='bichromatic' and p['spec'].get('components')!=spec.get('components'):
    raise ValueError('This checkpoint belongs to a different bichromatic combination.')
   if p['spec'].get('campaign_id'):spec['campaign_id']=p['spec']['campaign_id']
   folder=Path(p['folder']);ck=read(folder/'latest_checkpoint.json')
   if recovery_receipt:
    from checkpoint_recovery import verify
    recovery=verify(recovery_receipt,parent_id=parent_id)
    src=Path(recovery['checkpoint']);ck=dict(time_s=recovery['time_s'])
    spec['checkpoint_recovery']=str(Path(recovery_receipt).resolve())
   else:
    if not ck.get('healthy') or read(folder/'macro_error.json'):raise ValueError('No healthy checkpoint to resume.')
    src=folder/ck['file']
    integrity=read(folder/'final_integrity.json')
    if integrity.get('sha256')!=sha(src):raise ValueError('The checkpoint checksum does not match the integrity receipt.')
   if mpi_processes is None and p['spec'].get('mpi_processes'):spec['mpi_processes']=p['spec']['mpi_processes']
   spec['parent_id']=parent_id
  elif external:
   # Preserve the original and continuation as distinct evidence segments.
   from analysis import analyze
   original=EXISTING[case_id];pre=external['pre'];setup=external['setup']
   receipt=read(NIGHT/'W01_four_cycle_review.json') if case_id=='W01' else read(original/'four_cycle_independent_review.json')
   if pre.get('source_sha256')!=receipt.get('final_sim_SHA256') or sha(original/'wave_pilot_final.sim')!=pre.get('source_sha256'):raise ValueError('External continuation lineage is unverified.')
   if abs(setup.get('height_m',-1)-case['H'])>1e-8 or abs(setup.get('lambda_m',-1)-case['L'])>1e-8 or setup.get('step_dt_s')!=case['dt']:raise ValueError('The continuation has different wave conditions.')
   check,_,_=analyze(case,external['segments'])
   if not check['health']['ok'] or abs(check['time_s']-external['time_s'])>1e-7:raise ValueError('The continuation requires a history and numerical-health review.')
   folder=external['folder'];src=external['source'];ck={'time_s':external['time_s']}
   spec['parent_segments']=[str(p) for p in external['segments']]
   spec['external_source_receipt']=dict(source_sha256=pre['source_sha256'],completed_status=read(folder/'completed.json').get('status'),health_ok=True)
  else:
   if mode=='resume':raise ValueError('Resume requires a saved pause.')
   if case_id not in EXISTING:raise ValueError('This wave has no saved run to extend. Select a new run from C01.')
   folder=EXISTING[case_id];src=folder/'wave_pilot_final.sim';ck={'time_s':read(folder/'completed.json').get('time_s')}
  if not src.is_file() or ck.get('time_s') is None:raise ValueError('No completed checkpoint.')
  spec.update(source=str(src),source_sha=sha(src),source_time=ck['time_s'],parent_folder=str(folder))
  spec['extra_steps']=math.ceil(extra_cycles*case['T']/.0004)
  if mode=='resume' and parent_id:
   old=p['spec'];done=read(folder/'completed.json').get('steps',0)
   spec['stop_kind']=old.get('stop_kind','four_cycles' if old['mode']=='fresh' else 'steps')
   spec['smoke']=old.get('smoke',0)
   if case.get('wave_kind')=='bichromatic':
    spec.update(budget_s=old['budget_s'],extra_steps=0)
   elif old.get('smoke') and old.get('mode')=='fresh':spec['extra_steps']=max(1,old['smoke']-done)
   elif old.get('mode')!='fresh':spec['extra_steps']=max(1,old.get('extra_steps',spec['extra_steps'])-done)
   else:
    # Continue the remaining original diagnostic horizon, never launch another full 20-cycle budget.
    profile=spec.get('mesh_profile',{})
    end=profile.get('wave_origin_s',T0)+2*case['T']+profile.get('probe_distance_m',34.5)*case['T']/case['L']+20*case['T']
    spec['extra_steps']=max(1,math.ceil((end-spec['source_time'])/.0004))
 if smoke:
  if smoke not in (10,20):raise ValueError('Invalid smoke steps')
  spec['budget_s']=900
  if mode!='fresh':spec['extra_steps']=smoke
 from cycle_policy import POLICY_ID,TOTAL_CYCLES
 spec.update(cycle_policy_id=POLICY_ID,target_complete_cycles=TOTAL_CYCLES,discard_first_cycles=1,analysis_cycle_numbers=[2,3,4,5])
 if spec['stop_kind']=='four_cycles':spec['stop_kind']='five_cycles'
 if spec['stop_kind']=='five_cycles' and not spec.get('smoke'):spec['extra_steps']=0
 id=uuid.uuid4().hex[:16];folder=RUNS/(case_id+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+id[:6])
 key=request_key or uuid.uuid4().hex
 c=conn or connection()
 try:
  if conn is None:c.execute('BEGIN IMMEDIATE')
  previous=c.execute('SELECT id,case_id,status,folder FROM jobs WHERE request_key=?',(key,)).fetchone()
  if release_scan_hold and (not previous or previous['case_id']!=case_id or case_id not in ('W04b','W04c','W04e') or mode!='fresh'):
   raise ValueError('Expected the existing short-wave diagnostic HOLD entry.')
  if previous and (not release_scan_hold or previous['status']!='preflight_blocked'):return previous['id']
  if mode=='resume' and c.execute("SELECT 1 FROM jobs WHERE json_extract(spec,'$.parent_id')=? AND json_extract(spec,'$.mode')='resume' AND status NOT IN ('failed','cancelled','interrupted','preflight_blocked')",(parent_id,)).fetchone():raise ValueError('This checkpoint has already been resumed. Use the latest segment of this run.')
  if c.execute("SELECT 1 FROM jobs WHERE status IN ('queued','deferred','running','preflight','pausing') AND case_id=?",(case_id,)).fetchone():raise ValueError('This wave is already queued or running.')
  status='deferred' if case.get('custom') else 'queued'
  message='Waiting for the local campaign and a free solver slot.' if case.get('custom') else 'Oczekuje w kolejce'
  if release_scan_hold:
   id=previous['id']
   spec.update(scan_id='fixed_height_wavelength_scan',scan_order={'W04b':2,'W04c':3,'W04e':5}[case_id])
   c.execute("UPDATE jobs SET status=?,updated=?,spec=?,message=? WHERE id=? AND status='preflight_blocked'",
             (status,now(),json.dumps(spec),message,id))
  else:
   c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)',(id,now(),now(),status,case_id,json.dumps(spec),str(folder),message,None,None,key))
  if conn is None:c.commit()
 except BaseException:
  if conn is None:c.rollback()
  raise
 finally:
  if conn is None:c.close()
 event('queued',id=id,case=case_id,mode=mode)
 return id
