"""Read-only M13 completed wave-cycle review; writes only its own E-drive audit."""
from pathlib import Path
from datetime import datetime
import json, sys, hashlib
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030")
P=ROOT/"M13_wave_direct_20261031"
sys.path.insert(0,str(ROOT/"foil_live_dashboard_20261031"))
import foil_live
def read(p):
    try: return json.loads(p.read_text(encoding="utf-8-sig"))
    except (ValueError,OSError): return {}
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def main():
    out=P/"WATCH_R4V_20261101_0732.json"
    if out.exists(): raise RuntimeError("Refusing overwrite")
    result=foil_live.collect()
    matches=[r for r in result.get("runs",[]) if r.get("id")=="M13_GPU_W20_H050_continuation_R4V_20261101"]
    if len(matches)!=1: raise RuntimeError("R4V collector result missing")
    r=matches[0];c=r["phase_cycles"]
    r4=P/r["id"]
    receipt=read(r4/"stage_result.json")
    done=read(r4/"completed.json")
    if receipt.get("exit_code")!=0 or not receipt.get("source_unchanged") or done.get("status")!="target_reached": raise RuntimeError("R4V final receipt incomplete")
    src=r4/"wave_pilot_final.sim"
    if not src.exists() or src.stat().st_size<300000000: raise RuntimeError("Saved final state missing")
    four=[{k:a.get(k) for k in ("number","start","end","T","CL_mean","CD_mean","CL_ptp","CD_ptp","CL_mean_delta","CD_mean_delta","CL_cycle_RMS_abs","CD_cycle_RMS_abs")} for a in c.get("overlays",[])]
    doc={"at":datetime.now().astimezone().isoformat(),"type":"read_only_completed_M13_wave_review","source":str(r4),"source_final_sim_bytes":src.stat().st_size,"source_final_sim_sha256":sha(src),"receipt":receipt,"last":r.get("last"),"phase_cycles_count":c.get("count"),"phase_cycles_method":c.get("method"),"cycle_status":c.get("status"),"analysis_not_before_s":c.get("analysis_not_before_s"),"last_four_complete_periods":four,"lineage":r.get("lineage"),"frame":{k:r.get("frame",{}).get(k) for k in ("time_s","sha256","interface_CFL","verified_bytes")} if r.get("frame") else None,"calm_reference":result.get("calm_reference"),"wave_arrival_physically_confirmed":False,"periodic_forces_validated":False,"20_cycles_verified":False,"new_solver_started":False,"interpretation":"Estimated arrival/ramp and gauge threshold define diagnostic periods, not formal propagation/periodic validation."}
    out.write_text(json.dumps(doc,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"audit_path":str(out),"cycles_diagnostic":doc["phase_cycles_count"],"four":four,"last":doc["last"],"final_sha256":doc["source_final_sim_sha256"],"frame":doc["frame"],"status":r.get("status"),"reporting_only":True},ensure_ascii=False))
if __name__=="__main__":main()
