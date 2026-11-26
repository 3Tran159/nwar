"""Read-only one-off STAR audit of independently saved wave state; no steps/save, only copied input."""
from pathlib import Path
import sys,os,uuid,json,time,shutil,subprocess,threading,datetime
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
sys.path.insert(0,str(W))
import run_zero_start_12_matrix_20261031_R2 as z
from run_zero_start_12_matrix_20261031_R2 import read,write,sha,now
import launch_halfdt_wave_cpu2_with_M11_guard as perf
import bounded_cpu_pilot as guard
SRC=W/"zero_start_matrix_20261031_13h_R2"/"waves"/"L20_H500_coarse"/"wave_pilot_final.sim"
ROOT=W/"audit_saved_wave_binding_20261031_r3"
LOCKS=z.LOCKS
token=uuid.uuid4().hex
def run():
    assert not ROOT.exists() and not any(p.exists() for p in LOCKS)
    assert not any(p.exists() for p in (W.parent/"STOP_ALL",W/"STOP_ALL"))
    assert z.check_danger() is None
    s=perf.main_state();assert s is not None
    perf.only_owned_main_star(s)
    win,baseline=perf.get_gpu_durations(s)
    assert len(win)>=200 and baseline>0
    assert read(SRC.parent/"completed.json")["status"]=="wall_budget"
    assert read(SRC.parent/"stage_result.json")["exit_code"]==0
    assert read(W/"zero_start_matrix_R2_coarse_continuation_20261031_2"/"controller_error.json")["error_type"]=="RuntimeError"
    macro=W/"AuditSavedWaveBindingReadOnly_20261031.java"
    assert macro.is_file() and (W/"resume_coarse_r2_compilecheck_20261031"/"compiled"/"macro"/"AuditSavedWaveBindingReadOnly_20261031.class").exists()
    own=[]
    try:
        for l in LOCKS:
            with l.open("x",encoding="utf8") as f:json.dump({"pid":os.getpid(),"token":token,"kind":"audit_read_only_saved_nofoil_wave","at":now().isoformat()},f)
            own.append(l)
        ROOT.mkdir()
        input=ROOT/"input.sim";shutil.copy2(SRC,input)
        assert sha(input)==sha(SRC)
        localMacro=ROOT/macro.name;shutil.copy2(macro,localMacro)
        write(ROOT/"audit_plan.json",{"at":now().isoformat(),"source_sha256":sha(SRC),"model":"wave-only no foil","source_physical_s":2.507,"M11":str(s),"steps_requested":0,"source_preserved":True,"CPU_workers":2,"GPU":False})
        with (ROOT/"star.log").open("x",encoding="utf8") as log:
            cmd=[str(guard.STAR),*guard.saved_options(2),"-batch",str(localMacro),str(input)]
            p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf8",errors="replace",creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            write(ROOT/"process.json",{"pid":p.pid,"controller_pid":os.getpid(),"at":now().isoformat(),"read_only":True,"steps":0})
            def drain():
                for line in p.stdout:log.write(guard.redact(line));log.flush()
            th=threading.Thread(target=drain,daemon=True);th.start()
            began=time.monotonic()
            while p.poll() is None:
                if time.monotonic()-began>600:
                    write(ROOT/"audit_timeout.json",{"at":now().isoformat(),"reason":"Read-only audit did not finish within 10 min, needs manual review"})
                    break
                time.sleep(5)
            if p.poll() is not None:
                th.join(timeout=10)
                code=p.returncode
                log.flush()
                data=(ROOT/"star.log").read_text(encoding="utf8",errors="replace")
                write(ROOT/"audit_receipt.json",{"at":now().isoformat(),"exit_code":code,"source_unmodified":sha(SRC)==sha(input),"data":{"found_audit_complete":"AUDIT_COMPLETE_NO_STEPS_NO_SAVE" in data,"error_count":data.count(" error: "),"saved_t":2.507},"no_solver_steps":True})
    finally:
        for l in reversed(own):
            if ('p' not in locals() or p.poll() is not None) and read(l).get("token")==token:
                l.unlink()
if __name__=="__main__":run()
