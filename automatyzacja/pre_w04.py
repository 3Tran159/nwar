"""PRE W04 display and independent calm gate evaluation. Never changes C01."""
from common import *
from history_view import history_view, _history
import numpy as np

REVIEW=HERE/'reviews/W04_20261102'
PRE=DATA/'PRE_W04_20261102'
CALM_RUN=PRE/'calm'
REFERENCE={'CL':.31565950495122014,'CD':.007002316911710474}
THRESHOLD=.5
WINDOW=.2
DT=.0004
PHASES={
 'building_wider_wave_band':'Preparing the wider refined wave band',
 'extending_domain_without_stretching':'Extending the domain at unchanged cell sizes',
 'checking_imported_mesh':'Checking the expanded mesh',
 'geometry_ready_for_protected_region_audit':'Checking the foil mesh and wave envelope',
 'auditing_protected_mesh':'Checking the foil mesh and wave envelope',
 'mapping_C01':'Transferring original C01 to the expanded mesh',
 'calm_running':'Calm flow at 18 m/s · waiting for convergence',
 'ready_for_wave':'Calm gate passed · W04 can start',
 'stable_reference_mismatch':'Stable calm flow differs from C01 · wave blocked',
 'needs_review':'Preparation requires review',
 'paused':'Preparation paused',
 'observation_complete':'Observation saved · awaiting the reference decision',
}

def convergence(values,start=None,ramp_s=0.):
 """Every 0.2 s compare two full adjacent 500-sample windows.

 Stability is the worst of mean drift and the two relative RMS values.
 Two consecutive stable checks, eligible after 0.6 s, must also match C01.
 Partial, duplicate or missing time samples cannot qualify.
 """
 if not len(values):return []
 start=float(start if start is not None else values[0,0]-DT)
 n=round(WINDOW/DT);out=[];stable_count=0;compatible_count=0
 for end in range(2*n,len(values)+1,n):
  segment=values[end-2*n:end];t=float(segment[-1,0])
  continuous=bool(np.isfinite(segment).all() and np.all(np.abs(np.diff(segment[:,0])-DT)<DT*.1)
                 and abs(t-(start+end*DT))<DT*.1)
  row=dict(time_s=t,elapsed_s=t-start,window_s=WINDOW,threshold_pct=THRESHOLD,complete=continuous)
  stable=continuous;compatible=continuous
  for k,name in ((1,'CD'),(2,'CL')):
   a,b=segment[:n,k],segment[n:,k];ma,mb=float(np.mean(a)),float(np.mean(b))
   drift=100*abs(mb-ma)/max(abs(mb),1e-15)
   old_rms=100*float(np.std(a))/max(abs(ma),1e-15)
   new_rms=100*float(np.std(b))/max(abs(mb),1e-15)
   deviation=100*abs(mb-REFERENCE[name])/abs(REFERENCE[name])
   row.update({name+'_mean':mb,name+'_drift_pct':drift,name+'_previous_rms_pct':old_rms,
               name+'_rms_pct':new_rms,name+'_stability_pct':max(drift,old_rms,new_rms),
               name+'_C01_pct':deviation})
   stable &= max(drift,old_rms,new_rms)<THRESHOLD
   compatible &= deviation<=THRESHOLD
  eligible=t-start>=ramp_s+.6-DT*.1
  stable_count=stable_count+1 if stable and eligible else 0
  compatible_count=compatible_count+1 if stable and compatible and eligible else 0
  row.update(stable=bool(stable),compatible=bool(compatible),eligible=eligible,
             consecutive_stable=stable_count,consecutive_compatible=compatible_count,
             wave_allowed=compatible_count>=2,
             stable_reference_mismatch=stable_count>=2 and not compatible)
  # JSON must remain valid even for interrupted/nonfinite raw rows.
  row={k:(v if not isinstance(v,float) or math.isfinite(v) else None) for k,v in row.items()}
  out.append(row)
 return out

def endpoint_convergence(values, ramp_s=1.):
 """Independent adjacent-window checks ending exactly at the saved endpoint.

 Resume times need not be multiples of 0.2 s. Preserve the same sample count,
 RMS, mean-drift and two-check criteria without discarding the final samples.
 """
 n=round(WINDOW/DT)
 if len(values)<3*n:return []
 segment=values[-3*n:]
 checks=convergence(segment,float(segment[0,0]-DT),ramp_s=0.)
 stable_count=compatible_count=0
 for row in checks:
  eligible=row['time_s']>=ramp_s+.6-DT*.1
  stable_count=stable_count+1 if row['stable'] and eligible else 0
  compatible_count=compatible_count+1 if row['stable'] and row['compatible'] and eligible else 0
  row.update(eligible=eligible,consecutive_stable=stable_count,
             consecutive_compatible=compatible_count,wave_allowed=compatible_count>=2,
             stable_reference_mismatch=stable_count>=2 and not row['compatible'])
 return checks

def calm_folders():
 manifest=read(PRE/'continuation.json')
 first=Path(manifest.get('root_folder',CALM_RUN)).resolve()
 if not first.is_relative_to(PRE.resolve()):raise ValueError('PRE root outside preparation directory')
 folders=[first]
 for name in manifest.get('folders',[]):
  folder=Path(name).resolve()
  if not folder.is_relative_to(PRE.resolve()):raise ValueError('PRE continuation outside preparation directory')
  if folder not in folders:folders.append(folder)
 return folders

def calm_values():
 parts=[]
 for folder in calm_folders():
  values=_history(folder)
  if not len(values):continue
  if parts and abs(values[0,0]-parts[-1][-1,0])<DT*.1:values=values[1:]
  if len(values):parts.append(values)
 return np.concatenate(parts) if parts else np.empty((0,3))

def calm_checkpoint(folder):
 """A failed attempt can contribute only its explicitly selected saved checkpoint."""
 folder=Path(folder);recovery=read(folder/'history_cutoff.json')
 if not recovery:return folder/'final.sim'
 checkpoint=Path(recovery['checkpoint'])
 if not checkpoint.resolve().is_relative_to(folder.resolve()):raise ValueError('Recovery checkpoint outside its attempt')
 return checkpoint

def stop_reason():
 folder=calm_folders()[-1];done=read(folder/'completed.json')
 if done.get('status')!='field_health_guard':return None
 guard=read(folder/'field_guard.json')
 if guard.get('reason')=='water_balance_closure':return 'Water inventory no longer matches the integrated boundary flux. Checkpoint and full history saved.'
 inventory=read(folder/'baseline_inventory_audit.json');rows=tail(folder/'conservation.csv')
 current=number(rows[-1].get('water_volume_m3')) if rows else None
 baseline=number(inventory.get('water_m3'));limit=number(inventory.get('allowed_drift_m3'))
 if None not in (current,baseline,limit) and abs(current-baseline)>limit:
  return 'Water inventory change '+format(current-baseline,'+.3f')+' m³ exceeded the '+format(limit,'.3f')+' m³ limit during startup. Checkpoint and full history saved.'
 return 'Field health guard stopped preparation. Checkpoint and full history saved; inspect the recorded field checks.'

def snapshot():
 geometry=read(REVIEW/'state.json');prep=read(PRE/'state.json')
 state=prep or geometry
 if not state:return None
 status=state.get('status');active=bool(state.get('birth') and state['birth']==birth(state.get('pid')))
 folders=calm_folders();folder=folders[-1]
 hist=history_view(folders);values=calm_values();setup=read(folder/'setup.json') or read(CALM_RUN/'setup.json')
 checks=convergence(values,0.,setup.get('startup_current_ramp_s',1.))
 last=values[-1] if len(values) else [None,None,None]
 rr=tail(folder/'history.csv');recent=rr[-1] if rr else {};costs=[]
 for a,b in zip(rr[:-1],rr[1:]):
  wa,wb=number(a.get('wall_s')),number(b.get('wall_s'))
  sa,sb=number(a.get('step')),number(b.get('step'))
  if None not in (wa,wb,sa,sb) and wb>wa and sb>sa:costs.append((wb-wa)/(sb-sa))
 age=time.time()-(folder/'history.csv').stat().st_mtime if (folder/'history.csv').is_file() else None
 health_rows=tail(folder/'field_health.csv') or tail(folders[-2]/'field_health.csv') if len(folders)>1 else tail(folder/'field_health.csv')
 speed=number(health_rows[-1].get('inlet_imposed_speed_m_s')) if health_rows else None
 ramp_s=setup.get('startup_current_ramp_s',1.)
 elapsed=max(0.,float(last[0])) if len(values) else 0.
 ramp_complete=bool(len(values) and elapsed>=ramp_s-DT*.1)
 cost=float(np.median(costs[-30:])) if costs else None
 stale=bool(active and age and age>180)
 ramp_remaining_steps=0 if ramp_complete else math.ceil(max(0.,ramp_s-elapsed)/setup.get('dt_s',DT))
 ramp=dict(duration_s=ramp_s,elapsed_s=ramp_s if ramp_complete else min(ramp_s,elapsed),
           percent=100. if ramp_complete else 100*min(ramp_s,elapsed)/ramp_s if ramp_s>0 else 0.,
           complete=ramp_complete,started=bool(len(values)),target_speed_m_s=setup.get('constant_reference_velocity_m_s',18.),
           remaining_wall_s=0. if ramp_complete else ramp_remaining_steps*cost if active and not stale and cost else None)
 global_rows=tail(folder/'global_ramp_velocity.csv') if setup.get('initialization')=='whole_domain_momentum_ramp' else []
 global_time=number(global_rows[-1].get('time_s')) if global_rows else None
 global_speeds=[dict(x_m=number(r.get('x_m')),water_mean_Ux_m_s=number(r.get('water_mean_Ux_m_s')))
                for r in global_rows if number(r.get('time_s'))==global_time] if global_rows else []
 label=PHASES.get(status,status)
 if status=='calm_running':
  label='Loading mesh and initializing flat water from rest' if not len(values) else 'Ramping from rest to 18 m/s' if not ramp_complete else 'Calm flow at 18 m/s · waiting for convergence'
  if setup.get('initialization')=='whole_domain_momentum_ramp' and len(values) and not ramp_complete:
   label='Ramping the whole domain from rest to 18 m/s'
 live=dict(**hist,time_s=last[0],CD=last[1],CL=last[2],s_per_step=cost,
           interface_CFL=number(recent.get('interface_CFL')),age_s=age,stale=stale,
           history_label='PRE W04 · full calm history on the expanded mesh',
           progress_label=label,goal_steps=None,eta_s=None,percent=None,current_speed_m_s=speed,
           convergence=checks,reference=REFERENCE,threshold_pct=THRESHOLD,ramp_s=ramp_s,speed_ramp=ramp,
           startup_scope=setup.get('startup_acceleration_scope'),global_water_speeds=global_speeds,
           convergence_eligible_s=setup.get('settling_eligible_after_s',1.6))
 return dict(id='PRE_W04',case_id='PRE W04',preparation=True,status='running' if active else status,
             phase=status,active=active,folder=str(folder),label=label,live=live,
             error=state.get('error') or (stop_reason() if not active else None),receipt=read(PRE/'calm_receipt.json'),
             downloads=[name for name in ('PRE_W04_history.png','PRE_W04_settling.png','PRE_W04_convergence.png','convergence.csv','history.csv','calm_receipt.json')
                        if (PRE/name).is_file()])

def export():
 """Permanent scientific figures and raw histories, independent of wave reports."""
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import shutil
 folders=calm_folders();values=calm_values()
 if not len(values):return
 setup=read(folders[0]/'setup.json')
 checks=convergence(values,0.,setup.get('startup_current_ramp_s',1.))
 previous=None
 with (PRE/'history.csv').open('w',newline='',encoding='utf8') as target:
  writer=None
  for folder in folders:
   if not (folder/'history.csv').is_file():continue
   cutoff=read(folder/'history_cutoff.json').get('time_s')
   with (folder/'history.csv').open(newline='',encoding='utf8') as source:
    reader=csv.DictReader(source)
    if writer is None:writer=csv.DictWriter(target,fieldnames=reader.fieldnames);writer.writeheader()
    for row in reader:
     t=number(row.get('time_s'))
     if cutoff is not None and t is not None and t>cutoff+1e-9:continue
     if t is None or (previous is not None and abs(t-previous)<DT*.1):continue
     writer.writerow(row);previous=t
 if checks:
  with (PRE/'convergence.csv').open('w',newline='',encoding='utf8') as f:
   w=csv.DictWriter(f,fieldnames=checks[0]);w.writeheader();w.writerows(checks)
 markers=history_view(folders)['resume_markers'];ramp=setup.get('startup_current_ramp_s',1.)
 for suffix,subset,title in [('history',values,'Full CL/CD history'),('settling',values[values[:,0]>=ramp-1e-9],'CL/CD settling at fixed inlet speed 18 m/s')]:
  if not len(subset):continue
  fig,axs=plt.subplots(2,1,figsize=(11,6.5),sharex=True)
  for ax,k,name,color in ((axs[0],1,'CD','#087f8c'),(axs[1],2,'CL','#c17a19')):
   ref=REFERENCE[name];ax.plot(subset[:,0],subset[:,k],color=color,label='PRE W04')
   ax.axhspan(ref*.995,ref*1.005,color='#087f8c',alpha=.14,label='C01 ±0.5%')
   ax.axhline(ref,color='#586a74',ls='--',label='Original C01');ax.set_ylabel('CL hydrodynamic' if name=='CL' else 'CD');ax.grid(alpha=.2)
   if suffix=='history':ax.axvline(ramp,color='#7f8d93',ls='-.',label='Ramp complete')
   for marker in markers:
    if subset[0,0]<=marker['time_s']<=subset[-1,0]:ax.axvline(marker['time_s'],color='#586a74',ls=':',label='Resume '+format(marker['time_s'],'.4f')+' s')
   ax.legend(loc='best',fontsize=8)
  axs[-1].set_xlabel('Physical time [s]');fig.suptitle('PRE W04 · '+title)
  fig.text(.5,.012,'CL excludes buoyancy: CL = CL_total − 22.7181891 N / 3855.6 N. Original C01 uses the same convention.',ha='center',fontsize=9)
  fig.tight_layout(rect=(0,.04,1,.96));fig.savefig(PRE/('PRE_W04_'+suffix+'.png'),dpi=170);fig.savefig(PRE/('PRE_W04_'+suffix+'.svg'));plt.close(fig)
 fig,axs=plt.subplots(2,1,figsize=(11,7),sharex=True)
 for ax,suffix,title in ((axs[0],'stability_pct','Stability of adjacent 0.2 s windows'),(axs[1],'C01_pct','Mean deviation from the original C01')):
  for name,color in (('CD','#087f8c'),('CL','#c17a19')):
   ax.plot([r['time_s'] for r in checks],[r[name+'_'+suffix] for r in checks],'.-',color=color,label=name)
  ax.axhline(.5,color='#b64737',ls='--',label='0.5% threshold');ax.set_ylim(bottom=0);ax.set_ylabel('Difference [%]');ax.set_title(title);ax.grid(alpha=.2);ax.legend()
 axs[-1].set_xlabel('Physical time [s]');fig.suptitle('PRE W04 · calm convergence and C01 compatibility')
 fig.text(.5,.01,'Stability = max(mean change, previous RMS, current RMS). Two consecutive eligible checks required.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.03,1,.96));fig.savefig(PRE/'PRE_W04_convergence.png',dpi=170);plt.close(fig)

if __name__=='__main__':export()
