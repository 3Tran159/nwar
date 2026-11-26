from pathlib import Path
import csv,json,urllib.request,os,sys,subprocess
R=Path(r"E:\ntnu_mesh_optimization_20261030")
def j(p):
 try:return json.loads(Path(p).read_text(encoding="utf8-sig"))
 except: return {}
s=j(R/"mesh_queue_state.json");d=Path(s.get("directory",""))
print("QUEUE",json.dumps(s,ensure_ascii=False))
for k in ("star.log","progress.json","history.csv","setup.json","completed.json","exit.json"):
 p=d/k
 if not p.is_file():print(k,"MISSING");continue
 if k=="history.csv":
  with p.open(encoding="utf8-sig",newline="") as f:
   rd=csv.DictReader(f);rows=list(rd)
  print(k,"rows",len(rows),"last",{key:rows[-1][key] for key in ("step","physical_time_s","max_CFL","interface_max_CFL","wall_seconds") if rows and key in rows[-1]} if rows else None)
 elif k=="star.log":
  print(k,"bytes",p.stat().st_size,"tail",p.read_text(encoding="utf8",errors="replace").splitlines()[-4:])
 else:print(k,p.stat().st_size,j(p))
r=urllib.request.Request("http://127.0.0.1:8772/api/mesh-queue",headers={"Origin":"http://127.0.0.1:8771"})
try:
 x=json.load(urllib.request.urlopen(r,timeout=5));x.pop("csrf",None);print("NEW_API",json.dumps(x,ensure_ascii=False))
except Exception as e:print("NEW_API_ERR",str(e))
html=urllib.request.urlopen("http://127.0.0.1:8771/",timeout=7).read().decode("utf8",errors="replace")
print("UI_QUEUE_BUTTON", "Resume queue (M11" in html,"UI_NEWSERVICE", "127.0.0.1:8772" in html)
print("OLD_M12",j(Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030\force_stabilization_20261029\calm_settle_G10_F_GPU_live_r2_resume_20261030_173420_4854e1\completed.json")))
