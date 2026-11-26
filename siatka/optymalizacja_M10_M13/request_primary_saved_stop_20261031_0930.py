"""Request one generation-pinned, local authenticated, gentle SAVE/STOP of M12.
User-approved project-primary CL/CD threshold has passed twice, verified on raw.
Never SIGKILL; no controller/source edits; POST via tested local dashboard route.
"""
from pathlib import Path
import csv,datetime,hashlib,json,math,os,re,sys,urllib.request,urllib.error,uuid
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030")
STUDY=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
PARENT=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
BASE="http://127.0.0.1:8771"
def load(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def stop(reason):
 raise RuntimeError(reason)
def local_stamp():return datetime.datetime.now().astimezone().isoformat()
def get(url):
 req=urllib.request.Request(BASE+url,headers={"Host":"127.0.0.1:8771","Cache-Control":"no-store"})
 with urllib.request.urlopen(req,timeout=10) as resp:return resp.read()
def journal(d):
 line=json.dumps(d,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n"
 with (ROOT/"decisions.jsonl").open("a",encoding="utf-8") as f:f.write(line);f.flush();os.fsync(f.fileno())
def record(name,data):
 p=ROOT/name;temp=p.with_name(p.name+"."+uuid.uuid4().hex+".tmp")
 temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8");os.replace(temp,p)
now=datetime.datetime.now().astimezone()
if now.date()!=datetime.date(2026,10,31) or now.hour>=12:stop("No M12 early stop beyond authorized morning window")
plan=load(ROOT/"plan.json")
if hashlib.sha256((ROOT/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()!=plan["recovery_policy"]["runbook_sha256"]:stop("Runbook mismatch")
if plan["selection"]["user_primary_CL_CD_override"].get("authorized") is not True:stop("CL/CD permission missing")
auditpath=ROOT/"project_primary_independent_audit_20261031_0930.json"
audit=load(auditpath)
review=datetime.datetime.fromisoformat(audit["review_at_local"])
if not (0<=(now-review).total_seconds()<600):stop("Independent scientific audit stale")
if audit["consecutive_primary_checks"]!=2 or not all(audit[k] for k in ("runbook_sha_verified","source_sim_sha_verified")):stop("Scientific evidence incomplete")
if not all(audit["control_source_hashes_verified"].values()):stop("Controller digest missing")
if not ("PROJECT PRIMARY" in audit["decision"] and "LEGACY" in audit["decision"]):stop("Decision evidence ambiguous")
state=load(STUDY/"gpu_study_state.json")
run=Path(state["directory"])
if state["status"]!="GPU_job_running" or state["scope"]!="calm_water_only" or "G10_F" not in state["job"]:stop("Active main job changed")
if not run.is_dir() or load(run/"process.json").get("pid")!=state.get("star_pid"):stop("M12 process identity invalid")
if (STUDY/"STOP").exists() or (run/"STOP").exists() or (PARENT/"STOP_ALL").exists():stop("Previous stop/hold active")
if (ROOT/"parallel_cpu_20261031"/"auxiliary.lock").exists():stop("Auxiliary lock exists")
if load(ROOT/"parallel_cpu_20261031"/"current.json").get("status") not in ("calm_pilot_completed","pilot_completed"):stop("Aux state not safely idle")
controller=load(STUDY/"gpu_live_study.lock");queue=load(PARENT/"queue.lock")
if controller.get("pid")!=state["pid"] or queue.get("pid")!=state["pid"] or controller.get("token")!=queue.get("token"):stop("Owner/queue lock conflict")
receipt=load(PARENT/"mesh_control_receipt.json")
if receipt.get("status")!="passed" or receipt.get("tests",0)<16:stop("Controller validation not documented")
for path,hexhash in receipt["source_sha256"].items():
 if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=hexhash:stop("Validated controller changed: "+Path(path).name)
if (STUDY/"dashboard_control"/"pause.json").is_file() and load(STUDY/"dashboard_control"/"pause.json").get("state")!="resumed":stop("Existing user pause state")
last=None
with (run/"history.csv").open("rb") as f:
 f.seek(0,2);pos=f.tell();f.seek(max(0,pos-1500));s=f.read().decode("utf-8",errors="replace").splitlines()
 for line in reversed(s):
  parts=line.split(",")
  if len(parts)==18:
   try:
    t=float(parts[3]);v=float(parts[9]);cfl=float(parts[13]);step=int(parts[1])
    if math.isfinite(t) and math.isfinite(v) and math.isfinite(cfl):last=(t,step,v,cfl);break
   except ValueError:pass
if last is None or last[0]<audit["physical_time_s"] or last[0]>3.7015:stop("History does not agree with audit/stage")
if last[3]>=1.05:stop("Last interface CFL guard issue")
api=json.loads(get("/api/mesh-study"))
generation=str(state["pid"])+"|"+state["job"]+"|"+str(run)
if api.get("generation")!=generation or api.get("job")!=state["job"] or api.get("status")!="running" or api.get("can_pause") is not True:stop("Local generation or controllability changed")
page=get("/dashboard.html").decode("utf-8",errors="strict")
m=re.search(r'window\.NTNU_LOCAL_TOKEN\s*=\s*("(?:\\.|[^"\\])*")\s*;',page)
if m is None:stop("Local token could not be read from dashboard; no bypass")
token=json.loads(m.group(1))
if not token or len(token)<30:stop("Local authorization token invalid")
identifier=uuid.uuid4().hex
intent={"at":local_stamp(),"event":"user_primary_CL_CD_verified_request_gentle_M12_save_stop","id":identifier,"job":state["job"],
 "controller_pid":state["pid"],"star_pid":state["star_pid"],"generation":generation,
 "scientific_audit":str(auditpath),"audit_sha256":hashlib.sha256(auditpath.read_bytes()).hexdigest(),
 "formal_times_s":[3.0013,3.2013],"two_primary_passes_from_raw":True,"legacy_four_way_pass":False,
 "snapshot_time_s":last[0],"snapshot_steps":last[1],"source_unmodified":True,"control_route":"local authenticated generation-pinned pause API","solver_kill":False,
 "C01_wave_hold_unchanged":True,"HF_untouched":True}
journal(intent)
record("project_primary_saved_stop_intent_20261031_0930.json",intent)
body=json.dumps({"generation":generation}).encode("utf-8")
req=urllib.request.Request(BASE+"/api/mesh-study/pause",data=body,headers={
 "Host":"127.0.0.1:8771","Origin":BASE,"X-NTNU-Control":token,
 "Content-Type":"application/json"},method="POST")
try:
 with urllib.request.urlopen(req,timeout=25) as resp:
  result=json.loads(resp.read())
  if resp.status!=202:stop("Controller returned unexpected response")
except urllib.error.HTTPError as e:
 error=(e.read().decode("utf-8",errors="replace") or "")[:200]
 journal({"event":"gentle_M12_save_stop_refused","at":local_stamp(),"id":identifier,"http_status":e.code,"reason":error})
 stop("Pause endpoint refused request "+str(e.code))
except Exception as e:
 journal({"event":"gentle_M12_save_stop_uncertain","at":local_stamp(),"id":identifier,"error":str(type(e).__name__)})
 raise
checkstate=load(STUDY/"dashboard_control"/"pause.json")
accepted=bool(checkstate.get("state")=="pause_requested" and checkstate.get("directory")==str(run) and checkstate.get("controller_pid")==state["pid"] and checkstate.get("star_pid")==state["star_pid"])
response={"at":local_stamp(),"event":"M12_gentle_saved_stop_requested","id":identifier,"endpoint_acknowledged":True,
 "control_marker_owned":accepted,"pause_id":checkstate.get("id"),"local_status":json.loads(get("/api/mesh-study")).get("status"),
 "message":"Save requested at completed physical step; not yet certified saved","solver_killed":False,"raw_legacy_status_unchanged":True}
journal(response)
record("project_primary_saved_stop_request_result_20261031_0930.json",response)
print(json.dumps(response,ensure_ascii=False))
