"""Explicit W08 diagnostic and bounded overnight follow-up after W06 acceptance."""
from common import *
PLAN=HERE/'bichromatic_w08.json'

def approved_manual_start(entry, plan):
 manual=read(HERE/'qa/w08_manual_launch_20261105.json')
 spec=entry['spec']
 return (entry['case_id']=='W08' and manual.get('authorized') is True
         and spec.get('campaign_id')==manual.get('campaign_id')==plan['id']
         and entry.get('request_key')==manual.get('request_key')==plan['id']+'_W08_manual_20261105_W01_W06'
         and spec.get('mode')=='fresh' and spec.get('components')==manual.get('components'))

def approved_manual_resume(entry, plan):
 spec=entry['spec']
 if spec.get('mode')!='resume' or not spec.get('parent_id'):return False
 child=entry
 seen={entry['id']}
 while child['spec'].get('mode')=='resume':
  child_spec=child['spec']
  parent_id=child_spec.get('parent_id')
  if not parent_id or parent_id in seen:return False
  seen.add(parent_id)
  parent=job(parent_id)
  parent_spec=parent['spec']
  if (parent['case_id']!='W08' or parent['status']!='paused'
      or parent_spec.get('campaign_id')!=plan['id']
      or parent_spec.get('components')!=spec.get('components')):return False
  folder=Path(parent['folder'])
  ck=read(folder/'latest_checkpoint.json');done=read(folder/'completed.json')
  stage=read(folder/'stage_result.json');integrity=read(folder/'final_integrity.json')
  history=tail(folder/'history.csv')
  endpoint=number(child_spec.get('source_time'))
  if (stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True
      or any((folder/name).exists() for name in ('macro_error.json','macro_error.txt'))
      or done.get('status')!='paused_saved' or ck.get('healthy') is not True
      or ck.get('file')!='wave_pilot_final.sim'
      or Path(child_spec['source']).resolve()!=(folder/ck['file']).resolve()
      or not integrity.get('sha256') or child_spec.get('source_sha')!=integrity['sha256']
      or not history or endpoint is None
      or any(t is None or abs(t-endpoint)>1e-7 for t in
             (number(ck.get('time_s')),number(done.get('time_s')),
              number(integrity.get('time_s')),number(history[-1].get('time_s'))))):
   return False
  child=parent
 return approved_manual_start(child,plan)

def case():
 p=read(PLAN)
 if not p.get('authorized'):return None
 components=p['components']
 conditions=' + '.join(f"{c['baseline']} (H = {c['H_m']:.2f} m, λ = {c['lambda_m']:g} m, φ = {c['phase_deg']:g}°)" for c in components)
 return dict(id='W08',display_id='W08bi',title='Bichromatic diagnostic',condition_label=conditions,
             H=1.,L=30.,T=period(30),dt=.0004,existing=None,ready=p.get('compiled',False),blocker=None if p.get('compiled') else 'Bichromatic generator preparation',
             scientific='diagnostic',wave_kind='bichromatic',diagnostic_only=True,components=components)

def duration():
 t1,t2=period(30),period(20);beat=1/abs(1/t1-1/t2)
 # Two slow-component startup periods, slowest inlet transit, five beat envelopes.
 return 2*max(t1,t2)+69.5/(20/t2)+5*beat+.1*beat

def followup(plan,apply=False,budget_only=False):
 p=read(PLAN)
 prior=[j for j in jobs() if j['case_id']=='W08' and j['spec'].get('campaign_id')==plan['id']]
 if prior and not budget_only:return dict(status='optional_w08_'+prior[0]['status'],job_id=prior[0]['id'])
 deadline=datetime.fromisoformat(p['night_deadline']);current=datetime.now().astimezone()
 if current>=deadline:return dict(status='complete',optional_w08='skipped_night_finished')
 rates=[]
 for j in jobs():
  if j['case_id'] not in ('W04','W06'):continue
  history=tail(Path(j['folder'])/'history.csv')[-300:]
  for a,b in zip(history[:-1],history[1:]):
   dt=number(b.get('time_s'));ta=number(a.get('time_s'));wa=number(a.get('wall_s'));wb=number(b.get('wall_s'))
   if None not in (dt,ta,wa,wb) and dt>ta and wb>wa:rates.append((wb-wa)/(dt-ta))
  if len(rates)>100:break
 if len(rates)<20:return dict(status='waiting_timing',optional_w08='No reliable measured duration estimate')
 import statistics
 estimate=duration()*statistics.median(rates)*1.25+600
 if estimate>(deadline-current).total_seconds():return dict(status='complete',optional_w08='skipped_insufficient_night_time',estimated_wall_h=estimate/3600,remaining_h=(deadline-current).total_seconds()/3600)
 if not p.get('compiled'):return dict(status='blocked',reason='W08 generator has not passed compilation')
 if budget_only:return dict(status='ready',estimated_wall_h=estimate/3600)
 if any(j['status'] in ('running','queued','preflight','pausing') for j in jobs()):return dict(status='waiting_worker')
 owner=read(DATA/'worker.lock')
 if owner.get('birth') and birth(owner.get('pid'))==owner['birth']:return dict(status='waiting_worker')
 if not apply:return dict(status='ready',case='W08',estimated_wall_h=estimate/3600)
 id=enqueue('W08',request_key=plan['id']+'_W08_bichromatic_20261103',mpi_processes=1)
 from server import ensure_worker,enable_report_updates
 enable_report_updates()
 return dict(status='dispatched',case='W08',job_id=id,worker_pid=ensure_worker())
