"""Read-only numerical comparison; writes a distinct E: diagnostic, never touches original histories."""
from pathlib import Path
import csv,json,datetime,statistics,math
R=Path(r"E:\ntnu_mesh_optimization_20261030")
M11=R/"M11_G10_M_GPU_queue_20261031_105607_91db08"/"history.csv"
M12=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030\force_stabilization_20261029\calm_settle_G10_F_GPU_live_r2_resume_20261030_173420_4854e1\history.csv")
def load(p):
 out=[]
 with p.open(encoding="utf-8-sig",newline="") as f:
  for x in csv.DictReader(f):
   try:
    row={key:float(x[key]) for key in ("physical_time_s","step","CD","CL","pressure_drag_N","viscous_drag_N","max_CFL","interface_max_CFL")}
    if all(math.isfinite(y) for y in row.values()):out.append(row)
   except (ValueError,KeyError):pass
 return out
a,b=load(M11),load(M12)
assert len(a)>2000 and len(b)>2000
def window(data,lo,hi):
 return [x for x in data if lo-1e-9<x["physical_time_s"]<=hi+1e-9]
def stats(data):
 assert len(data)>=500
 return {"n":len(data),"first_s":data[0]["physical_time_s"],"last_s":data[-1]["physical_time_s"],
  "CL":statistics.fmean(x["CL"] for x in data),"CD":statistics.fmean(x["CD"] for x in data),
  "pressure_drag_N":statistics.fmean(x["pressure_drag_N"] for x in data),
  "viscous_drag_N":statistics.fmean(x["viscous_drag_N"] for x in data),
  "CL_RMS_pct":100*statistics.pstdev(x["CL"] for x in data)/abs(statistics.fmean(x["CL"] for x in data)),
  "CD_RMS_pct":100*statistics.pstdev(x["CD"] for x in data)/abs(statistics.fmean(x["CD"] for x in data))}
t=a[-1]["physical_time_s"];tm=b[-1]["physical_time_s"]
av=stats(window(a,t-.2,t))
ap=stats(window(a,t-.4,t-.2))
br=stats(window(b,tm-.2,tm))
bs=stats(window(b,t-.2,t))
def diffr(m,n):return 100*(m/n-1)
def shifts(prev,cur):
 pden=3855.6
 dp=(cur["pressure_drag_N"]-prev["pressure_drag_N"])/pden
 dv=(cur["viscous_drag_N"]-prev["viscous_drag_N"])/pden
 return dict(CL_mean_shift_pct=diffr(cur["CL"],prev["CL"]),
  CD_mean_shift_pct=diffr(cur["CD"],prev["CD"]),
  prev_CL_RMS_pct=prev["CL_RMS_pct"],recent_CL_RMS_pct=cur["CL_RMS_pct"],
  prev_CD_RMS_pct=prev["CD_RMS_pct"],recent_CD_RMS_pct=cur["CD_RMS_pct"],
  abs_pressure_delta_over_total_CD_pct=100*abs(dp)/abs(cur["CD"]),
  abs_viscous_delta_over_total_CD_pct=100*abs(dv)/abs(cur["CD"]),
  sum_abs_components_over_CD_pct=100*(abs(dp)+abs(dv))/abs(cur["CD"]),
  opposing_signs=dp*dv<0)
result={"at":datetime.datetime.now().astimezone().isoformat(),
 "source_M11":str(M11),"source_M12":str(M12),
 "last_M11_time_s":t,"last_M12_time_s":tm,
 "M11_last_instant":{"CL":a[-1]["CL"],"CD":a[-1]["CD"],"step":a[-1]["step"]},
 "M12_last_instant":{"CL":b[-1]["CL"],"CD":b[-1]["CD"],"step":b[-1]["step"]},
 "instant_diff_M11_minus_M12_pct":{"CL":diffr(a[-1]["CL"],b[-1]["CL"]),"CD":diffr(a[-1]["CD"],b[-1]["CD"])},
 "M11_prev_0p2s":ap,"M11_last_0p2s":av,
 "M12_last_0p2s":br,"M12_matched_M11_time_0p2s":bs,
 "M11_recent_vs_M12_settled_last_0p2s_pct":{"CL":diffr(av["CL"],br["CL"]),"CD":diffr(av["CD"],br["CD"])},
 "M11_vs_M12_same_physical_window_0p2s_pct":{"CL":diffr(av["CL"],bs["CL"]),"CD":diffr(av["CD"],bs["CD"])},
 "M11_settling_0p2s":shifts(ap,av),
 "M11_step_dt_s":a[-1]["physical_time_s"]-a[-2]["physical_time_s"],
 "M12_step_dt_s":b[-1]["physical_time_s"]-b[-2]["physical_time_s"],
 "limitations":"M11 still evolving; different dt and unequal history. Comparisons are diagnostic not formal cross-mesh agreement or GCI. CL already hydro corrected in CSV."}
(R/"m11_vs_m12_readonly_latest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
