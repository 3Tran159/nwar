"""One approved, bounded GPU near-zero control to quantify the documented calm/wave mismatch.
Not an accepted forcing audit, not a dt sensitivity retry, no automatic following solver.
"""
from pathlib import Path
from datetime import datetime
import sys,os,json,uuid,subprocess,statistics,math,argparse
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'approved_wave_plan_20261101';P=R/'M13_wave_direct_20261031';W=R/'wave_surface_only'
F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029');sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
SOURCE=R/'M13_farfield15_20261031'/'M13_GPU_calm_dt0004'/'final.sim'
MACRO=D/'M13NearZeroControl.java';OUT=P/'M13_GPU_Hnear0_matched_control_20261101'
LOCKS=[D/'h0_control.lock',R/'m13_wave_gpu.lock',P/'M13_wave_gpu_pilot.lock',W/'wave_inlet.lock']
EXTRA_LOCKS=[D/'forcing_audit.lock',D/'sensitivity.lock',R/'parallel_cpu_20261031'/'auxiliary.lock',W/'wave_mesh_comparison.lock']
BUDGET=10500

def journal(name,entry):
 with (R/name).open('a',encoding='utf-8') as f:f.write(json.dumps(dict(at=rt.now(),**entry),ensure_ascii=False)+'\n')

def preflight():
 now=datetime.now().astimezone();authorization=rt.read(D/'authorization.json');deadline=datetime.fromisoformat(authorization['until_local'])
 assert (deadline-now).total_seconds()>BUDGET+300,'Insufficient authorized time'
 assert authorization.get('one_GPU_only') is True and authorization.get('originals_immutable') is True
 plan=rt.read(R/'plan.json');assert rt.sha(R/'AUTONOMOUS_RECOVERY_PROMPT.md')==plan['recovery_policy']['runbook_sha256'],'Runbook SHA mismatch'
 assert rt.resource_problem() is None,rt.resource_problem()
 assert not any(p.exists() for p in (D/'STOP',D/'STOP_ALL',P/'STOP',P/'STOP_ALL',OUT/'STOP')),'Explicit user STOP/pause'
 assert not OUT.exists(),'Attempt already exists; inspect instead of relaunching'
 assert not any(lock.exists() for lock in LOCKS+EXTRA_LOCKS),'Another solver/audit owns locks'
 procs=rt.guard.processes();assert not any(name.lower().startswith(('starccm+','star-ccm+','mpiexec')) for parent,name in procs.values()),'Existing STAR/MPI process'
 assert rt.read(F/'campaign_hold.json').get('active') is True,'Historical campaign hold changed'
 review=rt.read(D/'forcing_review.json');assert review.get('status')=='INCONCLUSIVE_NOT_ACCEPTED'
 assert review.get('ready_for_matched_sensitivity') is False,'Scientific branch changed; re-review control need'
 assert review.get('sources_unchanged') is True and review['observed_wave_configuration']['wave_object_heavy_density_kg_m3']!=review['observed_wave_configuration']['inherited_calm_heavy_density_kg_m3']
 compile_info=rt.read(D/'h0_control_compile.json');assert compile_info.get('status')=='javac_pass'
 assert rt.sha(MACRO)==compile_info['macro_sha256'] and (D/'compiled_h0_control'/'macro'/'M13NearZeroControl.class').exists()
 assert SOURCE.is_file() and SOURCE.stat().st_size>400000000
 done=rt.read(SOURCE.parent/'completed.json');stage=rt.read(SOURCE.parent/'stage_result.json');ev=rt.read(SOURCE.parent/'project_primary_evidence.json')
 assert stage.get('exit_code')==0 and stage.get('source_unchanged') is True and stage.get('controller_reason')=='project_primary_two_passes'
 assert ev.get('raw_independently_recomputed') is True and len(ev.get('checks_s',[]))==2
 assert abs(done.get('time_s',0)-3.8992)<1e-7
 digest=rt.sha(SOURCE);saved_identity=rt.read(P/'M13_GPU_W20_H050_pilot_20261031_r2'/'source_identity.json')
 assert digest==saved_identity.get('sha256'),'Calm source differs from successful wave lineage'
 gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=12,creationflags=subprocess.CREATE_NO_WINDOW)
 assert gpu.returncode==0,'GPU query failed';free,load,temp=[int(v.strip()) for v in gpu.stdout.splitlines()[0].split(',')]
 assert free>=4000 and load<45 and temp<85,'GPU reserve/load/temperature guard'
 return {'checked_at':rt.now(),'source':str(SOURCE),'source_sha256':digest,'macro_sha256':rt.sha(MACRO),'cells':309441,'GPU':1,'dt_s':.0004,'inner':10,'H_m':.000001,'lambda_m':20,'gpu_free_mib':free,'gpu_temperature_C':temp,'max_steps':10000,'max_added_physical_s':4.0,'max_wall_s':BUDGET,'review_status_preserved':review['status'],'purpose':'Matched near-zero wave BC control from saved M13 calm; no whole-domain reset; only wave height differs from M13 incident-wave setup'}

def analyze():
 rows=rt.rows(OUT/'history.csv');done=rt.read(OUT/'completed.json');last=rows[-1] if rows else {}
 assert rows and int(last['step'])>=1 and abs(float(last['time_s'])-float(done['time_s']))<1e-7
 assert (OUT/'wave_pilot_final.sim').stat().st_size>400000000
 baseline=rt.rows(SOURCE.parent/'history.csv');bt=float(baseline[-1]['physical_time_s']);b=[r for r in baseline if bt-.2+1e-8<float(r['physical_time_s'])<=bt+1e-8]
 assert len(b)==500
 base={k:statistics.fmean(float(r[k]) for r in b) for k in ('CL','CD')}
 checks=[]
 f=OUT/'control_settling_checks.jsonl'
 if f.exists():checks=[json.loads(line) for line in f.read_text(encoding='utf-8').splitlines() if line.strip()]
 eligible=[v for v in checks if v.get('eligible_after2p4s')][-2:];verified=len(eligible)==2 and abs(eligible[-1]['time_s']-eligible[0]['time_s']-.2)<1e-7
 raw=[]
 for check in eligible:
  t=check['time_s'];metrics={}
  for key in ('CL_hydrodynamic','CD_total'):
   windows=[]
   for a,bnd in ((t-.4,t-.2),(t-.2,t)):
    vals=[float(r[key]) for r in rows if a+1e-8<float(r['time_s'])<=bnd+1e-8]
    assert len(vals)==500 and all(math.isfinite(v) for v in vals),'Incomplete raw control window'
    windows.append((statistics.fmean(vals),statistics.pstdev(vals)))
   (m0,s0),(m1,s1)=windows;delta=100*abs(m1-m0)/abs(m1);r0=100*s0/abs(m0);r1=100*s1/abs(m1)
   ok=max(delta,r0,r1)<.5;verified=verified and ok
   metrics[key]={'mean':m1,'shift_pct':delta,'rms_previous_pct':r0,'rms_latest_pct':r1,'pass':ok}
  raw.append({'time_s':t,'metrics':metrics})
 end=float(last['time_s']);tail=[r for r in rows if end-.2+1e-8<float(r['time_s'])<=end+1e-8]
 cl=statistics.fmean(float(r['CL_hydrodynamic']) for r in tail);cd=statistics.fmean(float(r['CD_total']) for r in tail)
 return {'at':rt.now(),'saved':True,'control_primary_settled_raw':bool(verified and done['status']=='control_primary_settled'),'time_s':end,'steps':int(last['step']),'CL_hydrodynamic':cl,'CD_total':cd,'baseline':base,'delta_CD_control_minus_original_calm':cd-base['CD'],'delta_CL_control_minus_original_calm':cl-base['CL'],'raw_checks':raw,'window_s':.2,'finite_tiny_H_is_not_exact_zero':True,'forcing_or_BC_equivalence_accepted':False,'sensitivity_gate_unchanged':True,'requires_scientific_review':True,'interpretation':'Control shift may include both BC changes and residual continued calm relaxation; not proof of a unique mechanism'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--preflight-only',action='store_true');ap.add_argument('--run',action='store_true');args=ap.parse_args();check=preflight()
 if args.preflight_only:print(json.dumps(dict(check,preflight='PASS',solver_started=False)),flush=True);return
 assert args.run,'Explicit --run required';token=uuid.uuid4().hex;owned=[]
 try:
  for lock in LOCKS:
   with lock.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'at':rt.now(),'token':token,'case':'M13_matched_nearzero_control','directory':str(OUT)},f)
   owned.append(lock)
  OUT.mkdir(exist_ok=False);rt.write(OUT/'approved_experiment.json',check)
  rt.write(D/'h0_control_state.json',{'status':'starting','at':rt.now(),'directory':str(OUT),'controller_pid':os.getpid()})
  stage=rt.read(D/'stage_state.json');stage.update(at=rt.now(),stage='B_nearzero_control_starting',implementation_in_progress=False,h0_control_directory=str(OUT),sensitivity_started=False)
  rt.write(D/'stage_state.json',stage)
  journal('attempts.jsonl',{'event':'approved_M13_nearzero_control_launch','directory':str(OUT),'source_sha256':check['source_sha256'],'GPU':1,'dt_s':.0004,'H_m':.000001,'real_steps_confirmed':False,'retry':False})
  env={'NTNU_M13_WAVE_OUT':str(OUT),'NTNU_M13_WAVE_DT':'.0004','NTNU_M13_WAVE_STEPS':'10000','NTNU_M13_WAVE_INNER':'10','NTNU_M13_WAVE_BUDGET':'10000'}
  _,result=rt.stage(OUT,SOURCE,MACRO,env=env,workers=1,gpu=True,mask=240,budget_s=BUDGET,protect_main=False,phase='M13_matched_nearzero_control')
  assert not (OUT/'macro_error.json').exists(),'Macro error; not success despite exit0'
  done=rt.read(OUT/'completed.json');assert done.get('status') in ('control_primary_settled','target_reached','wall_budget')
  report=analyze();rt.write(OUT/'control_result.json',report);rt.write(D/'h0_control_result.json',report)
  rt.write(D/'h0_control_state.json',{'status':'saved_pending_scientific_review','at':rt.now(),'directory':str(OUT),'source_unchanged':result['source_unchanged']})
  stage=rt.read(D/'stage_state.json');stage.update(at=rt.now(),stage='B_nearzero_control_saved_review_required');rt.write(D/'stage_state.json',stage)
  journal('decisions.jsonl',{'event':'M13_nearzero_control_saved','directory':str(OUT),'steps':done['steps'],'time_s':done['time_s'],'control_primary_settled_raw':report['control_primary_settled_raw'],'Q_control':report['delta_CD_control_minus_original_calm'],'forcing_gate_promoted':False})
  print(json.dumps({'event':'M13_nearzero_saved','steps':done['steps'],'time_s':done['time_s'],'Q_control':report['delta_CD_control_minus_original_calm']}),flush=True)
 except BaseException as ex:
  if OUT.exists():
   (OUT/'STOP').touch();rt.write(OUT/'experiment_error.json',{'at':rt.now(),'error':rt.guard.redact(str(ex))[:650],'no_automatic_retry':True})
   rt.write(D/'h0_control_state.json',{'status':'requires_review','at':rt.now(),'directory':str(OUT)})
  raise
 finally:
  pid=rt.read(OUT/'process.json').get('pid') if OUT.exists() else None
  if not pid or not rt.guard.alive(pid):
   for lock in reversed(owned):
    if rt.read(lock).get('token')==token:lock.unlink()
if __name__=='__main__':main()
