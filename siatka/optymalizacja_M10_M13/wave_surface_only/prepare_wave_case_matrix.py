"""Build prioritized design of experiments, not execute STAR solver."""
from pathlib import Path
import json,datetime,os,uuid
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
base=json.loads((ROOT/"morning_summary.json").read_text(encoding="utf-8"))
assert len(base["records"])==9
wavelengths={10:[.5],20:[.25,.5,.75],30:[.25,.5,.75]}
firsts=[(20,.5,"coarse"),(20,.5,"baseline"),(20,.5,"fine"),(30,.5,"coarse"),(30,.5,"baseline"),(30,.5,"fine"),(10,.5,"baseline"),(10,.5,"fine")]
key=lambda lam,H,level:(lam,H,level)
case=[]
for r in base["records"]:
 lam=int(r["wavelength_m"])
 for H in wavelengths[lam]:
  n=r["mesh"]
  rank=firsts.index((lam,H,n))+1 if (lam,H,n) in firsts else None
  case.append({
   "case_id":f"WS_L{lam}_H{round(100*H):03d}_{n}",
   "lambda_m":lam,"H_m":H,"mesh":n,
   "mesh_path":r["mesh_path"],"mesh_sha256":r["mesh_sha256"],"mesh_cells":r["cells"],
   "dx_m":r["dx_m"],"dz_surface_m":r["dz_m"],"lambda_per_dx":r["lambda_over_dx"],
   "H_over_dz":round(H/r["dz_m"],1),
   "time_step_s":.001,
   "time_order":"SECOND_ORDER",
   "inner_iterations":10,
   "startup":"first stabilized FLAT calm water; THEN incident wave at upstream inlet; preserve initial downstream flat interface",
   "screen_type":"short wave-only propagation: height, phase at gauge, reflection, interface CFL and mass, no foil forces",
   "priority":rank,
   "optional":rank is None,
   "status":"geometry_audited_no_solver",
   "settled_calm_checkpoint":None,
   "wave_completed":False,
   "measured_s_per_step":None,
   "measured_amplitude_error_pct":None,
   "measured_reflection":None
  })
assert len(case)==21 and len(set(q["case_id"] for q in case))==21
# Do not launch all 21: these represent allowable combinations. Only targeted examples
# can start when main GPU is idle and hold scope/permissions permit a validated no-foil run.
out={
 "created_at":datetime.datetime.now().astimezone().isoformat(),
 "mode":"planned_experiments_no_solver_launched",
 "cases":case,
 "geometry_variants":9,
 "wave_condition_count":7,
 "possible_wave_mesh_pairs":21,
 "pilot_priority":"Do not run full 21-case Cartesian product; first compare 3 dz for H=0.5 λ20/30, optional λ10 baseline/fine; then focus H0.25/H0.75 on selected mesh(es).",
 "timestep_s":.001,"separate_temporal_control_s":.0005,
 "safety":["M12/M11/M10 and planned controls have GPU priority","No STAR wave solver in parallel","C01/wave user hold remains in force","No automated release or global wave initialization","User allows wave-only testing if resource and authorization gates verified","Do not mistake geometry audit for CFD validation"],
 "result_policy":"Measured propagation/step cost etc only after actual wave solver and trustworthy raw logs."
}
dest=ROOT/"wave_case_matrix.json"
if dest.exists():
 old=json.loads(dest.read_text(encoding="utf-8"))
 assert old.get("geometry_variants")==9 and old.get("possible_wave_mesh_pairs")==21,"Unexpected existing matrix"
else:
 tmp=ROOT/("wavecases."+uuid.uuid4().hex+".tmp")
 tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 os.replace(tmp,dest)
print(json.dumps({"success":True,"cases_planned":len(case),"geometry_variants":9,"wave_conditions":7,"prioritized_pilot_cases":len(firsts),"wave_solver_launched":False,"report":str(dest)},ensure_ascii=False))
