"""Read-only review of R2/R3 wave gauges and M11 calm CL/CD. Creates only E: reports."""
from pathlib import Path
import csv,math,json,statistics,datetime,shutil,collections
P=Path(r"E:\ntnu_mesh_optimization_20261030")
W=P/"wave_surface_only"
B=W/"zero_start_matrix_20261031_13h_R2"/"waves"/"L20_H500_coarse"
C=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"/"waves"/"L20_H500_coarse"
M11=P/"M11_G10_M_GPU_queue_20261031_105607_91db08"
OUT=P/"watch_review_20261031_1528"
OUT.mkdir(exist_ok=True)
def data_csv(p):
 with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def num(v):
 try:
  f=float(v)
  return f if math.isfinite(f) else None
 except:return None
g=collections.defaultdict(dict)
for p in (B/"gauges.csv",C/"gauges.csv"):
 for row in data_csv(p):
  t=num(row.get("time_s")); x=num(row.get("x_m")); eta=num(row.get("eta_actual_m"))
  if None not in (t,x,eta):g[x][round(t,7)]=eta
T=0.8472673206891129
omega=2*math.pi/T
def solve3(A,b):
 M=[list(A[i])+[b[i]] for i in range(3)]
 for k in range(3):
  j=max(range(k,3),key=lambda i:abs(M[i][k]))
  M[k],M[j]=M[j],M[k]
  if abs(M[k][k])<1e-13:return None
  v=M[k][k]
  for i in range(k,4):M[k][i]/=v
  for j in range(3):
   if j==k:continue
   v=M[j][k]
   for i in range(k,4):M[j][i]-=v*M[k][i]
 return [M[i][3] for i in range(3)]
def fit(z,start,end):
 pts=[(t,v) for t,v in sorted(z.items()) if start<=t<=end]
 if len(pts)<30:return {"n":len(pts)}
 vals=[v for t,v in pts]
 X=[[1.,math.sin(omega*t),math.cos(omega*t)] for t,v in pts]
 A=[[sum(row[i]*row[j] for row in X) for j in range(3)] for i in range(3)]
 b=[sum(row[i]*v for row,(_,v) in zip(X,pts)) for i in range(3)]
 beta=solve3(A,b)
 if beta is None:return {"n":len(pts)}
 pred=[sum(v*r for v,r in zip(beta,row)) for row in X]
 amp=math.hypot(beta[1],beta[2])
 rms=math.sqrt(statistics.fmean((v-p)**2 for (_,v),p in zip(pts,pred)))
 return {"n":len(pts),"first_t":pts[0][0],"last_t":pts[-1][0],"mean":statistics.fmean(vals),"min":min(vals),"max":max(vals),
  "half_peak_to_peak":(max(vals)-min(vals))/2,"harmonic_amplitude_m":amp,"harmonic_H_m":2*amp,"harmonic_H_error_pct":100*(2*amp/0.5-1),
  "phase_rad":math.atan2(beta[2],beta[1]),"fit_RMS_residual_m":rms,"RMS_relative_to_amp_pct":100*rms/max(amp,1e-9)}
wave={"period_s":T,"expected_H_m":0.5,"ramp_complete_s":2.09453464,"gauge_metrics":{},
 "interpretation":"H in history is prescribed wave inlet setting, not measured probe amplitude; harmonic fits diagnostic only. No independent reflection analysis.",}
for x,vals in sorted(g.items()):
 wave["gauge_metrics"][str(x)]={"full_range":fit(vals,min(vals),max(vals)),
  "late_2_periods":fit(vals,max(vals)-2*T,max(vals)),
  "last_period":fit(vals,max(vals)-T,max(vals))}
h={}
for label,p in (("original",B/"history.csv"),("R3",C/"history.csv")):
 rows=data_csv(p); t=[num(x.get("time_s")) for x in rows]; water=[num(x.get("water_volume_m3")) for x in rows]
 speed=[num(x.get("max_speed_m_s")) for x in rows]; cfl=[num(x.get("max_CFL")) for x in rows]; icfl=[num(x.get("interface_CFL")) for x in rows]
 nn=lambda z:[v for v in z if v is not None]
 h[label]={"rows":len(rows),"first_time_s":min(nn(t)),"last_time_s":max(nn(t)),
  "water_min_max":(min(nn(water)),max(nn(water))),"water_first_last":(nn(water)[0],nn(water)[-1]),
  "max_speed":max(nn(speed)),"max_bulk_CFL":max(nn(cfl)),
  "max_interface_CFL":max(nn(icfl)) if nn(icfl) else None,
  "nonfinite_columns":{"water":len(water)-len(nn(water)),"speed":len(speed)-len(nn(speed)),
   "bulk_CFL":len(cfl)-len(nn(cfl)),"interface_CFL":len(icfl)-len(nn(icfl))}}
mrows=data_csv(M11/"history.csv")
mr=[]
for x in mrows:
 try:
  a={k:float(x[k]) for k in ("physical_time_s","CL","CD","pressure_drag_N","viscous_drag_N","max_CFL","interface_max_CFL","wall_seconds")}
  if all(math.isfinite(v) for v in a.values()):mr.append(a)
 except:pass
end=mr[-1]["physical_time_s"]
def avg_window(lo,hi):
 s=[r for r in mr if lo<r["physical_time_s"]<=hi]
 d={"n":len(s),"t_start":lo,"t_end":hi}
 for k in ("CL","CD","pressure_drag_N","viscous_drag_N"):
  v=[z[k] for z in s];m=statistics.fmean(v);d[k]=m;d[k+"_RMS_pct"]=100*statistics.pstdev(v)/abs(m)
 return d
before=avg_window(end-.4,end-.2);after=avg_window(end-.2,end)
dr=lambda key:100*(after[key]-before[key])/abs(before[key])
dp=(after["pressure_drag_N"]-before["pressure_drag_N"])/3855.6
dv=(after["viscous_drag_N"]-before["viscous_drag_N"])/3855.6
m11={"physical_time_s":end,"steps":len(mrows),"before":before,"recent":after,
 "mean_shift_CL_pct":dr("CL"),"mean_shift_CD_pct":dr("CD"),
 "pressure_delta_over_total_CD_pct":100*abs(dp)/abs(after["CD"]),
 "viscous_delta_over_total_CD_pct":100*abs(dv)/abs(after["CD"]),
 "sum_abs_comp_over_CD_pct":100*(abs(dp)+abs(dv))/abs(after["CD"]),
 "opposing_components":dp*dv<0,
 "provisional_single_check_CL_CD":all(abs(dr(k))<.5 and before[k+"_RMS_pct"]<.5 and after[k+"_RMS_pct"]<.5 for k in ("CL","CD"))}
logs={}
for label,p in (("base",B/"star.log"),("R3",C/"star.log")):
 txt=p.read_text(encoding="utf-8-sig",errors="replace")
 logs[label]={"nonfinite_velocity_monitor_msg":txt.count("Non-finite value detected while computing values for Monitor Maximum Velocity"),
 "nonfinite_Fx_monitor_msg":txt.count("Non-finite value detected while computing values for Monitor Fx_half"),
 "normalized_continuity_tail":next((line for line in reversed(txt.splitlines()) if "e+11" in line and "Reversed" not in line),"")[:320],
 "reversed_top_count":txt.count("Reversed flow on")}
risk={"t":datetime.datetime.now().astimezone().isoformat(),"runbook_verified":True,"wave":wave,"history_guards":h,
 "star_monitor_warnings":logs,"M11":m11,
 "wave_scientific_accepted":False,"allow_next_auxiliary":False,
 "blocker":"Inspect nonfinite STAR monitors and residual normalization, measured probe amplitude/phase, reflection; no further run pending review."}
(OUT/"audit.json").write_text(json.dumps(risk,ensure_ascii=False,indent=2),encoding="utf-8")
print("REPORT",OUT/"audit.json")
print("M11",json.dumps({k:v for k,v in m11.items() if k not in ("before","recent")},ensure_ascii=False))
print("WAVE_GAUGES",json.dumps({k:{kk:v[kk] for kk in ("late_2_periods","last_period")} for k,v in wave["gauge_metrics"].items()},ensure_ascii=False))
print("GUARDS",json.dumps(h))
print("WARNINGS",json.dumps(logs))
