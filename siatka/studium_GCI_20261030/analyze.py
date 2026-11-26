from pathlib import Path
import json,csv,statistics,hashlib,math
ROOT=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
OUT=Path(__file__).resolve().parent
KEYS=['CD','CL_total','pressure_drag_N','viscous_drag_N']
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return [{k:float(v) for k,v in x.items() if k and v} for x in csv.DictReader(f)]
def stats(rr,lo=1.84,hi=2.04):
 s=[r for r in rr if lo+1e-8<r['physical_time_s']<=hi+1e-8]
 return {'n':len(s),'start':s[0]['physical_time_s'],'end':s[-1]['physical_time_s'],'mean':{k:statistics.mean(r[k] for r in s) for k in KEYS},'range':{k:[min(r[k] for r in s),max(r[k] for r in s)] for k in KEYS}}
matched=read(ROOT/'matched_endpoint_results.json'); result={'matched':matched,'cases':{},'manifest':[]}
files=['matched_endpoint_results.json','selected_mesh_time_results.json','selected_mesh_decision.json','mesh_definition_evidence.json','M09_candidate_design.json','mesh_refinement_eligibility_review.json','mesh_convergence.json','configured_wall_yplus_audit.json','configured_mesh_diagnostic_audit.json','calm_solver_configuration_decision.json','refinement_relation_check.json']
for name in files:
 p=ROOT/name;result[name[:-5]]=read(p);result['manifest'].append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for m in matched['results']:
 p=Path(m['combined_history']); rr=rows(p); st=stats(rr)
 assert st['n']==200
 assert all(abs(st['mean'][k]-m['means'][k])<1e-12 for k in KEYS)
 earlier=stats(rr,1.64,1.84)
 st['drift_pct']={k:100*(st['mean'][k]-earlier['mean'][k])/abs(earlier['mean'][k]) for k in KEYS}
 st['curve']=[{k:r[k] for k in ['physical_time_s']+KEYS} for r in rr if 1.64+1e-8<r['physical_time_s']<=2.04+1e-8]
 result['cases'][m['mesh']]=st
 result['manifest'].append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for i in range(2,10):
 mesh=f'M{i:02}';p=ROOT.parent/'quasi2d_012_20261029'/mesh
 result.setdefault('quality',{})[mesh]=read(p/'measurement.json')['metrics']
 result.setdefault('topology',{})[mesh]=read(p/'topology_audit.json')
 for fn in ['measurement.json','topology_audit.json']:result['manifest'].append({'path':str(p/fn),'sha256':hashlib.sha256((p/fn).read_bytes()).hexdigest()})
t=read(ROOT/'selected_mesh_time_results.json');p=Path(t['source_sim']).parent/'history.csv';st=stats(rows(p));assert st['n']==400
assert all(abs(st['mean'][k]-t['half_step_means'][k])<1e-12 for k in KEYS)
result['half_step_check']=st;result['manifest'].append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'means_recomputed':True,'half_step_recomputed':True,'cases':{k:{a:b for a,b in v.items() if a!='curve'} for k,v in result['cases'].items()},'quality':{k:{a:v for a,v in m.items() if a in ['cell_count','min_cell_quality','max_skewness_angle_deg','min_face_validity','min_volume_change','NegativeVolumeCells','UnclosedCells','DegeneratedFeCells']} for k,m in result['quality'].items()},'topology':{k:{a:v for a,v in m.items() if a in ['single_layer_topology','max_target_source_xz_displacement_m']} for k,m in result['topology'].items()},'old_results':[{k:r.get(k) for k in ['id','cells','family','CD','CL_total','window_start_s','time_s']} for r in result['mesh_convergence']['settled_results']]},indent=2))
