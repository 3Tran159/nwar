"""One-shot fail-closed controller. Await own dual-pilot RECEIPTS, then restore M10 safely.
Never kill processes, clear foreign locks, change source .sim, or override user STOP_ALL.
"""
from pathlib import Path
import datetime,time,subprocess,sys,json,os
R=Path(r"E:\ntnu_mesh_optimization_20261030")
sys.path.insert(0,str(R))
import mesh_queue_control_m10_dt2_20261031 as control
P=R/"M10_W01a_dt0004_matched_GPU_20261031"
L=R/"m10_dt4_pilot.lock"
OWN=R/"m10_dt4_finalize_once.lock"
DEST=R/"m10_dt4_finalize_once_result.json"
def write(obj):
 control.write(DEST,obj)
def now():return control.stamp()
def run():
 with OWN.open("x",encoding="utf8") as f:json.dump({"pid":os.getpid(),"at":now()},f)
 try:
  started=time.monotonic()
  while time.monotonic()-started<1800:
   if (R/"STOP_ALL").exists():
    write(dict(at=now(),status="blocked_stop_all",did_not_resume=True));return
   if L.exists():
    owner=control.read(L)
    if not control.alive(owner.get("pid")):
     write(dict(at=now(),status="pilot_lock_owner_not_alive_no_archive",did_not_resume=True));return
    time.sleep(6);continue
   result=control.read(R/"m10_dt4_pilot_result.json")
   status=control.read(P/"current.json").get("status")
   if result and status in ("completed_matched_pilot","not_accepted_no_auto_retry"):
    script=R/"resume_M10_after_dt4_pilot_20261031.py"
    output=subprocess.run([r"C:\Python315\python.exe",str(script)],cwd=R,
       capture_output=True,text=True,encoding="utf8",errors="replace",timeout=85)
    write(dict(at=now(),status="decision_process_completed" if output.returncode==0 else "decision_blocked",
       choice_control_exit_code=output.returncode,stdout=output.stdout[-5000:],
       stderr=output.stderr[-1200:],source_checkpoints_untouched=True))
    return
   write(dict(at=now(),status="pilot_finished_without_recognized_receipt",pilot_status=status,did_not_resume=True))
   return
  write(dict(at=now(),status="timed_out_without_intervention",did_not_resume=True))
 finally:
  if OWN.exists() and control.read(OWN).get("pid")==os.getpid():OWN.unlink()
if __name__=="__main__":run()
