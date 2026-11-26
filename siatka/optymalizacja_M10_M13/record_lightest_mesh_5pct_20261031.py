"""Record the user's explicit maximum 5% practical screening criterion without changing active CFD."""
from pathlib import Path
from datetime import datetime
import json,hashlib,uuid,shutil,os
root=Path(r"E:\ntnu_mesh_optimization_20261030")
path=root/"plan.json"
before=path.read_bytes()
plan=json.loads(before.decode("utf-8-sig"))
assert plan["selection"]["stabilization"]["threshold_pct"]==0.5
assert plan["selection"]["agreement_pct"]==1.0
old=plan["selection"].get("lightweight_optimization_screen")
assert old is None or old.get("max_abs_relative_difference_each_pct")==5.0
now=datetime.now().astimezone().isoformat()
backup=root/("plan_before_lightest5_"+datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+uuid.uuid4().hex[:5]+".json")
backup.write_bytes(before)
plan["selection"]["lightweight_optimization_screen"]={
 "approved_by_user_at":now,
 "objective":"Select the lightest adequately reliable foil mesh for multi-wave CFD campaigns",
 "reference_mesh":"M12 / G10_F",
 "max_abs_relative_difference_each_pct":5.0,
 "coefficients":["hydrodynamic_CL","total_CD"],
 "both_required":True,
 "ordering":"Among meshes passing scientific/numerical guards and the individual 5% limits, minimize actual cell count and measured computational cost",
 "reference_basis":"Recompute means over a matched physical-time window for each run from raw data; compare against original M12 accepted reference, with explicit dt sensitivity assessment",
 "separate_temporal_settling_gate":"CL and total CD each mean drift and RMS <0.5% over adjacent full 0.2s windows, 2 consecutive checks",
 "numerical_guards":["correct physics/BC/geometry","valid prism coverage and cell quality","VOF/conservation/CFL safeguards","no conflicting solver resource impact"],
 "not_a_formal_GCI_or_ITTC_rule":True,
 "existing_stricter_1pct_reference_retained":"Original 1% GCI-oriented mesh agreement remains recorded for rigor; it is NOT a hard screen for this new 5% practical optimization objective.",
 "explanatory_note":"M10/M11/M12 have unequal dt, so their currently displayed CL/CD deviations are provisional for a strict mesh-only verdict."
}
plan["updated_at"]=now
if path.read_bytes()!=before:raise RuntimeError("Plan changed concurrently; no write")
tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(plan,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
os.replace(tmp,path)
with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps({"at":now,"event":"user_formalizes_5pct_each_CL_CD_vs_M12_lightest_mesh_screen","reference":"M12","max_abs_pct_each":5.0,"rank_by":"cell_count_and_measured_cost","stabilization_pct_unchanged":0.5,"legacy_GCI_1pct_preserved":True,"solver_untouched":True,"backup":str(backup)},ensure_ascii=False)+"\n")
v=json.loads(path.read_text(encoding="utf-8"))
assert v["selection"]["lightweight_optimization_screen"]["max_abs_relative_difference_each_pct"]==5.0
print(json.dumps({"updated":True,"ref":"M12","max_pct_each":5.0,"time_settling_pct":0.5,"old_stricter_1pct_not_erased":True,"only_plan_changed":True,"backup":str(backup)},ensure_ascii=False))
