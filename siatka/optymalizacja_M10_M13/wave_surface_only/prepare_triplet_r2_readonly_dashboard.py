from pathlib import Path
w=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
base=(w/"render_wave_triplet_comparison.py").read_text(encoding="utf8")
assert base.count('R=W/"wave_mesh_triplet_20261031"')==1
text=base.replace('R=W/"wave_mesh_triplet_20261031"','R=W/"wave_mesh_triplet_20261031_r2"')
p=w/"render_wave_triplet_comparison_r2.py"
assert not p.exists();compile(text,str(p),"exec");p.write_text(text,encoding="utf8")
print(p)
