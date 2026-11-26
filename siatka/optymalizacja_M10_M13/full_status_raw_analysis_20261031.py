"""READ-ONLY analysis of existing CFD raw data. No changes to solver, locks, macro or histories."""
from pathlib import Path
import csv,json,math,statistics,datetime,collections,hashlib
R=Path(r"E:\ntnu_mesh_optimization_20261030")
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
W=R/"wave_surface_only"
M11=R/"M11_G10_M_GPU_queue_20261031_105607_91db08"/"history.csv"
M12=B/"force_stabilization_20261029"/"calm_settle_G10_F_GPU_live_r2_resume_20261030_173420_4854e1"/"history.csv"
M10=B/"force_stabilization_20261029"/"calm_pilot_W01a_continued_r1"/"history.csv"
wave1=W/"zero_start_matrix_20261031_13h_R2"/"waves"/"L20_H500_coarse"
wave2=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"/"waves"/"L20_H500_coarse"
def csv_rows(p):
 with p.open(newline="",encoding="utf-8-sig") as f:
  return [dict(x) for x in csv.DictReader(f)]
def mean(t,k):return statistics.fmean(float(x[k]) for x in t)
def rms(t,k):
 v=[float(x[k]) for x in t];m=statistics.fmean(v)
 return 100*statistics.pstdev(v)/abs(m)
def pct(v,ref):return 100*(v/ref-1)
def section(data,l,r):
 return [x for x in data if l<float(x["physical_time_s"])<=r]
def force_stat(tab):
 return {"n":len(tab),"start_time":float(tab[0]["physical_time_s"]),"end_time":float(tab[-1]["physical_time_s"]),
  "CL_mean":mean(tab,"CL"),"CD_mean":mean(tab,"CD"),
  "CL_RMS_pct":rms(tab,"CL"),"CD_RMS_pct":rms(tab,"CD"),
  "pressure_drag_N":mean(tab,"pressure_drag_N"),"viscous_drag_N":mean(tab,"viscous_drag_N")}
a,b,c=csv_rows(M11),csv_rows(M12),csv_rows(M10)
t=float(a[-1]["physical_time_s"]);T=float(b[-1]["physical_time_s"])
ap=force_stat(section(a,t-.4,t-.2)); ar=force_stat(section(a,t-.2,t))
br=force_stat(section(b,T-.2,T));bm=force_stat(section(b,t-.2,t))
pdrift=ar["pressure_drag_N"]-ap["pressure_drag_N"]
vdrift=ar["viscous_drag_N"]-ap["viscous_drag_N"]
cd_den=abs(ar["CD_mean"])*3855.6
result={"at":datetime.datetime.now().astimezone().isoformat(),
"mesh_force":{
"M10":{"n_cells":317277,"rows":len(c),"last_t_s":float(c[-1]["physical_time_s"]),
 "last_CL_total":float(c[-1].get("CL_total",0)),
 "last_CD":float(c[-1]["CD"]),
 "CL_hydro_derived_once":float(c[-1]["CL_total"])-22.718189111947265/3855.6,
 "note":"only short W01a continuation, NOT stabilized"},
"M11":{"n_cells":595285,"rows":len(a),"last_step":int(a[-1]["step"]),"last_t_s":t,"last_CL":float(a[-1]["CL"]),"last_CD":float(a[-1]["CD"]), "previous_window":ap,"last_window":ar,
 "CL_window_shift_pct":pct(ar["CL_mean"],ap["CL_mean"]),
 "CD_window_shift_pct":pct(ar["CD_mean"],ap["CD_mean"]),
 "pressure_delta_over_total_CD_pct":100*abs(pdrift)/cd_den,
 "viscous_delta_over_total_CD_pct":100*abs(vdrift)/cd_den,
 "sum_component_moduli_pct":100*(abs(pdrift)+abs(vdrift))/cd_den,
 "component_opposing_sign":pdrift*vdrift<0,
 "current_single_diagnostic_window_pass":all((abs(pct(ar[k+"_mean"],ap[k+"_mean"]))<0.5 and ap[k+"_RMS_pct"]<0.5 and ar[k+"_RMS_pct"]<0.5) for k in ("CL","CD")),
 "note":"NOT two consecutive formal checks; different dt from M12"},
"M12":{"n_cells":1154199,"rows":len(b),"last_step":int(b[-1]["step"]),"last_t_s":T,"last_CL":float(b[-1]["CL"]),"last_CD":float(b[-1]["CD"]),"last_window":br,"matched_M11_time_window":bm,"saved_primary_two_pass":True},
"relative_M11_vs_M12":{
 "instantaneous_CL_pct":pct(float(a[-1]["CL"]),float(b[-1]["CL"])),
 "instantaneous_CD_pct":pct(float(a[-1]["CD"]),float(b[-1]["CD"])),
 "last_0p2s_mean_vs_M12_final_0p2s_CL_pct":pct(ar["CL_mean"],br["CL_mean"]),
 "last_0p2s_mean_vs_M12_final_0p2s_CD_pct":pct(ar["CD_mean"],br["CD_mean"]),
 "same_physical_0p2s_CL_pct":pct(ar["CL_mean"],bm["CL_mean"]),
 "same_physical_0p2s_CD_pct":pct(ar["CD_mean"],bm["CD_mean"]),
 "time_step_not_matched":True
}},
"wave":{}}
h1,h2=csv_rows(wave1/"history.csv"),csv_rows(wave2/"history.csv")
g1,g2=csv_rows(wave1/"gauges.csv"),csv_rows(wave2/"gauges.csv")
period=0.8472673206891129
end=float(h2[-1]["time_s"]); start=end-2*period
series=collections.defaultdict(list)
for x in g1+g2:
 try:
  tt=float(x["time_s"]);xx=float(x["x_m"]);y=float(x["eta_actual_m"])
  if start<=tt<=end and math.isfinite(y):series[xx].append((tt,y))
 except:continue
gauges=[]
for x,v in sorted(series.items()):
 # remove duplicated exact t from the stage boundary
 points=sorted(dict((round(t,6),y) for t,y in v).items())
 vals=[y for t,y in points]
 av=statistics.fmean(vals)
 s=statistics.fmean((y-av)*math.sin(2*math.pi*(t-start)/period) for t,y in points)*2
 co=statistics.fmean((y-av)*math.cos(2*math.pi*(t-start)/period) for t,y in points)*2
 gauges.append(dict(x_m=x,n=len(points),max_eta_m=max(vals),min_eta_m=min(vals),H_peak_to_peak_m=max(vals)-min(vals),
  harmonic_H_m=2*math.hypot(s,co),eta_mean_m=av))
all_h=h1+h2
result["wave"]={
 "case":"H0.5 lambda20 FS_coarse 41200 cells","time_s":end,"wave_start_time_s":0.4,"post_ramp_last_2_periods":dict(begin_s=start,end_s=end),
 "first_stage":{"steps":int(h1[-1]["step"]),"status":json.loads((wave1/"completed.json").read_text())["status"]},
 "continuation":{"steps":int(h2[-1]["step"]),"status":json.loads((wave2/"completed.json").read_text())["status"]},
 "total_wave_solver_steps":int(h1[-1]["step"])+int(h2[-1]["step"]),
 "first_wall_s":float(h1[-1]["wall_s"]),"continuation_wall_s":float(h2[-1]["wall_s"]),
 "weighted_s_per_step":(float(h1[-1]["wall_s"])+float(h2[-1]["wall_s"]))/(int(h1[-1]["step"])+int(h2[-1]["step"])),
 "max_bulk_CFL":max(float(x["max_CFL"]) for x in all_h),
 "max_interface_CFL_finite":max(float(x["interface_CFL"]) for x in all_h if x["interface_CFL"].lower()!="nan"),
 "water_vol_start_m3":float(h1[0]["water_volume_m3"]),"water_vol_end_m3":float(h2[-1]["water_volume_m3"]),
 "water_vol_range_m3":max(float(x["water_volume_m3"]) for x in all_h)-min(float(x["water_volume_m3"]) for x in all_h),
 "gauges_late":gauges,
 "full_propagation_or_wave_grid_accepted":False,
 "warning":"These peak-to-peak values are measured on last 2 commanded periods; no decomposition of reflections or phase-error validation, and no independent mesh comparison."}
out=R/"full_status_raw_analysis_latest.json"
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps(result,ensure_ascii=False,indent=2))
