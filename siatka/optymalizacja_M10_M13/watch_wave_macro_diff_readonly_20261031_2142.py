"""Read-only comparison of known successful and failing incident-wave macros."""
import difflib, pathlib
r=pathlib.Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
good=r/"WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0"/"NoFoilInletWavePilot.java"
bad=r/"zero_start_matrix_evening_20261031_182305_689cb9"/"waves"/"L20_H500_baseline"/"WaveFromOwnCalm_20261031.java"
half=r/"zero_start_matrix_evening_dt05_20261031"/"waves"/"L20_H500_baseline"/"WaveFromOwnCalmDtHalfEvening.java"
for a,b in [(good,bad),(bad,half)]:
    print("=== DIFF",a.name,"VS",b.name,"===")
    src=a.read_text(encoding="utf-8").splitlines()
    dst=b.read_text(encoding="utf-8").splitlines()
    print("Lines:",len(src),len(dst))
    lines=list(difflib.unified_diff(src,dst,fromfile=a.name,tofile=b.name,n=1))
    for line in lines[:220]: print(line)
    if len(lines)>220: print("... TRUNCATED",len(lines),"diff lines total")
