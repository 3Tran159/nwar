"""Prepare fresh isolated R4 continuation from R3 scientific checkpoint. No STAR solve here."""
from pathlib import Path
import json,subprocess,hashlib
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
R3=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"
SRC=R3/"waves"/"L20_H500_coarse"
P=W/"resume_coarse_r4_compilecheck_20261031"
NEW=W/"resume_coarse_from_saved_20261031_r4.py"
assert not P.exists() and not NEW.exists()
done=json.loads((SRC/"completed.json").read_text(encoding="utf8"))
stage=json.loads((SRC/"stage_result.json").read_text(encoding="utf8"))
plan=json.loads((R3/"plan.json").read_text(encoding="utf8"))
assert done["status"]=="target_reached" and done["steps"]==2000 and abs(done["time_s"]-4.507)<1e-8
assert stage["exit_code"]==0 and stage["source_unchanged"] and stage["controller_reason"] is None
assert (SRC/"wave_pilot_final.sim").stat().st_size>20_000_000
assert plan["start_physical_s"]<done["time_s"] and plan["physical_dt_s"]==0.001
s=(SRC/"ContinueWaveOnlySavedR3.java").read_text(encoding="utf8")
assert s.count("public class ContinueWaveOnlySavedR3 extends StarMacro")==1
s=s.replace("public class ContinueWaveOnlySavedR3 extends StarMacro","public class ContinueWaveOnlySavedR4 extends StarMacro")
assert s.count('ManagedVofWave existing=')==1
assert s.count('.equals("IndependentNoFoil_L20_H050_InletRamp 1"))')==1
assert s.count('private final double t0=Double.parseDouble(System.getenv("NTNU_NOFOIL_SOURCE_T"))')==1
assert "s.getSolution().initializeSolution()" not in s and ".clearSolution()" not in s
P.mkdir();(P/"compiled").mkdir()
macro=P/"ContinueWaveOnlySavedR4.java"
macro.write_text(s,encoding="utf8")
javac=Path(r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe")
cp=r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
proc=subprocess.run([str(javac),"-cp",cp,"-d",str(P/"compiled"),str(macro)],capture_output=True,text=True,timeout=90)
assert proc.returncode==0 and (P/"compiled"/"macro"/"ContinueWaveOnlySavedR4.class").exists(),proc.stdout+proc.stderr
(P/"compile_receipt.json").write_text(json.dumps(dict(status="javac_pass",source_r3=str(SRC),source_unmodified=True)),encoding="utf8")
old=(W/"resume_coarse_from_saved_20261031_r3.py").read_text(encoding="utf8")
repl=[
('SOURCE=W/"zero_start_matrix_20261031_13h_R2"/"waves"/"L20_H500_coarse"',
 'SOURCE=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"/"waves"/"L20_H500_coarse"'),
('NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"',
 'NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_4"'),
('assert read(SOURCE/"completed.json").get("status")=="wall_budget", "Not safe bounded stop"',
 'assert read(SOURCE/"completed.json").get("status")=="target_reached", "R3 must have successfully saved"'),
('assert len(h)>=2000 and int(h[-1]["step"])==2107','assert len(h)>=2000 and int(h[-1]["step"])==2000'),
('assert 2.5<t<2.52 and abs(t-read(SOURCE/"completed.json")["time_s"])<1e-7',
 'assert 4.50<t<4.52 and abs(t-read(SOURCE/"completed.json")["time_s"])<1e-7'),
('verified=W/"resume_coarse_r3_compilecheck_20261031"',
 'verified=W/"resume_coarse_r4_compilecheck_20261031"'),
('source=verified/"ContinueWaveOnlySavedR3.java"',
 'source=verified/"ContinueWaveOnlySavedR4.java"'),
('(verified/"compiled"/"macro"/"ContinueWaveOnlySavedR3.class").is_file()',
 '(verified/"compiled"/"macro"/"ContinueWaveOnlySavedR4.class").is_file()')
]
for a,b in repl:
    assert old.count(a)==1,(a,old.count(a))
    old=old.replace(a,b)
start=old.index('    failed=W/"zero_start_matrix_R2_coarse_continuation_20261031_2"')
end=old.index('    assert shutil.disk_usage(',start)
old=old[:start]+'''    assert read(SOURCE/"completed.json")["steps"]==2000
    assert read(SOURCE/"stage_result.json")["controller_reason"] is None
    assert read(W/"zero_start_12_current.json").get("status")=="coarse_continuation_saved_for_review", "Another wave controller changed state"
    assert read(W/"zero_start_matrix_R2_coarse_continuation_20261031_3"/"controller_result.json").get("final_sim_exists") is True
    assert (SOURCE/"wave_pilot_final.sim").stat().st_size>20_000_000
'''+old[end:]
assert 'def guard_checks()' in old and 'perf.only_owned_main_star(main)' in old
compile(old,str(NEW),"exec")
NEW.write_text(old,encoding="utf8")
print("PREPARED_R4",str(NEW),"JAVAC_OK",True,"SOURCE_T",done["time_s"],"SOURCE_BYTES",(SRC/"wave_pilot_final.sim").stat().st_size)
