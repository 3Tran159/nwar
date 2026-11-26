"""Auditable, derived-only wave analysis. Phase comes from one fixed gauge, never force fitting."""
from common import *
from cycle_policy import selection, ANALYSIS_CYCLES, POLICY_ID as CYCLE_POLICY_ID
import numpy as np
def numeric_rows(path,with_evidence=False):
 import io,hashlib
 try:content=Path(path).read_bytes()
 except OSError:return ({},{}) if with_evidence else {}
 # Ignore only a trailing line still being written; all interior gaps remain visible.
 if content and not content.endswith(b'\n'):content=content[:content.rfind(b'\n')+1]
 raw=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
 evidence=dict(path=str(path),sha256=hashlib.sha256(content).hexdigest(),snapshot_bytes=len(content),hash_basis='CSV bytes consumed by this analysis snapshot')
 if not raw:return ({},evidence) if with_evidence else {}
 fields=[k for k in raw[0] if k]
 result={k:np.array([number(r.get(k)) if number(r.get(k)) is not None else np.nan for r in raw],dtype=float) for k in fields}
 return (result,evidence) if with_evidence else result
def merge_segments(segments,dt=.0004):
 """Only join exact continuation boundaries. Never fill a physical-time gap."""
 result={};evidence=[]
 for folder in segments:
  data,receipt=numeric_rows(Path(folder)/'history.csv',with_evidence=True)
  if not data:continue
  t=data.get('time_s')
  if t is None or not np.all(np.isfinite(t)) or np.any(np.diff(t)<=0):raise ValueError('Discontinuous or nonmonotonic history: '+str(folder))
  take=np.ones(len(t),dtype=bool)
  if result:
   end=result['time_s'][-1]
   if abs(t[0]-end)>dt*.2:raise ValueError('Continuation history gap or overlap: '+str(folder))
   take=t>end+dt*.2
   common=set(result)&set(data)
   result={k:np.concatenate((result[k],data[k][take])) for k in common}
  else:result=data
  evidence.append(dict(receipt,samples=int(take.sum())))
 return result,evidence
def gauge_series(segments,x=-.5):
 parts=[]
 for folder in segments:
  data=numeric_rows(Path(folder)/'gauges.csv')
  if not data:continue
  mask=np.isclose(data['x_m'],x)
  a=np.column_stack((data['time_s'][mask],data['eta_actual_m'][mask]))
  if len(a):
   if parts:a=a[a[:,0]>parts[-1][-1,0]+1e-8]
   if len(a):parts.append(a)
 return np.concatenate(parts) if parts else np.empty((0,2))
def exact_segment(t,y,a,b,max_gap):
 if len(t)<2 or a<t[0]-1e-9 or b>t[-1]+1e-9 or b<=a:return None
 i=np.searchsorted(t,a,side='right');j=np.searchsorted(t,b,side='left')
 tt=np.r_[a,t[i:j],b];yy=np.r_[np.interp(a,t,y),y[i:j],np.interp(b,t,y)]
 if not np.all(np.isfinite(yy)) or np.max(np.diff(tt))>max_gap:return None
 return tt,yy
def mean_segment(t,y,a,b,max_gap):
 p=exact_segment(t,y,a,b,max_gap)
 return None if p is None else float(np.trapezoid(p[1],p[0])/(b-a))
def cycles(data,gauge,H,L,origin=T0,probe_distance=34.5):
 result=dict(count=0,cycles=[],repeatable=False,phase_probe_x_m=-.5,phase_method='Crossings of the fixed probe level at x=-0.5 m; no force phase fitting',period_planning_s=period(L),**selection([]))
 if len(gauge)<30 or not data:return result
 T=period(L);eligible=origin+2*T+probe_distance*T/L
 valid=gauge[(gauge[:,0]>=eligible)&np.isfinite(gauge).all(axis=1)]
 if len(valid)<30:return result
 if np.max(np.diff(valid[:,0]))>.012:return dict(result,error='Phase-probe history is not continuous')
 tailg=valid[valid[:,0]>=valid[-1,0]-5*T]
 level=float((np.percentile(tailg[:,1],5)+np.percentile(tailg[:,1],95))/2)
 cross=[]
 for a,b in zip(valid[:-1],valid[1:]):
  if a[1]<=level<b[1]:
   t=a[0]+(level-a[1])*(b[0]-a[0])/(b[1]-a[1])
   if not cross or t-cross[-1]>.5*T:cross.append(float(t))
 t=data['time_s'];phase=np.linspace(0,1,121)
 cl=data['CL_hydrodynamic'];cd=data['CD_total']
 complete=[]
 for a,b in zip(cross[:-1],cross[1:]):
  if not .65*T<b-a<1.35*T:continue
  cs=exact_segment(t,cl,a,b,.0013);ds=exact_segment(t,cd,a,b,.0013)
  gs=exact_segment(gauge[:,0],gauge[:,1],a,b,.012)
  if cs is None or ds is None or gs is None:continue
  ct=a+phase*(b-a)
  complete.append(dict(number=len(complete)+1,start=a,end=b,T=b-a,
   CL_mean=float(np.trapezoid(cs[1],cs[0])/(b-a)),CD_mean=float(np.trapezoid(ds[1],ds[0])/(b-a)),
   CL_amp=float(np.ptp(cs[1])/2),CD_amp=float(np.ptp(ds[1])/2),eta_mean=float(np.trapezoid(gs[1],gs[0])/(b-a)),H_measured=float(np.ptp(gs[1])),
   phase=phase.tolist(),CL=np.interp(ct,t,cl).tolist(),CD=np.interp(ct,t,cd).tolist(),eta=np.interp(ct,gauge[:,0],gauge[:,1]).tolist()))
 result.update(count=len(complete),cycles=complete,analysis_not_before_s=eligible,phase_level=level,period_measured_s=float(np.mean([c['T'] for c in complete[-4:]])) if complete else None)
 result.update(selection(complete))
 selected=result['analyzed_cycles']
 result['period_measured_s']=float(np.mean([c['T'] for c in selected])) if selected else None
 for c in complete:c['analysis_included']=c['number'] in result['analyzed_cycle_numbers']
 if result['analyzed_count']==ANALYSIS_CYCLES:
  last=result['analyzed_cycles'];metrics={}
  for name in ('CL','CD'):
   means=np.array([c[name+'_mean'] for c in last]);amps=np.array([c[name+'_amp'] for c in last]);curves=np.array([c[name] for c in last])
   scale=max(abs(float(means.mean())),float(amps.mean()),1e-7)
   spread=float(np.max(abs(means-means.mean()))/scale);aspread=float(np.max(abs(amps-amps.mean()))/max(float(amps.mean()),1e-7))
   rms=float(np.sqrt(np.mean((curves-curves.mean(axis=0))**2))/scale)
   metrics[name]=dict(mean_spread=spread,amplitude_spread=aspread,phase_RMS=rms,passed=spread<.01 and aspread<.08 and rms<.05)
  heights=np.array([c['H_measured'] for c in last]);levels=np.array([c['eta_mean'] for c in last])
  gauge_ok=bool(np.all((heights>.8*H)&(heights<1.2*H)) and np.max(abs(levels))<.35 and np.ptp(levels)/max(H/2,1e-7)<.10)
  a,b=last[0]['start'],last[-1]['end']
  result.update(window=[a,b],CL_mean=mean_segment(t,cl,a,b,.0013),CD_mean=mean_segment(t,cd,a,b,.0013),metrics=metrics,gauge_repeatable=gauge_ok,repeatable=all(m['passed'] for m in metrics.values()) and gauge_ok)
 return result
def health(data):
 if not data:return dict(ok=False,reason='Brak historii')
 checks={}
 limits={'max_CFL':(0,25),'interface_CFL':(0,2.2),'max_speed_m_s':(0,50),'alpha_min':(-.00001,1.00001),'alpha_max':(-.00001,1.00001),'p_min_Pa':(-1e7,1e7),'p_max_Pa':(-1e7,1e7)}
 for k,(lo,hi) in limits.items():
  a=data.get(k,np.array([np.nan]));ok=bool(np.isfinite(a).all() and np.all((a>=lo)&(a<=hi)))
  checks[k]=dict(ok=ok,min=float(np.nanmin(a)) if np.isfinite(a).any() else None,max=float(np.nanmax(a)) if np.isfinite(a).any() else None)
 v=data.get('water_volume_m3',np.array([np.nan]));checks['water_inventory']=dict(ok=bool(np.isfinite(v).all() and np.max(abs(v-v[0]))<=.8),change_m3=float(v[-1]-v[0]) if np.isfinite(v).all() else None,note='Volume change does not replace mass-flux closure.')
 for k in ('CL_hydrodynamic','CD_total','Fx_N','Fz_N'):
  checks[k]=dict(ok=bool(k in data and np.isfinite(data[k]).all()))
 return dict(ok=all(v['ok'] for v in checks.values()),checks=checks)
def segment_chain(j,seen=None):
 seen=set() if seen is None else seen
 if j['id'] in seen:raise ValueError('Circular source lineage')
 seen.add(j['id']);spec=j['spec'];out=[]
 if spec.get('parent_id'):out=segment_chain(job(spec['parent_id']),seen)
 elif spec.get('parent_segments'):out=[Path(p) for p in spec['parent_segments']]
 elif spec.get('parent_folder'):out=[Path(spec['parent_folder'])]
 if spec.get('checkpoint_recovery'):
  from checkpoint_recovery import verify
  recovered=verify(spec['checkpoint_recovery'],parent_id=spec.get('parent_id'),full=False)
  if not out or out[-1].resolve()!=Path(recovered['original_folder']).resolve():raise ValueError('Recovery parent chain mismatch')
  out[-1]=Path(recovered['view_folder'])
 out.append(Path(j['folder']));return out
def analyze(case,folders):
 data,evidence=merge_segments(folders)
 gauge_x=-.5 if len(gauge_series([folders[0]],-.5)) else -6.
 g=gauge_series(folders,gauge_x)
 setup=read(Path(folders[0])/'wave_setup_audit.json');origin=setup.get('t0',T0);distance=setup.get('probe_distance_m',34.5)
 result=dict(case=case['id'],H=case['H'],L=case['L'],wave_origin_s=origin,probe_distance_m=distance,source_segments=evidence,health=health(data),cycles=cycles(data,g,case['H'],case['L'],origin=origin,probe_distance=distance),time_s=float(data['time_s'][-1]) if data else None,samples=len(data.get('time_s',[])),scientific_NWAR_accepted=False,Q_delta_CD=None)
 result['cycles']['phase_probe_x_m']=gauge_x
 result['cycles']['phase_method']='Crossings of the fixed probe level at x='+str(gauge_x)+' m; no force phase fitting'
 result['cycles']['common_probe_available']=gauge_x==-.5
 if case.get('wave_kind')=='bichromatic':
  result['wave_kind']='bichromatic';result['components']=case['components'];result['diagnostic_only']=True
  result['cycles']=dict(count=0,cycles=[],repeatable=False,phase_probe_x_m=gauge_x,phase_method='Bichromatic: no single repeated carrier cycle',error='Bichromatic diagnostic: full histories and beat envelopes; no regular-wave cycle acceptance',**selection([]))
 return result,data,g
