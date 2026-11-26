from pathlib import Path
import json,datetime
E=Path(r'E:\ntnu_mesh_optimization_20261030');W=E/'wave_surface_only';F=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
def read(p):
 try:return json.loads(p.read_text(encoding='utf-8-sig'))
 except:return {}
print('TIME',datetime.datetime.now().astimezone().isoformat())
for p in sorted(W.rglob('*.json')):
 if any(k in p.name.lower() for k in ('state','queue','summary','result','completed','config','manifest','progress')) and p.stat().st_mtime>1793440000:
  if any(k in str(p).lower() for k in ('compiled','compilecheck','audit_saved')):continue
  x=read(p)
  if isinstance(x,dict):
   desc={k:x[k] for k in ('status','stage','directory','case','case_id','dt_s','time_s','steps','stage_index','total','completed','queue','cases','mesh','mesh_id','cells','target_s','workers','star_pid','pid') if k in x}
   print(str(p.relative_to(W)),json.dumps(desc,ensure_ascii=False)[:1100])
print('F LEGACY RESULTS')
for name in ('mesh_convergence.json','matched_endpoint_results.json','queue.json'):
 x=read(F/name);print(name,json.dumps(x,ensure_ascii=False)[:3400])
print('E FOIL PRIMARY')
for p in E.glob('M*/project_primary_evidence.json'):
 print(p.parent.name,json.dumps(read(p),ensure_ascii=False)[:2200])
print('E CURRENT SETUP')
s=read(E/'mesh_queue_state.json');p=Path(s.get('directory',''))
for n in ('setup.json','progress.json','latest_checkpoint.json','source_identity.json'):
 print(n,json.dumps(read(p/n))[:1700])
