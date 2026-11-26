"""Install read-only Wave Mesh Lab into existing mobile CFD dashboard bridge.

Guards: exact source fingerprint, independent collector sanity, Python and JS
syntax checks, backup and atomic replacement. Does not control STAR solvers.
"""
from pathlib import Path
from datetime import datetime
import importlib.util,hashlib,json,os,shutil,subprocess,sys,uuid
D=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard")
STAGE=Path(r"E:\ntnu_mesh_optimization_20261030\wave_mesh_dashboard")
STAGE.mkdir(parents=True,exist_ok=True)
BRIDGE=D/"local_mesh_dashboard.py"
OLD_SHA="5b83b77c0e4891e5c8c5c8cb8040d4f2e7a4ff7c100a84947715079e7daae9ac"
COL=D/"wave_mesh_live.py"
JS=D/"wave_mesh_panel.js"
CSS=D/"wave_mesh_panel.css"
for p in (BRIDGE,COL,JS,CSS):assert p.is_file() and p.stat().st_size>150
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=BRIDGE.read_bytes()
assert digest(BRIDGE)==OLD_SHA,"Dashboard bridge has changed: do not overwrite concurrently"
old=before.decode("utf-8")
def one(a,b):
 global old
 if old.count(a)!=1:raise RuntimeError("Expected single bridge anchor: "+a[:130])
 old=old.replace(a,b,1)
one("import mesh_gci_activity,mesh_development_activity,uploader",
    "import mesh_gci_activity,mesh_development_activity,uploader,wave_mesh_live")
one("importlib.reload(mesh_gci_activity);importlib.reload(mesh_development_activity)",
    "importlib.reload(mesh_gci_activity);importlib.reload(mesh_development_activity);importlib.reload(wave_mesh_live)")
one("mesh_live_focus_v4.enrich(g, mesh_gci_activity.STUDY)",
    "mesh_live_focus_v4.enrich(g, mesh_gci_activity.STUDY)\n        wm=wave_mesh_live.collect()")
one("activity=dict(mesh_gci=g,mesh_development=dev)",
    "activity=dict(mesh_gci=g,mesh_development=dev,wave_mesh_tests=wm)")
one("css += (HERE/'mesh_live_focus_v4.css').read_text(encoding='utf-8')",
    "css += (HERE/'mesh_live_focus_v4.css').read_text(encoding='utf-8')\n    css += (HERE/'wave_mesh_panel.css').read_text(encoding='utf-8')")
one("code += '\\n' + (HERE/'mesh_live_focus_v4.js').read_text(encoding='utf-8')",
    "code += '\\n' + (HERE/'mesh_live_focus_v4.js').read_text(encoding='utf-8')\n    code += '\\n' + (HERE/'wave_mesh_panel.js').read_text(encoding='utf-8')")
one("updateWindowClocks(cached,Math.max(0,(Date.now()-Date.parse(cached.sampled_at))/1000),online);requestAnimationFrame(sendHeight)",
    "updateWindowClocks(cached,Math.max(0,(Date.now()-Date.parse(cached.sampled_at))/1000),online);renderWaveMesh(cached,online);requestAnimationFrame(sendHeight)")
one('<section id="mesh-gci" class="gci-panel hidden"></section></div>',
    '<section id="mesh-gci" class="gci-panel hidden"></section><section id="wave-mesh-tests" aria-label="Wave mesh experiment progress"></section></div>')
one('title="Mesh development and live convergence M02 to M12"',
    'title="Mesh development, live convergence and free-surface mesh tests"')
compile(old,str(BRIDGE),"exec")
sys.path.insert(0,str(D))
import wave_mesh_live as w
data=w.collect()
assert data["ready"] and data["audited_mesh_count"]==9 and len(data["cases"])==21
assert data["attempted_case_count"]>=1
assert data["latest"]["status"] in ("guard","calm_pilot_done","calm_running","loading","wave_running","wave_verified"),data["latest"]
json.dumps(data,allow_nan=False)
node=Path(r"F:\Program Files\nodejs\node.exe")
assert node.is_file()
jschk=subprocess.run([str(node),"--check",str(JS)],capture_output=True,text=True,timeout=20)
if jschk.returncode:raise RuntimeError("Wave UI JS syntax error: "+jschk.stderr[-1200:])
# Check this candidate bridge and exact assets in staging before activating.
candidate=STAGE/"candidate_local_mesh_dashboard.py"
candidate.write_text(old,encoding="utf-8")
compile(candidate.read_text(encoding="utf-8"),str(candidate),"exec")
backdir=STAGE/("backup_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
backdir.mkdir(exist_ok=False)
shutil.copy2(BRIDGE,backdir/BRIDGE.name)
manifest={"at":datetime.now().astimezone().isoformat(),
 "baseline_bridge_sha256":OLD_SHA,"backup":str(backdir/BRIDGE.name),
 "assets":{p.name:digest(p) for p in (COL,JS,CSS)},
 "collector_smoke":{"wave_mesh_cases":len(data["cases"]),"audited_meshes":data["audited_mesh_count"],"latest_status":data["latest"]["status"]},
 "changes":"read-only wave mesh progress table with automatic snapshot refresh",
 "solver_touched":False}
assert digest(BRIDGE)==OLD_SHA,"Bridge changed after validation"
tmp=BRIDGE.with_name(BRIDGE.name+"."+uuid.uuid4().hex+".tmp")
tmp.write_text(old,encoding="utf-8")
os.replace(tmp,BRIDGE)
manifest["installed_bridge_sha256"]=digest(BRIDGE)
(STAGE/"installation.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps({"installed":True,"backup":str(backdir),"bridge_hash":manifest["installed_bridge_sha256"],"cases":len(data["cases"]),"audited":data["audited_mesh_count"],"attempted":data["attempted_case_count"],"latest":data["latest"]["status"],"solver_touched":False},ensure_ascii=False))
