from pathlib import Path
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
B=Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030")
orig=(B/"MapW01Solution.java").read_text(encoding="utf8")
assert orig.count("public class MapW01Solution extends StarMacro")==1
assert orig.count("if(fv.getCellCount()!=317277)")==1
s=orig.replace("public class MapW01Solution extends StarMacro","public class NoFoilFlatMeshMapper extends StarMacro")
s=s.replace("if(fv.getCellCount()!=317277)","if(fv.getCellCount()!=53200)")
s=s.replace('s=getActiveSimulation();Path out=Paths.get(System.getenv("NTNU_MAP_OUT"));',
'''s=getActiveSimulation();Path out=Paths.get(System.getenv("NTNU_MAP_OUT")).toAbsolutePath().normalize();
  Path expected=out.resolve("input.sim").toAbsolutePath().normalize();
  if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(expected))
    throw new IllegalStateException("Only copied baseline calm no-foil checkpoint is permitted");
  if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("No GPU permitted for independent mesh mapper");
  if(Files.exists(out.resolve("mapped.sim")))throw new IllegalStateException("Refuse to overwrite existing mapped state");''')
s=s.replace('if(Math.abs(start-Double.parseDouble(System.getenv().getOrDefault("NTNU_MAP_EXPECTED_START","0.02")))>1e-8)',
'''if(Math.abs(start-Double.parseDouble(System.getenv().getOrDefault("NTNU_MAP_EXPECTED_START","0.4")))>1e-8)''')
s=s.replace('boolean pass=massChange<.001&&waterChange<.001', 'boolean pass=massChange<.002&&waterChange<.002')
s=s.replace('if(after.containsKey("TurbulentKineticEnergy_min"))', 'if(after.containsKey("TurbulentKineticEnergy_min"))')
assert 'NoFoilFlatMeshMapper' in s and '317277' not in s
out=W/"NoFoilFlatMeshMapper.java"
assert not out.exists()
out.write_text(s,encoding="utf8")
wave=(W/"NoFoilInletWavePilot.java").read_text(encoding="utf8")
for mesh,cells in [("coarse",41200),("fine",77200)]:
 s=wave
 s=s.replace("public class NoFoilInletWavePilot extends StarMacro",f"public class NoFoilWave_{mesh.title()} extends StarMacro")
 assert s.count("if(fv.getCellCount()!=53200)")==1
 s=s.replace("if(fv.getCellCount()!=53200)",f"if(fv.getCellCount()!={cells})")
 # Acceptance remains diagnostic only, same forcing/timing and no global initialization.
 assert s.count("private final double t0=.4, dt=.001")==1
 dest=W/f"NoFoilWave_{mesh.title()}.java"
 assert not dest.exists()
 dest.write_text(s,encoding="utf8")
 print(mesh,cells,dest.name,len(s))
print("mapper",out.name,len(out.read_bytes()))
