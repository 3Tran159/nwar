from pathlib import Path
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
old=W/"resume_coarse_from_saved_20261031.py"
new=W/"resume_coarse_from_saved_20261031_r2.py"
assert not new.exists()
s=old.read_text(encoding="utf8")
a='NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_1"'
b='NEW=W/"zero_start_matrix_R2_coarse_continuation_20261031_2"'
assert s.count(a)==1;s=s.replace(a,b)
a='assert read(W/"zero_start_12_current.json").get("status")=="blocked_no_auto_retry","Current campaign owner changed"'
b='''failed=W/"zero_start_matrix_R2_coarse_continuation_20261031_1"
    assert read(failed/"controller_error.json").get("error_type")=="RuntimeError"
    assert "ManagedVofWave cannot be converted to star.vof.VofWave" in (failed/"waves"/"L20_H500_coarse"/"star.log").read_text(encoding="utf8",errors="replace")
    assert not (failed/"waves"/"L20_H500_coarse"/"history.csv").exists()
    assert read(W/"zero_start_12_current.json").get("status")=="loading","Current wave campaign status changed"'''
assert s.count(a)==1;s=s.replace(a,b)
i=s.index("def build_macro(out):")
j=s.index("def main():",i)
s=s[:i]+'''def build_macro(out):
    verified=W/"resume_coarse_r2_compilecheck_20261031"
    source=verified/"ContinueWaveOnlySavedR2.java"
    assert source.exists() and (verified/"compiled"/"macro"/"ContinueWaveOnlySavedR2.class").is_file()
    macro=out/source.name
    shutil.copy2(source,macro)
    assert sha(macro)==sha(source)
    return macro
'''+s[j:]
compile(s,str(new),"exec")
new.write_text(s,encoding="utf8")
print("PREPARED",new,"preserved_first_failure",True)
