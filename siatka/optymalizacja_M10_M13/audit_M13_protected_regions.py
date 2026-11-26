"""Reuse reviewed read-only topology auditor on M10 and M13, no original writes."""
from pathlib import Path
import sys,json,hashlib
D=Path(r'E:\ntnu_mesh_optimization_20261030\M13_farfield15_20261031')
S=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030')
sys.path.insert(0,r'F:\ntnu\mesh_screening_20261028\quasi2d_012_20261029\deps311')
import numpy as np
out=D/'protected_audit';out.mkdir(exist_ok=True)
paths={'M10':S/'handoff/mesh_star_export.CGNS','M13':D/'geometry/mesh.CGNS'}
assert all(p.is_file() for p in paths.values())
source=(S/'audit_family.py').read_text(encoding='utf-8').split("nominal={'W01a':48",1)[0]
old="(HERE/'gci_w01a_20261030/handoff/mesh_star_export.CGNS') if mesh=='W01a' else HERE/'gci_w01a_20261030'/mesh/'mesh.CGNS'"
assert source.count(old)==2
source=source.replace(old,'PATHS[mesh]')
old="OUT=HERE/'gci_w01a_20261030'/'family_audit';OUT.mkdir(exist_ok=True)"
assert source.count(old)==1
source=source.replace(old,'OUT=DEST;OUT.mkdir(exist_ok=True)')
# Function definitions only; the original family-comparison driver is not executed.
space={'__file__':str(S/'audit_family.py'),'PATHS':paths,'DEST':out}
exec(compile(source,'audited_geometry_functions','exec'),space)
results={}
for mesh in ('M10','M13'):
 results[mesh]=space['audit'](mesh,48);results[mesh]['topology']=space['topology'](mesh)
 columns=json.loads((out/(mesh+'_wall_columns.json')).read_text(encoding='utf-8'))
 length=results[mesh]['foil_perimeter_m']
 results[mesh]['nominal_prism_coverage']=sum(r['length_m'] for r in columns if r['layers']>=48)/length
 results[mesh]['any_prism_coverage']=sum(r['length_m'] for r in columns if r['layers']>=1)/length
 (out/(mesh+'_summary.json')).write_text(json.dumps(results[mesh],indent=2),encoding='utf-8')
a,b=results['M10'],results['M13'];t=b['topology']
first_ratio=b['midchord_height_stats']['0']['median_m']/a['midchord_height_stats']['0']['median_m']
tangent=[]
for k in a['matched_wall_samples']:
 if k in b['matched_wall_samples']:tangent.append(np.array(b['matched_wall_samples'][k]['heights_m'])/np.array(a['matched_wall_samples'][k]['heights_m']))
ratio=np.array(tangent)
gates={'one_cell_span':t['single_layer_topology'],'paired_planes':t['max_xz_mismatch_m']<1e-10 and t['plane_error_m']<1e-10,
 'same_bounds':a['bounds_m']==b['bounds_m'],'same_fluid_area':abs(a['total_fluid_section_area_m2']/b['total_fluid_section_area_m2']-1)<1e-5,
 'first_layer_preserved':abs(first_ratio-1)<.02,
 'prism_layers_not_degraded':b['nominal_prism_coverage']>=a['nominal_prism_coverage']-.001,
 'protected_wall_grading':bool(np.all(np.abs(np.median(ratio,axis=0)-1)<.10))}
answer={'pass':all(gates.values()),'gates':gates,'cells_M10':a['cells'],'cells_M13':b['cells'],
 'first_layer_median_ratio':first_ratio,'coverage_M10':a['nominal_prism_coverage'],'coverage_M13':b['nominal_prism_coverage'],
 'wall_grading_median_ratios':np.median(ratio,axis=0).tolist(),'scope':'Geometry and protected prism topology only; no solver acceptance or new GCI'}
(out/'protected_regions_pass.json').write_text(json.dumps(answer,indent=2),encoding='utf-8')
print(json.dumps(answer))
if not answer['pass']:raise SystemExit(2)
