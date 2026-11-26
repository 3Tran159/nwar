from pathlib import Path
import csv,json,re,math
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
CASES={"morning_CPU2_H05_dt1": W/"WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0",
       "evening_CPU1_H05_dt1": W/"zero_start_matrix_evening_20261031_182305_689cb9"/"waves"/"L20_H500_baseline",
       "evening_CPU1_H05_dt05":W/"zero_start_matrix_evening_dt05_20261031"/"waves"/"L20_H500_baseline",
       "nearflat_CPU1_H00001_dt1": W/"wave_nearflat_inlet_CPU1_20261031_once"}
def readcsv(p):
 try:
  with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
 except OSError:return []
def js(p):
 try:return json.loads(p.read_text(encoding="utf-8-sig"))
 except (OSError,ValueError):return {}
def rng(rows,k):
 vals=[]
 for r in rows:
  try:
   v=float(r.get(k,"nan"))
   if math.isfinite(v):vals.append(v)
  except:pass
 return {"min":min(vals),"max":max(vals),"last":vals[-1]} if vals else None
result={}
for name,p in CASES.items():
 h=readcsv(p/"history.csv"); l=(p/"star.log").read_text(encoding="utf-8",errors="replace").splitlines() if (p/"star.log").exists() else []
 warns={pattern:sum(pattern.lower() in x.lower() for x in l) for pattern in ("Non-finite value detected","Reversed flow","Connection reset","A floating point error")}
 timing=[]
 for i,x in enumerate(l):
  if re.search(r"TimeStep\s+(400|401|404|405|410|415|418|419|420|450|500|600|900)\b",x):timing.append(l[i:i+3])
 result[name]=dict(history_count=len(h),time=h[-1].get("time_s") if h else None,water=rng(h,"water_volume_m3"),speed=rng(h,"max_speed_m_s"),CFL=rng(h,"max_CFL"),reported_wave_H=rng(h,"actual_wave_height_m"),warns=warns,last_code=js(p/"stage_result.json").get("exit_code"),physical_receipt=js(p/"completed.json"),step_segments=timing[:12],source=js(p/"identity.json"))
out=W/"wave_night_solver_compare_20261031.json";out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
for name,r in result.items(): print(name,"steps",r["history_count"],"t",r["time"],"CFL",r["CFL"],"warns",r["warns"],"exit",r["last_code"])
print("SAVED",out)