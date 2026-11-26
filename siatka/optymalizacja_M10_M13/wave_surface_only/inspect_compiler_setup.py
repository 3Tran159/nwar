from pathlib import Path
import json,os,shutil
w=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
for p in w.glob("*.py"):
 try:
  for i,l in enumerate(p.read_text(encoding="utf8").splitlines()):
   if "javac" in l or "star.jar" in l or "javaexec" in l or "java -cp" in l:
    print(p.name,i+1,l.strip()[:230])
 except Exception:pass
for q in ("javac","java"):print("PATH",q,shutil.which(q))
for p in w.glob("compiled_wave_inlet_pilot_20261031/*"): print("COMPILED",p.name)
