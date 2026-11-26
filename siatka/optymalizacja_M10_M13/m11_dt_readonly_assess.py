from pathlib import Path
import csv,json,math,statistics
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
R=Path(r"E:\ntnu_mesh_optimization_20261030")
a=[("M11 pilot",B/"force_stabilization_20261029"/"calm_pilot_G10_M_continued_r1"),
("M12 final",B/"force_stabilization_20261029"/"calm_settle_G10_F_GPU_live_r2_resume_20261030_173420_4854e1"),
("M10 pilot",B/"force_stabilization_20261029"/"calm_pilot_W01a_continued_r1")]
for name,p in a:
 try:
  with (p/"history.csv").open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
  print(name, "rows",len(rows),"last_t",rows[-1].get("physical_time_s"),"columns",list(rows[0]))
  for k in ["max_CFL","interface_max_CFL","max_velocity_m_s","CD","CL","CL_total","wall_seconds"]:
   vals=[float(r[k]) for r in rows[-min(400,len(rows)):] if k in r and r[k]!="" and math.isfinite(float(r[k]))]
   if vals:print(" ",k,"max",max(vals),"min",min(vals),"median",statistics.median(vals))
 except Exception as e:print(name,"ERROR",type(e).__name__,str(e)[:150])
print("possible_varying_timestep_trials")
for p in R.rglob("pilot_result.json"):
 try:
  x=json.loads(p.read_text(encoding="utf8-sig"))
  if any(q in str(p).lower() for q in ["m11","g10_m"]):print(p.name,str(p.parent),str(x)[:300])
 except Exception:pass
