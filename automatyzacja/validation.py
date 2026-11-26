"""Evidence-backed per-run verification. Scientific NWAR gates remain explicit."""
from common import *
from analysis import analyze,segment_chain
import numpy as np
import argparse
from project_results import acceptance,policy

def native_parent_links(entry, reference):
 parents=[];seen={entry['id']};child=entry
 while child.get('spec',{}).get('native_recovery'):
  recovery=child['spec']['native_recovery'];parent=job(recovery['parent_id'])
  if parent['id'] in seen or parent['case_id']!=entry['case_id']:raise ValueError('Invalid native checkpoint lineage')
  source=Path(child['spec']['source'])
  if (not source.resolve().is_relative_to(Path(parent['folder']).resolve())
      or str(source)!=recovery['checkpoint'] or sha(source)!=recovery['sha256']):
   raise ValueError('Native continuation source differs from its parent checkpoint')
  seen.add(parent['id']);parents.append(parent);child=parent
 links=[]
 for parent in reversed(parents):
  folder=Path(parent['folder']);spec=parent['spec'];origin=read(folder/'source_identity.json')
  source=Path(spec['source']);actual=sha(source);stage=read(folder/'stage_result.json')
  ok=(bool(spec.get('native_recovery')) or source.resolve()==reference.resolve())
  ok &= (origin.get('path') is not None and Path(origin['path']).resolve()==source.resolve()
         and origin.get('sha256')==actual==spec['source_sha']
         and stage.get('source_unchanged') is True and stage.get('ownership')=='windows_job_closed')
  links.append(dict(folder=str(folder),source=str(source),expected_sha256=spec['source_sha'],
                    actual_sha256=actual,ok=bool(ok),native_checkpoint_segment=True))
 return links

def lookup(id):
 if id in EXISTING:return dict(id=id,case_id=id,folder=str(EXISTING[id]),status='completed',legacy=True)
 from report import external_runs
 found=next((j for j in external_runs() if j['id']==id),None)
 return found or job(id)

def validate(entry,result=None,data=None):
 # A worker already calculating may still hold the previous analysis module.
 # Refresh derived analysis at final verification, without touching STAR.
 import analysis,importlib
 from cycle_policy import POLICY_ID
 if getattr(analysis,'CYCLE_POLICY_ID',None)!=POLICY_ID:importlib.reload(analysis)
 if result is not None and result.get('cycles',{}).get('cycle_policy_id')!=POLICY_ID:result=None;data=None
 id=entry['id'];folder=Path(entry['folder']);spec=entry.get('spec',{});checks=[]
 def add(key,title,status,criterion,values=None,files=None,group='run'):
  checks.append(dict(id=key,title=title,status=status,criterion=criterion,values=values or {},evidence_files=[str(p) for p in (files or [])],group=group))
 def status(ok,available=True):return ('passed' if ok else 'failed') if available else 'pending'
 def digest(p):return sha(p) if Path(p).is_file() else None
 try:
  case=next(c for c in catalog() if c['id']==entry['case_id'])
  chain=[folder] if entry.get('legacy') else [Path(spec['parent_folder']),folder] if entry.get('external') else segment_chain(entry)
  if result is None:result,data,_=analyze(case,chain)
  done=read(folder/'completed.json');stage=read(folder/'stage_result.json');macro_error=read(folder/'macro_error.json')
  native_complete=False
  if spec.get('native_production'):
   from native_production import native_completion_verified
   native_complete=native_completion_verified(folder)
  add('solver','Solver completion',status((stage.get('exit_code')==0 or native_complete) and not macro_error,bool(stage)), 'Clean exit or independently verified native target completion; final checkpoint saved, no macro error.',dict(exit_code=stage.get('exit_code'),native_completion_verified=native_complete,stop_reason=done.get('status'),macro_error=macro_error),[folder/'stage_result.json',folder/'completed.json',folder/'native_completion_review.json'] if spec.get('native_production') else [folder/'stage_result.json',folder/'completed.json'])
  final=folder/('wave_pilot_extended_final.sim' if entry.get('external') else 'wave_pilot_final.sim')
  if entry.get('legacy'):
   receipt_file=NIGHT/'W01_four_cycle_review.json' if id=='W01' else folder/'four_cycle_independent_review.json'
   receipt=read(receipt_file);expected=receipt.get('final_sim_SHA256')
  elif entry.get('external'):
   receipt_file=DATA/'validations'/(id+'.json');old=read(receipt_file)
   expected=next((x.get('values',{}).get('actual_sha256') for x in old.get('checks',[]) if x['id']=='checkpoint'),None)
  else:
   receipt_file=folder/'final_integrity.json';expected=read(receipt_file).get('sha256')
  actual=digest(final);large=final.is_file() and final.stat().st_size>400_000_000
  ck_ok=bool(large and actual and (actual==expected if expected else entry.get('external') and stage.get('exit_code')==0 and stage.get('source_unchanged') is True))
  add('checkpoint','Checkpoint integrity',status(ck_ok,bool(done and actual)), 'SHA-256 matches the receipt; the first external checkpoint review records its fingerprint after a clean solver exit.',dict(actual_sha256=actual,expected_sha256=expected,bytes=final.stat().st_size if final.exists() else None,first_external_snapshot=bool(entry.get('external') and not expected)),[final,receipt_file])
  if entry.get('legacy'):source=SOURCE;source_expected=SOURCE_SHA
  elif entry.get('external'):
   pre=read(folder/'resume_preflight.json');source=Path(pre.get('source',''));source_expected=pre.get('source_sha256')
  else:source=Path(spec['source']);source_expected=spec['source_sha']
  source_actual=digest(source)
  source_ok=source_actual==source_expected and bool(source_expected) and stage.get('source_unchanged') is True
  add('source','Unchanged source checkpoint',status(source_ok,bool(stage)), 'The source checkpoint retains its approved SHA-256 before and after calculation.',dict(expected_sha256=source_expected,actual_sha256=source_actual,source_unchanged=stage.get('source_unchanged')),[source,folder/'stage_result.json'])
  profile=spec.get('mesh_profile');profile_ok=False
  if profile:
   from wave_profiles import verify_spec
   verify_spec(entry['case_id'],spec);profile_ok=True
  links=[];previous=SOURCE;lineage_ok=True
  if profile:
   from pre_w04 import PRE,calm_folders
   from pre_lineage import prepared_lineage
   prepared=read(Path(profile.get('calm_receipt',PRE/'calm_receipt.json')))
   previous,lineage_ok,links=prepared_lineage(prepared,prepared.get('history_folders',calm_folders()),digest)
  if spec.get('native_recovery'):
   native_links=native_parent_links(entry,previous)
   links.extend(native_links);lineage_ok &= bool(native_links) and all(link['ok'] for link in native_links)
   previous=Path(spec['source'])
  lineage_chain=chain
  if spec.get('imported_native_continuation'):
   from imported_native_resume import verify
   imported=verify(spec)
   lineage_ok &= imported['health_ok'] is True
   links.append(dict(folder=imported['folder'],source=str(previous),expected_sha256=imported['sha256'],actual_sha256=spec['source_sha'],ok=True,verified_imported_checkpoint=True,original_C01_sha256=SOURCE_SHA))
   previous=Path(spec['source'])
   lineage_chain=chain[len(spec['parent_segments']):]
  for part in lineage_chain:
   origin=read(part/'source_identity.json');actual_parent=digest(previous)
   recovered=None
   if (part/'checkpoint_recovery.json').exists():
    from checkpoint_recovery import verify
    recovered=verify(part/'checkpoint_recovery.json')
   unchanged=read(part/'stage_result.json').get('source_unchanged') is True or bool(recovered and recovered.get('original_source_unchanged'))
   ok=bool(origin.get('path') and Path(origin['path']).resolve()==previous.resolve() and origin.get('sha256')==actual_parent and unchanged)
   links.append(dict(folder=str(part),source=origin.get('path'),expected_sha256=origin.get('sha256'),actual_sha256=actual_parent,ok=ok));lineage_ok &= ok
   if recovered:
    previous=Path(recovered['checkpoint'])
    links[-1]['explicit_diagnostic_recovery']=dict(original_folder=recovered['original_folder'],original_exit_code=recovered.get('original_exit_code'),checkpoint=str(previous),time_s=recovered['time_s'],raw_history_preserved=True)
   else:previous=part/('wave_pilot_extended_final.sim' if (part/'wave_pilot_extended_final.sim').exists() else 'wave_pilot_final.sim')
  from calm_reference import reference_for
  calm_receipt=reference_for(entry,verify=True)
  lineage_ok &= bool(links and (profile_ok and digest(SOURCE)==SOURCE_SHA if profile else links[0]['actual_sha256']==SOURCE_SHA) and calm_receipt.get('project_primary_settled'))
  add('c01_lineage','Accepted C01 reference and source provenance',status(lineage_ok,bool(done)), 'Verified saved calm reference and source chain; historical original C01 remains unchanged.',dict(reference_id=calm_receipt['reference_id'],C01_sha256=calm_receipt['checkpoint_sha256'],original_C01_sha256=SOURCE_SHA,links=links),[p/'source_identity.json' for p in chain]+[Path(profile['calm_receipt']) if profile else CALM/'C01_final_acceptance_20261101.json'])
  if profile:
   add('pre_w04','PRE W04: expanded mesh and accepted calm reference',status(profile_ok,bool(done)), 'Protected foil mesh and expanded wave band passed; two consecutive CL/CD stability checks <0.5% in adjacent 0.2 s windows. Original C01 compatibility is required unless a replacement reference was explicitly accepted.',prepared,[Path(profile['calm_receipt']),ROOT/'nwar_automation_20261102/mesh_W04_20261102/protected_receipt.json'])
  mesh_catalog=read(ROOT/'results_catalog/mesh_comparison.json')
  reviewed=[{k:m.get(k) for k in ('mesh','cells','dt_s','accepted')} for m in mesh_catalog.get('runs',[]) if m.get('group')=='current']
  mesh_ok=any(m['mesh']=='M13' and m['accepted'] is True for m in reviewed)
  add('mesh_prior','M13 mesh reviewed before C01',status(mesh_ok,bool(reviewed)), 'The prior M10–M13 review and accepted M13 mesh remain valid. A new mesh study is not required at this stage.',dict(previous_mesh_review=reviewed),[ROOT/'results_catalog/mesh_comparison.json'])
  setups=[read(p/'wave_setup_audit.json') for p in chain];setup=next((s for s in reversed(setups) if s),{})
  dt=setup.get('dt_s');H=setup.get('H_m');L=setup.get('lambda_m')
  expected_cells=profile['cells'] if profile else 309441
  config_ok=setup.get('cells')==expected_cells and dt==.0004 and H==case['H'] and abs((L or 0)-case['L'])<1e-7 and setup.get('global_initialization') is False
  if profile:config_ok &= setup.get('mesh_profile')==profile['id'] and setup.get('t0')==profile['wave_origin_s'] and setup.get('probe_distance_m')==profile['probe_distance_m']
  add('config','Mesh, wave and time step',status(config_ok,bool(setup)), 'Reviewed M13 profile: '+str(expected_cells)+' cells; Δt=0.0004 s; H and λ match the selected wave; no global initialization.',dict(cells=setup.get('cells'),dt_s=dt,H_m=H,lambda_m=L,requested_H_m=case['H'],requested_lambda_m=case['L'],global_initialization=setup.get('global_initialization'),mesh_profile=profile),[p/'wave_setup_audit.json' for p in chain if (p/'wave_setup_audit.json').exists()])
  densities=[read(p/'native_C01_rho_readback.json') for p in chain];rho=next((s for s in reversed(densities) if s),{})
  waves=[read(p/'wave_density_audit.json') for p in chain];wrho=next((s for s in reversed(waves) if s),{})
  density_ok=all(rho.get(k)==v for k,v in [('water_material_density',1000),('air_material_density',1.2),('Calm_heavy',1000),('Calm_light',1.2)]) and wrho.get('FifthOrder_water_rho')==1000 and wrho.get('FifthOrder_air_rho')==1.2
  add('density','Material, C01 and wave densities',status(density_ok,bool(rho and wrho)), 'Water 1000 kg/m³ and air 1.2 kg/m³ in all three settings.',dict(material_and_calm=rho,wave=wrho),[p/n for p in chain for n in ('native_C01_rho_readback.json','wave_density_audit.json') if (p/n).exists()])
  t=data.get('time_s',np.array([]));diff=np.diff(t)
  continuous=bool(len(t)>1 and np.isfinite(t).all() and np.all(abs(diff-.0004)<1e-7))
  endpoint=bool(done and len(t) and abs(t[-1]-done.get('time_s',-1))<1e-7)
  add('continuity','Time continuity and checkpoint endpoint',status(continuous and endpoint,bool(done and len(t)>1)), 'Positive 0.0004 s time step throughout the joined history; final time matches the saved checkpoint.',dict(samples=len(t),dt_min=float(diff.min()) if len(diff) else None,dt_max=float(diff.max()) if len(diff) else None,history_end_s=float(t[-1]) if len(t) else None,checkpoint_end_s=done.get('time_s'),segments=result['source_segments']),[p/'history.csv' for p in chain]+[folder/'completed.json'])
  norm={}
  for name,force,offset in [('CD_total','Fx_N',0),('CL_hydrodynamic','Fz_N',22.718189111947265)]:
   if name in data and force in data:norm[name+'_max_error']=number(float(np.max(abs(data[name]-(data[force]-offset)/3855.6))))
  add('normalization','CL and CD normalization',status(len(norm)==2 and all(v is not None and v<1e-10 for v in norm.values()),bool(norm)), 'CD=Fx/3855.6; CL_hydro=(Fz−22.718189111947265)/3855.6.',norm,[p/'history.csv' for p in chain])
  add('health','Numerical health and VOF',status(result['health']['ok'],bool(data)), 'CFL≤25; interface CFL≤2.2; speed≤50 m/s; α in [−10⁻⁵,1+10⁻⁵]; |p|≤10⁷ Pa; water-volume change≤0.8 m³; no NaN/Inf.',result['health'],[p/'history.csv' for p in chain])
  cy=result['cycles'];enough=cy['analyzed_count']==4 and cy['count']>=5
  add('cycles','Five measured cycles; evaluate cycles 2–5','passed' if enough else 'pending', 'Record 5 complete measured cycles. Exclude cycle 1 by position; retain cycles 2–5 without force-based selection.',{k:cy.get(k) for k in ('count','analyzed_count','discarded_cycle_numbers','analyzed_cycle_numbers','cycle_policy_id','phase_probe_x_m','phase_method','analysis_not_before_s','phase_level','period_measured_s','window')},[p/'gauges.csv' for p in chain])
  add('repeatability','Force and wave repeatability',status(cy['repeatable'],enough), 'Cycles 2–5: CL/CD mean spread<1%, amplitude spread<8%, phase RMS<5%; measured height 80–120% of H; probe level and drift within project limits.',dict(metrics=cy.get('metrics'),gauge_repeatable=cy.get('gauge_repeatable'),last_cycles=[{k:c[k] for k in ('number','start','end','CL_mean','CD_mean','H_measured','eta_mean')} for c in cy['analyzed_cycles']]),[p/'gauges.csv' for p in chain]+[p/'history.csv' for p in chain])
  for key,title,criterion in [
   ('forcing','Forcing near the foil and reflections','Direct verified export of wave forcing and quantitative reflection assessment.'),
   ('time_convergence','Time-step convergence of ΔCD','Matched calm/wave pair at a smaller Δt, using the same phase boundaries.'),
   ('formal_uncertainty','Quantitative uncertainty assessment','Optional future work after the trend analysis; the existing mesh review remains accepted.'),
   ('mass_closure','Mass-flux closure','Reconcile mass change with integrated boundary fluxes; water inventory alone is insufficient.')]:
   add(key,title,'future',criterion,dict(reason='Outside current stage criteria. Does not block acceptance or Q.'),group='future')
  outcome,project_accepted=acceptance(checks,spec.get('smoke',0))
  if spec.get('short_wave_diagnostic'):
   project_accepted=False
  receipt=dict(id=id,case_id=entry['case_id'],generated_at=now(),run_verification=outcome,project_accepted=project_accepted,qualitative_NWAR_accepted=project_accepted,scientific_NWAR_accepted=False,policy_id=policy()['id'],scope=policy()['scope'],smoke=spec.get('smoke',0),checks=checks,counts={s:sum(c['status']==s for c in checks) for s in ('passed','failed','pending','future')},required_counts={s:sum(c['status']==s for c in checks if c['group']=='run') for s in ('passed','failed','pending')})
 except Exception as ex:
  receipt=dict(id=id,case_id=entry['case_id'],generated_at=now(),run_verification='failed',scientific_NWAR_accepted=False,error=str(ex),checks=checks)
 write(DATA/'validations'/(id+'.json'),receipt)
 return receipt

def main():
 p=argparse.ArgumentParser();p.add_argument('--id',required=True);args=p.parse_args()
 print(json.dumps(validate(lookup(args.id)),ensure_ascii=True))
if __name__=='__main__':main()
