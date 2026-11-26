from pathlib import Path
import os,shutil,json
import build_m09_gci as b
out=b.OUT/'mapping_check_M09';out.mkdir()
source=b.R/'matched_endpoint_20261029/M09_SO_common_t2040_r1/final.sim'
before=b.sha(source);shutil.copy2(source,out/'input.sim');assert b.sha(out/'input.sim')==before
os.environ.update(NTNU_MAP_OUT=str(out),NTNU_MAP_MESH=str(b.Q/'M09/mesh.CGNS'),NTNU_MAP_CELLS='214908')
b.run_star(out/'input.sim',b.OUT/'MapM09Solution.java',out/'star.log',1800)
assert b.sha(source)==before
audit=b.read(out/'mapping_audit.json');print(json.dumps(audit,indent=2))
assert audit['pass'] and (out/'mapped.sim').exists()
