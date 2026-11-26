"""Record independent geometry QA result, leaving solver and primary plan unmodified."""
from pathlib import Path
import os,json,uuid,shutil
from datetime import datetime
root=Path(r"E:\ntnu_mesh_optimization_20261030")
sub=root/"wave_surface_only"
planp=sub/"plan.json"
a=json.loads((sub/"independent_geometry_audit.json").read_text(encoding="utf-8"))
b=json.loads((sub/"baseline_dataset_equivalence.json").read_text(encoding="utf-8"))
assert a.get("all_pass") is True and b.get("numerical_mesh_equivalent") is True
plan=json.loads(planp.read_text(encoding="utf-8"))
assert plan["execution_status"] in ("geometry_generated_only_no_solver_started","geometry_independent_audit_pass_no_solver_started")
now=datetime.now().astimezone().isoformat()
if plan["execution_status"]=="geometry_generated_only_no_solver_started":
 backup=sub/("plan_before_audit_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".json")
 shutil.copy2(planp,backup)
 plan["execution_status"]="geometry_independent_audit_pass_no_solver_started"
 plan["updated_at"]=now
 plan["geometry_validation"]={
  "topology_geometry_pass":True,
  "audit_file":str(sub/"independent_geometry_audit.json"),
  "baseline_hdf5_datasets_identical_to_reference":True,
  "baseline_binary_SHA_different_not_dataset_content":True,
  "reference_equivalence_file":str(sub/"baseline_dataset_equivalence.json"),
  "validated_scope":"CGNS face connectivity, BC identifiers, numerical node positions, free-surface band, nonnegative analytic cell volume and one span layer; no STAR-CCM+ mesh importer acceptance or wave propagation tested",
  "case_cells":{"FS_coarse":41200,"FS_baseline":53200,"FS_fine":77200},
  "next":"No solver while M12/M11/M10 active. After resources and hold check, ensure no-foil calm checkpoint then inlet wave propagation at 0.001 s, plus bounded temporal 0.0005 s comparison; do not assume 1 ms physical accuracy or full wave GCI."
 }
 tmp=planp.with_name("plan."+uuid.uuid4().hex+".tmp")
 tmp.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 os.replace(tmp,planp)
 event={"at":now,"event":"independent_wave_mesh_geometry_topology_audit_pass","cases":plan["geometry_validation"]["case_cells"],
 "all_pass":True,"baseline_reference_data_identical":True,
 "report":str(sub/"independent_geometry_audit.json"),
 "no_solver_started":True,"C01_wave_hold_unchanged":True}
 with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
  f.write(json.dumps(event,ensure_ascii=False)+"\n")
 print(json.dumps({"updated":True,"geometry_audit_pass":True,"solver_started":False,"wave_hold_changed":False,"plan":str(planp)},ensure_ascii=False))
else:
 print(json.dumps({"already_recorded":True}))
