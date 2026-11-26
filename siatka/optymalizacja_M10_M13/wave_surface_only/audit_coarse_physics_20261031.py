from pathlib import Path
import csv,math,json,statistics,hashlib
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
D=[
W/"zero_start_matrix_R2_coarse_continuation_20261031_3"/"waves"/"L20_H500_coarse",
W/"zero_start_matrix_R2_coarse_continuation_20261031_4"/"waves"/"L20_H500_coarse"
]
def rows(p):
 with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def solve(A,B):
 n=len(B)
 a=[list(x)+[y] for x,y in zip(A,B)]
 for c in range(n):
  j=max(range(c,n),key=lambda j:abs(a[j][c]))
  a[j],a[c]=a[c],a[j]
  if abs(a[c][c])<1e-12:return None
  v=a[c][c]
  for k in range(c,n+1):a[c][k]/=v
  for i in range(n):
   if i==c:continue
   v=a[i][c]
   for k in range(c,n+1):a[i][k]-=v*a[c][k]
 return [r[-1] for r in a]
def fit(s,T):
 omega=math.tau/T
 B=[[1.0,math.cos(omega*t),math.sin(omega*t)] for t,y in s]
 gram=[[sum(q[i]*q[j] for q in B) for j in range(3)] for i in range(3)]
 rhs=[sum(q[i]*y for q,(t,y) in zip(B,s)) for i in range(3)]
 sol=solve(gram,rhs)
 if not sol:return None
 mean,C,S=sol
 rms=math.sqrt(sum((y-(mean+C*math.cos(omega*t)+S*math.sin(omega*t)))**2 for t,y in s)/len(s))
 return dict(mean_m=mean,amplitude_m=math.hypot(C,S),height_m=2*math.hypot(C,S),phase_rad=math.atan2(-S,C),fit_rms_m=rms,points=len(s),min_m=min(y for t,y in s),max_m=max(y for t,y in s))
def wrap(a):return (a+math.pi)%math.tau-math.pi
T=0.8472673206891129; start=3.6
allg={};allh={}
for p in D:
 for row in rows(p/"gauges.csv"):
  try:t=float(row["time_s"]);x=float(row["x_m"]);eta=float(row["eta_actual_m"])
  except:continue
  if math.isfinite(t) and math.isfinite(eta) and t>=start:
   allg.setdefault(x,{})[round(t,8)]=eta
 for row in rows(p/"history.csv"):
  try:t=float(row["time_s"])
  except:continue
  if t>=start:allh[round(t,8)]=row
f={}
for x,rs in sorted(allg.items()):
 s=sorted(rs.items())
 f[str(x)]=fit(s,T) if len(s)>10 else None
water=[float(r["water_volume_m3"]) for r in allh.values()]
cfl=[float(r["max_CFL"]) for r in allh.values()]
icfl=[float(r["interface_CFL"]) for r in allh.values()]
speed=[float(r["max_speed_m_s"]) for r in allh.values()]
p={}
for xa,xb in [(-10,0),(0,10),(10,20),(-15,-10)]:
 a,b=f[str(float(xa))],f[str(float(xb))]
 if a and b:
  # eta(x,t)= A cos(omega*t-k*x+phi), phase at downstream x decreases by k*dx
  delta=wrap(b["phase_rad"]-a["phase_rad"])
  expected=wrap(-math.tau*(xb-xa)/20)
  p[f"{xa}_to_{xb}"]=dict(observed_wrapped_rad=delta,expected_wrapped_rad=expected,phase_error_rad=wrap(delta-expected))
report={
"at":"2026-10-31T22:5x Europe/Oslo, analytical run (read-only source)",
"status":"kinematic_plausibility_only_not_accepted","date_case":"2026-10-31",
"case":"wave-only FS_coarse H0.5 lambda20",
"sample_after_t_s":start,"last_time_s":max(allh) if allh else None,
"model_T_s":T,"periods_in_window":(max(allh)-start)/T if allh else 0,
"gauges_harmonic_fit":f,"phase_comparison":p,
"volume":{"min":min(water),"max":max(water),"max_pct_excursion_from38p4":100*max(abs(v-38.4) for v in water)/38.4},
"CFL":{"max":max(cfl),"max_interface_finite":max((v for v in icfl if math.isfinite(v)),default=None),"nan_count":sum(not math.isfinite(v) for v in icfl)},
"speed_max_m_s":max(speed),
"inputs":[{"path":str(q),"sha256":hashlib.sha256(q.read_bytes()).hexdigest()} for p in D for q in [p/"gauges.csv",p/"history.csv",p/"star.log"]],
"known_numerical_blocker":"Last coarse STAR continuity printed approximately 2.44e11 and water residual 5.45e6 despite finite gauge and volume. Residual behavior not reconciled; no convergence/mesh acceptance; R4 user/performance stop instead of converged wave acceptance.",
"note":"Outlet x40 gauge is in damping vicinity; not a validation/reference of reflections. This is postprocessing only and never certifies wave-only mesh."
}
out=W/"wave_coarse_physics_audit_20261031.json"
out.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
print("WROTE",out,"n",len(allh),"T",T,"volume_max_pct",round(report["volume"]["max_pct_excursion_from38p4"],4),"max_CFL",round(max(cfl),4))
for x in ["-15.0","-10.0","0.0","10.0","20.0","40.0"]:
 a=f.get(x)
 print("x",x,"H",round(a["height_m"],4) if a else None,"phase",round(a["phase_rad"],3) if a else None,"rms",round(a["fit_rms_m"],5) if a else None)
for p,v in report["phase_comparison"].items():print("dphase",p,round(v["observed_wrapped_rad"],3),"target",round(v["expected_wrapped_rad"],3),"error",round(v["phase_error_rad"],3))