from pathlib import Path
import json,hashlib,datetime,urllib.request,os,sys,csv,statistics,math
P=Path(r"E:\ntnu_mesh_optimization_20261030")
W=P/"wave_surface_only"
print("DEVICE_TIME",datetime.datetime.now().astimezone().isoformat(),flush=True)
plan=json.loads((P/"plan.json").read_text(encoding="utf-8-sig"))
runbook=P/"AUTONOMOUS_RECOVERY_PROMPT.md"
actual=hashlib.sha256(runbook.read_bytes()).hexdigest()
expected=plan.get("recovery_policy",{}).get("runbook_sha256")
print("RUNBOOK_HASH_MATCH",actual==expected,"EXPECTED",expected,"ACTUAL",actual,flush=True)
print("SELECTION_OVERRIDE",json.dumps(plan.get("selection",{}).get("user_primary_CL_CD_override"),ensure_ascii=False)[:1400])
print("PARALLEL_POLICY",json.dumps(plan.get("parallel_execution",{}),ensure_ascii=False)[:3000])
print("RUNBOOK_LAST_SECTION",runbook.read_text(encoding="utf-8-sig")[-2400:])
def read(p,tail=1700):
 try:return p.read_text(encoding="utf-8-sig")[-tail:]
 except Exception as e:return "READ_ERROR "+str(e)
for x in ("decisions.jsonl","attempts.jsonl","watchdog_last_sample.json","mesh_queue_state.json","parallel_cpu_20261031/current.json","parallel_cpu_20261031/auxiliary.lock","wave_surface_only/zero_start_12_current.json","wave_surface_only/zero_start_matrix_R2_coarse_continuation_20261031_3/current.json"):
 print("FILE",x,read(P/x),flush=True)
print("FLAGS",[(str(q),q.exists()) for q in (P/"STOP_ALL",P/"STOP_ALL.txt",P/"STOP_ALL.flag",W/"campaign_hold.json",P/"mesh_queue_launch.lock")])
try:
 r=urllib.request.urlopen("http://127.0.0.1:8771/api/mesh-study",timeout=3).read().decode("utf-8")
 print("LOCAL_API",r[:3500])
except Exception as e:print("LOCAL_API_ERR",str(e))
q=P/"M11_G10_M_GPU_queue_20261031_105607_91db08"
for x in ("progress.json","settling_check.json","completed.json","exit.json","process.json","latest_checkpoint.json"):
 print("M11_FILE",x,read(q/x,2100))
for x in ("progress.json","monitor.json","pilot_result.json","completed.json","exit.json","initial_flat_audit.json"):
 root=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"
 found=list(root.rglob(x))
 print("R3_FILE",x,[(str(t),read(t,1400)) for t in found[:5]])
print("R3_ROOT",[(str(p),p.is_dir()) for p in (W/"zero_start_matrix_R2_coarse_continuation_20261031_3").iterdir()])
for x in ("cpu_study_state.json","gpu_study_state.json","calm_stabilization_progress.json","calm_mesh_screen.json","gci_results.json"):
 cp=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")/x
 print("SCI_FILE",x,read(cp,1300))
