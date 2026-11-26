from pathlib import Path
w=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
src=w/"NoFoilInletWavePilot.java";dest=w/"NoFoilInletWaveHalfDtPilot.java"
assert src.is_file() and not dest.exists()
s=src.read_text(encoding="utf8")
assert s.count("public class NoFoilInletWavePilot extends StarMacro")==1
assert s.count("private final double t0=.4, dt=.001, duration=")==1
s=s.replace("public class NoFoilInletWavePilot extends StarMacro","public class NoFoilInletWaveHalfDtPilot extends StarMacro")
s=s.replace("private final double t0=.4, dt=.001, duration=","private final double t0=.4, dt=.0005, duration=")
dest.write_text(s,encoding="utf8")
print("HALFDT_MACRO_CREATED",dest,"source_unchanged",True,"only_timestep_and_class_name_changed",True)
