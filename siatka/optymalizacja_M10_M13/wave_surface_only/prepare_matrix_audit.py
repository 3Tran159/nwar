"""Create independent generalized topology auditor from unchanged original, then run later with Python 3.11."""
from pathlib import Path
import json,hashlib
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
old=ROOT/"independent_geometry_audit.py"
source=old.read_text(encoding="utf-8")
def once(a,b):
 global source
 if source.count(a)!=1:raise RuntimeError("Unexpected source anchor "+a[:120])
 source=source.replace(a,b,1)
once('cases={"FS_coarse":.05,"FS_baseline":.025,"FS_fine":.0125}', 'manifest=json.loads((root/"geometry_matrix_manifest.json").read_text(encoding="utf-8"));cases={r["wave"]+"/"+r["name"]:r for r in manifest["records"]}')
once('def audit(p,dz):','def audit(p,dz,dx,xmin,xmax):')
once('nx==401 and np.isclose(xs[0],-35) and np.isclose(xs[-1],45) and np.allclose(np.diff(xs),.2,atol=1e-8)','nx==round((xmax-xmin)/dx)+1 and np.isclose(xs[0],xmin) and np.isclose(xs[-1],xmax) and np.allclose(np.diff(xs),dx,atol=1e-8)')
once('np.isclose(volumes.sum(),48.,rtol=1e-10)','np.isclose(volumes.sum(),(xmax-xmin)*30*.02,rtol=1e-10)')
once('check(m["cells"]==ncell and abs(m["total_volume_m3"]-48)<1e-8,"metadata mismatch")','check(m["cells"]==ncell and abs(m["total_volume_m3"]-(xmax-xmin)*30*.02)<1e-8 and np.isclose(m["dx_m"],dx),"metadata mismatch")')
once('"dx_m":.2,"span_m":.02','"dx_m":dx,"span_m":.02')
once('for name,dz in cases.items():\n try:report["cases"][name]=audit(root/name/"mesh_exact.CGNS",dz)','for name,row in cases.items():\n try:report["cases"][name]=audit(Path(row["mesh_path"]),row["dz_m"],row["dx_m"],row["domain"][0][0],row["domain"][1][0])')
once('dest=root/"independent_geometry_audit.json"','dest=root/"matrix_independent_geometry_audit.json"')
code_path=ROOT/"audit_wave_matrix.py"
if code_path.exists():assert code_path.read_text(encoding="utf-8")==source
else:code_path.write_text(source,encoding="utf-8")
compile(source,str(code_path),"exec")
print(json.dumps({"ready":True,"files":len(cases),"script_sha256":hashlib.sha256(source.encode("utf-8")).hexdigest(),"existing_script_unchanged":True}))
