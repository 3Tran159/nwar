"""Build a wider M13 wave band and longer domain without coarsening cell controls."""
from common import *
import subprocess,shutil
from worker import native,owned_lock,rt

BASE=ROOT/'M13_farfield15_20261031'
OUT=DATA/'mesh_W04_20261102'
REVIEW=HERE/'reviews'/'W04_20261102'
CP='E:/Program Files/Siemens/21.02.007-R8/STAR-CCM+21.02.007-R8/star/lib/java/platform/modules/ext/*'
JAVAC='C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe'

def prepare():
 OUT.mkdir(exist_ok=True,parents=True);compiled=OUT/'compiled';compiled.mkdir(exist_ok=True)
 design=dict(id='M13_W04',case='W04',at=now(),H_m=1.5,lambda_m=38.99857691441418,
             free_surface_target_m=.02,free_surface_z_m=[1.,3.],original_free_surface_z_m=[1.6,2.4],
             x_bounds_m=[-70.,90.],original_x_bounds_m=[-35.,45.],extension_dx_max_m=.2,
             forcing_length_m=40.,damping_length_m=40.,forcing_end_x_m=-30.,damping_start_x_m=50.,
             span_m=.02,prism_layers=48,prism_first_m=1.530612244897959e-6,
             original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA,
             reference_policy='One original C01. Wave allowed only after adjacent 0.2 s calm windows are stable below 0.5% and both means agree with original C01 within 0.5%.',
             no_new_Q_reference=True,no_cell_stretching=True)
 write(REVIEW/'design.json',design);write(OUT/'design.json',design)
 files=[]
 for name in ('MeshM13Farfield15','AuditRawM13','AuditFinalM13','FinalizeM13'):
  s=(BASE/(name+'.java')).read_text(encoding='utf8');new=name.replace('M13','W04')
  s=s.replace(name,new).replace(BASE.as_posix(),OUT.as_posix())
  s=s.replace('AuditRawM13.java','AuditRawW04.java').replace('AuditFinalM13.java','AuditFinalW04.java')
  if name=='MeshM13Farfield15':
   anchor='long start=System.nanoTime();auto.updateAutoSourceMesh();'
   assert anchor in s
   s=s.replace(anchor,'''VolumeCustomMeshControl fs=(VolumeCustomMeshControl)auto.getCustomMeshControls().getObject("Q2D_free_surface");
int boxes=0;for(Object item:fs.getGeometryObjects().getObjects())if(item instanceof SimpleBlockPart){
 SimpleBlockPart box=(SimpleBlockPart)item;box.setCorners(new DoubleVector(new double[]{-100,-.1,1.0}),new DoubleVector(new double[]{100,.1,3.0}));box.rebuildSimpleShapePart();boxes++;
}
if(boxes!=1)throw new IllegalStateException("Expected exactly one existing free-surface refinement block");
Files.writeString(out.resolve("refinement_readback.json"),"{\\"free_surface_target_m\\":0.02,\\"z_min_m\\":1.0,\\"z_max_m\\":3.0,\\"prism_layers\\":48,\\"other_absolute_sizes_preserved\\":true}");
long start=System.nanoTime();auto.updateAutoSourceMesh();''')
  path=OUT/(new+'.java');path.write_text(s,encoding='utf8');files.append(path)
 extrusion=(BASE/'extrude_exact.py').read_text(encoding='utf8')
 extrusion=extrusion.replace("sys.path.insert(0,'F:\\\\ntnu\\\\mesh_screening_20261028\\\\quasi2d_012_20261029\\\\deps311')",'sys.path.insert(0,'+repr(str(DEP))+')')
 extrusion=extrusion.replace('M09-derived 4-lambda wave-domain mesh preparation','W04 wider-band 4-lambda wave-domain mesh preparation').replace('M13 native far-field+15%','M13 W04 wider wave band, unchanged size controls')
 (OUT/'extrude_exact.py').write_text(extrusion,encoding='utf8')
 p=subprocess.run([JAVAC,'-cp',CP,'-d',str(compiled),*map(str,files)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
 write(OUT/'compile_receipt.json',dict(ok=p.returncode==0,files={p.name:sha(p) for p in files},messages=p.stderr[-3000:]))
 if p.returncode:raise RuntimeError(p.stderr)
 return design

def state(status,**more):
 value=dict(status=status,at=now(),pid=os.getpid(),birth=birth(os.getpid()),case='W04',**more)
 write(REVIEW/'state.json',value);write(OUT/'state.json',value);print(json.dumps(value),flush=True)

def main():
 design=prepare();token=uuid.uuid4().hex;owned=[]
 assert not native(),'A solver is active'
 assert not any(j['status'] in ('queued','running','preflight','pausing') for j in jobs()),'Queue must be idle'
 assert not any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS),'STOP or resource reservation active'
 assert not rt.resource_problem(),rt.resource_problem()
 source=BASE/'raw/mesh_before_audit.sim';source_sha=sha(source)
 assert not (OUT/'raw').exists(),'Existing build preserved; do not overwrite'
 try:
  for p in SOLVER_LOCKS:owned_lock(p,token,'W04_mesh_adaptation');owned.append(p)
  assert not native(),'A solver started during reservation'
  state('building_wider_wave_band',source=str(source),source_sha256=source_sha)
  rt.stage(OUT/'raw',source,OUT/'MeshW04Farfield15.java',workers=4,gpu=False,mask=sum(1<<i for i in (4,5,6,7)),budget_s=1800,protect_main=False,phase='W04_mesh')
  assert (OUT/'raw/mesh.CGNS').is_file()
  state('extending_domain_without_stretching')
  with (OUT/'extrusion.log').open('w',encoding='utf8') as log:
   p=subprocess.run([str(PYTHON),str(OUT/'extrude_exact.py'),str(OUT/'raw/mesh.CGNS'),str(OUT/'raw/mesh_exact.CGNS'),'-70','90','.2'],stdout=log,stderr=log,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
  assert p.returncode==0,'Extrusion failed; see extrusion.log'
  mesh=read(OUT/'raw/mesh_exact.validation.json');cells=mesh['cells']
  assert 309441<cells<1500000 and mesh['negative_or_zero_reconstructed_volumes']==0 and mesh['nonmanifold_source_edges']==0
  state('checking_imported_mesh',cells=cells)
  rt.stage(OUT/'geometry',OUT/'raw/mesh.sim',OUT/'FinalizeW04.java',env={'NTNU_M13_EXPECTED_CELLS':str(cells)},workers=4,gpu=False,mask=sum(1<<i for i in (4,5,6,7)),budget_s=1800,protect_main=False,phase='W04_mesh_quality')
  metrics=read(OUT/'geometry/measurement.json')['metrics']
  gates={k:metrics.get(k)==0 for k in ('NegativeVolumeCells','UnclosedCells','DegeneratedFeCells')}
  gates.update(min_quality=metrics.get('min_cell_quality',0)>=.01,face_validity=metrics.get('min_face_validity',0)>=.5,
               one_cell_span=abs(metrics.get('centroid_y_range_m',100))<1e-7,original_preserved=sha(source)==source_sha and sha(SOURCE)==SOURCE_SHA)
  receipt=dict(passed=all(gates.values()),gates=gates,metrics=metrics,cells=cells,mesh_sha256=sha(OUT/'geometry/mesh.CGNS'),design=design)
  write(OUT/'geometry_receipt.json',receipt);write(REVIEW/'geometry_receipt.json',receipt)
  assert receipt['passed'],'Mesh quality check failed'
  state('geometry_ready_for_protected_region_audit',cells=cells)
 except Exception as ex:
  state('needs_review',error=rt.guard.redact(str(ex))[:700]);raise
 finally:
  if not native():
   for p in reversed(owned):
    if read(p).get('token')==token:p.unlink()

if __name__=='__main__':main()
