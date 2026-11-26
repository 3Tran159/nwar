"""One bounded, independently owned CPU2 continuation from verified no-foil wave saved at t=2.507.
New files only on E:. Does not modify saved source, M11, M12, held C01 or HF.
"""
from pathlib import Path
import os, sys, json, uuid, shutil, datetime
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
R=W.parent
sys.path.insert(0,str(W))
import run_zero_start_12_matrix_20261031_R2 as z
import launch_halfdt_wave_cpu2_with_M11_guard as perf
from run_zero_start_12_matrix_20261031_R2 import read, write, sha, now
SOURCE=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"/"waves"/"L20_H500_coarse"
NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_4"
LOCKS=z.LOCKS
TOKEN=uuid.uuid4().hex
def guard_checks():
    assert now().date()==datetime.date(2026,10,31), "No new starts after authorized day"
    plan=read(R/"plan.json")
    assert sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"],"Runbook changed"
    assert plan["parallel_execution"]["authorized"] and plan["parallel_execution"]["maximum_auxiliary_solvers"]==1
    assert read(Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\campaign_hold.json")).get("active") is True
    assert z.check_danger() is None, z.check_danger()
    assert not NEW.exists(), "Already attempted continuation, never duplicate it"
    assert not any(x.exists() for x in LOCKS),"Auxiliary lock is in use"
    assert read(SOURCE/"completed.json").get("status")=="target_reached", "R3 must have successfully saved"
    prior=read(SOURCE/"stage_result.json")
    assert prior.get("exit_code")==0 and prior.get("source_unchanged") is True and prior.get("controller_reason") is None
    h=z.rows(SOURCE/"history.csv")
    assert len(h)>=2000 and int(h[-1]["step"])==2000
    t=float(h[-1]["time_s"])
    assert 4.50<t<4.52 and abs(t-read(SOURCE/"completed.json")["time_s"])<1e-7
    assert float(h[-1]["max_CFL"])<1 and float(h[-1]["max_speed_m_s"])<25
    setup=read(SOURCE/"wave_setup_audit.json")
    assert setup["model"]=="FifthOrderVofWave" and setup["lambda_m"]==20 and setup["target_H_m"]==0.5
    assert setup["GPU"]==0 and setup["initialization_performed"] is False and setup["wave_boundary_bindings"][1]["forcing"]=="YES"
    assert (SOURCE/"wave_pilot_final.sim").is_file() and (SOURCE/"wave_pilot_final.sim").stat().st_size>20_000_000
    assert read(SOURCE/"completed.json")["steps"]==2000
    assert read(SOURCE/"stage_result.json")["controller_reason"] is None
    assert read(W/"zero_start_12_current.json").get("status")=="coarse_continuation_saved_for_review", "Another wave controller changed state"
    assert read(W/"zero_start_matrix_R2_coarse_continuation_20261031_3"/"controller_result.json").get("final_sim_exists") is True
    assert (SOURCE/"wave_pilot_final.sim").stat().st_size>20_000_000
    assert shutil.disk_usage("E:\\").free>25*1024**3 and shutil.disk_usage("C:\\").free>15*1024**3
    import bounded_cpu_pilot as bc
    assert bc.free_memory()>16*1024**3
    main=perf.main_state()
    assert main is not None,"Main GPU M11 changed"
    perf.only_owned_main_star(main)
    durations,baseline=perf.get_gpu_durations(main)
    assert len(durations)>=200 and 0<baseline<20
    main_rows=z.rows(main/"history.csv")
    assert main_rows and (datetime.datetime.now().timestamp()-(main/"history.csv").stat().st_mtime)<180, "M11 history stale"
    return main,baseline,t
def build_macro(out):
    verified=W/"resume_coarse_r4_compilecheck_20261031"
    source=verified/"ContinueWaveOnlySavedR4.java"
    assert source.exists() and (verified/"compiled"/"macro"/"ContinueWaveOnlySavedR4.class").is_file()
    macro=out/source.name
    shutil.copy2(source,macro)
    assert sha(macro)==sha(source)
    return macro
def main():
    main_state,base,t0=guard_checks()
    locked=[]
    try:
        for path in LOCKS:
            with path.open("x",encoding="utf8") as f:json.dump({"pid":os.getpid(),"token":TOKEN,"kind":"saved_nofoil_wave_continuation","at":now().isoformat()},f)
            locked.append(path)
        NEW.mkdir(exist_ok=False)
        macro=build_macro(NEW)
        z.ROOT=NEW
        write(NEW/"plan.json",{
          "at":now().isoformat(),"source":str(SOURCE/"wave_pilot_final.sim"),
          "source_sha256":sha(SOURCE/"wave_pilot_final.sim"),
          "start_physical_s":t0,"physical_dt_s":0.001,"planned_additional_steps":2000,
          "lambda_m":20,"H_m":0.5,"mesh_cells":41200,
          "main_M11":str(main_state),"main_baseline_s_per_step":base,
          "continuation_no_reinitialization":True,
          "one_auxiliary_CPU2_below_normal":True,
          "scientific_acceptance_automatic":False,
          "owned_locks":[str(x) for x in locked]
        })
        save,folder=z.stage(main_state,base,"waves","L20_H500_coarse",
          SOURCE/"wave_pilot_final.sim",macro,
          dict(NTNU_NOFOIL_CELLS="41200",NTNU_NOFOIL_SOURCE_T=str(t0),
            NTNU_NOFOIL_WAVE_DT=".001",NTNU_NOFOIL_WAVE_STEPS="2000"),
          max_wall_s=2400)
        write(NEW/"controller_result.json",{
          "status":"saved_bounded_continuation_no_scientific_acceptance",
          "at":now().isoformat(),"directory":str(folder),
          "completion":read(folder/"completed.json"),
          "final_sim_exists":save.exists(),
          "original_source_preserved":True
        })
        write(z.STATUS,{"status":"coarse_continuation_saved_for_review","at":now().isoformat(),"directory":str(folder),"reason":"Do not mark full wave validated until probe analysis"})
    except BaseException as e:
        if NEW.exists():
            write(NEW/"controller_error.json",{"at":now().isoformat(),"error_type":type(e).__name__,"reason":str(e)[:700]})
        raise
    finally:
        for path in reversed(locked):
            if read(path).get("token")==TOKEN:
                path.unlink()
if __name__=="__main__":
    main()
