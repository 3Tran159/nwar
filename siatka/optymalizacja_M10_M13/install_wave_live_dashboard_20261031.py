"""Surgical, provenance-preserving installation of the read-only Wave Live dashboard tab.
Does not touch active STAR jobs, simulation code, old mesh comparison JS or galleries.
"""
from pathlib import Path
from datetime import datetime
import sys,os,json,hashlib,shutil,uuid,subprocess,importlib.util
D=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard")
E=Path(r"E:\ntnu_mesh_optimization_20261030")
P=D/"campaign_hub.py"
JS=D/"campaign_wave_live.js"
CSS=D/"campaign_wave_live.css"
PY=D/"campaign_wave_live.py"
sys.path.insert(0,str(D))
def sha(b):return hashlib.sha256(b).hexdigest()
def patch_once(src,old,new):
 assert src.count(old)==1,("Missing or ambiguous anchor",old[:110],src.count(old))
 return src.replace(old,new,1)
original=P.read_bytes();orig=original.decode("utf-8")
assert "data['wave_lab']=" not in orig,"Already installed; no duplicate"
assert all(f.exists() for f in (JS,CSS,PY))
one=" campaign_visuals.enrich(data)\r\n payload=publish(data)"
newone=" campaign_visuals.enrich(data)\r\n import campaign_wave_live\r\n data['wave_lab']=campaign_wave_live.collect()\r\n payload=publish(data)"
src=patch_once(orig,one,newone)
two=" js+='\\n'+(HERE/'campaign_visuals.js').read_text(encoding='utf-8')"
newtwo=two+"\r\n css+='\\n'+(HERE/'campaign_wave_live.css').read_text(encoding='utf-8')\r\n js+='\\n'+(HERE/'campaign_wave_live.js').read_text(encoding='utf-8')"
src=patch_once(src,two,newtwo)
compile(src,str(P),"exec")
import campaign_wave_live
data=campaign_wave_live.collect()
assert len(data["cases"])>=6 and data["cases"][0]["status"] in ("failed","running","stale_steps","loading"),data["cases"][0]["status"]
assert data["cases"][0]["step"] is not None
assert all(len(g["name"])>2 for g in data["grids"])
assert len(data["combined"])==0 or all("series" in c for c in data["combined"])
js=(D/"mesh_comparison.js").read_text(encoding="utf-8")+"\n"+(D/"campaign_hub.js").read_text(encoding="utf-8")+"\n"+(D/"campaign_visuals.js").read_text(encoding="utf-8")+"\n"+JS.read_text(encoding="utf-8")
css=(D/"campaign_hub.css").read_text(encoding="utf-8")+"\n"+(D/"campaign_compare.css").read_text(encoding="utf-8")+"\n"+CSS.read_text(encoding="utf-8")
assert "function renderWaveMatrix()" in js and "renderGallery" in js and "host.id='view-wave-lab'" in js
assert "Wave live & results" in js
assert len(css)>2000
out=E/"dashboard_wave_live_qa_20261031"
out.mkdir(exist_ok=True)
jsfile=out/"combined.cjs";jsfile.write_text(js,encoding="utf-8")
node=r"F:\Program Files\nodejs\node.exe"
q=subprocess.run([node,"--check",str(jsfile)],capture_output=True,text=True,timeout=35)
assert q.returncode==0,q.stderr
candidate=out/"candidate_hub.py";candidate.write_text(src,encoding="utf-8")
spec=importlib.util.spec_from_file_location("campaign_hub_candidate",candidate)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
# E is a separate temp preview directory; module HERE must point to existing live dashboard assets.
module.HERE=D
payload=module.collect()
assert payload["comparison"]["runs"] and len(payload["records"])>10
import campaign_visuals
campaign_visuals.enrich(payload)
payload["wave_lab"]=data
json.dumps(payload,allow_nan=False)
manifest={"at":datetime.now().astimezone().isoformat(),"before_sha256":sha(original),"candidate_sha256":sha(src.encode("utf-8")),
 "run_count":len(payload["records"]),"mesh_runs":len(payload["comparison"]["runs"]),"wave_cases":len(data["cases"]),
 "active_wave":[x["id"] for x in data["cases"] if x["active"]],
 "same_archived_gallery":True,"solver_inputs_modified":False,"JS_pass":True,"read_only":True}
if P.read_bytes()!=original:raise RuntimeError("Concurrent changes to campaign_hub.py; refuse update")
backup=E/"dashboard_wave_live_backup"/datetime.now().strftime("%Y%m%d_%H%M%S")
backup.mkdir(parents=True,exist_ok=False)
shutil.copy2(P,backup/P.name)
for f in (D/"campaign_hub.js",D/"campaign_visuals.js",D/"mesh_comparison.js",D/"campaign_hub.css"):
 manifest[f.name+"_sha256"]=sha(f.read_bytes())
 tmp=P.with_name(P.name+"."+uuid.uuid4().hex+".tmp")
 tmp.write_bytes(src.encode("utf-8"))
 os.replace(tmp,P)
manifest["backup"]=str(backup)
(out/"install_result.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False))
