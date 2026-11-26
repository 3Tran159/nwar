"""Two globally refined M09 meshes; preserve continuous prism grading, originals and other jobs."""
from pathlib import Path
import sys,json,math,hashlib,shutil,subprocess,time,threading,datetime,os,re
HERE=Path(__file__).resolve().parent
OUT=HERE/'gci_m09_20261030'; OUT.mkdir(exist_ok=True)
R=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
Q=R.parent/'quasi2d_012_20261029'
sys.path.insert(0,str(R.parent/'night_20261028'))
from night_queue import STAR,saved_options,redact,free_memory
def write(p,x):
 p.with_suffix('.tmp').write_text(json.dumps(x,indent=2),encoding='utf-8');p.with_suffix('.tmp').replace(p)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def state(status,**kw):
 write(OUT/'build_state.json',dict(status=status,pid=os.getpid(),updated_at=datetime.datetime.now().astimezone().isoformat(),**kw));print(status,kw,flush=True)
def run_star(source,macro,log,timeout=7200):
 if log.exists():raise RuntimeError('Existing attempt preserved: '+str(log))
 if free_memory()<18*1024**3 or shutil.disk_usage(str(OUT)).free<15*1024**3:raise RuntimeError('Insufficient free resources')
 with log.open('x',encoding='utf-8') as f:
  p=subprocess.Popen([str(STAR),*saved_options(2),'-batch',str(macro),str(source)],cwd=OUT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
  write(log.with_suffix('.pid.json'),{'pid':p.pid,'CPU_workers':2});start=time.time()
  def drain():
   for line in p.stdout:f.write(redact(line));f.flush()
  t=threading.Thread(target=drain);t.start()
  while p.poll() is None:
   if free_memory()<5*1024**3 or shutil.disk_usage(str(OUT)).free<4*1024**3 or time.time()-start>timeout:
    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    t.join(30);raise RuntimeError('Owned mesh job stopped: resource or timeout guard')
   time.sleep(3)
  t.join(30);write(log.with_suffix('.exit.json'),{'returncode':p.returncode,'wall_s':time.time()-start})
  if p.returncode:raise RuntimeError('STAR job failed; inspect '+str(log))
def run_py(script,args,log,timeout=3600):
 with log.open('x',encoding='utf-8') as f:
  p=subprocess.run([sys.executable,str(script),*map(str,args)],stdout=f,stderr=subprocess.STDOUT,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise RuntimeError('Python audit failed: '+str(log))
def replace_once(t,a,b):
 if t.count(a)!=1:raise RuntimeError('Template mismatch '+a[:60])
 return t.replace(a,b)
def main():
 h0=1.530612244897959e-6;T=.01546;N0=48
 lo,hi=1.,1.4
 for _ in range(100):
  g=(lo+hi)/2
  if h0*math.expm1(N0*math.log(g))/math.expm1(math.log(g))>T:hi=g
  else:lo=g
 a=N0*math.log((lo+hi)/2)
 designs=[]
 for level,n in [('G09_M',67),('G09_F',94)]:
  ref=n/N0;g=math.exp(a/n);first=T*math.expm1(a/n)/math.expm1(a)
  designs.append(dict(id=level,layers=n,linear_refinement_vs_M09=ref,first_layer_m=first,prism_growth=g,total_prism_m=T,base_m=.25/ref,foil_target_m=.0028571428571428576/ref,foil_min_m=.00028571428571428574/ref,global_min_m=.0003571428571428572/ref,near_foil_m=.00892857142857143/ref,free_surface_m=.028571428571428574/ref,protected_middle_m=.14285714285714288/ref))
 write(OUT/'design.json',dict(reference='M09',reference_layers=48,reference_growth=math.exp(a/48),grading_function='y(eta)=T*expm1(a*eta)/expm1(a); eta=k/N',grading_exponent=a,objective='Verify the light M09 mesh; finer levels are accuracy references for later cost reduction.',spanwise_layers=1,effective_refinement_dimension=2,designs=designs))
 extrusion=(R/'extrude_source_mesh.py').read_text()
 extrusion=replace_once(extrusion,"Q=Path('F:/ntnu/mesh_screening_20261028/quasi2d_012_20261029');sys.path.insert(0,str(Q/'deps311'))","sys.path.insert(0,"+repr(str(HERE/'.deps'))+")")
 (OUT/'extrude.py').write_text(extrusion,encoding='utf-8')
 results=[]
 for d in designs:
  name=d['id'];raw=OUT/(name+'_raw');out=OUT/name
  if raw.exists() or out.exists():raise RuntimeError('Preserve previous attempt '+name)
  raw.mkdir();out.mkdir();write(out/'design.json',d)
  source=Q/'M09_build/mesh.sim';h=sha(source)
  shutil.copy2(source,raw/'input_M09_copy.sim')
  assert sha(raw/'input_M09_copy.sim')==h
  state('meshing',mesh=name,design=d)
  macro=(R/'MeshRawM09.java').read_text()
  macro=macro.replace('MeshRawM09','Mesh'+name)
  macro=replace_once(macro,(Q/'M09_build').as_posix(),raw.as_posix())
  replacements={'double base=0.25;':f"double base={d['base_m']};",'0.0003571428571428572/base':str(d['global_min_m'])+'/base','setValue(1.530612244897959e-06)':f"setValue({d['first_layer_m']})",'setNumLayers(48)':f"setNumLayers({d['layers']})",'0.0028571428571428576/base':str(d['foil_target_m'])+'/base','0.00028571428571428574/base':str(d['foil_min_m'])+'/base','0.00892857142857143/base':str(d['near_foil_m'])+'/base','0.028571428571428574/base':str(d['free_surface_m'])+'/base'}
  for old,new in replacements.items():macro=replace_once(macro,old,new)
  begin=macro.index('SimpleBlockPart middle=')
  end=macro.index('for(DirectedMeshPartCollection pc:',begin)
  macro=macro[:begin]+'((VolumeCustomMeshControl)auto.getCustomMeshControls().getObject("Q2D_protected_middle_M09")).getCustomValues().get(VolumeControlSize.class).setRelativeSize('+str(d['protected_middle_m'])+'/base*100);\n'+macro[end:]
  macro=re.sub(r'Files.writeString\(out.resolve\("mesh_timing.json"\).*?;\n','',macro)
  audit_path=OUT/('AuditRaw'+name+'.java')
  macro=replace_once(macro,(R/'AuditRawM09.java').as_posix(),audit_path.as_posix())
  macro_path=OUT/('Mesh'+name+'.java');macro_path.write_text(macro,encoding='utf-8')
  def auditcode(cls,dest):
   return (R/'AuditQ2DM04.java').read_text().replace('AuditQ2DM04',cls).replace((Q/'M04').as_posix(),dest.as_posix()).replace('"M04"','"'+name+'"')
  audit_path.write_text(auditcode('AuditRaw'+name,raw),encoding='utf-8')
  run_star(raw/'input_M09_copy.sim',macro_path,raw/'mesh.log')
  assert sha(source)==h
  cells=read(raw/'measurement.json')['metrics']['cell_count']
  if not 10000<cells<1600000:raise RuntimeError('Unexpected cell count '+str(cells))
  state('exact_extrusion',mesh=name,cells=cells)
  run_py(OUT/'extrude.py',[raw/'mesh.CGNS',raw/'mesh_exact.CGNS'],raw/'extrusion.log')
  shutil.copy2(raw/'mesh.sim',out/'input_raw_copy.sim')
  final=(R/'FinalizeM09.java').read_text().replace('FinalizeM09','Finalize'+name)
  final=replace_once(final,(Q/'M09').as_posix()+'"',out.as_posix()+'"')
  final=replace_once(final,(Q/'M09_build/mesh_exact.CGNS').as_posix(),(raw/'mesh_exact.CGNS').as_posix())
  final=replace_once(final,'!=214908','!='+str(cells))
  final=replace_once(final,(R/'AuditFinalM09.java').as_posix(),(OUT/('AuditFinal'+name+'.java')).as_posix())
  (OUT/('Finalize'+name+'.java')).write_text(final,encoding='utf-8')
  (OUT/('AuditFinal'+name+'.java')).write_text(auditcode('AuditFinal'+name,out),encoding='utf-8')
  state('final_quality_audit',mesh=name,cells=cells)
  run_star(out/'input_raw_copy.sim',OUT/('Finalize'+name+'.java'),raw/'finalize.log')
  met=read(out/'measurement.json')['metrics'];ex=read(raw/'mesh_exact.validation.json')
  gates={k:met.get(k)==0 for k in ['NegativeVolumeCells','UnclosedCells','DegeneratedFeCells']}
  gates.update(min_cell_quality=met.get('min_cell_quality',0)>=.01,min_face_validity=met.get('min_face_validity',0)>=.5,exact_source_extrusion=ex['source_cells_unchanged'] and ex['nonmanifold_source_edges']==0,source_unchanged=sha(source)==h)
  result=dict(mesh=name,cells=cells,gates=gates,metrics=met,source_sha256=h,status='basic_quality_passed' if all(gates.values()) else 'needs_review')
  write(out/'basic_audit.json',result);results.append(result)
  if not all(gates.values()):raise RuntimeError('Quality gate failed '+name)
 state('both_meshes_built_pending_family_audit',results=results,flow_launched=False)
if __name__=='__main__':
 try:main()
 except BaseException as e:state('needs_review',error=str(e));raise
