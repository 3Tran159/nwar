from pathlib import Path
import json,datetime
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
R=W.parent
prior=W/"wave_mesh_triplet_20261031"/"map_coarse"
s=(prior/"star.log").read_text(encoding="utf8",errors="replace")
assert "variable expected is already defined in method execute()" in s
assert (prior/"stage_result.json").is_file() and json.loads((prior/"stage_result.json").read_text())["exit_code"]==1
for lock in (R/"parallel_cpu_20261031"/"auxiliary.lock",W/"wave_inlet.lock",W/"wave_mesh_comparison.lock"):
 assert not lock.exists(),str(lock)
src=(W/"NoFoilFlatMeshMapper.java").read_text(encoding="utf8")
assert src.count("Path expected=")==1 and src.count("long expected=")==1
s=src.replace("public class NoFoilFlatMeshMapper extends StarMacro","public class NoFoilFlatMeshMapperR2 extends StarMacro")
s=s.replace("Path expected=out.resolve","Path expectedSource=out.resolve")
s=s.replace(".equals(expected))",".equals(expectedSource))")
assert "long expected=" in s and "Path expected=" not in s
macro=W/"NoFoilFlatMeshMapperR2.java"
assert not macro.exists();macro.write_text(s,encoding="utf8")
original=(W/"run_wave_mesh_triplet_cpu2_20261031.py").read_text(encoding="utf8")
assert original.count('BASE=W/"wave_mesh_triplet_20261031"')==1
run=original.replace('BASE=W/"wave_mesh_triplet_20261031"','BASE=W/"wave_mesh_triplet_20261031_r2"')
assert run.count('W/"NoFoilFlatMeshMapper.java"')==1
run=run.replace('W/"NoFoilFlatMeshMapper.java"','W/"NoFoilFlatMeshMapperR2.java"')
assert run.count('"NoFoilFlatMeshMapper.java"')==1
run=run.replace('"NoFoilFlatMeshMapper.java"','"NoFoilFlatMeshMapperR2.java"')
assert run.count('assert read(PAR/"current.json").get("status")=="completed_diagnostic"')==1
run=run.replace('assert read(PAR/"current.json").get("status")=="completed_diagnostic"',
'''previous=read(PAR/"current.json")
 assert previous.get("status")=="wave_mesh_triplet_needs_review" and previous.get("reason")=="Stage failure map_coarse exit=1"
 assert not (W/"wave_mesh_triplet_20261031"/"map_coarse"/"mapped.sim").exists()
 assert "variable expected is already defined" in (W/"wave_mesh_triplet_20261031"/"map_coarse"/"star.log").read_text(encoding="utf8",errors="replace")''')
dest=W/"run_wave_mesh_triplet_cpu2_r2_20261031.py"
assert not dest.exists();compile(run,str(dest),"exec");dest.write_text(run,encoding="utf8")
with (R/"decisions.jsonl").open("a",encoding="utf8") as f:f.write(json.dumps(dict(at=datetime.datetime.now().astimezone().isoformat(),event="wave_mesh_triplet_R2_one_time_compile_correction",prior_attempt=str(prior),diagnosis="Duplicate Java expected variable shadowing path and cell count in disposable mapper. STAR returned compile failure, zero CFD steps. Original input untouched.",change="Only rename path expected variable in new macro; distinct BASE and controller copy; no active solver modified",no_blind_retries=True),ensure_ascii=False)+"\n")
print("CREATED",macro,dest)
