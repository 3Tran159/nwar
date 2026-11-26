"""Read-only campaign view. C01/W01 aliases never change original case identities."""
from pathlib import Path
from datetime import datetime,timezone
import json,csv,math,statistics,time,ctypes,base64,hashlib
HERE=Path(__file__).parent;ROOT=HERE.parent;D=ROOT/'approved_wave_plan_20261101'
def read(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def rows(p):
 try:
  with Path(p).open(encoding='utf-8-sig',newline='') as f:return [r for r in csv.DictReader(f) if None not in r]
 except (OSError,csv.Error):return []
def n(x):
 try:
  v=float(x);return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None
def alive(pid):
 if not isinstance(pid,int) or pid<1:return False
 try:
  k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p;k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];k.CloseHandle.argtypes=[ctypes.c_void_p]
  h=k.OpenProcess(0x1000,False,pid)
  if not h:return False
  try:c=ctypes.c_ulong();return bool(k.GetExitCodeProcess(h,ctypes.byref(c))) and c.value==259
  finally:k.CloseHandle(h)
 except (OSError,AttributeError):return False
def thin(a,count=800):
 if len(a)<=count:return a
 v=a[::math.ceil(len(a)/count)];return v if v[-1]==a[-1] else v+[a[-1]]
def reviewed_w01_means():
 """Display certified four-cycle force means, NOT scientific NAR/forcing acceptance."""
 p=ROOT/'clean_c01_campaign_20261101'/'W01_rho1000_air1p2_r2_20261101'
 receipt_path=ROOT/'clean_c01_campaign_20261101'/'night_wave_queue_20261101'/'W01_four_cycle_review.json'
 try:
  review=read(receipt_path);stage=read(p/'stage_result.json');done=read(p/'completed.json')
  calm=read(ROOT/'clean_c01_campaign_20261101'/'state.json')
  if (review.get('case')!='W01' or Path(review.get('folder','')).resolve()!=p.resolve()
   or review.get('status')!='FOUR_CYCLES_REPEATABLE_PENDING_SPATIAL_FORCING_REVIEW'
   or review.get('saved_and_valid') is not True or review.get('four_cycles_repeated') is not True
   or calm.get('C01_primary_settled') is not True
   or review.get('source_sha256')!=calm.get('accepted_checkpoint_SHA256')
   or stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True
   or done.get('steps')!=review.get('total_steps')
   or abs(float(done.get('time_s',-1))-float(review.get('ended_time_s',-2)))>1e-6
   or not (p/'wave_pilot_final.sim').is_file()):return {}
  history=p/'history.csv'
  if history.stat().st_size>50000000 or hashlib.sha256(history.read_bytes()).hexdigest()!=review.get('raw_history_SHA256'):return {}
  metrics=review.get('metrics') or {}
  if not all(metrics.get(k,{}).get('pass') is True for k in ('CL','CD','eta')):return {}
  cl=n(metrics['CL'].get('mean'));cd=n(metrics['CD'].get('mean'))
  window=review.get('four_period_window_s')
  if cl is None or cd is None or not isinstance(window,list) or len(window)!=2 or not all(n(x) is not None for x in window):return {}
  return {'mean_CL':cl,'mean_CD':cd,'window_s':window,'reviewed_cycles':4,
   'mean_provenance':'Niezależnie zaliczone 4 cykle sił W01; sonda x=−6 m; forcing i ΔCD/Q nadal do weryfikacji',
   'mean_receipt_path':str(receipt_path),'mean_receipt_sha256':hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
 except (OSError,ValueError,TypeError,KeyError):return {}
def run_status(p):
 c=read(p/'completed.json');stage=read(p/'stage_result.json');proc=read(p/'process.json');err=read(p/'macro_error.json') or read(p/'experiment_error.json')
 h=rows(p/'history.csv');last=h[-1] if h else {};age=None
 try:age=time.time()-(p/'history.csv').stat().st_mtime
 except OSError:pass
 if (p/'USER_CANCEL_REQUEST_20261101_1142.json').exists():state='cancelled'
 elif err or stage.get('exit_code') not in (0,None):state='failed'
 elif c and stage.get('exit_code')==0 and stage.get('source_unchanged') is True:state='saved'
 elif c:state='saving'
 elif alive(proc.get('pid')):state='running' if age is not None and age<120 else 'loading' if not h else 'stale'
 elif proc:state='unconfirmed'
 else:state='planned'
 return {'status':state,'time_s':n(last.get('time_s',last.get('physical_time_s'))),'step':n(last.get('step')),'history_age_s':age,'last_CL':n(last.get('CL_hydrodynamic',last.get('CL'))),'last_CD':n(last.get('CD_total',last.get('CD'))),'rows':len(h),'error':err.get('error'),'completed':c,'stage_receipt':stage,'path':str(p)}
def enrich(data):
 manifest=read(HERE/'campaign.json');foil=data.get('foil_live',{});runs=foil.get('runs',[]);analysis=read(D/'analysis_corrected.json')
 ref=foil.get('calm_reference',{}) # Only explicit matched-reference policy may supply C01.
 review=read(D/'forcing_review.json');sensitivity=read(D/'sensitivity_review.json');h0=read(D/'h0_control_state.json')
 entries=[]
 for item in manifest['cases']:
  row=dict(item);row.update(status='planned',mean_CL=None,mean_CD=None,Q_CD=None,delta_CD_pct=None,delta_CL_pct=None,cycles=0,phase_points=[],run_id=None,source_path=None,scientifically_accepted=False)
  paths=item.get('source_runs') or ([item['future_folder']] if item.get('future_folder') else [])
  if item['kind']=='calm':
   if not ref.get('verified_for_wave_comparison'):
    row.update(status='reference_pending',mean_CL=None,mean_CD=None,series=[],source_path=None,time_s=None,step=None,calm_primary_pass=False,reference_status='pending_compatibility',scientifically_accepted=False)
    if paths and Path(paths[-1]).exists():
     p=Path(paths[-1]);state=run_status(p);row.update(state);raw=rows(p/'history.csv')
     series=[[n(r.get('physical_time_s',r.get('time_s'))),n(r.get('CL',r.get('CL_hydrodynamic'))),n(r.get('CD',r.get('CD_total')))] for r in raw]
     cert=read(p/'C01_result.json');good=cert.get('project_primary_settled') is True
     row.update(source_path=str(p),run_id='C01-clean-rho1000-air1p2',series=thin([x for x in series if None not in x]),reference_status='calm_settled_wave_comparison_pending' if good else 'pending_primary_settling',calm_primary_pass=good)
     if good:row.update(mean_CL=n(cert.get('CL')),mean_CD=n(cert.get('CD')),calm_scientific_accepted=True,scientifically_accepted=False,reference_comparison_allowed=False)
     meta=read(p/'live_foil_wave_frame.json');name=meta.get('image','')
     if name and Path(name).name==name and name.endswith('.png'):
      try:
       binary=(p/name).read_bytes()
       if hashlib.sha256(binary).hexdigest()==meta.get('sha256'):row['frame']=dict(meta,data_url='data:image/png;base64,'+base64.b64encode(binary).decode('ascii'))
      except OSError:pass
    entries.append(row);continue
   p=Path(ref['source']);state=run_status(p);row.update(state);evidence=foil.get('calm_certification',{})
   good=ref.get('verified_for_wave_comparison') is True
   raw=rows(p/'history.csv');series=[[n(r.get('physical_time_s',r.get('time_s'))),n(r.get('CL',r.get('CL_hydrodynamic'))),n(r.get('CD',r.get('CD_total')))] for r in raw];series=[x for x in series if None not in x]
   row.update(status='reference' if good and state['status']=='saved' else state['status'],mean_CL=ref.get('CL'),mean_CD=ref.get('CD'),series=thin(series),calm_primary_pass=good,source_path=str(p),reference_window=ref.get('window_s',ref.get('window')),scientifically_accepted=good)
  else:
   candidates=[r for r in runs if r.get('path') in paths]
   matching=sorted(candidates,key=lambda r:(r.get('active',False),r.get('last',{}).get('time') or 0),reverse=True)
   if matching:
    r=matching[0];state=run_status(Path(r['path']));cyc=r.get('phase_cycles',{});block=cyc.get('four_cycle_time_mean',{})
    row.update(state);row.update(source_path=r['path'],run_id=r['id'],series=r.get('series',[]),cycles=cyc.get('count',0),cycle_analysis=cyc,median_step_s=r.get('median_step_s'),observed_dt_s=r.get('dt'),native_frame_available=bool(r.get('frame')))
    row.update(mean_CL=block.get('CL'),mean_CD=block.get('CD'),window_s=[block.get('start_s'),block.get('end_s')],period_measured_s=cyc.get('period_measured_s'),source_lineage=r.get('lineage',[]))
    if item['id']=='W01' and Path(r['path'])==Path(analysis.get('source','missing')):
     row.update(mean_CL=analysis.get('force_block',{}).get('CL'),mean_CD=analysis.get('force_block',{}).get('CD'),window_s=analysis.get('physical_window_s'),period_measured_s=analysis.get('period_measured_s'))
     row['period_STAR_s']=review.get('observed_wave_configuration',{}).get('period_native_s')
    matched_ref=r.get('calm_reference',{}) if r.get('reference_comparison_allowed') is True else {}
    if row['mean_CD'] is not None and matched_ref.get('CD'):
     row['Q_CD']=row['mean_CD']-matched_ref['CD'];row['delta_CD_pct']=100*row['Q_CD']/matched_ref['CD']
    if row['mean_CL'] is not None and matched_ref.get('CL'):row['delta_CL_pct']=100*(row['mean_CL']/matched_ref['CL']-1)
    if len(cyc.get('overlays',[]))==4:
     over=cyc['overlays'];row['phase_points']=[[over[0]['points'][j][0],statistics.fmean(c['points'][j][1] for c in over),statistics.fmean(c['points'][j][2] for c in over)] for j in range(121)]
   elif paths and Path(paths[-1]).exists():
    live=Path(paths[-1]);row.update(run_status(live));raw=rows(live/'history.csv')
    series=[[n(r.get('physical_time_s',r.get('time_s'))),n(r.get('CL_hydrodynamic',r.get('CL'))),n(r.get('CD_total',r.get('CD')))] for r in raw]
    row.update(source_path=str(live),series=thin([x for x in series if None not in x]),scientifically_accepted=False)
   else:row['status']='domain_review' if item.get('domain_review_required') else 'queued'
  entries.append(row)
 # Bind only independently checked force means. Never unlock the C01 wave-comparison gate.
 certificate=reviewed_w01_means()
 if certificate:
  for entry in entries:
   if (entry.get('id')=='W01' and entry.get('kind')=='wave'
    and entry.get('source_path')==str(ROOT/'clean_c01_campaign_20261101'/'W01_rho1000_air1p2_r2_20261101')):
    entry.update(certificate)
    entry['cycles']=max(int(entry.get('cycles') or 0),4)
 controls=[]
 for item in manifest['controls']:
  c=dict(item);c.update(run_status(Path(item['source_runs'][0])));controls.append(c)
 active=[c['id'] for c in entries+controls if c.get('status') in ('running','loading','stale','saving')]
 return {'sampled_at':datetime.now(timezone.utc).isoformat(),'namespace':manifest['namespace'],'cases':entries,'controls':controls,'sources':manifest['sources'],'active_ids':active,'reference':ref,'next_case':manifest.get('next_case','W02'),'deadline_local':manifest['deadline_local'],'gate':{'forcing_review':review.get('status'),'ready_for_sensitivity':review.get('ready_for_matched_sensitivity') is True,'sensitivity_review':sensitivity.get('status'),'current_control':h0.get('status')},'notes':manifest['policy'],'legacy_hold_preserved':manifest['legacy_F_campaign_hold_unchanged'],'selection':'C01/Wxx are display aliases; original folders, raw histories and receipts remain unchanged.'}
