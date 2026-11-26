"""Read-only updater bounded to the currently authorized CFD comparison; no solver actions."""
from pathlib import Path
import time,datetime,subprocess,os,sys,json
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
R=W/"wave_mesh_triplet_20261031_r2"
LOCK=W/"wave_mesh_comparison.lock"
SCRIPT=W/"render_wave_triplet_comparison_r2.py"
def stamp():return datetime.datetime.now().astimezone().isoformat()
deadline=time.monotonic()+4*3600
while time.monotonic()<deadline:
 p=subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
 with (R/"view_refresh.log").open("a",encoding="utf8") as f:f.write(stamp()+" "+("OK" if p.returncode==0 else "VIEW_ERROR")+"\n")
 if not LOCK.exists():break
 time.sleep(60)
# One final refresh, even if original controller stopped.
subprocess.run([sys.executable,str(SCRIPT)],capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
