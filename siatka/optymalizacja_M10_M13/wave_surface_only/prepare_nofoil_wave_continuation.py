from pathlib import Path
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
old=(W/"NoFoilInletWavePilot.java").read_text(encoding="utf8")
s=old
def replace_once(a,b):
 global s
 assert s.count(a)==1,repr((a,s.count(a)))
 s=s.replace(a,b)
replace_once("NoFoilInletWavePilot extends StarMacro","NoFoilInletWaveContinuation extends StarMacro")
replace_once("private final double t0=.4, dt=.001, duration=2*.8472673206891129;","private final double t0=.9, rampStart=.4, dt=Double.parseDouble(System.getenv(\"NTNU_NOFOIL_WAVE_DT\")), duration=2*.8472673206891129;")
replace_once("(t-t0)/duration","(t-rampStart)/duration")
replace_once("Expected physical flat-current checkpoint at t=0.4 s","Expected completed wave pilot checkpoint at t=0.9 s")
replace_once('if(Math.abs(initialVolume-38.4)>.005||Math.abs(initialSpeed-18)>.05)','if(Math.abs(initialVolume-38.4)>.02||Math.abs(initialSpeed-18)>1.0)')
replace_once('if(!Double.isFinite(z)||Math.abs(z)>.002)','if(!Double.isFinite(z)||Math.abs(z)>.15)')
replace_once('wm.setEnableTheoryComparison(true);\n   FifthOrderVofWave wave=createWave(wm);',
'''// Keep the completed upstream wave forcing and full flow fields exactly as saved.
   VofWave existing=fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
   if(!(existing instanceof FifthOrderVofWave) || !existing.getPresentationName().equals("IndependentNoFoil_L20_H050_InletRamp"))
     throw new IllegalStateException("Prior FifthOrder inlet wave binding not present");
   FifthOrderVofWave wave=(FifthOrderVofWave)existing;
   if(wave.getWaveHeight().getDefinition()==null || !wave.getWaveHeight().getDefinition().contains("$Time"))
     throw new IllegalStateException("Wave ramp formula absent; cannot continue");
''')
a='   inlet.getValues().get(VelocityProfile.class).setMethod(FunctionVectorProfileMethod.class);'
b='   ArrayList<Object> bindings=new ArrayList<>();'
i=s.index(a);j=s.index(b,i)
s=s[:i]+'''   // Do not change inlet boundary, outlet, forcing zone, VOF or field initialization.
   if(!fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(wave))
     throw new IllegalStateException("Existing wave target mismatch");
'''+s[j:]
replace_once('if(steps<3||steps>800)','if(steps<3||steps>2000)')
replace_once('setup.put("startup","previously computed stable flat-current field, then incident wave at upstream inlet; no clear/initialize");',
'''setup.put("startup","existing saved wave from upstream inlet; continue without rebinding or global reinitialization");
   setup.put("continuation_origin","verified isolated t0.9 wave pilot");
   setup.put("wave_origin_t_s",rampStart);''')
replace_once('setup.put("source_t_s",t0);setup.put("dt_s",dt);',
'''setup.put("source_t_s",t0);setup.put("dt_s",dt);
   if(dt!=.001 && dt!=.0005)throw new IllegalStateException("Temporal test only 1ms or 0.5ms");''')
replace_once('result.put("stage","incident_wave_ramp_only; no acceptance; downstream arrival not yet established");',
'''result.put("stage","independent no-foil inlet-wave continuation; no wave propagation or mesh acceptance asserted");''')
replace_once('result.put("calm_source_preserved",true);','result.put("calm_source_preserved",true);')
replace_once('if(elapsed>1800)','if(elapsed>2400)')
# protect source .sim (loaded directly from copied input.sim).
out=W/"NoFoilInletWaveContinuation.java"
assert not out.exists()
out.write_text(s,encoding="utf8")
print("wrote",out,"bytes",out.stat().st_size,"source_backup_untouched",True)
