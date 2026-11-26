"""Adopt only independently verified, short matched M10 dt2 GPU pilot; original queue worker unchanged."""
from pathlib import Path
import sys,json
R=Path(r"E:\ntnu_mesh_optimization_20261030")
sys.path.insert(0,str(R))
import mesh_queue_control_20261031 as c
pilot=R/"M10_W01a_dt0002_GPU_pilot_20261031_162106_a9e382"
report=c.read(R/"m10_dt_pilot_result.json")
done=c.read(pilot/"completed.json")
ex=c.read(pilot/"exit.json")
f=pilot/"final.sim"
assert not (R/"m10_dt_pilot.lock").exists(), "M10 timestep pilot is still active"
assert not c.LOCK.exists(), "Another mesh queue generation holds the lock"
assert not (R/"m10_dt_selection.json").exists(), "No duplicate M10 dt-selection"
state=c.read(c.STATE)
assert state.get("status")=="paused" and state.get("stage")=="M10" and c.PAUSE.exists()
assert not c.alive(state.get("controller_pid"))
assert c.original_ok()
assert report.get("solver_complete") and report.get("guard_ok") and report.get("source_preserved")
assert report.get("paired_samples")==71
assert report.get("reference_dt_s")==.0001 and report.get("pilot_dt_s")==.0002
assert report.get("max_interface_CFL",3)<1 and report.get("max_bulk_CFL",100)<25
for q in ("CL","CD"):
 m=report["forces"][q]
 assert m["last_20_mean_abs_relative_pct"]<.15 and m["maximum_abs_relative_pct"]<.3, ("Unacceptable dt drift",q,m)
assert done.get("status")=="target_reached" and done.get("steps")==71 and abs(done.get("time_s",0)-.6052)<1e-8
assert ex.get("returncode")==0 and ex.get("source_unchanged") is True
assert c.read(pilot/"EXPORT_OK.json").get("time_s")==done["time_s"]
assert f.is_file() and f.stat().st_size>100_000_000
assert c.sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==c.read(R/"plan.json")["recovery_policy"]["runbook_sha256"]
other=R/"parallel_cpu_20261031"/"auxiliary.lock"
assert not other.exists()
assert not (R/"STOP_ALL").exists()
worker=R/"mesh_queue_worker_M10_dt2_20261031.py"
controller=R/"mesh_queue_control_m10_dt2_20261031.py"
assert worker.is_file() and controller.is_file()
assert "M10_SELECTION" in worker.read_text(encoding="utf8") and "mesh_queue_worker_M10_dt2_20261031.py" in controller.read_text(encoding="utf8")
c.no_other_stars()
selection=dict(approved_for_continuation_pilot=True,
 status="M10_dt2_allowed_for_exploratory_settling_NOT_final_temporal_validation",
 at=c.stamp(), source_dt_s=.0001,candidate_dt_s=.0002,
 pilot_checkpoint_time_s=done["time_s"],directory=str(pilot),
 final_sim_sha256=c.sha(f),pilot_CFL_guard_pass=True,force_short_pilot_guard_pass=True,
 comparison_force_error_last20_pct={q:report["forces"][q]["last_20_mean_abs_relative_pct"] for q in ("CL","CD")},
 max_abs_force_error_pct={q:report["forces"][q]["maximum_abs_relative_pct"] for q in ("CL","CD")},
 physical_guard_CFL=dict(interface=report["max_interface_CFL"],bulk=report["max_bulk_CFL"]),
 original_M10_dt0001_saved_unmodified=True,original_M11_M12_untouched=True,
 source_original_preserved=True,full_matched_endpoint_temporal_control_required=True,
 new_worker_sha256=c.sha(worker),new_controller_sha256=c.sha(controller),
 original_worker_sha256=c.sha(R/"mesh_queue_worker_20261031.py"),
 no_original_worker_edit=True)
c.write(R/"m10_dt_selection.json",selection)
with (R/"decisions.jsonl").open("a",encoding="utf8") as z:
 z.write(json.dumps(dict(at=c.stamp(),event="M10_larger_dt_short_pilot_passed",
  selection=selection,scope="Exploratory M10 only, original queue/macro preserved; final temporal sensitivity still open"),ensure_ascii=False)+"\n")
print(json.dumps(selection,ensure_ascii=False),flush=True)
