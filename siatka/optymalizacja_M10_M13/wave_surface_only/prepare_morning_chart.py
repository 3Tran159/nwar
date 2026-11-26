"""Make a compact morning comparison table + chart from verified CGNS geometry.
No CFD solver, no forecast masquerading as measured wave propagation.
"""
from pathlib import Path
from datetime import datetime
import csv,json,hashlib,math,os,uuid
root=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
manifest=json.loads((root/"geometry_matrix_manifest.json").read_text(encoding="utf-8"))
audit=json.loads((root/"matrix_independent_geometry_audit.json").read_text(encoding="utf-8"))
assert manifest["scope"]=="wave_geometry_only" and manifest["simulation_steps_taken"]==0
assert audit["all_pass"] is True
records=[]
for record in manifest["records"]:
 key=record["wave"]+"/"+record["name"]
 qa=audit["cases"].get(key,{})
 assert qa.get("status")=="geometry_topology_pass"
 assert qa.get("n_cells")==record["n_cells"]
 assert qa.get("sha256")==record["sha256"]
 assert math.isclose(qa["free_surface_dz_m"],record["dz_m"],abs_tol=1e-12)
 assert Path(record["mesh_path"]).is_file()
 assert qa["checks"]["watertight_face_incidence_and_oriented_internal_faces"]
 assert qa["checks"]["all_analytic_volumes_positive_and_48m3"],qa["checks"]
 wave=record["wave"]
 H=record["height_options_m"]
 records.append({
  "wavelength_m":record["lambda_m"],
  "mesh":record["name"],
  "cells":record["n_cells"],
  "dx_m":record["dx_m"],
  "dz_m":record["dz_m"],
  "lambda_over_dx":round(record["lambda_per_dx"]),
  "H_over_dz_for_H025":round(.25/record["dz_m"],1) if .25 in H else None,
  "H_over_dz_for_H050":round(.5/record["dz_m"],1) if .5 in H else None,
  "H_over_dz_for_H075":round(.75/record["dz_m"],1) if .75 in H else None,
  "geometry_status":"independent_topology_audit_pass",
  "CFD_status":"not_run",
  "target_dt_s":0.001,
  "temporal_control_dt_s":0.0005,
  "wall_seconds_per_step_measured":None,
  "wave_amplitude_error_pct_measured":None,
  "wave_phase_error_deg_measured":None,
  "reflection_coefficient_measured":None,
  "mass_imbalance_pct_measured":None,
  "wave_CFL_measured":None,
  "mesh_path":record["mesh_path"],
  "mesh_sha256":record["sha256"]
 })
assert len(records)==9
files={
 "morning_summary.json": {
  "created_at":datetime.now().astimezone().isoformat(),
  "raw_source":str(root/"geometry_matrix_manifest.json"),
  "independent_audit":str(root/"matrix_independent_geometry_audit.json"),
  "status":"9 independent CGNS geometry topology checks passed; no wave propagation CFD measurements on these 9 variants",
  "all_geometry_audited":True,
  "all_wave_propagation_results_available":False,
  "target_wave_dt_s":0.001,
  "comparison_dt_control_s":0.0005,
  "readout_policy":"Do not claim validated propagation, wall cost or preferred wave mesh based on geometry alone",
  "models":[{"lambda_m":10,"H_m":[.5],"dx_m":.1},{"lambda_m":20,"H_m":[.25,.5,.75],"dx_m":.2},{"lambda_m":30,"H_m":[.25,.5,.75],"dx_m":.2}],
  "records":records,
  "prior_waves_note":"Historical 1 ms no-foil wave run at 53200 cells had a downstream backflow stability guard around t=0.704 s; not an accepted wave propagation result. Geometry-only tests cannot resolve this boundary issue.",
  "sequential_start":"First stabilized flat calm water, then wave from upstream domain origin; do not initialize full wave throughout domain.",
  "M12_or_HF_changed":False,
  "C01_wave_hold_changed":False
 }
}
target=root/"morning_summary.json"
if target.exists():
 prev=json.loads(target.read_text(encoding="utf-8"))
 assert prev.get("records") == records,"Found existing summary with different records, stop to avoid overwrite"
else:
 temp=root/("summary."+uuid.uuid4().hex+".tmp")
 temp.write_text(json.dumps(files["morning_summary.json"],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 os.replace(temp,target)
table=root/"morning_table.csv"
if table.exists():
 assert table.stat().st_size>50,"Existing table empty"
else:
 with table.open("x",newline="",encoding="utf-8-sig") as f:
  fields=["wavelength_m","mesh","cells","dx_m","dz_m","lambda_over_dx","H_over_dz_for_H025","H_over_dz_for_H050","H_over_dz_for_H075","geometry_status","CFD_status","target_dt_s","wall_seconds_per_step_measured","wave_amplitude_error_pct_measured","wave_phase_error_deg_measured","reflection_coefficient_measured"]
  writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
  writer.writeheader()
  writer.writerows(records)
# Plot grouped chart: actual CGNS cells only.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
lams=[10,20,30]
levels=[("coarse",.05),("baseline",.025),("fine",.0125)]
width=.23
x=np.arange(len(lams))
fig,ax=plt.subplots(figsize=(11.5,5.7))
for i,(level,dz) in enumerate(levels):
 ys=[next(r["cells"] for r in records if r["wavelength_m"]==lam and r["mesh"]==level)/1000 for lam in lams]
 rects=ax.bar(x+(i-1)*width,ys,width,label=f"{level}  |  dz = {dz*1000:g} mm")
 for rect,count in zip(rects,ys):
  ax.annotate(f"{count:.1f}k",(rect.get_x()+rect.get_width()/2,rect.get_height()),xytext=(0,4),textcoords="offset points",ha="center",va="bottom",fontsize=10)
ax.set_xticks(x,[f"lambda = {lam} m" for lam in lams])
ax.set_ylabel("Number of cells [thousands]")
ax.set_ylim(0,130)
ax.set_title("Wave-only meshes | Independently audited geometry",pad=18)
ax.legend(ncol=3,loc="upper left",frameon=False,fontsize=9)
ax.grid(axis="y",alpha=.15)
ax.set_axisbelow(True)
fig.text(.07,.02,"Geometry/topology checks only. No CFD wave-propagation results yet. Wave target dt = 1 ms.",ha="left",fontsize=9)
fig.subplots_adjust(left=.09,right=.99,bottom=.16,top=.83)
for extension in ("png","svg"):
 name=root/("comparison_chart."+extension)
 if name.exists():
  assert name.stat().st_size>1000,"Existing chart unexpectedly empty"
 else:
  fig.savefig(name,dpi=150,bbox_inches="tight")
plt.close(fig)
notes=root/"morning_report_notes.md"
if not notes.exists():
 text=["# Wave-only mesh-screen compact briefing","",
 "Geometry verified by independent CGNS topology/volume/face audit. Wave CFD not yet computed for these candidates.",
 "",
 "| Lambda [m] | Coarse cells (dz50mm) | Baseline cells (dz25mm) | Fine cells (dz12.5mm) | dx [m] | lambda/dx |",
 "|---:|---:|---:|---:|---:|---:|"]
 for lam in lams:
  a=[next(r["cells"] for r in records if r["wavelength_m"]==lam and r["mesh"]==level) for level,_ in levels]
  dx=next(r["dx_m"] for r in records if r["wavelength_m"]==lam)
  text.append(f"| {lam} | {a[0]:,} | {a[1]:,} | {a[2]:,} | {dx:g} | {round(lam/dx)} |")
 text+=["","## Wave-height resolution in the vertical",
 "| H [m] | H/dz coarse | H/dz baseline | H/dz fine |","|---:|---:|---:|---:|"]
 for h in (.25,.5,.75):
  text.append(f"| {h:.2f} | {h/.05:g} | {h/.025:g} | {h/.0125:g} |")
 text+=["","## Do not confuse geometry with CFD evidence",
 "- All 9 variants: topology and analytic volume checks pass. No accepted wave propagation run was performed on these variants.",
 "- Horizontal lambda/dx: 100 at 10m, 100 at 20m, 150 at 30m. Only a design parameter.",
 "- Wavelengths 20m and 30m each consider H = .25,.5,.75 m; 10m considers H=.5m. H does not require remeshing, so there are 9 geometries rather than 21.",
 "- Prefer wave dt=0.001s if stable; test 0.0005s on one selected variant separately. Current M12 dt=0.0001s is not the production wave default.",
 "- Calm baseline must stabilize; incoming wave is generated at upstream domain origin with initially flat water elsewhere. Waiting for wave arrival and discarding startup is required.",
 "- Historical 1ms propagation encountered a boundary backflow/stability guard near t=.704s, so no unverified result can be admitted.",
 "- Before combining with foil mesh: verify near-foil prism controls, local resolution, free-surface interface, transition, mass balance, CFL and whether wave has correct amplitude, period and phase.",
 "",
 "Plots: comparison_chart.png / comparison_chart.svg. Raw data: morning_summary.json / morning_table.csv.",
 ""]
 notes.write_text("\n".join(text),encoding="utf-8")
print(json.dumps({"created":True,"records":len(records),"charts":["comparison_chart.png","comparison_chart.svg"],"summary":str(target),"table":str(table),"all_geometry_pass":True,"CFD_results":False,"solver_changed":False},ensure_ascii=False))
