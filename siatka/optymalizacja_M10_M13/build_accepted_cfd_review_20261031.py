"""Read-only result handoff. All new reports E:, no solver mutation."""
from pathlib import Path
import csv,datetime,hashlib,json,os,uuid,urllib.request,statistics,math,sys
R=Path(r"E:\ntnu_mesh_optimization_20261030")
S=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
M=S/"force_stabilization_20261029"/"calm_settle_G10_F_GPU_live_r2_resume_20261030_173420_4854e1"
W=R/"wave_surface_only"/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"
O=R/"cfd_review_20261031_0933"
O.mkdir(parents=True,exist_ok=True)
def load(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def write(p,s):
 tmp=p.with_name(p.name+"."+uuid.uuid4().hex+".tmp");tmp.write_text(s,encoding="utf-8");os.replace(tmp,p)
def readcsv(p):
 with Path(p).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
plan=load(R/"plan.json")
assert hashlib.sha256((R/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()==plan["recovery_policy"]["runbook_sha256"]
with urllib.request.urlopen("http://127.0.0.1:8771/api/mesh-study",timeout=8) as res:control=json.load(res)
assert control["status"]=="paused" and control["can_resume"] and not control["can_pause"]
assert Path(control["file"]).resolve()==(M/"final.sim").resolve()
sys.path.insert(0,str(F));import mesh_study_control as ctl
assert ctl.safe_saved(M,True)["status"]=="stopped_by_marker"
assert not ctl.alive(19040) and not ctl.alive(1996)
done=load(M/"completed.json");ex=load(M/"exit.json");export=load(M/"EXPORT_OK.json")
assert done["status"]=="stopped_by_marker" and ex["returncode"]==0
assert export["cells"]==1154199 and abs(export["time_s"]-done["time_s"])<1e-9
assert not (S/"gpu_live_study.lock").exists()
pause=load(S/"dashboard_control"/"pause.json")
assert pause["state"]=="pause_requested" and (S/"STOP").read_text()==pause["id"]
audit=load(R/"project_primary_independent_audit_20261031_0930.json")
assert audit["consecutive_primary_checks"]==2 and audit["runbook_sha_verified"]
assert all(audit["control_source_hashes_verified"].values()) and audit["guards"]["max_interface_CFL_0p45s"]<1.05
flat=load(W/"pilot_result.json")
assert flat["status"]=="calm_pilot_completed" and flat["completed"]["steps"]==400 and flat["final_sim_exists"]
hist=readcsv(W/"history.csv");gauges=readcsv(W/"gauges.csv")
assert len(hist)>=400 and len(gauges)>=200
speed=[float(x["max_speed_m_s"]) for x in hist]
cfl=[float(x["max_CFL"]) for x in hist]
vol=[float(x["water_volume_m3"]) for x in hist]
eta=[float(x["eta_actual_m"]) for x in gauges]
assert max(abs(v-18) for v in speed)<.01 and max(abs(e) for e in eta)<.000001
assert max(cfl)<.1 and max(vol)-min(vol)<.0001 and (W/"calm_pilot_final.sim").stat().st_size>20_000_000
now=datetime.datetime.now().astimezone().isoformat()
a=audit["formal_checks"]["3.2013"]
result={
 "at":now,"main_M12":{"status":"PROJECT PRIMARY CL/CD SETTLED / LEGACY FOUR-COMPONENT TEST NOT PASSED",
 "saved_stop_verified":True,"time_s":done["time_s"],"steps":done["steps"],
 "cells":1154199,"saved_path":str(M/"final.sim"),"saved_bytes":(M/"final.sim").stat().st_size,
 "solver_exit_zero":True,"owner_paused":True,"source_unchanged":ex["source_unchanged"],
 "formal_checks":audit["formal_checks"],"flow_guards":audit["guards"],
 "cross_mesh_1pct_agreement_proved":False,"ITTC_or_GCI_certified":False},
 "wave_nofoil":{"status":"CALM THROUGH-FLOW NUMERIC PILOT COMPLETE; WAVE NOT ACTIVATED",
 "cells":53200,"time_s":flat["completed"]["time_s"],"steps":400,"dt_s":.001,
 "saved_calm":str(W/"calm_pilot_final.sim"),"source_bytes":(W/"calm_pilot_final.sim").stat().st_size,
 "max_velocity_deviation_from_18":max(abs(x-18) for x in speed),
 "max_bulk_CFL":max(cfl),"water_volume_range_m3":max(vol)-min(vol),
 "max_abs_eta_m":max(abs(x) for x in eta),"interface_CFL":"NOT_MEASURED",
 "wave_activated":False,"propagation_accepted":False},
 "next":"Do not restart saved M12 automatically. Obtain comparable primary settled results for M10/M11 before light foil mesh selection. Independently test λ20 H0.5 no-foil wave inlet from saved flat calm, with conservative guards; original C01 wave hold remains.",
 "intervention":"M12 gentle pause and verified save only; no hard kill, no wave solver started."}
write(O/"cfd_state.json",json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
csvout=O/"progress_table.csv"
tmp=csvout.with_name(csvout.name+"."+uuid.uuid4().hex+".tmp")
with tmp.open("w",encoding="utf-8",newline="") as f:
 wr=csv.writer(f)
 wr.writerow(["case","stage","cells","dt_s","time_s","steps","CL_mean","CL_shift_pct","CD_mean","CD_shift_pct","RMS_CL_pct","RMS_CD_pct","pressure_delta_over_total_CD_pct","viscous_delta_over_total_CD_pct","result"])
 for t,m in audit["formal_checks"].items():
  wr.writerow(["M12","primary_check_"+t,1154199,.0001,t,"",m["CL"]["mean"],m["CL"]["shift_pct"],m["CD"]["mean"],m["CD"]["shift_pct"],m["CL"]["rms_latest_pct"],m["CD"]["rms_latest_pct"],m["component_pressure_pct_of_total_CD"],m["component_viscous_pct_of_total_CD"],"PRIMARY_PASS_LEGACY_FAIL"])
 wr.writerow(["M12","saved_stop",1154199,.0001,done["time_s"],done["steps"],"","","","","","","","","SAVED_RECEIPTS_VERIFIED"])
 wr.writerow(["wave_nofoil_L20_H050_baseline","calm_only",53200,.001,.4,400,"","","","","","","","","NO_WAVE"])
os.replace(tmp,csvout)
report=f"""# CFD checkpoint: 31.10.2026 {datetime.datetime.now().strftime('%H:%M')} Europe/Oslo

## M12 hydrofoil, 1,154,199 cells
**PROJECT PRIMARY CL/CD SETTLED / LEGACY FOUR-COMPONENT TEST NOT PASSED**.
Gentle stop and save verified at t={done['time_s']:.4f} s, {done['steps']} steps. STAR exit=0; saved final.sim {((M/'final.sim').stat().st_size/1e9):.3f} GB with matching completed/export receipts.
Two formal checks at 3.0013s and 3.2013s reproduced from complete raw records. At second: CL shift {a['CL']['shift_pct']:.3f}%; total CD shift {a['CD']['shift_pct']:.3f}%; last RMS CL {a['CL']['rms_latest_pct']:.3f}%; CD {a['CD']['rms_latest_pct']:.3f}%. Pressure change normalized to CD {a['component_pressure_pct_of_total_CD']:.3f}%, viscous {a['component_viscous_pct_of_total_CD']:.3f}%, sum abs {a['sum_abs_components_pct_of_total_CD']:.3f}% (no opposite-sign compensation).
Fluid/VOF check: volume range over last 0.45s {audit['guards']['water_volume_range_pct_0p45s']:.5f}%, max bulk CFL {audit['guards']['max_bulk_CFL_0p45s']:.3f}, max interface CFL {audit['guards']['max_interface_CFL_0p45s']:.3f}.
These are PROJECT criteria, not general ITTC rules, iterative uncertainty estimates or GCI. M10/M11 still require comparable settled windows; no light mesh selected yet.

## Wave mesh only
The 53,200-cell λ20m, H0.5m baseline has an independently saved **flat calm** t=0.4s at 18m/s, 400 steps of 0.001s; max bulk CFL {max(cfl):.3f}; water-volume range {(max(vol)-min(vol)):.2e}m3, max absolute free surface η {max(abs(x) for x in eta):.2e}m. Interface CFL unavailable for empty alpha-threshold, not equal to zero.
No incident wave, no wave propagation or reflection validation yet. Next safe step: audited upstream-inlet wave from preserved calm .sim on a disposable copy; reject transient and diagnose historical outlet backflow. Original C01/HF untouched.
"""
write(O/"technical_checkpoint.md",report)
event={"at":now,"event":"M12_project_primary_saved_stop_success_verified",
 "saved_at_time_s":done["time_s"],"sim_bytes":(M/"final.sim").stat().st_size,
 "exit_code":0,"export_time_s":export["time_s"],"project_primary_raw_two_pass":True,
 "legacy_four_way_pass":False,"review_dir":str(O),"wave_still_not_launched":True,"GCI_not_certified":True}
with (R/"decisions.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps(event,ensure_ascii=False)+"\n");f.flush()
print(json.dumps({"saved_M12":True,"time_s":done["time_s"],"sim_gb":round((M/"final.sim").stat().st_size/1e9,3),
 "CL_shift_pct":round(a["CL"]["shift_pct"],3),"CD_shift_pct":round(a["CD"]["shift_pct"],3),
 "wave_calm_400_steps":True,"wave_propagation_validated":False,"report_dir":str(O)},ensure_ascii=False))
