from pathlib import Path
import json, shutil
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
first=W/"zero_start_matrix_R2_coarse_continuation_20261031_1"
old=first/"waves"/"L20_H500_coarse"
log=(old/"star.log").read_text(encoding="utf8",errors="replace")
assert "ManagedVofWave cannot be converted to star.vof.VofWave" in log
assert not (old/"history.csv").exists(), "Source already advanced; no duplicate allowed"
err=json.loads((first/"controller_error.json").read_text(encoding="utf8"))
assert err["error_type"]=="RuntimeError"
src=first/"ContinueWaveOnlySavedR2.java"
s=src.read_text(encoding="utf8")
oldline="VofWave existing=fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();"
newline="ManagedVofWave existing=fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();"
assert s.count(oldline)==1
s=s.replace(oldline,newline)
out=W/"resume_coarse_r2_compilecheck_20261031"
assert not out.exists(), "Compilecheck already prepared"
out.mkdir()
(out/"ContinueWaveOnlySavedR2.java").write_text(s,encoding="utf8")
(out/"compiled").mkdir()
print("NEW_MACRO",str(out/"ContinueWaveOnlySavedR2.java"),"old_source_unchanged",True)
