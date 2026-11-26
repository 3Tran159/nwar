"""Build, reconstruct, audit and map ONE new far-field mesh. No originals modified."""
from pathlib import Path
from datetime import datetime
import sys,os,json,shutil,subprocess,uuid
ROOT=Path(r'E:\ntnu_mesh_optimization_20261030');D=ROOT/'M13_farfield15_20261031'
S=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030')
sys.path.insert(0,str(ROOT))
import owned_experiment_runtime_20261031 as rt
PY=Path(r'E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\python\python.exe')
TOKEN=uuid.uuid4().hex
LOCK=D/'build.lock'
def state(status,**more):
 v={'status':status,'at':rt.now(),'pid':os.getpid(),'mesh':'M13',**more};rt.write(D/'build_state.json',v);print(json.dumps(v,ensure_ascii=False),flush=True)
def main():
 plan=rt.read(D/'candidate.json');assert plan['id']=='M13' and plan['status']=='prepared_not_built'
 q=rt.read(ROOT/'mesh_queue_state.json');done=rt.read(ROOT/'mesh_queue_completed_M10.json')
 assert q.get('status')=='done' and done.get('project_primary_pass') is True,'Wait for saved accepted M10; no competing mesh build'
 assert not rt.guard.alive(q.get('star_pid'))
 assert not (ROOT/'mesh_queue_launch.lock').exists(),'Original queue still owns launch lock'
 assert rt.resource_problem() is None
 source=Path(plan['source']);assert rt.sha(source)==plan['source_sha256']
 m10=Path(done['output']);assert (m10/'final.sim').is_file() and rt.read(m10/'exit.json').get('returncode')==0
 assert not LOCK.exists()
 with LOCK.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'token':TOKEN,'at':rt.now()},f)
 try:
  state('native_meshing',source=str(source))
  rt.stage(D/'raw',source,D/'MeshM13Farfield15.java',workers=4,mask=sum(1<<i for i in (4,5,6,7)),budget_s=1800,phase='mesh')
  assert (D/'raw/mesh.CGNS').exists()
  state('exact_extrusion')
  with (D/'extrusion.log').open('x',encoding='utf-8') as log:
   result=subprocess.run([str(PY),str(D/'extrude_exact.py'),str(D/'raw/mesh.CGNS'),str(D/'raw/mesh_exact.CGNS'),'-35','45','.2'],stdout=log,stderr=subprocess.STDOUT,cwd=D,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
  assert result.returncode==0,'Extrusion failed'
  v=rt.read(D/'raw/mesh_exact.validation.json');cells=v['cells']
  assert 10000<cells<450000 and v['negative_or_zero_reconstructed_volumes']==0 and v['nonmanifold_source_edges']==0
  state('star_import_quality_audit',cells=cells)
  rt.stage(D/'geometry',D/'raw/mesh.sim',D/'FinalizeM13.java',{'NTNU_M13_EXPECTED_CELLS':str(cells)},workers=4,mask=sum(1<<i for i in (4,5,6,7)),budget_s=1800,phase='mesh')
  metrics=rt.read(D/'geometry/measurement.json')['metrics']
  gates={k:metrics.get(k)==0 for k in ('NegativeVolumeCells','UnclosedCells','DegeneratedFeCells')}
  gates.update(min_quality=metrics.get('min_cell_quality',0)>=.01,face_validity=metrics.get('min_face_validity',0)>=.5,exact_span=abs(metrics.get('centroid_y_range_m',100))<1e-7,source_preserved=rt.sha(source)==plan['source_sha256'])
  audit={'cells':cells,'gates':gates,'metrics':metrics,'pass':all(gates.values()),'scope':'Geometry/topology/STAR import; no force convergence or wave acceptance'}
  rt.write(D/'geometry_audit.json',audit)
  assert all(gates.values()),'Geometry quality requires review'
  plan.update(status='geometry_built_audited',actual_cells=cells,cell_reduction_pct=100*(1-cells/317277),quality=gates,artifact=str(D/'geometry/mesh.sim'))
  rt.write(D/'candidate.json',plan)
  state('mapping_from_saved_M10',cells=cells,M10_source=str(m10/'final.sim'))
  shutil.copy2(S/'MapW01Solution.java',D/'MapW01Solution.java')
  mt=rt.read(m10/'completed.json')['time_s']
  out=D/'mapped'
  rt.stage(out,m10/'final.sim',D/'MapW01Solution.java',{'NTNU_MAP_OUT':str(out),'NTNU_MAP_MESH':str(D/'raw/mesh_exact.CGNS'),'NTNU_MAP_CELLS':str(cells),'NTNU_MAP_EXPECTED_START':str(mt)},workers=4,mask=sum(1<<i for i in (4,5,6,7)),budget_s=1800,phase='mapping')
  assert rt.read(out/'mapping_audit.json').get('pass') is True and (out/'mapped.sim').is_file()
  plan.update(status='geometry_and_mapping_ready',mapped_sim=str(out/'mapped.sim'),mapped_time_s=mt,flow_solver_started=False)
  rt.write(D/'candidate.json',plan)
  state('ready_for_flow',cells=cells,start_time_s=mt,source=str(out/'mapped.sim'),cell_reduction_pct=plan['cell_reduction_pct'])
 except BaseException as ex:
  state('needs_review',error=rt.guard.redact(str(ex))[:500]);raise
 finally:
  if rt.read(LOCK).get('token')==TOKEN:LOCK.unlink()
if __name__=='__main__':main()
