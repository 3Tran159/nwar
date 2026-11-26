"""Review completed dt4 matched pilot, then generation-checked resume either dt4 or saved dt2.
NEVER trigger while own GPU pilot is active. No overwritten scripts, sources, or histories.
"""
from pathlib import Path
import sys,json,datetime,shutil
R=Path(r"E:\ntnu_mesh_optimization_20261030")
sys.path.insert(0,str(R))
import mesh_queue_control_m10_dt2_20261031 as base
PILOT=R/"M10_W01a_dt0004_matched_GPU_20261031"
REPORT=R/"m10_dt4_pilot_result.json"
SELECTION=R/"m10_dt4_selection.json"
def check():
 assert datetime.datetime.now().astimezone().date()==datetime.date(2026,10,31)
 assert not (R/"m10_dt4_pilot.lock").exists(), "Matched-time pilot still active"
 assert not (R/"mesh_queue_launch.lock").exists(), "Another queue owns launch"
 for x in (R/"STOP_ALL", R/"parallel_cpu_20261031"/"auxiliary.lock", R/"m10_dt_pilot.lock",R/"m11_dt_pilot.lock"):
  assert not x.exists(),"Conflicting state "+str(x)
 assert base.original_ok(), "Saved original M12 project run must remain verified"
 state=base.read(base.STATE)
 assert state.get("status")=="paused" and state.get("stage")=="M10"
 assert not base.alive(state.get("controller_pid"))
 assert base.PAUSE.exists()
 pause=base.read(base.PAUSE)
 assert pause.get("token")==state.get("token") and pause.get("stage")=="M10"
 assert (R/"mesh_queue_worker_M10_dt4_20261031.py").is_file()
 assert (R/"mesh_queue_worker_M10_resume_saved_dt2_20261031.py").is_file()
 assert (PILOT/"plan.json").is_file()
 report=base.read(REPORT)
 assert report.get("status") in ("bounded_matched_M10_0p2_vs_0p4_test_not_final_settling","not_accepted_no_auto_retry")
 assert base.read(PILOT/"current.json").get("status") in ("completed_matched_pilot","not_accepted_no_auto_retry")
 base.no_other_stars()
 assert shutil.disk_usage("C:\\").free>15*2**30 and shutil.disk_usage("E:\\").free>25*2**30
 return report
def main():
 report=check()
 if report.get("preliminary_exploratory_dt4_supported") and \
    report["candidate_performance"]["max_interface_CFL"]<=.95 and \
    report["candidate_performance"]["max_bulk_CFL"]<25:
  c=__import__("mesh_queue_control_m10_dt4_20261031")
  source=PILOT/"candidate_dt0004"
  done=c.read(source/"completed.json");ex=c.read(source/"exit.json");receipt=c.read(source/"EXPORT_OK.json")
  assert done.get("status")=="target_reached" and done.get("steps")==71 and abs(done.get("time_s",0)-.9244)<1e-8
  assert ex.get("returncode")==0 and ex.get("source_unchanged") is True
  assert receipt.get("time_s")==done.get("time_s") and receipt.get("cells")==317277
  file=source/"final.sim"
  assert file.is_file() and file.stat().st_size>100_000_000
  assert not SELECTION.exists()
  selection=dict(approved_for_continuation_pilot=True,
     at=c.stamp(),status="dt0p4_exploratory_only_not_final_temporal_validation",
     directory=str(PILOT),final_sim_sha256=c.sha(file),
     source_time_s=done["time_s"],source_dt_s=.0002,candidate_dt_s=.0004,
     pilot_CFL_guard_pass=True,force_short_pilot_guard_pass=True,
     candidate_CFL=report["candidate_performance"]["max_interface_CFL"],
     comparison_forces=report["forces"],
     original_saved_M10_dt2_preserved=True,original_saved_M11_M12_preserved=True,
     separate_terminal_temporal_control_required=True)
  c.write(SELECTION,selection)
  branch="dt0004"
  reason="Matched 0.2/0.4ms pilots pass with interface CFL <=0.95"
 else:
  c=__import__("mesh_queue_control_m10_resume_saved_dt2_20261031")
  assert not SELECTION.exists()
  branch="saved_dt0002"
  reason="0.4ms pilot rejected or insufficient CFL safety margin; resume original 0.2ms checkpoint"
 state=c.snapshot()
 assert state.get("status")=="paused" and state.get("job")=="Next: M10" and state.get("can_resume")
 result=c.resume({"generation":state["generation"]})
 output=dict(at=c.stamp(),choice=branch,why=reason,control_result=result,
    original_sim_files_untouched=True,original_held_wave_untouched=True,
    not_final_timestep_validation=True)
 c.write(R/"m10_dt4_resume_decision_20261031.json",output)
 with (R/"decisions.jsonl").open("a",encoding="utf8") as f:
  f.write(json.dumps(dict(event="M10_dt4_pilot_decision_and_queue_resume",**output),ensure_ascii=False)+"\n")
 print(json.dumps(output,ensure_ascii=False),flush=True)
if __name__=="__main__":
 try:main()
 except Exception as e:
  output=dict(at=base.stamp(),status="RESUME_NOT_PERFORMED_UNVERIFIED",error_type=type(e).__name__,
    reason=str(e)[:450],M10_saved_state_preserved=True)
  base.write(R/"m10_dt4_resume_blocker_20261031.json",output)
  print(json.dumps(output,ensure_ascii=False),flush=True)
  raise
