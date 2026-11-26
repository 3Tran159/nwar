from pathlib import Path
import re,json
root=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
keywords=("can_resume","mesh-study/resume","mesh-study","mesh_study_control","Resume")
files=[]
for path in root.glob("*"):
 if path.is_file() and path.suffix.lower() in (".py",".html",".js") and path.stat().st_size<5_000_000:
  try:
   s=path.read_text(encoding="utf-8-sig")
   hits=[(i+1,line.strip()[:220]) for i,line in enumerate(s.splitlines()) if any(w in line for w in keywords)]
   if hits:files.append(dict(path=str(path),hits=hits[:15]))
  except Exception:pass
print(json.dumps(files[:55],indent=2,ensure_ascii=False))
