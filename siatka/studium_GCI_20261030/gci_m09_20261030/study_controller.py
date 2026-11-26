"""Audited M09 mesh family -> mapped warm starts -> common-dt pilots -> GCI/controls."""
from pathlib import Path
import os,sys,json,time,datetime,shutil,subprocess,threading,hashlib,csv,math
O=Path(__file__).resolve().parent;H=O.parent;sys.path.insert(0,str(H/'.deps'))
import numpy as np
from scipy.optimize import brentq
R=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
sys.path.insert(0,str(R.parent/'night_20261028'))
from night_queue import STAR,saved_options,redact,free_memory
REF=R/'matched_endpoint_20261029/M09_SO_common_t2040_r1'
MESHES=['M09','G09_M','G09_F'];KEYS=['CD','CL_total','pressure_drag_N','viscous_drag_N']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(p)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def state(status,**kw):
 write(O/'study_state.json',dict(status=status,pid=os.getpid(),updated_at=datetime.datetime.now().astimezone().isoformat(),**kw));print(status,kw,flush=True)
def stopped():return (O/'STOP').exists() or (O/'STOP_ALL').exists() or (R/'STOP_ALL').exists()
def rows(p):return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(p.open(encoding='utf-8-sig'))]
def gpu_busy():
 cmd="@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'starccm+.exe' -and $_.CommandLine -match '-gpgpu' }).Count"
 p=subprocess.run(['powershell','-NoProfile','-Command',cmd],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=30)
 if p.returncode:raise RuntimeError('Cannot check GPU ownership')
 return int(p.stdout.strip())>0
def wait_resources(gpu):
 while free_memory()<18*1024**3 or (gpu and gpu_busy()):
  if stopped():raise RuntimeError('Stop marker detected')
  state('waiting_for_resources',requires_gpu=gpu);time.sleep(30)
 if shutil.disk_usage(str(O)).free<15*1024**3:raise RuntimeError('Less than 15 GiB free study storage')
def run_star(name,source,macro,env_extra,gpu,budget=172800):
 out=O/'runs'/name
 if out.exists():raise RuntimeError('Existing attempt preserved: '+name)
 out.mkdir(parents=True);wait_resources(gpu)
 original_hash=sha(source);shutil.copy2(source,out/'input.sim')
 if sha(out/'input.sim')!=original_hash:raise RuntimeError('Copy identity mismatch')
 write(out/'source_identity.json',dict(path=str(source),sha256=original_hash))
 env=os.environ.copy();env.update(env_extra);env['NTNU_STAB_OUT']=str(out);env['NTNU_MAP_OUT']=str(out)
 cmd=[str(STAR),*saved_options(1 if gpu else 2)]
 if gpu:cmd+=['-gpgpu','auto:1']
 cmd+=['-batch',str(macro),str(out/'input.sim')]
 with (out/'star.log').open('x',encoding='utf-8') as log:
  p=subprocess.Popen(cmd,cwd=out,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
  write(out/'process.json',dict(pid=p.pid,started_at=datetime.datetime.now().astimezone().isoformat(),gpu=gpu))
  state('running',job=name,star_pid=p.pid,gpu=gpu,output=str(out))
  def drain():
   for line in p.stdout:log.write(redact(line));log.flush()
  th=threading.Thread(target=drain);th.start();start=time.time();guard=None
  while p.poll() is None:
   if stopped() or free_memory()<8*1024**3 or shutil.disk_usage(str(O)).free<6*1024**3 or time.time()-start>budget:
    (out/'STOP').touch();guard=guard or time.time()
   if free_memory()<4*1024**3 or shutil.disk_usage(str(O)).free<2*1024**3 or (guard and time.time()-guard>600):
    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);break
   time.sleep(5)
  rc=p.wait();th.join(30)
 unchanged=sha(source)==original_hash;write(out/'process_exit.json',dict(returncode=rc,source_unchanged=unchanged,wall_s=time.time()-start))
 if rc or not unchanged or guard:raise RuntimeError('Job stopped or failed: '+name)
 return out
def flow(name,source,start,target,dt,inner,cells,pilot=False):
 env={'NTNU_STAB_DT':str(dt),'NTNU_STAB_TARGET':str(target),'NTNU_STAB_INNER':str(inner),'NTNU_STAB_CELLS':str(cells),'NTNU_STAB_START':str(start),'NTNU_STAB_INIT':'false','NTNU_STAB_ORDER':'SECOND_ORDER','NTNU_STAB_BUDGET':'172200','NTNU_STAB_PRIOR_HISTORY':'','NTNU_GCI_MAX_CFL':'1e8' if pilot else '10','NTNU_GCI_INTERFACE_CFL':'1e8' if pilot else '1'}
 out=run_star(name,source,O/'ContinueGCI.java',env,True)
 done=read(out/'completed.json')
 if done['status']!='target_reached' or abs(done['time_s']-target)>dt*.2 or not (out/'EXPORT_OK.json').exists():raise RuntimeError('Flow completion gate failed: '+name+' '+str(done))
 data=rows(out/'history.csv');vf=rows(out/'vof_substeps.csv')
 diag={'max_CFL':max(r['max_CFL'] for r in data),'interface_max_CFL':max(r['interface_max_CFL'] for r in data),'VOF_effective_max_CFL':max(r['flow_CFL_divided_by_substeps'] for r in vf),'max_yplus':max(r['max_yplus'] for r in data),'max_velocity':max(r['max_velocity_m_s'] for r in data)}
 write(out/'flow_diagnostics.json',diag)
 setup=read(out/'setup.json');ref=read(REF/'setup.json')
 for k in ['rho','current','wind','waterline','boundaries','reference_area_m2','span_m','models']:
  if setup[k]!=ref[k]:raise RuntimeError('Physics mismatch '+k+' in '+name)
 return out,diag
def mean(data,key,lo,hi):
 a=np.array([r[key] for r in data if lo+1e-8<r['physical_time_s']<=hi+1e-8])
 if len(a)<20 or not np.all(np.isfinite(a)):raise RuntimeError('Incomplete averaging window')
 return float(a.mean())
def summary(paths,target):
 data=[]
 for p in paths:data.extend(rows(p/'history.csv'))
 a={}
 for k in KEYS:
  means=[mean(data,k,target-.6+j*.2,target-.4+j*.2) for j in range(3)]
  a[k]={'means':means,'mean':mean(data,k,target-.6,target),'max_adjacent_shift_abs':max(abs(means[1]-means[0]),abs(means[2]-means[1])),'max_adjacent_shift_pct':100*max(abs(means[1]-means[0]),abs(means[2]-means[1]))/max(abs(means[-1]),1e-12)}
 return a
def gci(values,area,cells):
 # Inputs coarse, medium, fine. Only the x-z plane is refined: h=sqrt(A/N).
 h=[math.sqrt(area[m]/cells[m]) for m in MESHES];f3,f2,f1=values;e21=f2-f1;e32=f3-f2;r21=h[1]/h[2];r32=h[0]/h[1]
 result={'phi_coarse_medium_fine':values,'h_coarse_medium_fine_m':h,'r21':r21,'r32':r32}
 if abs(e21)<1e-15 or abs(e32)<1e-15:return dict(result,status='differences_unresolved')
 if e21*e32<=0:return dict(result,status='oscillatory_no_standard_monotone_GCI')
 ratio=e32/e21
 def fun(p):return math.exp(p*math.log(r21))*math.expm1(p*math.log(r32))/math.expm1(p*math.log(r21))-ratio
 if fun(.001)*fun(12)>=0:return dict(result,status='no_positive_observed_order_in_0.001_to_12')
 p=brentq(fun,.001,12);ext=f1+(f1-f2)/math.expm1(p*math.log(r21))
 absolute_fine=1.25*abs(e21)/math.expm1(p*math.log(r21))
 absolute_medium=1.25*abs(e32)/math.expm1(p*math.log(r32))
 result.update(status='GCI_estimate_pending_nuisance_checks',observed_p=p,extrapolated=ext,GCI_fine_abs=absolute_fine,GCI_fine_pct=100*absolute_fine/abs(f1),GCI_medium_abs=absolute_medium,GCI_medium_pct=100*absolute_medium/abs(f2),GCI_M09_abs=absolute_medium*math.exp(p*math.log(r32)),GCI_M09_pct=100*absolute_medium*math.exp(p*math.log(r32))/abs(f3),asymptotic_ratio=absolute_medium/(math.exp(p*math.log(r21))*absolute_fine),order_caution=p>4)
 return result
def main():
 state('waiting_for_completed_mesh_audit')
 while True:
  if stopped():raise RuntimeError('Stop marker')
  b=read(O/'build_state.json')
  if b['status']=='needs_review':raise RuntimeError('Mesh build requires review: '+b['error'])
  if b['status']=='both_meshes_built_pending_family_audit':break
  time.sleep(20)
 state('auditing_actual_mesh_family')
 with (O/'family_audit.log').open('x',encoding='utf-8') as f:
  p=subprocess.run([sys.executable,str(O/'audit_family.py')],stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=1800)
 if p.returncode:raise RuntimeError('Family audit failed')
 fam=read(O/'family_audit/family_audit.json')
 if not all(fam['gates'].values()):raise RuntimeError('Actual geometry refinement gates failed; no flow study launched')
 cells={m:fam['meshes'][m]['cells'] for m in MESHES};area={m:fam['meshes'][m]['total_fluid_section_area_m2'] for m in MESHES}
 source={'M09':REF/'final.sim'}
 for m in MESHES[1:]:
  audit=read(O/m/'basic_audit.json')
  if not all(audit['gates'].values()):raise RuntimeError('Basic quality gate failed '+m)
  out=run_star('map_'+m,REF/'final.sim',O/'MapM09Solution.java',{'NTNU_MAP_MESH':str(O/(m+'_raw')/'mesh_exact.CGNS'),'NTNU_MAP_CELLS':str(cells[m])},False,7200)
  if not read(out/'mapping_audit.json')['pass'] or not (out/'mapped.sim').exists():raise RuntimeError('Mapping audit failed '+m)
  source[m]=out/'mapped.sim'
 dt=.0001;pilots={}
 for attempt in range(4):
  ratios=[]
  for m in MESHES:
   out,d=flow('pilot_'+m+'_r'+str(attempt+1),source[m],2.04,2.05,dt,10,cells[m],True);pilots[m]=out
   ratios.extend([d['max_CFL']/10,d['interface_max_CFL'],d['VOF_effective_max_CFL']/.5])
  worst=max(ratios)
  if worst<=1:break
  dt/=2**max(1,math.ceil(math.log2(worst*1.1)))
 else:raise RuntimeError('No acceptable common timestep after pilot refinements')
 write(O/'accepted_timestep.json',dict(dt_s=dt,pilots={k:str(v) for k,v in pilots.items()},CFL_pass=True))
 paths={m:[] for m in MESHES};sources={m:pilots[m]/'final.sim' for m in MESHES};start=2.05;target=3.
 for roundno in range(5):
  for m in MESHES:
   out,d=flow('study_'+m+'_r'+str(roundno+1),sources[m],start,target,dt,10,cells[m]);paths[m].append(out);sources[m]=out/'final.sim'
  sums={m:summary(paths[m],target) for m in MESHES};deltas={k:min(abs(sums[MESHES[j]][k]['mean']-sums[MESHES[j+1]][k]['mean']) for j in [0,1]) for k in KEYS}
  stability={k:all(sums[m][k]['max_adjacent_shift_pct']<=.05 and sums[m][k]['max_adjacent_shift_abs']<=.1*deltas[k] for m in MESHES) for k in ['CD','CL_total']}
  est={k:gci([sums[m][k]['mean'] for m in MESHES],area,cells) for k in KEYS}
  write(O/'spatial_progress.json',dict(target_s=target,means=sums,smallest_pair_differences=deltas,stability=stability,GCI=est))
  if all(stability.values()):break
  start=target;target=round(target+.6,8)
 else:raise RuntimeError('Force drift is not small relative to mesh differences by 5.4 s; GCI withheld')
 common=sources['G09_F'];controls={}
 for label,testdt,inner in [('baseline',dt,10),('dt_half',dt/2,10),('inner_twice',dt,20)]:
  out,d=flow('control_'+label,common,target,target+.8,testdt,inner,cells['G09_F'])
  controls[label]=summary([out],target+.8)
 gates={}
 for k in KEYS:
  base=controls['baseline'][k]['mean']
  e_time=abs(controls['dt_half'][k]['mean']-base)
  e_inner=abs(controls['inner_twice'][k]['mean']-base)
  e_long=abs(sums['G09_F'][k]['mean']-base)
  e_drift=max(controls[v][k]['max_adjacent_shift_abs'] for v in controls)
  gates[k]=dict(time_effect_abs=e_time,inner_effect_abs=e_inner,long_window_shift_abs=e_long,control_window_drift_abs=e_drift,allowed_abs=.1*deltas[k],**{"pass":max(e_time,e_inner,e_long,e_drift)<=.1*deltas[k]})
  if 'GCI_fine_abs' in est[k]:est[k]['status']='mesh_uncertainty_estimated' if gates[k]['pass'] and not est[k]['order_caution'] else 'not_verified_nuisance_or_order_review_required'
 write(O/'gci_results.json',dict(status='completed_checks',common_dt_s=dt,averaging_interval_s=[target-.6,target],cell_counts=cells,means=sums,controls=controls,nuisance_gates=gates,GCI=est,local_yplus_exceptions='Allowed by user; compare spatial diagnostics in each run, not automatically a full-wall y+ pass.',note='Numerical spatial verification for this quasi-2D model; not experimental validation or spanwise/3D convergence.'))
 state('completed_GCI_checks',verified_quantities=[k for k in KEYS if est[k].get('status')=='mesh_uncertainty_estimated'])
if __name__=='__main__':
 lock=O/'study.lock'
 try:
  with lock.open('x') as f:json.dump({'pid':os.getpid()},f)
  main()
 except BaseException as e:state('needs_review',error=str(e));raise
 finally:
  if lock.exists() and read(lock).get('pid')==os.getpid():lock.unlink()
