"""One-shot no-foil inlet boundary diagnostic, not wave validation.
Only the target wave height changes: H=0.0001m vs failed H=0.5m.
Same saved calm 53200-cell .sim, dt=0.001, CPU1, 10 inner and original compiled STAR macro.
All outputs E:. No modifications to original inputs, queue, M13, HF or held C01.
"""
from pathlib import Path
from datetime import datetime
import sys, os, json, uuid, hashlib, csv
R=Path(r"E:\ntnu_mesh_optimization_20261030")
W=R/"wave_surface_only"
P=R/"parallel_cpu_20261031"
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
OUT=W/"wave_nearflat_inlet_CPU1_20261031_once"
SRC=W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"/"calm_pilot_final.sim"
OLD=W/"zero_start_matrix_evening_20261031_182305_689cb9"/"waves"/"L20_H500_baseline"
GOOD=W/"WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0"
LOCKS=[P/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_mesh_comparison.lock"]
sys.path.insert(0,str(R))
import owned_experiment_runtime_20261031 as rt
def assert_preflight():
    now=datetime.now().astimezone()
    assert now.isoformat()<"2026-10-31T23:59:59+01:00" and now.date().isoformat()=="2026-10-31","No new starts after deadline"
    plan=rt.read(R/"plan.json")
    assert plan["selection"]["lightweight_optimization_screen"]["both_required"]
    assert rt.sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"]
    assert rt.read(F/"campaign_hold.json").get("active") is True
    assert rt.read(R/"M13_farfield15_20261031"/"flow_state.json").get("status")=="flow_saved_primary_accepted","M13 status changed"
    assert not OUT.exists(),"Attempt already exists: no duplicates"
    assert not any(k.exists() for k in LOCKS),"Auxiliary owned by another controller"
    assert rt.resource_problem() is None,rt.resource_problem()
    assert SRC.exists() and SRC.stat().st_size>30_000_000
    digest=rt.sha(SRC)
    assert digest==rt.read(OLD/"identity.json")["source_sha256"],"Failed test source mismatch"
    assert digest==rt.read(GOOD/"pilot_config.json")["source_sha256"],"Good pilot source mismatch"
    done=rt.read(SRC.parent/"completed.json")
    assert abs(float(done["time_s"])-.4)<1e-8 and done.get("steps")==400
    oldres=rt.read(OLD/"stage_result.json")
    assert oldres.get("exit_code")==1 and oldres.get("source_unchanged") is True
    good=rt.read(GOOD/"pilot_result.json")
    assert good.get("completed",{}).get("steps")==500 and good.get("final_sim_exists") is True
    macro=OLD/"WaveFromOwnCalm_20261031.java"
    assert macro.exists() and macro.stat().st_size>8000
    t=macro.read_text(encoding="utf-8")
    assert 'private final double t0=.4, dt=.001;' in t
    assert 'H=Double.parseDouble(System.getenv("NTNU_NOFOIL_H"))' in t
    assert 'steps<200||steps>5000' in t
    assert 's.getSimulationIterator().step(1)' in t
    for pid,name in rt.guard.processes().values():
        if "starccm" in name.lower() and "starccmw" not in name.lower():
            raise AssertionError("Another STAR execution process may own resources")
    return macro,digest
def main():
    macro,digest=assert_preflight()
    if "--preflight-only" in sys.argv:
        print(json.dumps({"status":"PREFLIGHT_PASS","source_sha256":digest,"date":rt.now(),"unchanged_original_macro":True,"test":"near-flat inlet 0.1mm on 53200 cells, 1ms CPU1"}),flush=True)
        return
    token=uuid.uuid4().hex
    acquired=[]
    try:
        for lock in LOCKS:
            with lock.open("x",encoding="utf-8") as f:
                json.dump({"pid":os.getpid(),"token":token,"at":rt.now(),"kind":"one_shot_nearflat_inlet_boundary_diagnostic","folder":str(OUT)},f)
            acquired.append(lock)
        OUT.mkdir(exist_ok=False)
        rt.write(OUT/"decision.json",{"at":rt.now(),"hypothesis":"Boundary wave-model activation itself versus finite wave amplitude","sole_physical_change":"wave target H from 0.5 m to 0.0001 m","source":str(SRC),"source_sha256":digest,"existing_macro_sha256":rt.sha(macro),"cells":53200,"dt_s":0.001,"cpu_workers":1,"inner":10,"steps_budget":200,"solver_wall_budget_s":1100,"scientific_acceptance":False,"retry_allowed":False,"C01_hold_preserved":True,"originals_unmodified":True})
        env={"NTNU_NOFOIL_WAVE_OUT":str(OUT),"NTNU_NOFOIL_OUT":str(OUT),"NTNU_NOFOIL_CELLS":"53200","NTNU_NOFOIL_WATER_M3":"38.4","NTNU_NOFOIL_LAMBDA":"20","NTNU_NOFOIL_H":"0.0001","NTNU_NOFOIL_XMIN":"-35","NTNU_NOFOIL_XMAX":"45","NTNU_NOFOIL_WAVE_PERIOD_S":str(20/23.612),"NTNU_NOFOIL_WAVE_STEPS":"200"}
        rt.write(W/"wave_nearflat_control_state.json",{"status":"starting","directory":str(OUT),"at":rt.now(),"controller_pid":os.getpid()})
        folder,stage=rt.stage(OUT,SRC,macro,env=env,workers=1,gpu=False,mask=1<<22,budget_s=1100,protect_main=False,phase="nearflat_inlet_boundary_diagnostic_only")
        completed=rt.read(OUT/"completed.json")
        h=rt.rows(OUT/"history.csv")
        last=h[-1] if h else {}
        confirmed=bool(stage["exit_code"]==0 and stage["source_unchanged"] and completed.get("steps")==200 and completed.get("status")=="target_reached" and abs(float(last.get("time_s",0))-.6)<1e-7 and (OUT/"wave_pilot_final.sim").stat().st_size>20000000)
        result={"at":rt.now(),"diagnostic_complete":confirmed,"not_wave_propagation_validation":True,"completed":completed,"history_rows":len(h),"last_measured":last,"source_unchanged":rt.sha(SRC)==digest,"output":str(OUT)}
        rt.write(OUT/"analysis_result.json",result)
        rt.write(W/"wave_nearflat_control_state.json",{"status":"diagnostic_saved_for_interpretation" if confirmed else "diagnostic_incomplete","at":rt.now(),"directory":str(OUT),"confirmed":confirmed})
        print(json.dumps({"event":"nearflat_diagnostic_result","diagnostic_complete":confirmed,"steps":completed.get("steps"),"time_s":completed.get("time_s"),"scientific_accepted":False}),flush=True)
    except BaseException as err:
        if OUT.exists():
            (OUT/"STOP").touch()
            rt.write(OUT/"controller_error.json",{"at":rt.now(),"error_class":type(err).__name__,"reason":rt.guard.redact(str(err))[:400],"action":"STOP only owned isolated auxiliary; no automatic retry"})
            rt.write(W/"wave_nearflat_control_state.json",{"status":"failed_no_autoretry","at":rt.now(),"directory":str(OUT)})
        raise
    finally:
        proc=rt.read(OUT/"process.json").get("pid") if OUT.exists() else None
        ended=not proc or not rt.guard.alive(proc)
        for lock in reversed(acquired):
            if ended and rt.read(lock).get("token")==token:
                lock.unlink()
if __name__=="__main__": main()
