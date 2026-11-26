from pathlib import Path
import subprocess,json,shutil
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
r2=W/"zero_start_matrix_R2_coarse_continuation_20261031_2"
audit=W/"audit_saved_wave_binding_20261031_r3"
log=(audit/"star.log").read_text(encoding="utf8",errors="replace")
receipt=json.loads((audit/"audit_receipt.json").read_text(encoding="utf8"))
assert receipt["exit_code"]==0 and receipt["source_unmodified"] and receipt["data"]["found_audit_complete"] and receipt["no_solver_steps"]
assert "AUDIT_REGION_FORCING_CLASS star.vof.FifthOrderVofWave" in log
assert "AUDIT_REGION_FORCING_NAME IndependentNoFoil_L20_H050_InletRamp 1" in log
assert "AUDIT_COMPLETE_NO_STEPS_NO_SAVE" in log
assert "Prior FifthOrder inlet wave binding not present" in (r2/"waves"/"L20_H500_coarse"/"star.log").read_text(encoding="utf8",errors="replace")
assert not (r2/"waves"/"L20_H500_coarse"/"history.csv").exists()
compile_dir=W/"resume_coarse_r3_compilecheck_20261031"
newmacro=compile_dir/"ContinueWaveOnlySavedR3.java"
assert not compile_dir.exists()
src=(W/"resume_coarse_r2_compilecheck_20261031"/"ContinueWaveOnlySavedR2.java").read_text(encoding="utf8")
a="public class ContinueWaveOnlySavedR2 extends StarMacro"
b="public class ContinueWaveOnlySavedR3 extends StarMacro"
assert src.count(a)==1;src=src.replace(a,b)
a='.equals("IndependentNoFoil_L20_H050_InletRamp"))'
b='.equals("IndependentNoFoil_L20_H050_InletRamp 1"))'
assert src.count(a)==1;src=src.replace(a,b)
compile_dir.mkdir();(compile_dir/"compiled").mkdir()
newmacro.write_text(src,encoding="utf8")
javac=Path(r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe")
classpath=r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
o=subprocess.run([str(javac),"-cp",classpath,"-d",str(compile_dir/"compiled"),str(newmacro)],capture_output=True,text=True,timeout=90)
assert o.returncode==0 and (compile_dir/"compiled"/"macro"/"ContinueWaveOnlySavedR3.class").is_file(),o.stdout+o.stderr
(compile_dir/"javac_receipt.json").write_text(json.dumps({"status":"compile_pass","source":"read_only_audited_object_name","source_unmodified":True},indent=2),encoding="utf8")
old=W/"resume_coarse_from_saved_20261031_r2.py"
dest=W/"resume_coarse_from_saved_20261031_r3.py"
assert not dest.exists()
s=old.read_text(encoding="utf8")
assert s.count('NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_2"')==1
s=s.replace('NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_2"','NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_3"')
i=s.index('    failed=W/"zero_start_matrix_R2_coarse_continuation_20261031_1"')
j=s.index('    assert shutil.disk_usage(',i)
s=s[:i]+'''    failed=W/"zero_start_matrix_R2_coarse_continuation_20261031_2"
    audit=W/"audit_saved_wave_binding_20261031_r3"
    assert read(failed/"controller_error.json").get("error_type")=="RuntimeError"
    assert "Prior FifthOrder inlet wave binding not present" in (failed/"waves"/"L20_H500_coarse"/"star.log").read_text(encoding="utf8",errors="replace")
    assert not (failed/"waves"/"L20_H500_coarse"/"history.csv").exists()
    assert read(audit/"audit_receipt.json")["data"]["found_audit_complete"] and read(audit/"audit_receipt.json")["source_unmodified"]
    assert "AUDIT_REGION_FORCING_NAME IndependentNoFoil_L20_H050_InletRamp 1" in (audit/"star.log").read_text(encoding="utf8",errors="replace")
    assert read(W/"zero_start_12_current.json").get("status")=="loading","Current wave campaign status changed"
'''+s[j:]
assert s.count('verified=W/"resume_coarse_r2_compilecheck_20261031"')==1
s=s.replace('verified=W/"resume_coarse_r2_compilecheck_20261031"','verified=W/"resume_coarse_r3_compilecheck_20261031"')
s=s.replace('assert source.exists() and (verified/"compiled"/"macro"/"ContinueWaveOnlySavedR2.class").is_file()',
'''assert source.exists() and (verified/"compiled"/"macro"/"ContinueWaveOnlySavedR3.class").is_file()''')
s=s.replace('source=verified/"ContinueWaveOnlySavedR2.java"','source=verified/"ContinueWaveOnlySavedR3.java"')
compile(s,str(dest),"exec")
dest.write_text(s,encoding="utf8")
print("R3_PREPARED_COMPILE_PASS",dest,"AUDITED_EXPECTED_OBJECT_NAME",True)
