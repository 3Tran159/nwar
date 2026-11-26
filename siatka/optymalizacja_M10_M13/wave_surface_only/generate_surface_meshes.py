"""Create isolated no-foil free-surface mesh variants. Does not launch STAR-CCM+."""
from pathlib import Path
import os,sys,subprocess,shutil,hashlib,json,uuid,datetime,math
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
ORIGINAL=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\build_exact_wave24m_r5.py")
W=Path(r"E:\ntnu\quasi2d_waves_20261029")
REFERENCE=W/"W20_H24_X4_Q2D_r5"/"mesh_exact.CGNS"
PY=Path(r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\python\python.exe")
assert sys.version_info.major==3,"Python required"
assert ORIGINAL.is_file() and REFERENCE.is_file() and PY.is_file()
assert shutil.disk_usage(ROOT).free>25*2**30
PLAN=json.loads((ROOT/"plan.json").read_text(encoding="utf-8"))
assert PLAN["execution_status"]=="plan_only_no_wave_solver_launched"
source=ORIGINAL.read_text(encoding="utf-8")
def once(old,new):
 global source
 assert source.count(old)==1,repr(old)
 source=source.replace(old,new,1)

once("W=Path('E:/ntnu/quasi2d_waves_20261029');out=W/'W20_H24_X4_Q2D_r5';out.mkdir(exist_ok=False)","W=Path('E:/ntnu/quasi2d_waves_20261029');out=Path(sys.argv[1]);dz=float(sys.argv[2]);assert dz in (.05,.025,.0125);out.mkdir(exist_ok=False,parents=True)")
once("x=np.linspace(-35,45,401);z=np.unique(np.r_[graded(-22,1.25,True),np.linspace(1.25,2.75,61),graded(2.75,8)])","x=np.linspace(-35,45,401);n=round(1.5/dz);assert abs(n*dz-1.5)<1e-10;z=np.unique(np.r_[graded(-22,1.25,True),np.linspace(1.25,2.75,n+1),graded(2.75,8)])")
once("'dz_free_surface_m':.025","'dz_free_surface_m':dz")
code_path=ROOT/"build_isolated_free_surface.py"
if code_path.exists():
 assert code_path.read_text(encoding="utf-8")==source,"Existing builder differs; stop"
else:code_path.write_text(source,encoding="utf-8")
names=[("FS_coarse",0.05),("FS_baseline",0.025),("FS_fine",0.0125)]
records=[]
env=dict(os.environ)
env["PYTHONUTF8"]="1"
for name,dz in names:
 case=ROOT/name
 if case.exists():
  meta=case/"mesh_exact.validation.json"
  assert meta.is_file() and (case/"mesh_exact.CGNS").is_file(), "Unknown existing case "+name
  records.append({"name":name,"status":"already_exists","meta":json.loads(meta.read_text(encoding="utf-8"))})
  continue
 assert shutil.disk_usage(ROOT).free>25*2**30
 # Geometry generation runs in a separate Python 3.11 process, no STAR CFD solver.
 result=subprocess.run([str(PY),str(code_path),str(case),str(dz)],capture_output=True,text=True,cwd=ROOT,env=env,timeout=180)
 if result.returncode:
  records.append({"name":name,"status":"failed","stdout_tail":result.stdout[-1000:],"stderr_tail":result.stderr[-1500:]})
  raise RuntimeError(json.dumps(records[-1]))
 meta=json.loads((case/"mesh_exact.validation.json").read_text(encoding="utf-8"))
 assert math.isclose(meta["total_volume_m3"],48.0,abs_tol=1e-6)
 assert meta["cells"]>0
 assert meta["dx_m"]==0.2 and meta["dz_free_surface_m"]==dz
 assert meta["span_m"]==0.02
 assert meta["boundary_face_counts"]["DOMAIN.span_source"]==meta["cells"]
 assert meta["boundary_face_counts"]["DOMAIN.span_target"]==meta["cells"]
 if name=="FS_baseline":
  original_hash=hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
  meta["reference_bytes_match"]=original_hash==meta["sha256"]
 records.append({"name":name,"status":"geometry_generated","cells":meta["cells"],"dx_m":meta["dx_m"],"dz_surface_m":dz,"volume_m3":meta["total_volume_m3"],"hash":meta["sha256"],"reference_match":meta.get("reference_bytes_match")})
ROOT.joinpath("geometry_manifest.json").write_text(json.dumps({"at":datetime.datetime.now().astimezone().isoformat(),"source":str(ORIGINAL),"source_sha256":hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),"reference_sha256":hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),"geometry_only":True,"no_solver_started":True,"records":records},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"geometry_only":True,"records":records},ensure_ascii=False))
