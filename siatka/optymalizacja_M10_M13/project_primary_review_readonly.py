"""Read-only CL/CD-first CFD review, no STAR process/lock/config mutation."""
from pathlib import Path
import json, csv, hashlib, datetime, math, statistics, os, uuid
R=Path(r"E:\ntnu_mesh_optimization_20261030")
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
def load(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def stamp():return datetime.datetime.now().astimezone().isoformat()
def raw(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
plan=load(R/"plan.json")
assert hashlib.sha256((R/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()==plan["recovery_policy"]["runbook_sha256"]
assert plan["selection"]["user_primary_CL_CD_override"]["authorized"]
assert plan["selection"]["stabilization"]["coefficients"]==["CL","CD"]
state=load(B/"gpu_study_state.json")
assert state["scope"]=="calm_water_only" and "G10_F" in state["job"] and state["gpu_count"]==1
run=Path(state["directory"])
setup=load(run/"setup.json")
assert setup["cells"]==1154199 and abs(setup["dt_s"]-.0001)<1e-13
assert setup["lift_convention"]=="hydrodynamic_lift_v1"
history=raw(run/"history.csv")
last=history[-1]
cl=float(last["CL"])
calc=float(last["CL_total"])-22.718189111947265/3855.6
assert abs(cl-calc)<1e-10
cost=[]
for a,b in zip(history[-151:],history[-150:]):
    if int(b["step"])==int(a["step"])+1 and float(b["physical_time_s"])>float(a["physical_time_s"]):
        d=float(b["wall_seconds"])-float(a["wall_seconds"])
        if d>0 and d<15:cost.append(d)
assessments=[]
with (run/"settling_checks.jsonl").open(encoding="utf-8-sig") as f:
    for line in f:
        if not line.strip():continue
        row=json.loads(line)
        if all(k in row for k in ("CL","CD","CD_pressure","CD_viscous","time_s")):
            primary_ok=all(row[k].get("relative_test_resolved",False)
             and row[k]["mean_change_pct"]<.5
             and row[k]["previous_RMS_pct"]<.5
             and row[k]["latest_RMS_pct"]<.5 for k in ("CL","CD"))
            p=row["CD_pressure"];v=row["CD_viscous"];cd=row["CD"]; denom=abs(cd["latest_mean"])
            dp=abs(p["latest_mean"]-p["previous_mean"])/denom*100
            dv=abs(v["latest_mean"]-v["previous_mean"])/denom*100
            signed_p=(p["latest_mean"]-p["previous_mean"])
            signed_v=(v["latest_mean"]-v["previous_mean"])
            assessments.append(dict(time_s=row["time_s"],cl_mean=row["CL"]["latest_mean"],cd_mean=cd["latest_mean"],cl_shift_pct=row["CL"]["mean_change_pct"],cd_shift_pct=cd["mean_change_pct"],cl_rms_prev_pct=row["CL"]["previous_RMS_pct"],cl_rms_latest_pct=row["CL"]["latest_RMS_pct"],cd_rms_prev_pct=cd["previous_RMS_pct"],cd_rms_latest_pct=cd["latest_RMS_pct"],primary_pass=primary_ok,legacy_pass=row.get("pass",False),pressure_own_shift_pct=p["mean_change_pct"],pressure_drift_relative_total_CD_pct=dp,viscous_drift_relative_total_CD_pct=dv,component_absolute_sum_relative_total_CD_pct=dp+dv,component_opposite_signed=signed_p*signed_v<0))
assert assessments
count=0
for v in reversed(assessments):
    if not v["primary_pass"]:break
    count+=1
cp=load(run/"latest_checkpoint.json")
cp_path=Path(cp["path"])
cp_ok=cp_path.is_file()
aux=load(R/"parallel_cpu_20261031"/"current.json")
m12_total_sec=float(last["physical_time_s"])
results={
 "review_at_local":stamp(),
 "scope":"read-only M12 project-primary force settling; NOT legacy solver completion or GCI",
 "plan_runbook_hash_verified":True,
 "main_job":state["job"],
 "main_mesh_cells":setup["cells"],
 "last_physical_time_s":m12_total_sec,
 "steps_since_resume":int(last["step"]),
 "instantaneous_CL_hydrodynamic":cl,
 "instantaneous_CD":float(last["CD"]),
 "last_150_step_median_wall_s_per_step":statistics.median(cost) if cost else None,
 "formal_assessments_last_5":assessments[-5:],
 "primary_consecutive_passes":count,
 "required_consecutive_passes":2,
 "project_primary_acceptance":count>=2,
 "legacy_4component_acceptance":bool(assessments[-1]["legacy_pass"]),
 "checkpoint_time_s":cp["time_s"],
 "checkpoint_exists":cp_ok,
 "checkpoint_bytes":cp_path.stat().st_size if cp_ok else None,
 "last_100_max_CFL":max(float(v["max_CFL"]) for v in history[-100:]),
 "last_100_max_interface_CFL":max(float(v["interface_max_CFL"]) for v in history[-100:]),
 "auxiliary":dict(status=aux.get("status"),throughput_pass=aux.get("throughput_pass"),auxiliary_stop_or_failure=aux.get("reason")),
 "decision":"Continue healthy main M12. Do not stop on first project-primary pass; second formal pass and cross-mesh evidence still missing." if count<2 else "Project-primary CL/CD two-pass criterion met; validate guards and safe saved-stop endpoint before any intervention.",
 "no_solver_modified":True
}
out=R/"project_primary_readiness_latest.json"
tmp=out.with_name(out.name+"."+uuid.uuid4().hex+".tmp")
tmp.write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
os.replace(tmp,out)
print(json.dumps({k:results[k] for k in ("review_at_local","last_physical_time_s","steps_since_resume","last_150_step_median_wall_s_per_step","primary_consecutive_passes","legacy_4component_acceptance","checkpoint_time_s","checkpoint_exists","last_100_max_CFL","last_100_max_interface_CFL","decision")},ensure_ascii=False))
print(json.dumps(results["formal_assessments_last_5"][-1],ensure_ascii=False))
