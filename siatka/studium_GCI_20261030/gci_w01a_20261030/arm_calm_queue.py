from pathlib import Path
import json,py_compile
O=Path(__file__).resolve().parent
assert json.loads((O/'calm_cpu_smoke_result.json').read_text())['pass_check']
p=O/'cpu_calm_study.py';t=p.read_text()
old=" state('waiting_for_calm_geometry_and_mapping_audit')"
new=""" if not read(O/'calm_cpu_smoke_result.json')['pass_check']:raise RuntimeError('Calm CPU preflight did not pass')
 state('waiting_for_calm_geometry_and_mapping_audit')"""
assert t.count(old)==1;t=t.replace(old,new)
old=" control_start=summaries['G10_F']['time_s'];common=sources['G10_F'];controls={}"
new=""" if not any('GCI_fine_abs' in estimates[k] and noise[k]['pass'] and not estimates[k]['order_caution'] for k in a.KEYS):
  for k in estimates:
   if 'GCI_fine_abs' in estimates[k]:estimates[k]['status']='not_verified_spatial_noise_or_order_review_required'
  write(O/'gci_results.json',dict(status='calm_mesh_screen_completed_GCI_not_resolved',cells=cells,dt_s=dt,summaries=summaries,spatial_noise=noise,GCI=estimates,controls_run=False,reason='No quantity has a resolved plausible monotonic grid trend with sufficiently small settling uncertainty; additional time-step controls would not establish GCI.',scope='Calm water only; no wave accuracy claim',source=original,gpu=False))
  state('calm_mesh_screen_completed_GCI_needs_review',verified_quantities=[],controls_skipped_to_avoid_uninformative_cost=True);return
 control_start=summaries['G10_F']['time_s'];common=sources['G10_F'];controls={}"""
assert t.count(old)==1;t=t.replace(old,new);p.write_text(t)
py_compile.compile(str(p),doraise=True)
p=O/'cpu_study.py';t=p.read_text();old="if __name__=='__main__':\n"
assert t.count(old)==1
if not (O/'cpu_wave_study_superseded.py.txt').exists():(O/'cpu_wave_study_superseded.py.txt').write_text(t)
t=t.replace(old,old+" raise RuntimeError('Wave GCI superseded by user: use cpu_calm_study.py for calm-only CPU verification')\n")
p.write_text(t);py_compile.compile(str(p),doraise=True)
print('Calm CPU queue verified. Direct launch of superseded wave queue disabled.')
