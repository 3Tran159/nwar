"""Only adopt larger dt for M11 after verified finite paired pilot and saved output.
Temporally accurate final CL/CD still requires separate validation at settled state.
"""
from pathlib import Path
import sys,os,json,shutil,hashlib,datetime
R=Path(r"E:\ntnu_mesh_optimization_20261030")
sys.path.insert(0,str(R))
import mesh_queue_control_20261031 as c
pilot=R/"M11_G10_M_dt0002_GPU_pilot_20261031_105103_6e9452"
report=c.read(R/"m11_dt_pilot_result.json")
done=c.read(pilot/"completed.json");ex=c.read(pilot/"exit.json");checkpoint=pilot/"final.sim"
assert not (R/"m11_dt_pilot.lock").exists(),"Test still running; do not adopt yet"
assert not c.LOCK.exists()
assert not (R/"m11_dt_selection.json").exists()
assert c.original_ok() and c.read(c.STATE)["status"]=="paused" and c.PAUSE.exists()
assert report.get("solver_complete") and report.get("guard_ok") and report.get("source_preserved")
assert report.get("paired_samples")==71 and abs(report.get("max_interface_CFL",3))<1.0
assert report["reference_dt_s"]==.0001 and report["pilot_dt_s"]==.0002
assert all(report["forces"][q]["last_20_mean_abs_relative_pct"]<.15 and report["forces"][q]["maximum_abs_relative_pct"]<.3 for q in ("CL","CD"))
assert done.get("status")=="target_reached" and abs(done.get("time_s",0)-.6052)<1e-8 and done["steps"]==71
assert ex.get("returncode")==0 and ex.get("source_unchanged") is True
assert c.read(pilot/"EXPORT_OK.json").get("time_s")==done["time_s"]
assert checkpoint.is_file() and checkpoint.stat().st_size>100_000_000
c.no_other_stars()
old=R/"mesh_queue_worker_20261031.py";new=R/"mesh_queue_worker_mixed_dt_20261031.py"
assert new.is_file() and new.stat().st_size>10000
previous_hash=c.sha(old);new_hash=c.sha(new)
# Both live STAR and controller are already stopped; this is our own newly created E: queue script.
backup=R/"mesh_queue_worker_pre_dt2_20261031.py"
assert not backup.exists()
shutil.copy2(old,backup)
assert c.sha(backup)==previous_hash
shutil.copy2(new,old)
assert c.sha(old)==new_hash
selection=dict(approved_for_continuation_pilot=True,status="M11_dt2_approved_for_exploratory_settling_not_final_numerical_validation",
  at=c.stamp(),source_dt_s=.0001,candidate_dt_s=.0002,pilot_checkpoint_time_s=done["time_s"],
  directory=str(pilot),final_sim_sha256=c.sha(checkpoint),
  comparison_force_error_last20_pct={k:report["forces"][k]["last_20_mean_abs_relative_pct"] for k in ("CL","CD")},
  full_matched_endpoint_temporal_control_required=True,
  physical_guard_CFL={"max_interface":report["max_interface_CFL"],"max_bulk":report["max_bulk_CFL"]},
  original_M12_untouched=True,original_M11_dt0001_saved_and_untouched=True,worker_previous_sha256=previous_hash,worker_new_sha256=new_hash)
c.write(R/"m11_dt_selection.json",selection)
with (R/"decisions.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(dict(at=c.stamp(),event="M11_dt0002_pilot_positive_switch_to_mixed_dt_queue",evidence=selection,scope="M11 only; waveform and M12 untouched; no final timestep accuracy claim"),ensure_ascii=False)+"\n")
print(json.dumps({k:selection[k] for k in ("status","candidate_dt_s","comparison_force_error_last20_pct","physical_guard_CFL","full_matched_endpoint_temporal_control_required")},ensure_ascii=False),flush=True)
