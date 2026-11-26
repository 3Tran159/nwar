from pathlib import Path
from datetime import datetime
import os,json,hashlib,shutil,uuid
root=Path(r"E:\ntnu_mesh_optimization_20261030")
plan_path=root/"plan.json"
runbook_path=root/"AUTONOMOUS_RECOVERY_PROMPT.md"
plan=json.loads(plan_path.read_text(encoding="utf-8-sig"))
before=runbook_path.read_bytes()
assert hashlib.sha256(before).hexdigest()==plan["recovery_policy"]["runbook_sha256"]
assert not plan.get("selection",{}).get("user_primary_CL_CD_override",{}).get("authorized",False)
tag="31 October 2026: CL and total CD are primary stopping quantities"
assert tag not in before.decode("utf-8-sig")
now=datetime.now().astimezone().isoformat()
backup=root/("force_gate_before_CL_CD_"+datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+uuid.uuid4().hex[:6])
backup.mkdir(exist_ok=False)
shutil.copy2(plan_path,backup/"plan.json")
shutil.copy2(runbook_path,backup/"AUTONOMOUS_RECOVERY_PROMPT.md")
addition="""

## 31 October 2026: CL and total CD are primary stopping quantities

Explicit user decision: DO NOT wait for the CD_pressure own 0.5% mean-change criterion. Both component-own-relative criteria (pressure, viscous) are DIAGNOSTIC ONLY, not required for project acceptance of settled calm-water CL and total CD. Existing active STAR macro still computes legacy four-component settling_check.pass; do not modify active code or rewrite legacy records. Its four-way fail does NOT necessarily mean a failure under the newly documented project-primary check, and a project-primary pass is NOT a legacy four-way solver pass.

Primary project check: hydrodynamic CL (buoyancy removed once) and TOTAL CD must BOTH have mean shift under 0.5% AND within-window RMS below 0.5% for both preceding and latest non-overlapping complete 0.2-second windows, at TWO consecutive formal checks 0.2 s apart. Use complete nondownsized raw data, identical normalization/physics/dt, verified source identity, healthy VOF/mass/CFL and valid saved state. Monitor pressure and viscous component changes normalized to the TOTAL CD and inspect possible cancellation of opposite-signed changes, as well as longer windows, without requiring either component's own 0.5% threshold. This is a project decision rule, not an ITTC standard, formal iterative uncertainty estimate or proof of mesh convergence.

If evidenced, status must say PROJECT PRIMARY CL/CD SETTLED / LEGACY FOUR-COMPONENT TEST NOT PASSED OR NOT APPLICABLE. Preserve original solver states. If running compiled macro doesn't stop, use ONLY a separately validated gentle saved-stop mechanism after confirming controller generation, user STOP/pause, resource guard and no conflicting processes. Otherwise recommend ending, do not intervene blindly. Apply project-primary rule consistently to M10/M11/M12, and still require actual comparable mesh-agreement evidence.

Reference c=S/span=0.0238/0.02=1.19 m. At U=18 m/s, c/U=0.0661111 physical s, i.e. a single 0.2-s window is about 3.025 chord transit times. Transit time does not by itself establish convergence of wake/forces.
"""
after=(before.decode("utf-8-sig")+addition).encode("utf-8")
newsha=hashlib.sha256(after).hexdigest()
s=plan["selection"]["stabilization"]
assert set(s["coefficients"])=={"CL","CD","CD_pressure","CD_viscous"}
s["legacy_solver_coefficients"]=["CL","CD","CD_pressure","CD_viscous"]
s["coefficients"]=["CL","CD"]
s["diagnostic_only_coefficients"]=["CD_pressure","CD_viscous"]
s["legacy_solver_unchanged"]=True
s["component_diagnostics"]="Pressure and viscous deltas relative to total CD and possible cancellation; no own-component 0.5%-gate."
plan["selection"]["user_primary_CL_CD_override"]={"authorized":True,"at":now,"primary_coefficients":["CL","CD"],"mean_shift_and_RMS_threshold_pct":0.5,"window_s":0.2,"consecutive_passes":2,"pressure_own_0p5_gate":False,"component_diagnostics_required":True,"legacy_active_solver_unchanged":True,"save_policy":"Only verified gentle saved stop; never falsely mark legacy solver stabilized."}
plan["gate"][0]="Project-primary settled CL and total CD on all three meshes with 2 passes of 0.5% mean/RMS checks; componentown drift diagnostic only. Preserve original solver results and independently require actual mesh agreement."
plan["recovery_policy"]["runbook_sha256"]=newsha
plan["updated_at"]=now
plan["force_convective_scale"]={"chord_m":1.19,"flow_speed_m_s":18.0,"transit_time_s":1.19/18,"assessment_0p2s_chord_transits":.2/(1.19/18)}
for path,contents in ((runbook_path,after),(plan_path,(json.dumps(plan,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))):
 tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
 tmp.write_bytes(contents);os.replace(tmp,path)
assert hashlib.sha256(runbook_path.read_bytes()).hexdigest()==json.loads(plan_path.read_text(encoding="utf-8"))["recovery_policy"]["runbook_sha256"]
with (root/"decisions.jsonl").open("a",encoding="utf-8") as f:
 f.write(json.dumps({"at":now,"event":"user_authorized_CL_CD_primary_only","legacy_solver_changed":False,"pressure_own_threshold_not_required":True,"primary":["CL","CD"],"diagnostics":["CD_pressure","CD_viscous"],"runbook_sha256":newsha,"backup":str(backup)},ensure_ascii=False)+"\n")
print(json.dumps({"ok":True,"hash_verified":True,"new_primary":["CL","CD"],"diagnostic_only":["CD_pressure","CD_viscous"],"convective_time_s":1.19/18,"running_solver_changed":False,"backup":str(backup)},ensure_ascii=False))
