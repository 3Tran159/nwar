"""Read-only STAR field audit on copied calm and saved wave cases. Zero solver steps."""
from pathlib import Path
import datetime,hashlib,json,shutil,sys,os,subprocess,time,uuid,re
R=Path(r"E:\ntnu_mesh_optimization_20261030")
W=R/"wave_surface_only"
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
sys.path.insert(0,str(R/"parallel_cpu_20261031"))
import bounded_cpu_pilot as g
ROOT=W/"wave_pressure_readonly_20261031"
M=W/"AuditWavePressureReadOnly_20261031.java"
SOURCES={
"flat_calm_53200":W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"/"calm_pilot_final.sim",
"coarse_wave_41200":W/"zero_start_matrix_R2_coarse_continuation_20261031_4"/"waves"/"L20_H500_coarse"/"wave_pilot_final.sim"
}
LOCKS=[R/"parallel_cpu_20261031"/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_mesh_comparison.lock"]
OWNLOCK=W/"wave_pressure_audit.lock"
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(2**20),b""):h.update(b)
 return h.hexdigest()
def save(path,data):
 tmp=path.with_name(path.name+".tmp."+uuid.uuid4().hex)
 tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 os.replace(tmp,path)
def prep():
 now=datetime.datetime.now().astimezone()
 assert now<datetime.datetime.fromisoformat("2026-11-01T09:00:00+01:00")
 assert not ROOT.exists() and not OWNLOCK.exists(), "No duplicate audit"
 assert not any(f.exists() for f in LOCKS),"Wave trial ownership conflict"
 assert not any(p.exists() for p in (R/"STOP_ALL",W/"STOP_ALL",F/"STOP_ALL")),"STOP_ALL present"
 plan=json.loads((R/"plan.json").read_text(encoding="utf-8"))
 assert sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"],"Runbook hash mismatch"
 assert json.loads((F/"campaign_hold.json").read_text(encoding="utf-8"))["active"] is True,"C01 hold changed"
 assert g.free_memory()>=16*1024**3 and shutil.disk_usage("C:/").free>=15*1024**3 and shutil.disk_usage("E:/").free>=25*1024**3,"Resource reserve failed"
 assert M.stat().st_size>900
 assert Path(g.STAR).exists()
 assert all(q.is_file() and q.stat().st_size>30_000_000 for q in SOURCES.values())
 for pid,(parent,name) in g.processes().items():
  if name.lower().startswith("starccm") and not name.lower().startswith("starccmw"):
   raise RuntimeError("Another active STAR execution process")
 return now
def main():
 now=prep()
 token=uuid.uuid4().hex
 with OWNLOCK.open("x",encoding="utf-8") as fh:json.dump({"controller_pid":os.getpid(),"token":token,"at":now.isoformat(),"owner":"read_only_pressure_audit"},fh)
 active=None
 try:
  ROOT.mkdir(exist_ok=False)
  save(ROOT/"preflight.json",{"at":now.isoformat(),"read_only":True,"source_count":2,"macro_sha256":sha(M),"target":"finite pressure/VOF/velocity fields in otherwise suspect wave-only solver, no new CFD run","C01_hold_unchanged":True})
  for name,source in SOURCES.items():
   # Verify no conflicting ownership before each source; do not touch .sim source.
   assert not any(q.exists() for q in LOCKS),"New wave trial started"
   folder=ROOT/name; folder.mkdir(exist_ok=False)
   digest=sha(source)
   target=folder/"input.sim";shutil.copy2(source,target)
   assert sha(target)==digest,"Copy invalid"
   copied=folder/M.name;shutil.copy2(M,copied)
   save(folder/"input_identity.json",{"source":str(source),"source_sha256":digest,"copy_sha256":sha(target),"macro_sha256":sha(M),"steps":0,"gpu":False,"workers":1})
   with (folder/"star.log").open("x",encoding="utf-8") as log:
    cmd=[str(g.STAR),*g.saved_options(1),"-batch",str(copied),str(target)]
    active=subprocess.Popen(cmd,cwd=str(folder),stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    save(folder/"process.json",{"pid":active.pid,"controller_pid":os.getpid(),"at":datetime.datetime.now().astimezone().isoformat(),"read_only":True})
    try:active.wait(timeout=420)
    except subprocess.TimeoutExpired:
     save(ROOT/"suspended_audit_timeout.json",{"case":name,"pid":active.pid,"at":datetime.datetime.now().astimezone().isoformat(),"action":"No kill, retain ownership and diagnose liveness"})
     print("STAR_READONLY_TIMEOUT retaining lock, case=",name,flush=True)
     return
    finally:log.flush()
   final=(folder/"star.log").read_text(encoding="utf-8",errors="replace")
   results=dict(re.findall(r"(PRESSURE_AUDIT_[A-Z_]+)\s+([^\s\r\n]+)",final))
   receipt={"case":name,"exit_code":active.returncode,"observed_complete":("PRESSURE_AUDIT_COMPLETE_NO_STEPS_NO_SAVE" in final),"source_hash_unchanged":sha(source)==digest,"source_copy_hash_unchanged":sha(target)==digest,"results":results,"no_solver_steps":True,"time":datetime.datetime.now().astimezone().isoformat()}
   save(folder/"receipt.json",receipt)
   print("READONLY",name,"exit",active.returncode,"complete",receipt["observed_complete"],"fields",{k:v for k,v in results.items() if k.startswith("PRESSURE_AUDIT_P_")},flush=True)
   if active.returncode!=0 or not receipt["observed_complete"]:break
  save(ROOT/"completed.json",{"status":"read_only_finished","at":datetime.datetime.now().astimezone().isoformat(),"no_solver_steps":True,"source_paths_unchanged":True,"C01_hold_preserved":True})
 finally:
  if active is None or active.poll() is not None:
   if OWNLOCK.is_file():
    try:
     j=json.loads(OWNLOCK.read_text(encoding="utf-8"))
     if j.get("token")==token:OWNLOCK.unlink()
    except (OSError,ValueError):pass
if __name__=="__main__":
 try:main()
 except BaseException as exc:
  if ROOT.exists():save(ROOT/"controller_error.json",{"type":type(exc).__name__,"message":str(exc)[:400],"at":datetime.datetime.now().astimezone().isoformat()})
  raise