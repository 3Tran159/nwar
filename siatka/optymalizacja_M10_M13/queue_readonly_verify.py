import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(r"E:\ntnu_mesh_optimization_20261030")))
import mesh_queue_control_20261031 as m
print("original_ok",m.original_ok())
print("snapshot",json.dumps(m.snapshot(),ensure_ascii=False))
print("no_other_stars",m.no_other_stars())
a=m.read(m.R/"project_primary_independent_audit_20261031_0930.json")
print("audit_keys",list(a))
print("audit_brief",json.dumps({k:v for k,v in a.items() if "pass" in k.lower() or "accept" in k.lower()},ensure_ascii=False)[:1500])
for stage in ("M11","M10"):
 import mesh_queue_worker_20261031 as w
 x=next(s for s in w.STAGES if s[0]==stage)
 p=w.verify_input(x)
 print("pilot",stage,str(p),m.sha(p/"final.sim")[:16],len(w.read_rows(p/"history.csv")))
