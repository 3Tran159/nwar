from pathlib import Path
import json, shutil, uuid, os
from datetime import datetime
root=Path(r"E:\ntnu_mesh_optimization_20261030")
path=root/"plan.json"
plan=json.loads(path.read_text(encoding="utf-8-sig"))
assert plan["version"]=="light-mesh-watch-4-adaptive-recovery", "Plan version changed; do not overwrite"
assert plan["recovery_policy"]["authorized"] and plan["wave_handoff"]["preserve_HF_session"]
stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
backup=root/("plan_before_wave_goal_"+stamp+"_"+uuid.uuid4().hex[:6]+".json")
shutil.copy2(path,backup)
plan["updated_at"]=datetime.now().astimezone().isoformat()
plan["mission"]={
 "ultimate_scientific_goal":"Run trustworthy hydrofoil simulations in multiple incident wave conditions, quantify wave-induced CL/CD and negative wave added resistance, then investigate active feedforward flap control.",
 "mesh_goal":"Select the lightest mesh that passes quality, force settling and comparable mesh-agreement checks and is usable as a starting point for wave-domain validation. Mesh is a means, not the deliverable.",
 "decision_principle":"Prefer sufficient scientific validity and compute efficiency over marginal cell-count savings. Stop optional mesh coarsening as soon as a defensible lightweight candidate exists and further saving is small or risks delaying wave research.",
 "calm_water_is_not_wave_validation":True,
 "do_not_relax": ["0.5% four-coefficient settling criterion","1% CL/CD agreement with two genuinely finer comparable meshes","documented mesh quality and source provenance","wave propagation/free-surface accuracy checks"],
 "stage_priority":[
  "Complete or transparently diagnose baseline calm-water mesh verification M12/M11/M10; do not fabricate confirmations",
  "Choose lowest-cost supported production candidate, possibly with no extra mesh variant if evidence is already sufficient",
  "Preserve a usable settled calm-water checkpoint and document wave-domain changes and validation blockers",
  "After explicit review of current C01/wave hold, prepare and execute C01, W01 and W02 with verified propagation",
  "Continue authorized contrasting wave-height/wavelength cases from original wave extension plan, analyze wave-added forces",
  "Once wave baseline is trustworthy, assess active flap control as a separate controlled comparison"
 ],
 "critical_transition":"Wave studies are the research outcome. Do not consume Saturday indefinitely making optional finer mesh screens if a scientifically adequate candidate is supported."
}
plan["wave_handoff"]["goal"]="After choosing an adequate light mesh, progress to validated CFD runs for multiple wave heights and wavelengths and then study negative wave added resistance and flap influence. Do not spend unlimited time searching for a marginally smaller mesh."
plan["wave_handoff"]["wave_program"]={
 "reference_plan":r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\mesh_selection_plan.json",
 "extension_plan":r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\wave_extension_plan.json",
 "sequence":[
  {"id":"C01","purpose":"Verified calm-water baseline on selected wave-ready mesh"},
  {"id":"W01","H_m":0.5,"lambda_m":20,"purpose":"First reference head-wave case"},
  {"id":"W02","H_m":0.5,"lambda_m":30,"purpose":"Second reference head-wave case"},
  {"id":"W03-W06","purpose":"Explore lower and higher wave heights at 20 m and 30 m wavelength according to authorized extension plan"},
  {"id":"W07+","purpose":"Explore shorter/other wavelengths and remaining authorized variations, subject to quality and compute budget"}
 ],
 "keep_shared_baseline": {"water_depth_m":24,"speed_m_s":18,"nominal_submergence_m":2,"wave_model_from_existing_plan":"FifthOrderVofWave","changing_wave_conditions_require_domain_resolution_review":True},
 "before_quantitative_wave_claims":[
  "verify incident wave amplitude/phase and propagation over multiple periods",
  "verify sponge forcing/damping, boundary reflections and 3 vs 4 wavelength sensitivity where planned",
  "verify free-surface mesh spatial and temporal resolution and interface CFL",
  "verify periodic force extraction and complete encounter-cycle averaging rather than initial transient",
  "baseline comparison same geometry, wave time settings, normalized lift without buoyancy"
 ],
 "hold_policy":"Current C01/wave hold remains in force until explicit readiness review and permitted release; mesh optimization automation does not automatically launch waves."
}
plan["finish_objective"]="Light, defensible wave-ready mesh is a milestone, not the scientific endpoint. If qualifying candidate is available, stop low-value coarsening and prioritize wave handoff (C01, W01/W02, then varying H and wavelength). Never bypass mesh evidence or wave propagation accuracy because of the calendar."
tmp=path.with_name("plan."+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
check=json.loads(tmp.read_text(encoding="utf-8"))
assert check["mission"]["calm_water_is_not_wave_validation"]
assert check["recovery_policy"]["runbook_sha256"]==plan["recovery_policy"]["runbook_sha256"]
assert check["wave_handoff"]["wave_program"]["sequence"][1]["lambda_m"]==20
os.replace(tmp,path)
with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps({"at":plan["updated_at"],"event":"user_reaffirmed_primary_scientific_goal","message":"Light reliable mesh then multiple validated incident wave conditions; do not optimize indefinitely","plan_backup":str(backup),"solver_changed":False,"wave_hold_changed":False},ensure_ascii=False)+"\n")
print(json.dumps({"success":True,"backup":str(backup),"mission":plan["mission"]["ultimate_scientific_goal"],"wave_cases":["C01","W01","W02","W03-W06","W07+"],"solver_changed":False,"hold_changed":False},ensure_ascii=False))
