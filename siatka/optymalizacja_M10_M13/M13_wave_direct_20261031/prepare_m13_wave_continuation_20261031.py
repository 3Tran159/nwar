"""Offline prepare a separate continuation macro for a successful saved M13 wave pilot.
Never touch active R2 source, no solver launch, no old result edits. Start requires new scientific gates.
"""
from pathlib import Path
import subprocess,json,hashlib
from datetime import datetime
P=Path(r"E:\ntnu_mesh_optimization_20261030\M13_wave_direct_20261031")
SOURCE=P/"M13InletWavePilotR2.java"
NEW=P/"M13ContinueWaveR3.java"
COMP=P/"compiled_r3"
assert SOURCE.is_file() and not NEW.exists() and not COMP.exists()
src=SOURCE.read_text(encoding="utf-8")
def edit(old,new):
 global src
 assert src.count(old)==1,(old[:110],src.count(old))
 src=src.replace(old,new,1)
edit("public class M13InletWavePilotR2 extends StarMacro",
     "public class M13ContinueWaveR3 extends StarMacro")
edit('steps<40||steps>1200||budget<300||budget>2400',
     'steps<400||steps>12000||budget<600||budget>14400')
edit('if(Math.abs(t0-3.8992)>1e-7)throw new IllegalStateException("Accepted M13 calm checkpoint mismatch");',
     '''double requiredTime=Double.parseDouble(System.getenv("NTNU_M13_WAVE_START_T"));
   if(Math.abs(t0-requiredTime)>dt*.1||t0<=3.8992)
    throw new IllegalStateException("Continuation checkpoint physical time mismatch");''')
edit('''FlatVofWave calm=(FlatVofWave)wm.getVofWaveManager().getVofWave("Calm");
   if(!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(calm))
    throw new IllegalStateException("Wave already active in M13 source");''',
     '''ManagedVofWave sourceWave=reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
   if(!(sourceWave instanceof FifthOrderVofWave)||
       !sourceWave.getPresentationName().contains("M13_Exploratory_Inlet_W20_H050"))
    throw new IllegalStateException("Continuation requires source M13 FifthOrder inlet wave");''')
a=src.index('   wm.setEnableTheoryComparison(true);')
b=src.index('   for(Object x:s.getSolverStoppingCriterionManager().getChildren())',a)
assert b>a and "wave.getWaveHeight().setDefinition" in src[a:b] and "inlet.getValues()" in src[a:b]
section='''   // Preserve the already-computed wave, current, inlet forcing, and VOF field unchanged.
   FifthOrderVofWave wave=(FifthOrderVofWave)sourceWave;
   period=20.0/23.612; ramp=2*period;
   if(wave.getWaveHeight().getDefinition()==null||
      !wave.getWaveHeight().getDefinition().contains("$Time"))
    throw new IllegalStateException("Original upstream ramp definition missing");
   Boundary inlet=reg.getBoundaryManager().getBoundary("DOMAIN.inlet");
   if(!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(wave))
    throw new IllegalStateException("Continuation lost original wave binding");
'''
src=src[:a]+section+src[b:]
edit('"M13 accepted calm final.sim; source copy only"','"M13 foil+wave already-computed checkpoint; copied and continued"')
edit('setup.put("t0",t0);','setup.put("t0",t0);setup.put("original_inlet_activation_s",3.899199999999636);')
edit('setup.put("CL_hydro_pre_switch",','setup.put("CL_hydro_at_continuation",')
edit('setup.put("CD_pre_switch",','setup.put("CD_at_continuation",')
edit('setup.put("global_initialization",false);setup.put("scientific_accepted",false);',
     'setup.put("global_initialization",false);setup.put("inlet_wave_rebound",false);setup.put("scientific_accepted",false);')
edit('step%200==0','step%1000==0')
# Keep benchmark guards and finite VOF/force criteria, no pressure/physics solver changes.
assert ".initializeSolution(" not in src and ".clearSolution(" not in src
assert "createVofWave(" not in src and "setDefinition(" not in src and "setMethod(" not in src
assert "s.getSimulationIterator().step(1)" in src
NEW.write_text(src,encoding="utf-8")
COMP.mkdir()
javac=r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
cp=r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
res=subprocess.run([javac,"-cp",cp,"-d",str(COMP),str(NEW)],capture_output=True,text=True,timeout=100)
receipt={"at":datetime.now().astimezone().isoformat(),"status":"javac_pass" if res.returncode==0 else "compile_error",
 "source":str(SOURCE),"source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 "new_macro":str(NEW),"new_sha256":hashlib.sha256(NEW.read_bytes()).hexdigest(),
 "scope":"Offline compiled conditional continuation ONLY after verified saved R2 pilot, same actual fields, dt=0.4ms, same bound FifthOrder wave, GPU, no reinit; up to 12k steps, bounded wall; checkpoints every 1000",
 "start_run":False,"compiler_stderr":res.stderr[-1500:]}
(P/"m13_wave_continuation_compile_receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
assert res.returncode==0 and (COMP/"macro"/"M13ContinueWaveR3.class").exists(),receipt
print(json.dumps({"ready":True,"solver_started":False,"macro":str(NEW),"new_sha256":receipt["new_sha256"]}))
