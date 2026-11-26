"""Compare baseline no-foil CGNS file against historical reference at the dataset level."""
from pathlib import Path
import json,sys,hashlib,datetime
sys.path.insert(0,r"F:\ntnu\mesh_screening_20261028\quasi2d_012_20261029\deps311")
import numpy as np,h5py
reference=Path(r"E:\ntnu\quasi2d_waves_20261029\W20_H24_X4_Q2D_r5\mesh_exact.CGNS")
candidate=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only\FS_baseline\mesh_exact.CGNS")
report={"at":datetime.datetime.now().astimezone().isoformat(),
 "reference":str(reference),"candidate":str(candidate),
 "file_hash_identical":hashlib.sha256(reference.read_bytes()).digest()==hashlib.sha256(candidate.read_bytes()).digest(),
 "dataset_differences":[],"attribute_differences":[],"dataset_count":0}
with h5py.File(reference,"r") as x,h5py.File(candidate,"r") as y:
 def walk(g):
  res={}
  def collect(name,obj):
   if isinstance(obj,h5py.Dataset):res[name]=obj
  g.visititems(collect)
  return res
 a=walk(x);b=walk(y)
 report["same_dataset_paths"]=set(a)==set(b)
 report["missing_in_candidate"]=sorted(set(a)-set(b))
 report["extra_in_candidate"]=sorted(set(b)-set(a))
 for name in sorted(set(a)&set(b)):
  i,j=a[name],b[name];report["dataset_count"]+=1
  if i.shape!=j.shape or i.dtype!=j.dtype:
   report["dataset_differences"].append({"name":name,"shape_reference":i.shape,"shape_candidate":j.shape});continue
  v,w=i[()],j[()]
  if not np.array_equal(v,w,equal_nan=True) if np.issubdtype(i.dtype,np.number) else not np.array_equal(v,w):
   report["dataset_differences"].append(name)
 report["numerical_mesh_equivalent"]=report["same_dataset_paths"] and len(report["dataset_differences"])==0
path=candidate.parent.parent/"baseline_dataset_equivalence.json"
path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"equivalent":report["numerical_mesh_equivalent"],"file_sha_identical":report["file_hash_identical"],"datasets":report["dataset_count"],"different_datasets":report["dataset_differences"][:20],"details":str(path)},ensure_ascii=False))
