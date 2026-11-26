"""Explicit dashboard continuation of a clean PRE pause; never reset fields."""
from common import *
from pre_w04 import PRE, calm_folders
from worker import native

REQUEST = PRE/'dashboard_resume.json'

def alive(owner):
 return bool(owner.get('birth') and owner['birth']==birth(owner.get('pid')))

def owned_pause(path, folder):
 marker=read(path)
 return marker.get('kind')=='pre_dashboard_pause' and marker.get('folder')==str(folder)

def checkpoint_info():
 folder=calm_folders()[-1];done=read(folder/'completed.json');stage=read(folder/'stage_result.json')
 owner=read(PRE/'state.json');request=read(REQUEST);latest=read(folder/'latest_checkpoint.json')
 receipt=read(PRE/'calm_receipt.json');checkpoint=folder/'final.sim';hist=tail(folder/'history.csv')
 reason=None
 if alive(owner) or alive(request):reason='Waiting for the current controller to finish.'
 elif done.get('status') not in ('stopped_by_marker','wall_budget'):reason='Only a clean saved pause or time-limit save can be resumed here.'
 elif stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True:reason='The solver did not finish its save cleanly.'
 elif read(folder/'setup.json').get('initialization')!='whole_domain_momentum_ramp':reason='This preparation needs its own continuation procedure.'
 elif any((folder/name).exists() for name in ('macro_error.txt','macro_error.json')):reason='The saved run has a solver error.'
 elif not checkpoint.is_file() or checkpoint.stat().st_size<400_000_000:reason='The full simulation checkpoint is missing.'
 elif not hist or number(hist[-1].get('time_s')) is None:reason='The saved force history is missing.'
 else:
  end=float(hist[-1]['time_s'])
  if any(number(value) is None or abs(float(value)-end)>1e-8 for value in (done.get('time_s'),latest.get('time_s'),receipt.get('checkpoint_time_s'))):
   reason='Checkpoint time does not match the end of the force history.'
  elif any(Path(value or '').resolve()!=checkpoint.resolve() for value in (latest.get('path'),receipt.get('checkpoint'))):
   reason='The checkpoint is not the latest selected PRE save.'
  elif not receipt.get('checkpoint_sha256'):reason='Checkpoint integrity evidence is missing.'
 return dict(available=reason is None,reason=reason,folder=str(folder),checkpoint=str(checkpoint),
             time_s=done.get('time_s'),sha256=receipt.get('checkpoint_sha256'),
             starting=alive(request) and request.get('folder')==str(folder))

def resume(folder, request_key, spawn):
 if not isinstance(request_key,str) or not 8<=len(request_key)<=100:raise ValueError('Missing request identifier.')
 prior=read(REQUEST)
 if prior.get('request_key')==request_key and prior.get('folder')==folder:
  return dict(message='This resume request was already accepted.',pid=prior.get('pid'))
 info=checkpoint_info()
 if folder!=info['folder']:raise ValueError('The selected checkpoint changed. Refresh the dashboard.')
 if not info['available']:raise ValueError(info['reason'])
 selected=Path(info['folder']);checkpoint=Path(info['checkpoint'])
 if native():raise ValueError('A solver is still active. Wait for its save and exit.')
 if any(j['status'] in ('queued','running','preflight','pausing') for j in jobs()):raise ValueError('The wave queue must be idle before resuming PRE W04.')
 blockers=[p for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS+[PRE/'STOP_ALL'] if p.exists()]
 pauses=[p for p in (PRE/'STOP',DATA/'PAUSE') if p.exists()]
 blockers += [p for p in pauses if not owned_pause(p,selected)]
 if blockers:raise ValueError('An external stop or resource reservation is active: '+str(blockers[0]))
 if sha(checkpoint)!=info['sha256']:raise ValueError('The saved checkpoint changed; continuation is blocked.')
 if sha(SOURCE)!=SOURCE_SHA:raise ValueError('The original C01 reference changed.')
 # Only markers created by this dashboard pause can be consumed. Keep an audit copy.
 saved={str(p):p.read_bytes() for p in pauses}
 write(PRE/('dashboard_resume_audit_'+uuid.uuid4().hex+'.json'),dict(at=now(),folder=folder,
       checkpoint=info,request_key=request_key,consumed_pause_markers=list(saved)))
 try:
  for p in pauses:
   if p.read_bytes()!=saved[str(p)]:raise ValueError('Pause marker changed during resume.')
   p.unlink()
  pid=spawn('run_pre_w04_global_ramp.py','--resume')
 except Exception:
  for p in pauses:
   if not p.exists():p.write_bytes(saved[str(p)])
  raise
 write(REQUEST,dict(at=now(),pid=pid,birth=birth(pid),folder=folder,request_key=request_key,
       checkpoint=info['checkpoint'],checkpoint_sha256=info['sha256'],time_s=info['time_s']))
 return dict(message='Resuming PRE W04 from '+format(info['time_s'],'.4f')+' s. Live charts and report updates are enabled.',pid=pid)
