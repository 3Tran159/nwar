"""Read-only, independent CGNS geometry audit for three no-foil vertical surface grids."""
from pathlib import Path
from datetime import datetime
import sys, os, json, hashlib, uuid, traceback
sys.path.insert(0,r"F:\ntnu\mesh_screening_20261028\quasi2d_012_20261029\deps311")
import numpy as np, h5py
root=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
manifest=json.loads((root/"geometry_matrix_manifest.json").read_text(encoding="utf-8"));cases={r["wave"]+"/"+r["name"]:r for r in manifest["records"]}
face_names=["Polyfaces_fluid","DOMAIN.inlet","DOMAIN.outlet","DOMAIN.bottom","DOMAIN.top","DOMAIN.span_source","DOMAIN.span_target"]
report={"created_at":datetime.now().astimezone().isoformat(),"audit_type":"independent_geometry_topology_only","fluid_solver_launched":False,"cases":{}}
def check(ok,why):
 if not ok: raise AssertionError(why)
def group_data(g,name):return np.asarray(g[name][" data"])
def audit(p,dz,dx,xmin,xmax):
 checks={}
 with h5py.File(p,"r") as f:
  b=f["Base/fluid"]; xyz=np.column_stack([group_data(b["GridCoordinates"],"Coordinate"+letter) for letter in "XYZ"])
  coords=np.round(xyz,10)
  nnode=len(coords)
  xs=np.unique(coords[:,0]);zs=np.unique(coords[:,2]);ys=np.unique(coords[:,1])
  nx=len(xs);nz=len(zs)
  ncell=(nx-1)*(nz-1)
  for key,ok in [
   ("two_span_planes",len(ys)==2 and np.allclose(ys,[20.,20.02],atol=1e-8)),
   ("x_coordinate_grid",nx==round((xmax-xmin)/dx)+1 and np.isclose(xs[0],xmin) and np.isclose(xs[-1],xmax) and np.allclose(np.diff(xs),dx,atol=1e-8)),
   ("z_coordinate_bounds",np.isclose(zs[0],-22) and np.isclose(zs[-1],8)),
   ("node_count",nnode==2*nx*nz),
   ("flat_analytic_cell_count",ncell>0),
   ("coordinate_finiteness",np.isfinite(coords).all())]:
   check(ok,key);checks[key]=True
  check(np.allclose(coords[:nx,0],xs),"first x row not monotonic")
  check(np.allclose(coords[::nx][:nz,2],zs),"z rows not monotonic")
  check(np.allclose(coords[nx*nz:,0],coords[:nx*nz,0]),"span x mismatch")
  check(np.allclose(coords[nx*nz:,2],coords[:nx*nz,2]),"span z mismatch")
  spacing=np.diff(zs)
  mid=(zs[:-1]>=1.25-1e-8)&(zs[1:]<=2.75+1e-8)
  check(mid.sum()==round(1.5/dz),"near-surface band level count")
  check(np.allclose(spacing[mid],dz,atol=1e-8),"free surface band dz is not constant")
  check(np.all(spacing>0),"non-positive layer thickness")
  checks["free_surface_band_spacing"]=True
  dz_min=float(np.min(spacing));dz_max=float(np.max(spacing))
  volumes=(np.diff(zs)[:,None]*np.diff(xs)[None,:]*.02)
  check(np.all(volumes>0),"nonpositive analytic volume")
  check(np.isclose(volumes.sum(),(xmax-xmin)*30*.02,rtol=1e-10),"volume not 48 m3")
  checks["all_analytic_volumes_positive_and_48m3"]=True
  fids={}
  fcount=0
  for name in face_names:
   g=b[name];er=group_data(g,"ElementRange").reshape(-1)
   start=int(er[0]);stop=int(er[1]);count=stop-start+1
   off=group_data(g,"ElementStartOffset").reshape(-1).astype(np.int64)
   conn=group_data(g,"ElementConnectivity").reshape(-1).astype(np.int64)
   check(off[0]==0 and off[-1]==len(conn) and len(off)==count+1,f"{name}: invalid face offsets")
   check(np.all(np.diff(off)==4),f"{name}: faces are not quads")
   check(np.all((conn>=1)&(conn<=nnode)),f"{name}: invalid node IDs")
   fids[name]=(start,stop,count)
   fcount+=count
  ids=np.concatenate([np.arange(s,e+1,dtype=np.int64) for s,e,_ in fids.values()])
  check(np.array_equal(ids,np.arange(1,fcount+1)),"face element ranges overlap or gap")
  checks["valid_contiguous_face_ids"]=True
  bg=b["fluid"];er=group_data(bg,"ElementRange").reshape(-1)
  check(int(er[0])==fcount+1 and int(er[1])==fcount+ncell,"cell element range mismatch")
  off=group_data(bg,"ElementStartOffset").reshape(-1).astype(np.int64)
  faces=group_data(bg,"ElementConnectivity").reshape(-1).astype(np.int64)
  check(len(off)==ncell+1 and off[0]==0 and off[-1]==len(faces),"cell offsets invalid")
  check(np.all(np.diff(off)==6),"not 6 faces per hexahedral cell")
  check(np.all((abs(faces)>=1)&(abs(faces)<=fcount)),"invalid signed face refs")
  absfaces=np.abs(faces)
  hits=np.bincount(absfaces,minlength=fcount+1)[1:]
  sign=np.bincount(absfaces,weights=np.sign(faces),minlength=fcount+1)[1:]
  internal_first,internal_last,_=fids["Polyfaces_fluid"]
  mask=np.zeros(fcount,dtype=bool);mask[internal_first-1:internal_last]=True
  check(np.all(hits[mask]==2),"internal face not referenced by exactly 2 cells")
  check(np.all(sign[mask]==0),"internal shared face orientation not opposite")
  check(np.all(hits[~mask]==1),"boundary face not referenced exactly once")
  check(int(np.sum(hits))==6*ncell,"face-to-cell incidence mismatch")
  checks["watertight_face_incidence_and_oriented_internal_faces"]=True
  check(fids["DOMAIN.span_source"][2]==ncell and fids["DOMAIN.span_target"][2]==ncell,"one span layer expected")
  checks["single_span_cell_layer"]=True
  # BC point ranges: each boundary BC maps to the matching face range
  for name in face_names[1:]:
   bc=b["ZoneBC"][name];rr=group_data(bc,"PointRange").reshape(-1)
   check(np.array_equal(rr, np.array(fids[name][:2])),"BC "+name+" does not match surface range")
  checks["six_boundary_point_ranges"]=True
  m=json.loads(p.with_name("mesh_exact.validation.json").read_text(encoding="utf-8"))
  check(m["cells"]==ncell and abs(m["total_volume_m3"]-(xmax-xmin)*30*.02)<1e-8 and np.isclose(m["dx_m"],dx),"metadata mismatch")
  check(m["sha256"]==hashlib.sha256(p.read_bytes()).hexdigest(),"mesh sha mismatch")
  checks["mesh_file_and_metadata_digest"]=True
  return {"status":"geometry_topology_pass","checks":checks,"n_cells":int(ncell),"n_nodes":int(nnode),
    "n_faces":int(fcount),"free_surface_dz_m":dz,"n_layers_within_surface_band":int(mid.sum()),
    "dz_global_min_m":dz_min,"dz_global_max_m":dz_max,
    "mean_volume_m3":float(np.mean(volumes)),"min_volume_m3":float(np.min(volumes)),
    "total_volume_m3":float(np.sum(volumes)),
    "face_count":{k:int(v[2]) for k,v in fids.items()},
    "dx_m":dx,"span_m":.02,"sha256":m["sha256"],"geometry_only_not_solver_validated":True}
for name,row in cases.items():
 try:report["cases"][name]=audit(Path(row["mesh_path"]),row["dz_m"],row["dx_m"],row["domain"][0][0],row["domain"][1][0])
 except Exception as ex:report["cases"][name]={"status":"audit_failed","error":str(ex)}
report["all_pass"]=all(v["status"]=="geometry_topology_pass" for v in report["cases"].values())
dest=root/"matrix_independent_geometry_audit.json"
tmp=root/("audit."+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
os.replace(tmp,dest)
print(json.dumps({"all_pass":report["all_pass"],"cases":{k:{"status":v["status"],"n_cells":v.get("n_cells"),"n_faces":v.get("n_faces"),"free_surface_dz_m":v.get("free_surface_dz_m"),"error":v.get("error")}for k,v in report["cases"].items()},"report":str(dest)},ensure_ascii=False))
