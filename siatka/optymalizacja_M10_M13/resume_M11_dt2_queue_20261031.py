from pathlib import Path
import sys,json
R=Path(r"E:\ntnu_mesh_optimization_20261030")
sys.path.insert(0,str(R))
import mesh_queue_control_20261031 as c
s=c.snapshot()
assert s.get("status")=="paused" and s.get("can_resume") and s.get("job")=="Next: M11",s
selected=c.read(R/"m11_dt_selection.json")
assert selected.get("approved_for_continuation_pilot") and selected["candidate_dt_s"]==.0002
result=c.resume({"generation":s["generation"]})
with (R/"decisions.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(dict(at=c.stamp(),event="user_authorized_M11_exploratory_dt2_queue_resumed_after_same_time_pilot",dt_s=.0002,queue_stage="M11",M12_unchanged=True,terminal_same_time_temporal_check_still_required=True),ensure_ascii=False)+"\n")
print(json.dumps(result,ensure_ascii=False))
