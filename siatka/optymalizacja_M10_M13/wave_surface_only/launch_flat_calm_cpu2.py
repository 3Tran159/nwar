"""Bounded independent L20 no-foil FLAT calm 1ms pilot on CPU2, protecting M12 GPU."""
import os,sys,json,time,shutil,subprocess,threading,hashlib,datetime,uuid,statistics,math
from pathlib import Path
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030")
WORK=ROOT/"parallel_cpu_20261031"
WAVE=ROOT/"wave_surface_only"
MAIN=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
ORIG=Path(r"E:\ntnu\quasi2d_waves_20261029\W20_H24_X4_Q2D_r5")
sys.path.insert(0,str(WORK))
import bounded_cpu_pilot as guard
MASK=guard.MASK
GIB=guard.GIB
def now():return datetime.datetime.now().astimezone().isoformat()
def write(path,data):guard.write(path,data)
def read(path):return guard.read(path)
def log(msg,**fields):
    print(json.dumps({"time":now(),"msg":msg,**fields},ensure_ascii=False),flush=True)
def main():
    plan=read(ROOT/"plan.json")
    assert hashlib.sha256((ROOT/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()==plan["recovery_policy"]["runbook_sha256"]
    policy=plan["parallel_execution"]
    assert policy["authorized"] and policy["maximum_auxiliary_solvers"]==1
    assert policy["first_auxiliary_backend"].startswith("CPU only")
    assert datetime.datetime.now().astimezone().date()==datetime.date(2026,10,31)
    assert datetime.datetime.now().hour<12
    assert read(WAVE/"plan.json")["geometry_validation"]["topology_geometry_pass"] is True
    assert read(WAVE/"baseline_dataset_equivalence.json")["numerical_mesh_equivalent"] is True
    # The source has a nonzero wave at t=0; the fresh macro explicitly MUST flatten it on a disposable copy.
    assert read(ORIG/"build_result.json")["audit"]["cells"]==53200
    assert abs(read(ORIG/"build_result.json")["audit"]["initial_gauges"][1]["eta_actual_m"])>.1
    source=ORIG/"built.sim"
    assert source.is_file() and source.stat().st_size>20_000_000
    src_sha=guard.sha(source)
    macro=WAVE/"PrepareNoFoilCalmPilot.java"
    macro_sha=guard.sha(macro)
    assert macro.is_file() and macro.stat().st_size>5000
    # No second auxiliary while the previous pilot is running or an old orphan could be present.
    lock=WORK/"auxiliary.lock"
    token=uuid.uuid4().hex
    with lock.open("x",encoding="utf-8") as f:json.dump({"pid":os.getpid(),"token":token,"role":"WS_L20_baseline_flat_calm_CPU2","at":now()},f)
    proc=None;output=None;result=None;failure=None
    try:
        mainstate=read(MAIN/"gpu_study_state.json")
        job=mainstate.get("job");mpid=mainstate.get("star_pid");cpid=mainstate.get("pid")
        assert mainstate.get("status")=="GPU_job_running" and "G10_F" in str(job)
        assert guard.alive(mpid) and guard.alive(cpid)
        mainhistory=Path(mainstate["directory"])/"history.csv"
        rows=guard.raw(mainhistory)
        baseline_costs=guard.costs(rows[-301:])
        assert len(baseline_costs)>=200
        baseline=statistics.median(baseline_costs)
        assert guard.stop_reason(rows,mainhistory,job,mpid) is None
        assert guard.free_memory()>16*GIB and shutil.disk_usage(str(WAVE)).free>25*GIB
        assert shutil.disk_usage("C:/").free>15*GIB
        source_export=read(ORIG/"build_result.json")
        output=WAVE/("WS_L20_H050_baseline_flatCalm_CPU2_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+"_"+token[:6])
        output.mkdir(exist_ok=False)
        shutil.copy2(source,output/"input.sim")
        assert guard.sha(output/"input.sim")==src_sha
        shutil.copy2(macro,output/macro.name)
        assert guard.sha(output/macro.name)==macro_sha
        config=dict(stage="flat_calm_ONLY",old_source_wave_filled=True,no_wave_activation=True,
             source=str(source),source_sha256=src_sha,macro_sha256=macro_sha,
             source_built_cells=53200,reference_CGNS_verified_equivalent=True,
             steps=400,dt_s=.001,inner=10,CPU_workers=2,CPU_mask=MASK,gpu=False,
             M12_job=job,M12_pid=mpid,M12_baseline_median_s_per_step=baseline,
             max_acceptable_slowdown=0.15,
             note="Independent calm stage, NOT a settled 1ms-wave propagation result, does not release foil-wave hold.")
        write(output/"pilot_config.json",config)
        write(WORK/"current.json",dict(status="preparing_nofoil_flat_calm",directory=str(output),controller_pid=os.getpid(),at=now(),**config))
        env=dict(os.environ,NTNU_NOFOIL_OUT=str(output),NTNU_NOFOIL_DT=".001",NTNU_NOFOIL_STEPS="400")
        assert guard.k.SetProcessAffinityMask(guard.k.GetCurrentProcess(),MASK)
        assert guard.k.SetPriorityClass(guard.k.GetCurrentProcess(),guard.BELOW_NORMAL)
        options=guard.saved_options(2)
        assert "-gpgpu" not in options
        args=[str(guard.STAR),*options,"-batch",str(output/macro.name),str(output/"input.sim")]
        t0=time.monotonic();first_stop=None;reason=None;bad=0;last_checked=rows[-1][0];samples=[]
        with (output/"star.log").open("x",encoding="utf-8") as logf:
            proc=subprocess.Popen(args,cwd=output,env=env,stdout=subprocess.PIPE,
               stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",
               creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            write(output/"process.json",dict(pid=proc.pid,controller_pid=os.getpid(),workers=2,gpu=False,mask=MASK,started_at=now()))
            log("nofoil_flat_calm_CPU2_started",pid=proc.pid,directory=str(output),main_m12_unchanged=True)
            def drain():
                for line in proc.stdout:logf.write(guard.redact(line));logf.flush()
            tr=threading.Thread(target=drain,daemon=True);tr.start()
            while proc.poll() is None:
                owned=guard.cap_owned(proc.pid,{mpid,cpid})
                mainrows=guard.raw(mainhistory)
                why=guard.stop_reason(mainrows,mainhistory,job,mpid)
                newer=[r for r in mainrows if r[0]>last_checked]
                if len(newer)>=31:
                    c=guard.costs(newer)
                    if c:
                        measured=statistics.median(c)
                        bad=bad+1 if measured>1.15*baseline else 0
                        last_checked=newer[-1][0]
                        samples.append(dict(at=now(),main_steps=len(newer),main_time_s=newer[-1][1],median_s_per_step=measured,slowdown_fraction=measured/baseline-1,excess_windows=bad))
                        if bad>=2:why=why or "M12_slowdown_over_15_percent_two_windows"
                if time.monotonic()-t0>2400:why=why or "total_pilot_wall_budget"
                if datetime.datetime.now().hour>=11 and datetime.datetime.now().minute>=45:why=why or "before_noon_stop"
                if why and reason is None:
                    reason=why;first_stop=time.monotonic()
                    (output/"STOP").touch()
                    log("auxiliary_graceful_stop_requested",reason=reason)
                progress=read(output/"progress.json")
                state=dict(status="stop_requested" if reason else "running_calm" if progress else "loading_calm",
                   at=now(),directory=str(output),controller_pid=os.getpid(),auxiliary_pid=proc.pid,
                   owned_auxiliary_pids=owned,M12_job=job,M12_baseline_s_per_step=baseline,
                   M12_last_time_s=mainrows[-1][1] if mainrows else None,
                   auxiliary_steps=progress.get("steps",0),auxiliary_time_s=progress.get("time_s"),
                   free_RAM_GiB=guard.free_memory()/GIB,reason=reason,timing_windows=samples[-100:])
                write(output/"monitor.json",state);write(WORK/"current.json",state)
                if first_stop and time.monotonic()-first_stop>600:
                    # Keep own process and lock if graceful stop stalls; do not force-kill an active save.
                    log("stop_request_still_pending_preserve_process",pid=proc.pid)
                    break
                time.sleep(5)
            if proc.poll() is None:
                result=dict(status="unresolved_auxiliary_graceful_stop",at=now(),directory=str(output),reason=reason,auxiliary_pid=proc.pid)
                write(WORK/"current.json",result);write(output/"pilot_result.json",result)
                return
            rc=proc.wait(timeout=45)
            tr.join(timeout=20)
        completed=read(output/"completed.json")
        cpc=output/"calm_pilot_final.sim"
        saved=bool(cpc.exists() and cpc.stat().st_size>20_000_000)
        result=dict(status="calm_pilot_completed" if rc==0 and completed.get("status")=="target_reached" and saved and not reason else "calm_pilot_stopped_or_failed",
            at=now(),directory=str(output),returncode=rc,reason=reason,completed=completed,
            initial_flat_audit=read(output/"initial_flat_audit.json"),final_sim_exists=saved,
            main_m12_config_unchanged=True,original_source_unchanged=guard.sha(source)==src_sha,
            timing_windows=samples,M12_baseline_s_per_step=baseline,
            trustworthy_wave_propagation_result=False)
        result["performance_pass"]=len(samples)>=2 and all(x["slowdown_fraction"]<=.15 for x in samples[-2:])
        write(output/"pilot_result.json",result);write(WORK/"current.json",result)
        log("nofoil_flat_calm_result",status=result["status"],saved=saved,completed=completed,performance_pass=result["performance_pass"])
    except BaseException as ex:
        failure=guard.redact(repr(ex))
        if output:
            (output/"STOP").touch()
            write(output/"controller_error.json",dict(at=now(),error=failure,source_preserved=True,main_unchanged=True))
        if proc and proc.poll() is None:
            write(WORK/"current.json",dict(status="controller_error_auxiliary_STOP_sent",directory=str(output),auxiliary_pid=proc.pid,error=failure))
        log("nofoil_flat_calm_failed_preflight_or_run",error=failure)
        raise
    finally:
        if (proc is None or proc.poll() is not None) and read(lock).get("token")==token:lock.unlink()
if __name__=="__main__":main()
