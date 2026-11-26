from pathlib import Path
import sys
w=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
sys.path.insert(0,str(w))
import launch_halfdt_wave_cpu2_with_M11_guard as l
l.preflight()
print("HALFDT_WAVE_READONLY_PREFLIGHT_PASS",l.now(),"main",l.main_state())
