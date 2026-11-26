from pathlib import Path
import csv,math,json,statistics,datetime
R=Path(r"E:\ntnu_mesh_optimization_20261030")
M=R/"M11_G10_M_GPU_queue_20261031_105607_91db08"/"history.csv"
W=R/"wave_surface_only"/"zero_start_matrix_20261031_13h_R2"/"waves"/"L20_H500_coarse"
def data(p):
 with p.open(encoding="utf8-sig",newline="") as f:return list(csv.DictReader(f))
a=data(M)
last=float(a[-1]["physical_time_s"])
left=[x for x in a if last-.4-1e-8<=float(x["physical_time_s"])<last-.2-1e-8]
right=[x for x in a if last-.2-1e-8<=float(x["physical_time_s"])<=last+1e-8]
names=["CL","CD","pressure_drag_N","viscous_drag_N"]
def stat(rows,key):
 y=[float(x[key]) for x in rows]
 mean=statistics.fmean(y)
 return {"mean":mean,"within_rms_pct":100*statistics.pstdev(y)/abs(mean) if mean else None}
l={x:stat(left,x) for x in names}
r={x:stat(right,x) for x in names}
shift={x:100*abs(r[x]["mean"]-l[x]["mean"])/abs(r[x]["mean"]) for x in ("CL","CD")}
den=abs(r["CD"]["mean"]*3855.6)
dp=r["pressure_drag_N"]["mean"]-l["pressure_drag_N"]["mean"]
dv=r["viscous_drag_N"]["mean"]-l["viscous_drag_N"]["mean"]
b=data(W/"history.csv")
if len(b)>=101:
 recent=b[-100:]
 cost=(float(recent[-1]["wall_s"])-float(recent[0]["wall_s"]))/(int(recent[-1]["step"])-int(recent[0]["step"]))
else:cost=None
o={"timestamp":datetime.datetime.now().astimezone().isoformat(),
"M11":{"t_last_s":last,"windows":[[last-.4,last-.2],[last-.2,last]],
"rows":[len(left),len(right)],"left":l,"right":r,"mean_change_pct":shift,
"project_primary_two_window_provisional_pass":all(z<.5 for z in shift.values()) and all(l[x]["within_rms_pct"]<.5 and r[x]["within_rms_pct"]<.5 for x in ["CL","CD"]),
"component_diagnostic_pct_of_CD":{"pressure":100*abs(dp)/den,"viscous":100*abs(dv)/den,"sum_abs":100*(abs(dp)+abs(dv))/den,"opposing_changes":dp*dv<0},
"not_formal_two_consecutive_checks":True},
"wave":{"recent_measured_s_per_step":cost,"planned_steps":2200,
"remaining_steps":2200-int(b[-1]["step"]),"steps_completed":int(b[-1]["step"]),
"current_elapsed_wall_s":float(b[-1]["wall_s"]),
"macro_budget_wall_s":1800,
"projected_total_wall_s_at_recent_rate":float(b[-1]["wall_s"])+(2200-int(b[-1]["step"]))*cost if cost else None,
"scientifically_accepted":False,
"height_column": "wave.getWaveHeight().getValue() = prescribed inlet-wave height, not probe-measured amplitude",
"residual_warning":"STAR normalized continuity residual ~1e10; reference may be nearly zero from flat-water initialization, so large normalized values alone do not establish divergence. Inspect absolute equations/inner convergence before quantitative claims.",
"actual_propagation":"Not yet demonstrated at x=0 by meaningful periodic probe amplitude; gauge time series needed."
}}
dest=R/"watch_secondary_scientific_audit_20261031_1340.json"
assert not dest.exists()
dest.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")
print(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False))
