from pathlib import Path
from datetime import datetime
import os,json,shutil,uuid,hashlib
root=Path(r"E:\ntnu_mesh_optimization_20261030")
planpath=root/"plan.json"
plan=json.loads(planpath.read_text(encoding="utf-8-sig"))
assert "wave_handoff" in plan and "mission" in plan and "recovery_policy" in plan
stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
backup=root/("plan_before_staged_wave_start_"+stamp+"_"+uuid.uuid4().hex[:6]+".json")
shutil.copy2(planpath,backup)
now=datetime.now().astimezone().isoformat()
startup={
 "mandatory":True,
 "user_instruction":"First stabilize flat calm water, then launch the incident wave from the START/UPSTREAM END of the computational domain. Never initialize a full wave simultaneously in the whole domain.",
 "phase_1_calm":{
  "wave_height_m":0,"wave_forcing":"off","wave_initial_condition":"flat water at z=2 m in baseline domain",
  "goal":"Obtain and save a verified calm-water velocity, pressure, turbulence and VOF field for the same domain and foil arrangement. For propagation-only calibration the no-foil domain also starts flat and steady.",
  "checks":["Finite stable flow and VOF","Control of conservation/mass and physically plausible forces","Use existing accepted 0.5% CL/CD force criteria in foil baseline, never mark failed baseline accepted","Record time, mesh/physics/BC identity, completed .sim and hash"]
 },
 "phase_2_inlet_wave":{
  "start_from":"verified phase-1 calm-water .sim without reinitializing/recreating the previous flow",
  "wave_origin":"upstream domain inlet x_min, or the narrow upstream wave forcing region if used as the physically equivalent boundary generator",
  "initial_free_surface":"preserve initially FLAT free surface downstream; do not prepopulate wave train in entire domain",
  "generator":"Configure selected wave model (existing FifthOrderVofWave), height and length, verified upstream orientation and phase; ramp/inlet transition if necessary for stability, counting it as startup transient",
  "propagation":"Allow wave to develop through upstream section, verify height/period/arrival and reflections at gauges; protect foil zone and damp outgoing waves downstream",
  "discard":"Discard initial boundary switching and wave-travel transient; begin force-period statistics only after arrival and sufficiently periodic response"
 },
 "results":{
  "time_indexing":"Preserve calm saved timestamp and physical time; distinguish wave onset timestamp, first arrival at foil, and first accepted averaging window",
  "comparison":"Calculate wave-induced forces relative to same-setup calm control with matching density/area/CL convention and stable comparison windows; do not mix unequal startup histories",
  "review_gates":"No full wave GCI required under current compute-budget policy, but require basic propagation, CFL/VOF, reflections, mass-budget and time-window sanity checks before interpretation"
 },
 "controls":{
  "no_active_solver_change":True,
  "do_not_remove_wave_hold":True,
  "do_not_launch_wave_on_this_plan_update":True,
  "preserve_HF":True,
  "independent_surface_mesh_trials":"Allowed geometrical preparation in separate E: root only if cheap and non-interfering. Propagation solver trials only after safe resource and hold authorization checks; not concurrent with current M12/M11/M10."
 }
}
plan["updated_at"]=now
plan["wave_handoff"]["staged_wave_start"]=startup
plan["wave_handoff"]["prepare_when_ready"]="Mandatory two stages per wave: verified flat calm-water continuation on same mesh/domain, then wave injected at upstream x_min or strictly localized inlet forcing from calm checkpoint; preserve initial flat downstream VOF and permit wave travel before evaluating forces. Record wave onset, arrival and averaging time; do not initialize a full wave field throughout domain."
plan["mission"]["stage_priority"]=[x for x in plan["mission"]["stage_priority"] if x != "After explicit review of current C01/wave hold, prepare and execute C01, W01 and W02 with verified propagation"]
plan["mission"]["stage_priority"].insert(3,"After explicit review of C01/wave hold, start from accepted flat calm water on the selected wave-domain mesh, inject each wave at upstream inlet and propagate it to the foil before sampling forces; then run W01/W02")
surface={
 "version":"wave-surface-separate-screen-v1",
 "created_at":now,
 "user_authorization":"Where resources permit, examine wave-only free-surface refinement without foil and later combine the wave refinement with the independently supported hydrofoil near-field mesh.",
 "purpose":"Find minimally adequate resolution to transport incident waves, isolating free-surface discretization error from foil near-wall and prism-grid error.",
 "wave_startup_reference":"plan.json wave_handoff.staged_wave_start applies to every propagation-only pilot: begin with stabilized flat water, then generate wave from upstream x_min, not entire-domain initial wave.",
 "baseline":{"foil":False,"U_m_s":18.0,"depth_m":24.0,"waterline_z_m":2.0,"x_m":[-35.0,45.0],"z_m":[-22.0,8.0],"span_m":0.02,"lambda_m":20.0,"H_m":0.5,"x_resolution_m":0.2,"near_surface_z_band_m":[1.25,2.75],"initial_wave_field":"flat","wave_fifth_order_for_propagation":True},
 "grid_candidates":[
  {"name":"FS_coarse","dz_at_free_surface_m":0.05,"cells_per_H_at_0.5m":10,"purpose":"Coarse reference"},
  {"name":"FS_baseline","dz_at_free_surface_m":0.025,"cells_per_H_at_0.5m":20,"purpose":"Retained previously built 53.2k-cell no-foil geometry, subject to transport review"},
  {"name":"FS_fine","dz_at_free_surface_m":0.0125,"cells_per_H_at_0.5m":40,"purpose":"Fine reference"}
 ],
 "only_one_parameter_changes":"vertical free-surface dz; hold horizontal dx, domain, wave model/forcing, U, time step, iteration settings and sponge/boundary controls constant across comparisons",
 "geometry_only_when_M12_busy":True,
 "do_not_run_solver_concurrently_with_M12":True,
 "do_not_touch_C_or_F_originals":True,
 "all_new_outputs_under":r"E:\ntnu_mesh_optimization_20261030\wave_surface_only",
 "waves_hold":"User hold on original C01/waves remains. Do not begin wave propagation runs without verifying scope/authorization and no conflicting solver; geometry-only meshing is independent and does not lift hold.",
 "prior_failure_note":"Earlier 53.2k-cell wave-no-foil run stopped near t=0.704s on stability guard with downstream boundary backflow; exclude such failed runs from wave propagation accuracy claims. Diagnose before deciding any full propagation run.",
 "validation_gates":["CGNS geometry, 1 span cell, section area/volume, ordered spacing, no negative volume/invalid faces","Boundary topology and consistent inlet/outlet, flat initial water before wave phase","Free-surface wave height/period/phase progression and transmission to the foil station","Finite CFL/VOF, realistic reflection/damping, credible mass/volume conservation, no unexplained growing disturbances","Compare equal physical time windows and gauge phases; measured runtime and cell count per candidate"],
 "integration":"After enough evidence, retain accepted vertical near-surface resolution and combine with accepted foil/prism/nearfield mesh, using independent audit of prism coverage/topology/free-surface transition and final short joined-grid CFD sanity check. Neither separate part proves full coupled mesh independence.",
 "priority":"Do not delay main mesh selection or launch of first meaningful wave cases for a costly full three-level wave GCI; use spare resources for lightweight evidence and be honest about uncertainty.",
 "execution_status":"plan_only_no_wave_solver_launched"
}
dest=root/"wave_surface_only"
dest.mkdir(parents=True,exist_ok=True)
sp=dest/"plan.json"
assert not sp.exists(),"Wave surface plan already exists; never overwrite"
sptmp=dest/("plan."+uuid.uuid4().hex+".tmp")
sptmp.write_text(json.dumps(surface,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
os.replace(sptmp,sp)
plan["wave_handoff"]["surface_grid_screen_reference"]=str(sp)
tmp=root/("plan."+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
assert json.loads(tmp.read_text(encoding="utf-8"))["wave_handoff"]["staged_wave_start"]["mandatory"] is True
os.replace(tmp,planpath)
with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps({"at":now,"event":"user_requires_calm_first_then_upstream_wave_start","surface_mesh_screen":str(sp),"solver_changed":False,"wave_hold_changed":False,"backup":str(backup)},ensure_ascii=False)+"\n")
print(json.dumps({"success":True,"staged_wave_start":True,"surface_mesh_screen_plan":str(sp),"backup":str(backup),"solver_changed":False,"wave_hold_changed":False},ensure_ascii=False))
