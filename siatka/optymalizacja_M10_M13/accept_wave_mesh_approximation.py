from pathlib import Path
from datetime import datetime
import json, shutil, uuid, os
root=Path(r"E:\ntnu_mesh_optimization_20261030")
p=root/"plan.json"
d=json.loads(p.read_text(encoding="utf-8-sig"))
assert d.get("mission",{}).get("calm_water_is_not_wave_validation") is True
assert d.get("recovery_policy",{}).get("authorized") is True
stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
backup=root/("plan_before_accepted_wave_approximation_"+stamp+"_"+uuid.uuid4().hex[:6]+".json")
shutil.copy2(p,backup)
now=datetime.now().astimezone().isoformat()
d["updated_at"]=now
d["mission"]["wave_mesh_accuracy_budget"]={
  "user_decision":"Explicitly accept not having a formally mesh-verified wave solution because of limited computing power; prioritize wave simulations once a defendable lightweight calm-water reference is chosen.",
  "formal_wave_GCI_required_to_start":False,
  "full_multi_mesh_wave_sensitivity_campaign_required":False,
  "status_for_wave_mesh":"Transferred from calm-water-supported mesh. Wave-specific grid convergence/uncertainty is NOT established.",
  "cost_strategy":"Reuse chosen calm-water-verified hydrofoil mesh as the starting template. Make only essential local wave/surface/domain adjustments as physics and stability demand, avoiding a new 3-mesh wave GCI campaign.",
  "minimal_wave_case_sanity_checks":[
    "Check incident wave height, length/period, direction and arrival at the foil against imposed conditions at available probes/field views.",
    "Check finite stable VOF, interface/flow CFL, mass conservation, and absence of severe unexplained numerical force spikes or unphysical wave reflections.",
    "Check that at least the foil and dynamically important free-surface band have plausible spatial resolution for the chosen wavelength/height, and respond to obvious under-resolution without a full convergence campaign.",
    "Compare wave-added loads only after initial transients, using consistent cycle windows and the same solver configuration across cases."
  ],
  "important_distinction":"Short plausibility/quality checks prevent invalid calculations; they are NOT formal wave mesh validation or proof of grid independence.",
  "research_claims":"Report results as exploratory, subject to unquantified wave-discretization uncertainty. Separate observations and within-mesh trends from validated absolute negative wave added resistance. Avoid strong quantitative accuracy claims absent further evidence.",
  "stop_rule":"Do not hold up wave research awaiting full wave-GCI. If simple checks reveal manifestly wrong propagation or unstable numerics, fix the concrete cause or clearly flag limitations instead of silently accepting invalid data.",
  "preserve_calm_gates":"Existing 0.5% calm force stabilization and 1% comparable CL/CD mesh-agreement gates remain unchanged. An early switch cannot misrepresent failed calm checks as passing.",
  "wave_hold":"Still respect existing user hold/ready review for C01 and waves. Policy does not itself authorize releasing that hold or auto-starting waves."
}
d["wave_handoff"]["goal"]="Find a light, credible calm-water mesh and proceed to several physically interpretable wave cases. User explicitly accepts lack of formal wave-mesh independence as a compute-budget limitation; keep cheap wave-plausibility checks and disclose uncertainty."
d["wave_handoff"]["launch_policy"]="No automatic release of existing C01/wave hold. Once approved, proceed with selected calm-mesh-based wave setup without demanding costly formal wave-GCI; require only necessary basic propagation/numerical sanity checks before interpreting wave forces. Document unquantified wave-grid uncertainty."
d["finish_objective"]="Once a sufficiently light and credible calm-water mesh is available, prioritize first defensible waves and varied H/lambda. Do not delay for full wave-specific grid convergence; user accepts this limited-resolution approximation. Never manufacture proof of wave accuracy."
d["mission"]["critical_transition"]="Treat full wave-grid verification as explicitly waived due to compute limits; use quick propagation, VOF, free-surface and force sanity checks. Advance to waves instead of repeating expensive mesh campaigns once sufficient calm-water evidence exists."
tmp=root/("plan_"+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
v=json.loads(tmp.read_text(encoding="utf-8"))
assert v["mission"]["wave_mesh_accuracy_budget"]["formal_wave_GCI_required_to_start"] is False
assert v["recovery_policy"]["runbook_sha256"]==d["recovery_policy"]["runbook_sha256"]
os.replace(tmp,p)
with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps({"at":now,"event":"user_accepted_wave_mesh_approximation","formal_wave_GCI_required":False,"basic_wave_sanity_required":True,"calm_water_gates_unchanged":True,"wave_hold_unchanged":True,"simulations_changed":False,"plan_backup":str(backup)},ensure_ascii=False)+"\n")
print(json.dumps({"updated":True,"plan":str(p),"backup":str(backup),"formal_wave_GCI_required":False,"minimal_wave_checks":len(d["mission"]["wave_mesh_accuracy_budget"]["minimal_wave_case_sanity_checks"]),"calm_gates_unchanged":True,"hold_changed":False,"solver_changed":False},ensure_ascii=False))
