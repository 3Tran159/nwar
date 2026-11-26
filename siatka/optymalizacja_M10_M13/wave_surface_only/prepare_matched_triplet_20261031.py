from pathlib import Path
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
src=(W/"PrepareNoFoilCalmThroughflow.java").read_text(encoding="utf8")
s=src
def rep(a,b):
 global s
 n=s.count(a);assert n==1,(a[:80],n);s=s.replace(a,b)
rep("public class PrepareNoFoilCalmThroughflow extends StarMacro","public class ContinueMappedNoFoilFlat extends StarMacro")
rep('if(Math.abs(dt-.001)>1e-12||steps<200||steps>500)', 'if(Math.abs(dt-.001)>1e-12||steps!=200)')
rep('if(fv.getCellCount()!=53200||Math.abs(s.getSolution().getPhysicalTime())>1e-10)', 'if(fv.getCellCount()!=Integer.parseInt(System.getenv("NTNU_NOFOIL_CELLS"))||Math.abs(s.getSolution().getPhysicalTime()-.4)>1e-10)')
rep("   calm.getCurrent().setComponents(18.0,0.0,0.0);\n   calm.getWind().setComponents(18.0,0.0,0.0);",
'''   if(Math.abs(calm.getCurrentVector().get(0)-18)>.000001)throw new IllegalStateException("Expected saved 18m/s calm field");''')
# Preserve previously computed fields, and do not overwrite initial or boundary conditions.
begin="   FieldFunction vel=waveField(\"Velocity\"),pressure=waveField(\"Hydrostatic Pressure of Heavy Fluid\"),frac=waveField(\"Volume Fraction of Heavy Fluid\");"
end='   s.getSimulationIterator().getAutoSave().setEnabled(false);'
assert s.count(begin)==1 and s.count(end)==1
i=s.index(begin);j=s.index(end,i)
s=s[:i]+'''   FieldFunction frac=waveField("Volume Fraction of Heavy Fluid");
   if(!(fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave() instanceof FlatVofWave))
     throw new IllegalStateException("Calm flat forcing identity required; no waves already present");
'''+s[j:]
rep("   // The reference input is wave-filled at t=0. Clear only the DISPOSABLE copy and initialize flat calm water.\n   s.getSolution().clearSolutionWithoutMeshReset();\n   s.getSolution().initializeSolution();\n   if(Math.abs(s.getSolution().getPhysicalTime())>1e-10)throw new IllegalStateException(\"Initialization unexpectedly advanced time\");",
'''   // The reference is already solved flat at t=0.4. NEVER clear or initialize.
   if(Math.abs(s.getSolution().getPhysicalTime()-.4)>1e-10)throw new IllegalStateException("Mapped calm t=0.4 expected");''')
rep('init.put("reinitialized_disposable_copy",true);','init.put("reinitialized_disposable_copy",false);')
rep('||Math.abs(t-step*dt)>dt*.1)','||Math.abs(t-.4-step*dt)>dt*.1)')
rep('if(!Double.isFinite(eta)||Math.abs(eta)>.10)', 'if(!Double.isFinite(eta)||Math.abs(eta)>.005)')
rep('if(elapsed>2200)','if(elapsed>1500)')
dest=W/"ContinueMappedNoFoilFlat.java"
assert not dest.exists();dest.write_text(s,encoding="utf8")
print("CALM",dest.name,len(s))
base=(W/"NoFoilInletWavePilot.java").read_text(encoding="utf8")
for tag,cells in (("Coarse",41200),("Baseline",53200),("Fine",77200)):
 s=base
 assert s.count("public class NoFoilInletWavePilot extends StarMacro")==1
 s=s.replace("public class NoFoilInletWavePilot extends StarMacro",f"public class WaveTriplet_{tag} extends StarMacro")
 assert s.count("private final double t0=.4, dt=.001")==1
 s=s.replace("private final double t0=.4, dt=.001","private final double t0=.6, dt=.001")
 assert s.count("($Time-<0.4 s>)")==1
 s=s.replace("($Time-<0.4 s>)","($Time-<0.6 s>)")
 assert s.count("if(fv.getCellCount()!=53200)")==1
 s=s.replace("if(fv.getCellCount()!=53200)",f"if(fv.getCellCount()!={cells})")
 dest=W/f"WaveTriplet_{tag}.java"
 assert not dest.exists();dest.write_text(s,encoding="utf8")
 print("WAVE",tag,cells,dest.name,len(s))
