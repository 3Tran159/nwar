from pathlib import Path
import sys,json,datetime,math,hashlib
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE/'.deps'))
import numpy as np
OUT=HERE/'gci_audit_20261030';A=json.loads((OUT/'geometry_audit.json').read_text())
Q=Path(r'F:\ntnu\mesh_screening_20261028\quasi2d_012_20261029');R=Q.parent/'force_stabilization_20261029'
BANDS=[(0,.0001),(.0001,.001),(.001,.005),(.005,.01)]
def mean_spacing(col,lo,hi):
 edges=np.array([0]+col['distances_m']);h=np.array(col['heights_m']);assert np.all(np.diff(edges)>0)
 overlap=np.maximum(0,np.minimum(edges[1:],hi)-np.maximum(edges[:-1],lo));assert abs(overlap.sum()-(hi-lo))<1e-10
 return float((overlap*h).sum()/(hi-lo))
colstats={};checks={}
for m,n in [('M04',40),('M06',44),('M07',48)]:
 rows=json.loads((OUT/(m+'_wall_columns.json')).read_text());rr=[r for r in rows if r['layers']>=n and .05<r['x_c']<.95]
 colstats[m]={f'{lo:g}-{hi:g}':float(np.median([mean_spacing(c,lo,hi) for c in rr])) for lo,hi in BANDS}
 q=json.loads((Q/m/'measurement.json').read_text(encoding='utf-8-sig'))['metrics'];top=json.loads((Q/m/'topology_audit.json').read_text(encoding='utf-8-sig'))
 assert q['cell_count']==A['meshes'][m]['cells']==top['cells'];assert all(q[k]==0 for k in ['NegativeVolumeCells','UnclosedCells','DegeneratedFeCells']);assert top['single_layer_topology'] and top['max_target_source_xz_displacement_m']==0
 checks[m]={'cells':q['cell_count'],'invalid_cells':0,'single_span_layer':True,'exact_span_translation':True,'midchord_full_columns':len(rr),'total_quad_thickness_median_m':float(np.median([c['distances_m'][n-1] for c in rr])),'measured_height_growth_median':float(np.median([np.median(np.array(c['heights_m'][1:n])/np.array(c['heights_m'][:n-1])) for c in rr]))}
 assert abs(checks[m]['total_quad_thickness_median_m']-.01546)<1e-4
pairs={f'{a}/{b}':{k:colstats[a][k]/colstats[b][k] for k in colstats[a]} for a,b in [('M04','M06'),('M06','M07')]}
restarts={}
for m,folder in {'M04':'temporal_order_20261029/T04_M04_SO_dt1ms_inner10_r1','M06':'M06_until_settled_r1','M07':'configured_mesh_20261029/M07_SO1ms_inner10_r1','M09':'matched_endpoint_20261029/M09_SO_common_t2040_r1'}.items():
 p=R/folder;s=json.loads((p/'setup.json').read_text(encoding='utf-8-sig'));done=json.loads((p/'completed.json').read_text(encoding='utf-8-sig'));assert (p/'final.sim').is_file()
 restarts[m]={'path':str(p/'final.sim'),'bytes':(p/'final.sim').stat().st_size,'time_s':done['time_s'],'time_order':s['order'],'dt_s':s['dt_s'],'inner':s['inner_iterations'],'cells':s['cells']}
A.update({'band_average_cell_heights_m':colstats,'band_average_spacing_ratios':pairs,'independent_quality_and_layer_checks':checks,'saved_restarts':restarts,'launch_decision':'not_eligible_for_planned_single_h_GCI','six_requested_runs_launched':False,'reason':'Near-wall first-cell ratio is approximately 1.4, while cell spacing deeper through most of the prism thickness barely refines. Distance-averaged spacing over finite bands confirms the mismatch; not merely a cell-boundary sampling artifact. A single scalar h does not represent this strongly nonuniform directional refinement adequately for the proposed whole-solution GCI. Existing meshes remain usable for mesh sensitivity, but formal GCI needs a redesigned systematic wall-normal family or separately quantified directional errors.','scope':'Pre-run mesh family audit only. No new solver process, queue mutation, mesh edit, or human-readable report. No claim that these meshes are invalid for CFD or that any possible directional verification is impossible.','criterion_source':'ITTC 7.5-03-01-01 rev05 (2024), section3.3, pp7-8: systematic relationship and nearly constant local refinement ratio; numerical suitability assessed separately from mesh validity.','completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
(OUT/'geometry_audit.json').write_text(json.dumps(A,indent=2),encoding='utf-8')
print(json.dumps({'checks':checks,'band_average_ratios':pairs,'restart_summary':{m:{k:v for k,v in d.items() if k not in ['path','bytes']} for m,d in restarts.items()},'decision':A['launch_decision'],'runs_launched':False},indent=2))
