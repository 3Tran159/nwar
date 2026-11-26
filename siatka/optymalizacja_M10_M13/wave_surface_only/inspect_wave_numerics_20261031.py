from pathlib import Path
import json,csv,re,math,hashlib,statistics
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
runs={
"flat_CPU2":W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c",
"wave_CPU2_H05_dt1":W/"WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0",
"wave_CPU1_H05_dt1":W/"zero_start_matrix_evening_20261031_182305_689cb9"/"waves"/"L20_H500_baseline",
"wave_CPU1_H05_dt05":W/"zero_start_matrix_evening_dt05_20261031"/"waves"/"L20_H500_baseline",
"nearflat_CPU1_dt1":W/"wave_nearflat_inlet_CPU1_20261031_once"
}
pat=re.compile(r"^\s*(\d+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+")
out={}
for name,path in runs.items():
 log=path/"star.log"
 lines=log.read_text(errors="replace",encoding="utf-8").splitlines() if log.exists() else []
 currstep=0; currtime=0; residual={}
 for ln in lines:
  m=re.search(r"TimeStep\s+(\d+):\s+Time\s+([\d.Ee+-]+)",ln)
  if m:
   currstep=int(m.group(1));currtime=float(m.group(2))
  a=pat.match(ln)
  if a and currstep:
   try:
    v=[float(x) for x in a.groups()[1:]]
    residual[currstep]={"cont":v[0],"mx":v[1],"my":v[2],"mz":v[3],"tke":v[4],"sdr":v[5],"water":v[6]}
   except:pass
 for fname in ["history.csv","gauges.csv"]:
  file=path/fname
  if file.exists():
   with file.open(encoding="utf-8-sig") as f: rows=list(csv.DictReader(f))
   if fname=="history.csv":
    h=rows
   else:
    g=rows
  elif fname=="history.csv":h=[]
  else:g=[]
 def mean_rms(v):
  return {"min":min(v),"max":max(v),"last":v[-1]} if v else None
 resitems=list(sorted(residual.items()))
 rsummary={}
 for k in ["cont","mx","my","mz","water"]:
  vals=[v[k] for step,v in resitems if math.isfinite(v[k]) and step>=400]
  rsummary[k]=mean_rms(vals)
 aft=[(step,vals) for step,vals in resitems if step in [400,401,402,405,410,418,419,420,500,600,900]]
 gauges={}
 for row in g:
  try:
   x=row["x_m"]; eta=float(row["eta_actual_m"]);t=float(row["time_s"])
   if x not in gauges:gauges[x]=[]
   gauges[x].append((t,eta))
  except:pass
 gauges={x:{"last":v[-1],"peak":max(abs(a) for t,a in v),"count":len(v)} for x,v in gauges.items()}
 out[name]={"step_timeline":aft,"max_residuals_post_0p4":rsummary,"gauges":gauges,"history_last":h[-1] if h else {},"history_count":len(h),"error_tail": [x for x in lines[-90:] if "Error" in x or "error" in x or "TimeStep" in x or "Server process" in x][-15:],"star_sha256":hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None}
 print(name,"H",len(h),"res",len(resitems),"gauge",len(g),"last",h[-1].get("time_s") if h else None,"cont",rsummary.get("cont"),"gaugemax",max([v["peak"] for v in gauges.values()],default=None))
outpath=W/"inspect_wave_numerics_20261031.json"
outpath.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
print("REPORT",outpath)