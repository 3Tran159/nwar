"""Read-only observed W04 encounter period and wave height at gauge locations."""
import csv,json,statistics,math
from pathlib import Path
base=Path(r"E:\ntnu_mesh_optimization_20261030\nwar_automation_20261102\runs\W04_20261103_084458_e67f66")
gauges={}
for filename in ("prior_gauges.csv","gauges.csv"):
    with (base/filename).open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            try:
                x=round(float(r["x_m"]),3)
                gauges.setdefault(x,[]).append((float(r["time_s"]),float(r["eta_actual_m"])))
            except (KeyError,ValueError):pass
def peaks(x):
    g=sorted(set(gauges.get(x,[])))
    if len(g)<100:return []
    step=statistics.median(g[i+1][0]-g[i][0] for i in range(0,len(g)-1))
    n=max(1,round(.02/step))
    f=[sum(g[max(0,i-n):min(len(g),i+n+1)][k][1] for k in range(len(g[max(0,i-n):min(len(g),i+n+1)])))/len(g[max(0,i-n):min(len(g),i+n+1)]) for i in range(len(g))]
    c=[(g[i][0],g[i][1]) for i in range(1,len(g)-1) if f[i]>f[i-1] and f[i]>=f[i+1] and g[i][0]>10.]
    out=[]
    for p in c:
        if not out or p[0]-out[-1][0]>.8:
            out.append(p)
        elif p[1]>out[-1][1]:out[-1]=p
    return out
res={}
for x in (-15.,-.5,0.,5.):
    pp=peaks(x)
    intervals=[pp[i+1][0]-pp[i][0] for i in range(len(pp)-1)]
    res[str(x)]={"crest_times_s":[round(a,5) for a,b in pp],"crest_elevations_m":[round(b,4) for a,b in pp],
                 "period_intervals_s":[round(v,6) for v in intervals],
                 "mean_period_s":statistics.mean(intervals) if intervals else None}
out=Path(__file__).with_name("observed_periods.json")
out.write_text(json.dumps(res,indent=2),encoding="utf-8")
print(json.dumps(res,indent=2))
