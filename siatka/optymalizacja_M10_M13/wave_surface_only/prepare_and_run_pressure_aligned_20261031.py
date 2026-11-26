"""One isolated H=0.5m no-foil numerical pilot. Only change vs failed CPU1 dt1ms:
matching top pressure-outlet hydrostatic field with wave model. Existing originals untouched.
This is an exploratory pressure/BC diagnostic, NEVER automatic propagation acceptance.
"""
from pathlib import Path
from datetime import datetime
import sys,os,json,uuid,shutil,subprocess,math
R=Path(r"E:\ntnu_mesh_optimization_20261030")
W=R/"wave_surface_only"
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
P=R/"parallel_cpu_20261031"
S=W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"/"calm_pilot_final.sim"
SOURCE_MACRO=W/"WaveFromOwnCalm_20261031.java"
PREP=W/"wave_pressure_aligned_prepared_20261031"
RUN=W/"WAVE_H050_pressure_aligned_CPU1_20261031_once"
OLD=W/"zero_start_matrix_evening_20261031_182305_689cb9"/"waves"/"L20_H500_baseline"
LOCKS=[P/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_mesh_comparison.lock"]
sys.path.insert(0,str(R))
import wave_halfstep_runtime_20261031 as rt
def read(p):return rt.read(p)
def prep():
    assert not PREP.exists() and not RUN.exists(),"Previous prepared/attempt exists"
    assert S.is_file() and S.stat().st_size>30000000
    assert SOURCE_MACRO.is_file() and SOURCE_MACRO.stat().st_size>14000
    text=SOURCE_MACRO.read_text(encoding="utf-8")
    assert "class WaveFromOwnCalm_20261031 extends StarMacro" in text
    line="   FifthOrderVofWave wave=createWave(wm);"
    assert text.count(line)==1
    addition="""   FifthOrderVofWave wave=createWave(wm);
   // Distinct test hypothesis: pressure outlet references hydrostatic pressure
   // belonging to the SAME FifthOrder wave as inlet U and VOF.
   Boundary topPressure=fluid.getBoundaryManager().getBoundary("DOMAIN.top");
   if(!topPressure.getBoundaryType().getPresentationName().toLowerCase(Locale.ROOT).contains("pressure"))
     throw new IllegalStateException("DOMAIN.top must be pressure outlet");
   FieldFunction waveHydrostatic=waveField(wave,"Hydrostatic Pressure of Heavy Fluid of ");
   StaticPressureProfile topProfile=topPressure.getValues().get(StaticPressureProfile.class);
   topProfile.setMethod(FunctionScalarProfileMethod.class);
   topProfile.getMethod(FunctionScalarProfileMethod.class).setFieldFunction(waveHydrostatic);
"""
    text=text.replace(line,addition).replace("WaveFromOwnCalm_20261031","WaveFromOwnCalmPressureAligned")
    assert text.count("topProfile.setMethod")==1
    assert "s.getSolution().initializeSolution()" not in text and "clearSolution()" not in text
    PREP.mkdir(exist_ok=False)
    (PREP/"compiled").mkdir()
    java=PREP/"WaveFromOwnCalmPressureAligned.java"
    java.write_text(text,encoding="utf-8")
    javac=Path(r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe")
    cp=r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
    q=subprocess.run([str(javac),"-cp",cp,"-d",str(PREP/"compiled"),str(java)],capture_output=True,text=True,timeout=90)
    receipt={"at":rt.now(),"status":"javac_pass" if q.returncode==0 else "compile_failed","original_macro_sha256":rt.sha(SOURCE_MACRO),"prepared_macro_sha256":rt.sha(java),"change":"only DOMAIN.top PressureProfile matches wave heavy-fluid hydrostatic pressure; rest same","err":q.stderr[-900:],"no_solver_launched":True}
    rt.write(PREP/"compile_receipt.json",receipt)
    if q.returncode!=0:raise RuntimeError("Java macro failed compilation: "+q.stderr[-900:])
    assert (PREP/"compiled"/"macro"/"WaveFromOwnCalmPressureAligned.class").is_file()
    return java
def guard_test():
    now=datetime.now().astimezone()
    assert now<datetime.fromisoformat("2026-11-01T09:00:00+01:00"),"Night permission ended"
    pl=read(R/"plan.json")
    assert rt.sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==pl["recovery_policy"]["runbook_sha256"]
    assert read(F/"campaign_hold.json").get("active") is True,"Held foil-wave changed"
    assert rt.resource_problem() is None,rt.resource_problem()
    assert not any(x.exists() for x in [*LOCKS,W/"wave_pressure_audit.lock"]),"Another STAR audit/solver owns resources"
    assert not RUN.exists(),"One-shot never duplicate"
    assert read(W/"wave_pressure_readonly_20261031"/"completed.json").get("status")=="read_only_finished","Pressure audit not yet completed"
    cal=read(W/"wave_pressure_readonly_20261031"/"flat_calm_53200"/"receipt.json")
    assert cal.get("exit_code")==0 and cal.get("observed_complete") and cal.get("source_hash_unchanged")
    pmin=float(cal["results"]["PRESSURE_AUDIT_P_MIN"]);pmax=float(cal["results"]["PRESSURE_AUDIT_P_MAX"])
    assert math.isfinite(pmin) and math.isfinite(pmax) and -1000<pmin<1000 and 100000<pmax<300000,"Calm pressure not healthy"
    done=read(S.parent/"completed.json")
    assert done.get("steps")==400 and abs(float(done["time_s"])-.4)<1e-8,"Calm checkpoint mismatch"
    assert rt.sha(S)==read(OLD/"identity.json").get("source_sha256"),"Not same failure family source"
    assert read(OLD/"stage_result.json").get("exit_code")==1,"Old failed baseline unexpected"
    assert not any(name.lower().startswith("starccm") and not name.lower().startswith("starccmw") for _,name in rt.guard.processes().values()),"Other STAR active"
    return rt.sha(S)
def main():
    if "--preflight-only" in sys.argv:
        digest=guard_test()
        print(json.dumps({"status":"SAFE_TO_START","source_sha256":digest,"at":rt.now(),"no_solver_launched":True}),flush=True)
        return
    if "--prepare-only" in sys.argv:
        macro=prep()
        print(json.dumps({"status":"COMPILED_PREPARED","path":str(macro),"no_solver_started":True}),flush=True)
        return
    source_hash=guard_test()
    macro=PREP/"WaveFromOwnCalmPressureAligned.java"
    assert read(PREP/"compile_receipt_r2.json").get("status")=="javac_pass"
    assert not RUN.exists()
    token=uuid.uuid4().hex
    captured=[]
    try:
        for path in LOCKS:
            with path.open("x",encoding="utf-8") as f:
                json.dump({"pid":os.getpid(),"token":token,"at":rt.now(),"kind":"one_off_pressure_aligned_wave_test","directory":str(RUN)},f)
            captured.append(path)
        RUN.mkdir(exist_ok=False)
        rt.write(RUN/"decision.json",{"at":rt.now(),"purpose":"single H0.5, lambda20, 1ms no-foil wave startup test","one_numerical_change":"matching top pressure outlet wave hydrostatic pressure","hypothesis":"calm-wave pressure BC mismatch causes initial residual shock","source_sha256":source_hash,"source":str(S),"macro_sha256":rt.sha(macro),"mesh_cells":53200,"CPU":1,"GPU":0,"dt_s":.001,"inner":10,"steps":500,"max_wall_s":1600,"no_automatic_retry":True,"scientifically_validated":False,"foil_wave_hold_preserved":True})
        env={"NTNU_NOFOIL_WAVE_OUT":str(RUN),"NTNU_NOFOIL_OUT":str(RUN),"NTNU_NOFOIL_CELLS":"53200","NTNU_NOFOIL_WATER_M3":"38.4","NTNU_NOFOIL_LAMBDA":"20","NTNU_NOFOIL_H":".5","NTNU_NOFOIL_XMIN":"-35","NTNU_NOFOIL_XMAX":"45","NTNU_NOFOIL_WAVE_PERIOD_S":str(20/23.612),"NTNU_NOFOIL_WAVE_STEPS":"500"}
        rt.write(W/"pressure_aligned_wave_state.json",{"status":"starting","at":rt.now(),"directory":str(RUN),"controller_pid":os.getpid()})
        folder,stage=rt.stage(RUN,S,macro,env=env,workers=1,gpu=False,mask=1<<22,budget_s=1600,protect_main=False,phase="nofoil_pressure_aligned_H050_single_pilot")
        h=rt.rows(RUN/"history.csv")
        done=rt.read(RUN/"completed.json")
        enough=bool(stage["exit_code"]==0 and stage["controller_reason"] is None and stage["source_unchanged"] and done.get("steps")==500 and done.get("status")=="target_reached" and (RUN/"wave_pilot_final.sim").is_file())
        metrics={"confirmed_500_steps":enough,"full_wave_propagation_validated":False,"step_count":len(h)-1,"last_h":h[-1] if h else None,"receipt":done,"source_preserved":rt.sha(S)==source_hash,"at":rt.now()}
        rt.write(RUN/"pilot_result.json",metrics)
        rt.write(W/"pressure_aligned_wave_state.json",{"status":"saved_diagnostic_no_scientific_acceptance" if enough else "incomplete","at":rt.now(),"directory":str(RUN),"passes_steps":enough})
        print(json.dumps({"event":"pressure_matched_test_end","steps":done.get("steps"),"t":done.get("time_s"),"passed_bounded":enough,"no_scientific_acceptance":True}),flush=True)
    except BaseException as err:
        if RUN.exists():
            (RUN/"STOP").touch()
            rt.write(RUN/"controller_error.json",{"time":rt.now(),"error_type":type(err).__name__,"message":rt.guard.redact(str(err))[:700]})
            rt.write(W/"pressure_aligned_wave_state.json",{"status":"failed_no_retry","at":rt.now(),"directory":str(RUN)})
        raise
    finally:
        starid=rt.read(RUN/"process.json").get("pid") if RUN.exists() else None
        ended=not starid or not rt.guard.alive(starid)
        for path in reversed(captured):
            if ended and read(path).get("token")==token:path.unlink()
if __name__=="__main__":main()
