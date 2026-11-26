"""Pure postprocessing of saved R4V wave gauges. Does not touch the STAR solver."""
from pathlib import Path
from datetime import datetime
import csv, json, math, hashlib, statistics
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030")
P=ROOT/"M13_wave_direct_20261031"
RUN=P/"M13_GPU_W20_H050_continuation_R4V_20261101"
OUT=P/"WAVE_PROPAGATION_AUDIT_20261101_0735.json"
START=9.928564996364855
END=13.31733761495712
T=0.84727
W=2*math.pi/T
def fit(series):
    z=[]
    for t,y in series:
        a=math.cos(W*t);b=math.sin(W*t);z.append((1.,a,b,y))
    m=[[sum(q[i]*q[j] for q in z) for j in range(3)]+[sum(q[i]*q[3] for q in z)] for i in range(3)]
    for i in range(3):
        k=max(range(i,3),key=lambda j:abs(m[j][i]))
        m[i],m[k]=m[k],m[i]
        piv=m[i][i]
        if abs(piv)<1e-12:raise ValueError("singular fit")
        for v in range(i,4):m[i][v]/=piv
        for j in range(3):
            if j==i:continue
            factor=m[j][i]
            for v in range(i,4):m[j][v]-=factor*m[i][v]
    mean,c,s=(m[i][3] for i in range(3))
    rms=math.sqrt(statistics.fmean((y-mean-c*math.cos(W*t)-s*math.sin(W*t))**2 for t,y in series))
    return {"points":len(series),"mean_m":mean,"harmonic_height_m":2*math.hypot(c,s),"phase_rad":math.atan2(-s,c),"fit_RMS_m":rms}
def wrap(z):return (z+math.pi)%(2*math.pi)-math.pi
def main():
    if OUT.exists():raise RuntimeError("Refusing overwrite")
    plan=json.loads((ROOT/"plan.json").read_text(encoding="utf-8"))
    digest=hashlib.sha256((ROOT/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()
    if digest!=plan["recovery_policy"]["runbook_sha256"]:raise RuntimeError("Runbook hash mismatch")
    stage=json.loads((RUN/"stage_result.json").read_text(encoding="utf-8"))
    if stage.get("exit_code")!=0 or not stage.get("source_unchanged"):raise RuntimeError("Unfinished source")
    rows={}
    fp=RUN/"gauges.csv"
    with fp.open(encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            t=float(row["time_s"])
            if START<=t<=END:
                x=float(row["x_m"]);rows.setdefault(x,[]).append((t,float(row["eta_actual_m"])))
    result={str(x):fit(a) for x,a in sorted(rows.items()) if len(a)>400}
    base=result.get("-25.0")
    if base:
        for key,r in result.items():
            x=float(key)
            r["height_error_vs_H0p5_pct"]=100*(r["harmonic_height_m"]/0.5-1)
            r["phase_diff_vs_x_minus25_rad"]=wrap(r["phase_rad"]-base["phase_rad"])
            r["phase_error_vs_lambda20_rad"]=wrap(r["phase_rad"]-base["phase_rad"]+2*math.pi*(x+25)/20)
    source_sha=hashlib.sha256(fp.read_bytes()).hexdigest()
    out={"at":datetime.now().astimezone().isoformat(),"case":"M13 R4V H0.5m lambda20m FifthOrder upstream only","scope":"diagnostic measured eta harmonic; not STAR FifthOrder exact theory verification","period_fit_s":T,"physical_window_s":[START,END],"probe_data_sha256":source_sha,"source":str(fp),"gauges":result,"phase_ref_x_m":-25,"damping_probe_x40_excluded_from_quality_claims":True,"relevant_limitations":"A fit of 4 nominal periods cannot establish wave reflection, exact imposed FifthOrder field, arrival timing or converged forces.","no_new_solver":True}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"saved":str(OUT),"gauge_subset":{x:{k:round(v,5) for k,v in r.items() if k in ("harmonic_height_m","fit_RMS_m","height_error_vs_H0p5_pct","phase_error_vs_lambda20_rad")} for x,r in result.items()},"source_unchanged":True},ensure_ascii=False))
if __name__=="__main__":main()
