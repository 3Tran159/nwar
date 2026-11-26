import os,shutil,json
from pathlib import Path
import build_w01_gci as b
out=b.OUT/'mapping_precheck_G10M';out.mkdir()
source=Path(r'E:\ntnu\quasi2d_waves_20261029\W01a_W20L4_M10_calm_start_r1\checkpoint_startup_t0.020.sim')
before=b.sha(source);shutil.copy2(source,out/'input.sim');assert b.sha(out/'input.sim')==before
os.environ.update(NTNU_MAP_OUT=str(out),NTNU_MAP_MESH=str(b.OUT/'G10_M_raw/mesh_exact.CGNS'),NTNU_MAP_CELLS='595285',NTNU_MAP_EXPECTED_START='.02')
b.run_star(out/'input.sim',b.OUT/'MapW01Solution.java',out/'star.log',2400)
assert b.sha(source)==before
audit=b.read(out/'mapping_audit.json')
print(json.dumps(audit,indent=2),flush=True)
assert audit['pass'] and (out/'mapped.sim').exists()
