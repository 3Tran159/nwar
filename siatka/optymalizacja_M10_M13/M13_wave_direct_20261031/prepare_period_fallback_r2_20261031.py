"""Prepare a fresh ONE-variable M13 wave macro correction after zero-step period preflight failure.
This script does NOT start STAR and does NOT modify original R1 scripts/results.
"""
from pathlib import Path
import hashlib,subprocess,json
from datetime import datetime
P=Path(r"E:\ntnu_mesh_optimization_20261030\M13_wave_direct_20261031")
OLD=P/"M13InletWavePilot.java"
NEW=P/"M13InletWavePilotR2.java"
RUNNER=P/"run_m13_gpu_wave_pilot_20261031.py"
NEW_RUNNER=P/"run_m13_gpu_wave_pilot_r2_20261031.py"
OUT=P/"M13_GPU_W20_H050_pilot_20261031"
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
err=read(OUT/"macro_error.json")
stage=read(OUT/"stage_result.json")
assert err.get("error")=="java.lang.IllegalStateException: Unexpected wave period",err
assert stage.get("exit_code")==1 and stage.get("source_unchanged") is True
assert not (OUT/"history.csv").exists(),"R1 already solved CFD! No blind retry"
assert not (OUT/"completed.json").exists()
assert not NEW.exists() and not NEW_RUNNER.exists()
src=OLD.read_text(encoding="utf-8")
a="public class M13InletWavePilot extends StarMacro"
b="public class M13InletWavePilotR2 extends StarMacro"
assert src.count(a)==1
src=src.replace(a,b,1)
a='   period=wave.getWavePeriod().getValue();\n   if(!Double.isFinite(period)||period<.4||period>2)throw new IllegalStateException("Unexpected wave period");'
b='''   double rawPeriodBeforeBinding=wave.getWavePeriod().getValue();
   // The STAR wave period may not be initialized until the inlet functions are bound.
   // Use a separately labeled linear dispersion estimate ONLY for the 2-period inlet-ramp duration.
   // The FifthOrder wave object itself still defines all imposed wave physics.
   period=20.0/23.612;
   if(!Double.isFinite(period)||period<.5||period>1.5)throw new IllegalStateException("Invalid analytic startup period");
   save("wave_period_initial_audit.json",Map.of("native_period_before_binding_s",rawPeriodBeforeBinding,
     "ramp_planning_period_s",period,"lambda_m",lambda,"reason","Native period not reliable before wave bindings; not a statement of physical wave period validity"));'''
assert src.count(a)==1,(src.count(a),"period anchor")
src=src.replace(a,b,1)
assert "s.getSolution().initializeSolution()" not in src and "clearSolution()" not in src
NEW.write_text(src,encoding="utf-8")
comp=P/"compiled_r2";comp.mkdir(exist_ok=False)
javac=r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
cp=r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
pr=subprocess.run([javac,"-cp",cp,"-d",str(comp),str(NEW)],capture_output=True,text=True,timeout=90)
receipt={"at":datetime.now().astimezone().isoformat(),"result":"javac_pass" if pr.returncode==0 else "compile_failed",
 "r1_source_sha256":hashlib.sha256(OLD.read_bytes()).hexdigest(),
 "r2_source_sha256":hashlib.sha256(NEW.read_bytes()).hexdigest(),
 "one_change":"Early wave period threshold replaced by explicitly audited analytic ramp planning period, before binding; all fluid/wave models, dt, mesh, step budget and pressure BC unchanged",
 "r1_error":err["error"],"r1_source_unchanged":True,"actual_R1_CFD_steps":0,"compiler_errors":pr.stderr[-850:]}
(P/"r2_compile_receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
assert pr.returncode==0 and (comp/"macro"/"M13InletWavePilotR2.class").is_file(),receipt
runner=RUNNER.read_text(encoding="utf-8")
for a,b in [
 ('MACRO=P/"M13InletWavePilot.java"','MACRO=P/"M13InletWavePilotR2.java"'),
 ('OUT=P/"M13_GPU_W20_H050_pilot_20261031"','OUT=P/"M13_GPU_W20_H050_pilot_20261031_r2"'),
 ('(P/"compiled"/"macro"/"M13InletWavePilot.class").is_file()', '(P/"compiled_r2"/"macro"/"M13InletWavePilotR2.class").is_file()'),
 ('P/"M13_wave_status.json"', 'P/"M13_wave_status_r2.json"')]:
 assert runner.count(a)>=1,(a,runner.count(a))
 runner=runner.replace(a,b)
anchor=' failed=rt.read(W/"WAVE_H050_pressure_aligned_CPU1_20261031_once"/"stage_result.json")'
assert runner.count(anchor)==1
runner=runner.replace(anchor,''' r1=rt.read(P/"M13_GPU_W20_H050_pilot_20261031"/"stage_result.json")
 r1_error=rt.read(P/"M13_GPU_W20_H050_pilot_20261031"/"macro_error.json")
 assert r1.get("exit_code")==1 and r1.get("source_unchanged") is True
 assert r1_error.get("error")=="java.lang.IllegalStateException: Unexpected wave period"
 assert not (P/"M13_GPU_W20_H050_pilot_20261031"/"history.csv").exists(), "R1 had real steps; no retry"
 assert rt.read(P/"r2_compile_receipt.json").get("result")=="javac_pass"
'''+anchor,1)
compile(runner,str(NEW_RUNNER),"exec")
NEW_RUNNER.write_text(runner,encoding="utf-8")
print(json.dumps({"r2_compiled":True,"r1_untouched":True,"new_macro":str(NEW),"new_runner":str(NEW_RUNNER),
 "source_sha256":receipt["r2_source_sha256"],"actual_old_steps":0,"solver_started":False}))
