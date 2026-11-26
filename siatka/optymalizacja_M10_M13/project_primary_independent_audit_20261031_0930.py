"""Independent, read-only numerical acceptance gate for one running G10_F.
No solver commands, no pause, no changes to original receipts."""
from pathlib import Path
import csv,datetime,hashlib,json,math,statistics,os,uuid
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030")
STUDY=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
PARENT=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
def load(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def items(p):
 with Path(p).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def check(x,msg):
 if not x:raise RuntimeError(msg)
def digest(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
now=datetime.datetime.now().astimezone()
plan=load(ROOT/"plan.json")
check(digest(ROOT/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"],"runbook mismatch")
check(plan["selection"]["user_primary_CL_CD_override"]["authorized"],"user permission missing")
control=load(PARENT/"mesh_control_receipt.json")
check(control.get("status")=="passed" and control.get("tests",0)>=16,"control tests not validated")
code_checks={Path(file).name:digest(file)==sha for file,sha in control["source_sha256"].items()}
check(all(code_checks.values()),"control code checksums mismatched")
state=load(STUDY/"gpu_study_state.json")
check(state.get("status")=="GPU_job_running" and state.get("scope")=="calm_water_only" and "G10_F" in state.get("job",""),"M12 identity")
run=Path(state["directory"])
config=load(run/"setup.json")
check(config["cells"]==1154199 and abs(config["dt_s"]-.0001)<1e-12 and config["inner_iterations"]==10 and config["gpu_count"]==1,"invalid solver setup")
check(config["lift_convention"]=="hydrodynamic_lift_v1" and config["current"]=="[18.0, 0.0, 0.0]" and config["rho"]==1000.0 and config["reference_area_m2"]==.0238,"physics setup mismatch")
check(not (STUDY/"STOP").exists() and not (run/"STOP").exists() and not (PARENT/"STOP_ALL").exists(),"existing stop marker")
check(not (STUDY/"dashboard_control"/"pause.json").is_file() or load(STUDY/"dashboard_control"/"pause.json").get("state")=="resumed","existing pause not clean")
gpu_lock=load(STUDY/"gpu_live_study.lock")
queue_lock=load(PARENT/"queue.lock")
check(gpu_lock.get("pid")==state["pid"] and queue_lock.get("pid")==state["pid"] and gpu_lock.get("token")==queue_lock.get("token"),"controller locks mismatch")
check(load(run/"process.json")["pid"]==state["star_pid"],"M12 PID mismatch")
auxlock=ROOT/"parallel_cpu_20261031"/"auxiliary.lock"
check(not auxlock.exists(),"unexpected auxiliary active")
source=load(run/"source_identity.json")
src_path=Path(source["path"])
check(src_path.is_file() and src_path.stat().st_size>1_000_000_000,"source sim missing")
source_sha_ok=digest(src_path)==source["sha256"]
check(source_sha_ok,"original source SIM hash mismatch")
rows=items(run/"history.csv")
check(len(rows)>12000,"M12 history insufficient")
f=lambda row,k:float(row[k])
dt=config["dt_s"]
span=rows[-4501:]
for a,b in zip(span,span[1:]):
 check(int(b["step"])==int(a["step"])+1 and abs(f(b,"physical_time_s")-f(a,"physical_time_s")-dt)<2e-8,"history time gap")
 for k in ("CL","CL_total","CD","pressure_drag_N","viscous_drag_N","max_CFL","interface_max_CFL","max_velocity_m_s"):
  check(math.isfinite(f(b,k)),"nonfinite "+k)
 check(abs(f(b,"CL")-(f(b,"CL_total")-22.718189111947265/3855.6))<1e-10,"CL convention")
 check(abs(f(b,"Fx_slice_N")-f(b,"pressure_drag_N")-f(b,"viscous_drag_N"))<=max(.01,abs(f(b,"Fx_slice_N"))*.0001),"force split mismatch")
 check(abs(f(b,"CD")-f(b,"Fx_slice_N")/3855.6)<1e-9,"CD normalization mismatch")
checks=[json.loads(l) for l in (run/"settling_checks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
latest=checks[-2:]
check(len(latest)==2 and all(k in latest[0] for k in ("CL","CD","CD_pressure","CD_viscous")),"two formal checks missing")
metrics={}
for j,assess in enumerate(latest):
 target=assess["time_s"]
 idx=min(range(len(rows)-1,max(-1,len(rows)-6500),-1),key=lambda i:abs(f(rows[i],"physical_time_s")-target))
 check(abs(f(rows[idx],"physical_time_s")-target)<1e-7,"assess time not in raw history")
 N=2000
 check(idx+1>=N*2,"insufficient raw windows")
 prior=rows[idx-(2*N)+1:idx-N+1]
 recent=rows[idx-N+1:idx+1]
 check(len(prior)==len(recent)==N and abs(f(prior[-1],"physical_time_s")-(target-.2))<1e-7,"windows not contiguous")
 stats={}
 for metric,key in (("CL","CL"),("CD","CD"),("CD_pressure","pressure_drag_N"),("CD_viscous","viscous_drag_N")):
  if key in ("pressure_drag_N","viscous_drag_N"):
   a=[f(r,key)/3855.6 for r in prior];b=[f(r,key)/3855.6 for r in recent]
  else:
   a=[f(r,key) for r in prior];b=[f(r,key) for r in recent]
  am=statistics.fmean(a);bm=statistics.fmean(b)
  shift=100*abs(bm-am)/abs(bm)
  rms_a=100*math.sqrt(statistics.fmean((x-am)**2 for x in a))/abs(am)
  rms_b=100*math.sqrt(statistics.fmean((x-bm)**2 for x in b))/abs(bm)
  expected=assess[metric]
  for k,v in (("previous_mean",am),("latest_mean",bm),("mean_change_pct",shift),("previous_RMS_pct",rms_a),("latest_RMS_pct",rms_b)):
   check(abs(expected[k]-v)<max(1e-10,abs(v)*1e-7),f"raw mismatch {metric} {k}")
  stats[metric]={"mean":bm,"shift_pct":shift,"rms_previous_pct":rms_a,"rms_latest_pct":rms_b,"pass":shift<.5 and rms_a<.5 and rms_b<.5}
 check(stats["CL"]["pass"] and stats["CD"]["pass"],"project CL/CD primary formal check failed")
 cdref=abs(stats["CD"]["mean"])
 dp=abs(stats["CD_pressure"]["mean"]-assess["CD_pressure"]["previous_mean"])/cdref*100
 dv=abs(stats["CD_viscous"]["mean"]-assess["CD_viscous"]["previous_mean"])/cdref*100
 signopp=(stats["CD_pressure"]["mean"]-assess["CD_pressure"]["previous_mean"])*(stats["CD_viscous"]["mean"]-assess["CD_viscous"]["previous_mean"])<0
 metrics[str(round(target,4))]={"CL":stats["CL"],"CD":stats["CD"],"component_pressure_pct_of_total_CD":dp,"component_viscous_pct_of_total_CD":dv,"sum_abs_components_pct_of_total_CD":dp+dv,"component_opposing_drift":signopp,"raw_samples_previous":len(prior),"raw_samples_recent":len(recent),"legacy_four_way":assess.get("pass")}
check(abs(latest[1]["time_s"]-latest[0]["time_s"]-.2)<1e-7,"formal checks not consecutive")
cont=items(run/"conservation.csv")
check(len(cont)>12000,"mass/volume history incomplete")
vol=[f(r,"water_volume_m3") for r in cont[-4500:]]
mass=[f(r,"mass_kg") for r in cont[-4500:]]
check(all(math.isfinite(x) and x>0 for x in vol+mass),"invalid volume/mass")
vol_rangepct=100*(max(vol)-min(vol))/statistics.fmean(vol)
check(vol_rangepct<.25,"water volume drift concerning")
max_i=max(f(r,"interface_max_CFL") for r in rows[-4500:])
max_c=max(f(r,"max_CFL") for r in rows[-4500:])
max_v=max(f(r,"max_velocity_m_s") for r in rows[-4500:])
check(max_i<1.05 and max_c<12 and max_v<50,"CFL/velocity numeric guard failure")
current_local=now.isoformat()
res={"review_at_local":current_local,"decision":"PROJECT PRIMARY CL/CD SETTLED; LEGACY FOUR-COMPONENT TEST NOT PASSED; do not call this ITTC or GCI acceptance",
 "runbook_sha_verified":True,"control_source_hashes_verified":code_checks,"source_sim_sha_verified":source_sha_ok,
 "physical_time_s":f(rows[-1],"physical_time_s"),"last_step":int(rows[-1]["step"]),"n_raw":len(rows),
 "formal_checks":metrics,"consecutive_primary_checks":2,
 "guards":{"water_volume_range_pct_0p45s":vol_rangepct,"water_volume_m3":vol[-1],
 "net_outward_mass_kg_s":f(cont[-1],"net_outward_mass_kg_s"),
 "max_bulk_CFL_0p45s":max_c,"max_interface_CFL_0p45s":max_i,"max_velocity_m_s_0p45s":max_v,
 "configured_dt_s":dt,"stop_markers":False,"M12_controller_pid":state["pid"],"M12_solver_pid":state["star_pid"]},
 "approved_stop_route":"only pretested same-origin /api/mesh-study/pause, generation checked, local token",
 "study_receipt_status":"passed 16 isolated tests; earlier real pause+saved final verified; no live test in receipt",
 "solver_changed":False}
out=ROOT/"project_primary_independent_audit_20261031_0930.json"
temp=out.with_name(out.name+"."+uuid.uuid4().hex+".tmp")
temp.write_text(json.dumps(res,indent=2,allow_nan=False,ensure_ascii=False)+"\n",encoding="utf-8")
os.replace(temp,out)
print(json.dumps(res,ensure_ascii=False,allow_nan=False))
