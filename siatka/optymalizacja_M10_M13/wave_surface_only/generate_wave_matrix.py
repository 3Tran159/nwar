"""Independent geometry-only λ/dz matrix; no STAR solver, no source overwrite."""
from pathlib import Path
import sys,json,hashlib,shutil,subprocess,os,datetime,math,uuid
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
OLD=ROOT/"build_isolated_free_surface.py"
PY=Path(r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\python\python.exe")
PLAN=json.loads((ROOT/"plan.json").read_text(encoding="utf-8-sig"))
assert PLAN["execution_status"]=="geometry_generated_only_no_solver_started"
assert "M12" in PLAN["timestep_priority"]["resource_safety"]
source=OLD.read_text(encoding="utf-8")
def replace_one(old,new):
 global source
 if source.count(old)!=1:
  raise ValueError("Source anchor count not 1: "+old)
 source=source.replace(old,new,1)
replace_one(
 "out=Path(sys.argv[1]);dz=float(sys.argv[2]);assert dz in (.05,.025,.0125);out.mkdir(exist_ok=False,parents=True)",
 "out=Path(sys.argv[1]);dz=float(sys.argv[2]);xmin=float(sys.argv[3]);xmax=float(sys.argv[4]);dx=float(sys.argv[5]);assert dz in (.05,.025,.0125) and dx in (.1,.2) and (xmin,xmax) in [(-35.,45.),(-52.5,67.5),(-17.5,22.5)];assert out.resolve().is_relative_to(Path(r'E:\\ntnu_mesh_optimization_20261030\\wave_surface_only').resolve());out.mkdir(exist_ok=False,parents=True)"
)
replace_one(
 "x=np.linspace(-35,45,401);n=round(1.5/dz)",
 "nx_steps=round((xmax-xmin)/dx);assert abs(nx_steps*dx-(xmax-xmin))<1e-9;x=np.linspace(xmin,xmax,nx_steps+1);n=round(1.5/dz)"
)
replace_one("np.max(abs(p[:,0]+35))<1e-9","np.max(abs(p[:,0]-xmin))<1e-9")
replace_one("np.max(abs(p[:,0]-45))<1e-9","np.max(abs(p[:,0]-xmax))<1e-9")
replace_one("'dx_m':.2","'dx_m':dx")
replace_one("'bounds':[[-35,20,-22],[45,20.02,8]]","'bounds':[[xmin,20,-22],[xmax,20.02,8]]")
builder=ROOT/"build_surface_domains.py"
if builder.exists():
 assert builder.read_text(encoding="utf-8")==source,"Existing builder changed!"
else:
 builder.write_text(source,encoding="utf-8")
wave_families=[
 {"wave":"L10","lambda_m":10.0,"x_min":-17.5,"x_max":22.5,"dx_m":.1,"heights_m":[.5]},
 {"wave":"L20","lambda_m":20.0,"x_min":-35.,"x_max":45.,"dx_m":.2,"heights_m":[.25,.5,.75]},
 {"wave":"L30","lambda_m":30.0,"x_min":-52.5,"x_max":67.5,"dx_m":.2,"heights_m":[.25,.5,.75]}
]
densities=[("coarse",.05),("baseline",.025),("fine",.0125)]
records=[]
for family in wave_families:
 for name,dz in densities:
  case=ROOT/family["wave"]/name if family["wave"]!="L20" else ROOT/("FS_"+name)
  meta=case/"mesh_exact.validation.json"
  if case.exists():
   if not meta.is_file() or not (case/"mesh_exact.CGNS").is_file():
    raise RuntimeError("Unexpected existing case without valid evidence "+str(case))
   rec=json.loads(meta.read_text(encoding="utf-8"))
   state="existing_geometry"
  else:
   if shutil.disk_usage(ROOT).free<25*2**30:
    raise RuntimeError("Insufficient E disk")
   proc=subprocess.run([str(PY),str(builder),str(case),str(dz),str(family["x_min"]),str(family["x_max"]),str(family["dx_m"])],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
   if proc.returncode:
    raise RuntimeError(f"Could not build {family['wave']}/{name}: {proc.stderr[-1200:]}")
   rec=json.loads(meta.read_text(encoding="utf-8"))
   state="new_geometry"
  expected_vol=(family["x_max"]-family["x_min"])*30*.02
  assert math.isclose(rec["total_volume_m3"],expected_vol,rel_tol=1e-9)
  assert math.isclose(rec["dx_m"],family["dx_m"],abs_tol=1e-9) and math.isclose(rec["dz_free_surface_m"],dz,abs_tol=1e-9)
  assert rec["bounds"]==[[family["x_min"],20,-22],[family["x_max"],20.02,8]]
  assert rec["boundary_face_counts"]["DOMAIN.span_source"]==rec["cells"]
  assert rec["boundary_face_counts"]["DOMAIN.span_target"]==rec["cells"]
  h=hashlib.sha256((case/"mesh_exact.CGNS").read_bytes()).hexdigest()
  assert h==rec["sha256"]
  records.append({"wave":family["wave"],"lambda_m":family["lambda_m"],"height_options_m":family["heights_m"],"name":name,"dx_m":family["dx_m"],"dz_m":dz,"lambda_per_dx":family["lambda_m"]/family["dx_m"],"H_per_dz":{f"{H:.2f}":round(H/dz,3) for H in family["heights_m"]},"n_cells":rec["cells"],"domain":rec["bounds"],"volume_m3":rec["total_volume_m3"],"mesh_path":str(case/"mesh_exact.CGNS"),"sha256":h,"status":state,"has_CFD_result":False})
  print(json.dumps({"case":family["wave"]+"/"+name,"cells":rec["cells"],"status":state},ensure_ascii=False),flush=True)
result={"created_at":datetime.datetime.now().astimezone().isoformat(),"scope":"wave_geometry_only","formal_wave_GCI":False,"dt_primary_s":0.001,"dt_check_s":0.0005,"simulation_steps_taken":0,"C01_hold_changed":False,"M12_changed":False,"records":records}
dest=ROOT/"geometry_matrix_manifest.json"
if dest.exists():
 old=json.loads(dest.read_text(encoding="utf-8"))
 assert old.get("scope")=="wave_geometry_only"
 backup=ROOT/("geometry_matrix_manifest.before_"+uuid.uuid4().hex+".json")
 shutil.copy2(dest,backup)
tmp=ROOT/("matrix."+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
os.replace(tmp,dest)
print(json.dumps({"done":True,"records":len(records),"cell_counts":{r["wave"]+"/"+r["name"]:r["n_cells"] for r in records}},ensure_ascii=False))
