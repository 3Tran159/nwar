"""Fail-closed C01 comparability gate. Derived data only; never alters CFD or raw evidence."""
from pathlib import Path
import json,math,hashlib
HERE=Path(__file__).parent;ROOT=HERE.parent
OLD=ROOT/'M13_farfield15_20261031'/'M13_GPU_calm_dt0004'
REQUIRED=('material_densities','wave_function_densities','force_normalization','reference_pressure','current_and_waterlevel','gravity_and_turbulence','mesh_and_geometry','boundary_and_forcing','dt_and_inner_iterations','zero_wave_limit','raw_primary_settling','physical_guards')
def read(path):
 try:
  v=json.loads(Path(path).read_text(encoding='utf-8-sig'));return v if isinstance(v,dict) else {}
 except (OSError,ValueError):return {}
def accepted():
 review=read(HERE/'C01_reference_review.json')
 if review.get('status')!='accepted_matched_reference' or review.get('comparison_allowed') is not True:return {},{},review
 if not all(review.get('compatibility_proofs',{}).get(k) is True for k in REQUIRED):return {},{},review
 try:
  p=Path(review['source_run']);p.resolve().relative_to(ROOT.resolve())
  if p.resolve()==OLD.resolve():return {},{},review
  receipt=read(p/'stage_result.json');done=read(p/'completed.json')
  result=read(p/'C01_result.json') or read(p/'control_result.json') or read(p/'project_primary_evidence.json')
  if receipt.get('exit_code')!=0 or receipt.get('source_unchanged') is not True or not done:return {},{},review
  if not (result.get('control_primary_settled_raw') is True or result.get('project_primary_pass') is True or result.get('project_primary_settled') is True):return {},{},review
  raw=p/'history.csv'
  if hashlib.sha256(raw.read_bytes()).hexdigest()!=review['history_sha256']:return {},{},review
  ref=review['reference'];values=[float(ref[k]) for k in ('CL','CD','dt_s')]
  if not all(math.isfinite(x) for x in values) or values[2]<=0 or not review.get('compatible_run_ids'):return {},{},review
  if not any((p/name).is_file() for name in ('final.sim','wave_pilot_final.sim')):return {},{},review
  return dict(ref,source=str(p),verified_for_wave_comparison=True),review.get('primary_certificate',{}),review
 except (OSError,KeyError,TypeError,ValueError):return {},{},review

def enforce(data):
 ref,cert,review=accepted();foil=data.get('foil_live',{})
 foil['reference_status']='accepted_matched_reference' if ref else 'pending_compatibility'
 foil['reference_review']=review
 foil['calm_reference']=ref;foil['calm_certification']=cert
 foil['calm_reference_archival_note']='Previous calm belongs to mesh study; retained in original archive, not a C01 wave reference.'
 for run in foil.get('runs',[]):
  applicable=bool(ref and run.get('id') in review.get('compatible_run_ids',[]) and abs(float(run.get('dt') or 0)-float(ref['dt_s']))<1e-12)
  run['calm_reference']=ref if applicable else {};run['calm_certification']=cert if applicable else {}
  run['reference_comparison_allowed']=applicable
  run['reference_status']='accepted_matched_reference' if applicable else 'pending_compatibility'
 diagnostic=foil.get('wave_diagnostics',{})
 for k in ('Q_CD','delta_CD_percent','delta_CL_percent'):diagnostic[k]=None
 diagnostic['calm_reference_exact']={}
 diagnostic['reference_comparison_status']='withheld_pending_matched_C01'
 diagnostic['historical_comparison_preserved_on_disk']=True
 return data
