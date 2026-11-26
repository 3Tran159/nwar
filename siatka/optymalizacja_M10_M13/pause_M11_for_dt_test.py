from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(r"E:\ntnu_mesh_optimization_20261030")))
import mesh_queue_control_20261031 as ctrl
s=ctrl.snapshot()
assert s["status"]=="running" and s["job"]=="M11",s
result=ctrl.pause({"generation":s["generation"]})
with (ctrl.R/"decisions.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(dict(at=ctrl.stamp(),event="user_M11_larger_dt_request",original_dt_s=.0001,candidate_dt_s=.0002,measured_M11_interface_CFL_at_old_dt=.3599,planned="gentle own queue pause/save, bounded equal-initial-time comparison of dt 0.0002 vs 0.0001, no change M12, do not assume equal temporal accuracy"),ensure_ascii=False)+"\n")
print("PAUSE",json.dumps(result,ensure_ascii=False))
