from pathlib import Path
import csv,statistics
R=Path(r"E:\ntnu_mesh_optimization_20261030")
a=R/"M11_G10_M_dt0002_GPU_pilot_20261031_105103_6e9452"/"history.csv"
b=R/"M11_G10_M_GPU_queue_20261031_104358_b59373"/"history.csv"
def rows(p):
 with p.open(encoding="utf8-sig",newline="") as f:return list(csv.DictReader(f))
aa=rows(a);bb={round(float(x["physical_time_s"]),7):x for x in rows(b)}
p=[(x,bb[round(float(x["physical_time_s"]),7)]) for x in aa if round(float(x["physical_time_s"]),7) in bb]
print("MATCHED",len(p),"PILOT",len(aa))
for k in ("CD","CL_total"):
 arr=[100*(float(x[k])-float(y[k]))/(float(y[k])-22.718189111947265/3855.6 if k=="CL_total" else float(y[k])) for x,y in p]
 if arr:print(k,"LAST20_AVG_ABS_PCT",statistics.fmean(map(abs,arr[-20:])),"LAST20_MAX_ABS_PCT",max(map(abs,arr[-20:])),"LAST_PERCENT",arr[-1])
