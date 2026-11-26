"""Read-only campaign view. C01/W01 aliases never change original case identities."""
from pathlib import Path
from datetime import datetime,timezone
import json,csv,math,statistics,time,ctypes
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
def run_status(p):
 c=read(p/'completed.json');stage=read(p/'stage_result.json');proc=read(p/'process.json');err=read(p/'macro_error.json') or read(p/'experiment_error.json')
 h=rows(p/'history.csv');last=h[-1] if h else {};age=None
 try:age=time.time()-(p/'history.csv').stat().st_mtime
 except OSError:pass
 if err or stage.get('exit_code') not in (0,None):state='failed'
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
   elif paths and Path(paths[-1]).exists():row.update(run_status(Path(paths[-1])))
   else:row['status']='domain_review' if item.get('domain_review_required') else 'queued'
  entries.append(row)
 controls=[]
 for item in manifest['controls']:
  c=dict(item);c.update(run_status(Path(item['source_runs'][0])));controls.append(c)
 active=[c['id'] for c in entries+controls if c.get('status') in ('running','loading','stale','saving')]
 return {'sampled_at':datetime.now(timezone.utc).isoformat(),'namespace':manifest['namespace'],'cases':entries,'controls':controls,'sources':manifest['sources'],'active_ids':active,'reference':ref,'next_case':'W02','deadline_local':manifest['deadline_local'],'gate':{'forcing_review':review.get('status'),'ready_for_sensitivity':review.get('ready_for_matched_sensitivity') is True,'sensitivity_review':sensitivity.get('status'),'current_control':h0.get('status')},'notes':manifest['policy'],'legacy_hold_preserved':manifest['legacy_F_campaign_hold_unchanged'],'selection':'C01/Wxx are display aliases; original folders, raw histories and receipts remain unchanged.'}
