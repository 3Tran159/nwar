"""Record wave timestep design priority, leave running solver and other workflows unchanged."""
from pathlib import Path
import json, shutil, uuid, os
from datetime import datetime
root=Path(r"E:\ntnu_mesh_optimization_20261030")
main=root/"plan.json"
surface=root/"wave_surface_only"/"plan.json"
m=json.loads(main.read_text(encoding="utf-8-sig"))
w=json.loads(surface.read_text(encoding="utf-8-sig"))
dt=json.loads(Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030\accepted_timestep.json").read_text(encoding="utf-8-sig"))
assert abs(dt["dt_s"]-1e-4)<1e-12 and dt["scope"]=="calm water"
assert m["wave_handoff"]["staged_wave_start"]["mandatory"] is True
assert w["execution_status"]=="plan_only_no_wave_solver_launched"
stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
backup=root/("timestep_policy_before_"+stamp+"_"+uuid.uuid4().hex[:6])
backup.mkdir(exist_ok=False)
for f in (main,surface):shutil.copy2(f,backup/f.name.replace("plan","main_plan" if f==main else "surface_plan"))
now=datetime.now().astimezone().isoformat()
policy={
 "user_priority":"Aim for dt=0.001 s in practical W01/W02 and other foil-in-wave runs; dt=0.0001 s M12 is a conservative calm-water mesh-screen setting and must not become a default production wave timestep.",
 "wave_production_target_dt_s":0.001,
 "wave_temporal_check_dt_s":0.0005,
 "fine_diagnostic_only_dt_s":0.0001,
 "selection_rule":"Choose the least expensive (mesh,dt,VOF substepping,inner convergence) combination with stable finite free-surface transport and sufficiently insensitive wave probes/force results. Neither grid size nor the earlier calm-water dt alone proves a viable 1 ms foil simulation.",
 "test_sequence":[
  "Use a common 1 ms physical step, same time order, 10 inner iterations and identical inlet/initial forcing, boundary/sponge conditions and probes across wave-only surface-mesh candidates. BEGIN with stabilized calm water, THEN inject wave upstream and allow propagation; never start with a domain filled by a wave.",
  "Repeat a short matched segment at 0.5 ms on a chosen candidate, using identical physical windows and compare gauge amplitude, phase, reflection, and where available force response. Probe half-step only if its cost is justified and bounded.",
  "If 1 ms triggers a guard, identify the local cause: advection/interface CFL, local foil cell size, pressure/VOF solver convergence, backflow near outlet or numerical startup. Do not assume refinement fixes a CFL failure; it can worsen time-step constraints.",
  "When preparing joined foil+wave mesh, preserve supported near-foil/prism and wave surface resolutions, check transition and validity, then perform short calm-to-wave pilot at 1 ms with full guards. If 1 ms cannot pass, prefer an evidence-supported 0.5 ms rather than relaxing safety or corrupting scientific agreement.",
  "0.1 ms is optional targeted diagnostic or independently supported fallback, not the default for all long waves."
 ],
 "prior_evidence":{
  "calm_M12_dt_s":0.0001,
  "historic_W01_with_foil_dt_s":0.001,
  "historic_W01_problem":"Earlier foil-wave continuation at dt=1 ms had interface CFL around 4.58 and later numerical air jet; no-foil 1 ms run encountered outlet backflow and 50 m/s guard at t=0.704 s. Neither is evidence that simply refining a surface mesh makes 1 ms stable.",
  "initial_wave_period_s_approx":0.847,
  "physical_steps_per_period_at_1ms_approx":847
 },
 "research_limitations":"1 ms temporal accuracy and robust VOF/force convergence remain hypotheses to test; do not claim validated until short matched check passes.",
 "resource_safety":"M12 is actively using GPU. Only offline mesh geometry/audit on spare CPU resources is permitted without altering its performance; do not launch another STAR solver or wave cases while the main solver holds resources or the C01 wave hold remains.",
 "changes_to_active_solver":False
}
m["updated_at"]=now
m["wave_handoff"]["timestep_priority"]=policy
m["mission"]["critical_transition"]="Use practical wave production target dt=0.001 s (if verified), compare to 0.0005 s on bounded cases; do not automatically use 0.0001 s M12 step for all waves. Short no-foil wave-surface trials then join with credible foil nearfield and start waves from calm checkpoint/inlet."
w["updated_at"]=now
w["timestep_priority"]=policy
w["baseline"]["preferred_wave_dt_s"]=0.001
w["baseline"]["temporal_sensitivity_dt_s"]=0.0005
w["only_one_parameter_changes"]="For the primary spatial comparison hold temporal step dt=0.001 s fixed along with model, forcing, domain and x-spacing, varying only free-surface dz. On the selected representative grid only, perform a separate matched temporal sensitivity 0.001 vs 0.0005 s; do not mix the tests in the same spatial-convergence comparison."
w["execution_status"]="geometry_generated_only_no_solver_started"
w["geometry_manifest"]=str(surface.parent/"geometry_manifest.json")
for path,content in ((main,m),(surface,w)):
 temp=path.with_name("plan_"+uuid.uuid4().hex+".tmp")
 temp.write_text(json.dumps(content,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 check=json.loads(temp.read_text(encoding="utf-8"))
 assert check["wave_handoff"]["staged_wave_start"]["mandatory"] if path==main else check["timestep_priority"]["wave_production_target_dt_s"]==0.001
 os.replace(temp,path)
with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps({"at":now,"event":"user_wave_production_dt_1ms_target","preferred_dt_s":0.001,"temporal_check_dt_s":0.0005,"calm_M12_unchanged":True,"wave_hold_unchanged":True,"new_wave_solver_started":False,"backup":str(backup)},ensure_ascii=False)+"\n")
print(json.dumps({"success":True,"wave_production_target_dt_s":0.001,"temporal_check_dt_s":0.0005,"geometry_variants":["FS_coarse 41200","FS_baseline 53200","FS_fine 77200"],"M12_unchanged":True,"wave_solver_launched":False,"wave_hold_unchanged":True,"backup":str(backup)},ensure_ascii=False))
