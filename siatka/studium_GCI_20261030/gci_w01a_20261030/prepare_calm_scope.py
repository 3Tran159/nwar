from pathlib import Path
import json,shutil,datetime
O=Path(__file__).resolve().parent
H=O.parent
def replace(t,old,new):
 if t.count(old)!=1:raise RuntimeError('Template mismatch '+old[:100])
 return t.replace(old,new)
src=(O/'ContinueWaveGCI.java').read_text()
t=src.replace('ContinueWaveGCI','ContinueCalmGCI')
t=replace(t,'private double dt,target,startTime,expectedPeriod;','private double dt,target,startTime; private final double window=.2;')
start=t.index('      if(!(selectedWave instanceof FifthOrderVofWave))')
end=t.index('      double pressureTol=',start)
t=t[:start]+'''      if(!(selectedWave instanceof FlatVofWave)||!selectedWave.equals(calm))throw new IllegalStateException("Saved calm W01a fields required; incident wave must be inactive");
      Boundary outlet=fluid.getBoundaryManager().getBoundary("DOMAIN.outlet"),bed=fluid.getBoundaryManager().getBoundary("DOMAIN.bottom");
      if(!String.valueOf(outlet.getConditions().get(BackflowSpecification.class).getReversedFlowPressureOption().getSelectedElement()).equals("ENVIRONMENTAL")||!String.valueOf(bed.getConditions().get(WallShearStressOption.class).getSelectedElement()).equals("SLIP"))throw new IllegalStateException("W01a boundary mismatch");
'''+t[end:]
t=t.replace('Wave GCI must continue saved fields without initialization','Calm GCI must continue saved fields without initialization')
t=t.replace('W01a wave continuation from a common computed checkpoint; phase-matched spatial verification, no reinitialization','Calm-water W01a mesh convergence, saved fields, no incident wave, no reinitialization')
a=t.index('      String priorPath=');b=t.index('      massBudget=',a);t=t[:a]+t[b:]
a=t.index('      double[] gaugeXs=');b=t.index('      recordBudget();',a);t=t[:a]+'''      Files.writeString(out.resolve("calm_audit.json"),json(Map.of("incident_wave_height_m",0,"source_wave",selectedWave.getPresentationName(),"type",selectedWave.getClass().getSimpleName(),"reinitialized",false,"start_time_s",startTime,"pressure_AMG_tolerance",pressureTol,"VOF_AMG_tolerance",vofTol,"GPU_count",s.getNumberOfGpgpus())));
'''+t[b:]
a=t.index('          if(steps==1){');b=t.index('          int vofSteps=',a);t=t[:a]+t[b:]
t=t.replace('samples.add(new double[]{t,d/q,l/q});','samples.add(new double[]{t,d/q,l/q,p/q,v/q});')
t=t.replace('if(samples.size()>2000)samples.remove(0);','if(samples.size()>2*(int)Math.round(window/dt)+10)samples.remove(0);')
t=t.replace('(int)Math.round(expectedPeriod/dt)','(int)Math.round(.5/dt)',1)
t=replace(t,'if(false){ // Fixed matched horizon for temporal-order experiment','if("true".equals(System.getenv("NTNU_CALM_SETTLE"))&&steps%(int)Math.round(window/dt)==0){')
t=t.replace('if(consecutivePasses>=1){state="stabilized";break;}','if(consecutivePasses>=2){state="stabilized";break;}')
a=t.index('  private boolean settlingPass()');b=t.index('  private ForceReport force(',a)
t=t[:a]+'''  private boolean settlingPass()throws Exception{
    int n=(int)Math.round(window/dt);
    if(Math.abs(n*dt-window)>1e-10)throw new IllegalStateException("Settling window must contain an integer number of constant time steps");
    if(samples.size()<2*n)return false;
    int end=samples.size();Map<String,Object> check=new LinkedHashMap<>();boolean pass=true;
    String[] keys={"CD","CL_total","CD_pressure","CD_viscous"};
    for(int col=1;col<=4;col++){
      double previous=0,latest=0,oldVariance=0,newVariance=0,low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
      for(int k=end-2*n;k<end-n;k++)previous+=samples.get(k)[col]/n;
      for(int k=end-n;k<end;k++)latest+=samples.get(k)[col]/n;
      for(int k=end-2*n;k<end-n;k++)oldVariance+=Math.pow(samples.get(k)[col]-previous,2)/n;
      for(int k=end-n;k<end;k++){double v=samples.get(k)[col];newVariance+=Math.pow(v-latest,2)/n;low=Math.min(low,v);high=Math.max(high,v);}
      boolean resolved=Math.abs(previous)>1e-8&&Math.abs(latest)>1e-8;
      double change=100*Math.abs(latest-previous)/Math.max(Math.abs(latest),1e-30);
      double rmsOld=100*Math.sqrt(oldVariance)/Math.max(Math.abs(previous),1e-30);
      double rmsNew=100*Math.sqrt(newVariance)/Math.max(Math.abs(latest),1e-30);
      boolean ok=resolved&&Double.isFinite(change)&&Double.isFinite(rmsOld)&&Double.isFinite(rmsNew)&&change<.5&&rmsOld<.5&&rmsNew<.5;
      pass&=ok;check.put(keys[col-1],Map.of("previous_mean",previous,"latest_mean",latest,"mean_change_pct",change,"previous_RMS_pct",rmsOld,"latest_RMS_pct",rmsNew,"latest_peak_to_peak_pct",100*(high-low)/Math.max(Math.abs(latest),1e-30),"relative_test_resolved",resolved,"pass",ok));
    }
    check.put("time_s",samples.get(end-1)[0]);check.put("pass",pass);check.put("consecutive_passes",pass?consecutivePasses+1:0);
    check.put("criterion","Two adjacent non-overlapping 0.2 s windows; absolute relative mean shift and within-window RMS must each be <0.5% for CL, CD total, CD pressure and CD viscous. Require two successive passing checks 0.2 s apart. Near-zero coefficients cannot pass an unresolved relative test. Stabilization is not itself a GCI result.");
    Files.writeString(out.resolve("settling_check.json"),json(check));
    Files.writeString(out.resolve("settling_checks.jsonl"),json(check)+"\\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);return pass;
  }
'''+t[b:]
assert 'expectedPeriod' not in t and 'activeWave' not in t
(O/'ContinueCalmGCI.java').write_text(t,encoding='utf-8')
# Supersede only the idle post-build mapper. The running mesher stays unchanged.
p=H/'postbuild_w01_gci.py'
shutil.copy2(p,H/'postbuild_w01_gci_wave_superseded.py')
t=p.read_text().replace("checkpoint_startup_t0.020.sim')","final.sim')")
t=replace(t,"if b.sha(SOURCE)!=expected:raise RuntimeError('Source checkpoint differs from handoff')","""if b.sha(SOURCE.parent/'checkpoint_startup_t0.020.sim')!=expected:raise RuntimeError('Original handoff checkpoint changed')
 done=b.read(SOURCE.parent/'completed.json');calm=b.read(SOURCE.parent/'requested_wave_audit.json')
 if done['status']!='stopped_by_marker' or abs(done['time_s']-.587)>1e-8 or calm['class']!='FlatVofWave' or calm['height_m']!=0:raise RuntimeError('Saved final calm checkpoint not as expected')
 expected=b.sha(SOURCE)
 b.write(O/'calm_source_identity.json',dict(path=str(SOURCE),sha256=expected,time_s=done['time_s'],source_requested_wave=calm,originals_preserved=True))
 os.environ['NTNU_MAP_EXPECTED_START']=str(done['time_s'])""")
t=t.replace("'source_checkpoint_time_s':.02","'source_checkpoint_time_s':done['time_s']")
t=t.replace("'geometry_and_mapping_verified_wave_startup_definition_pending'","'calm_geometry_and_mapping_verified'")
t=replace(t,"state('geometry_and_mapping_verified_pending_W01a_wave_startup',starting_states=starts,reason='Handoff explicitly has wave inactive and ramp under audit. A frozen tested inlet-wave startup and matched phase windows are required before launching wave GCI.')","state('calm_geometry_and_mapping_verified',starting_states=starts,source_time_s=done['time_s'],incident_wave_height_m=0)")
# CPU affinity remains disjoint from the main GPU driver.
t=replace(t,"try:main()","try:\n  import ctypes\n  k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p;k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]\n  if not k.SetProcessAffinityMask(k.GetCurrentProcess(),1020):raise RuntimeError('Affinity failed')\n  main()")
p.write_text(t,encoding='utf-8')
scope=dict(at=datetime.datetime.now().astimezone().isoformat(),scope="Calm-water verification of W01a meshes only",incident_wave_height_m=0,CPU_only=True,GPU_main_wave_untouched=True,source_time_s=.587,coefficients=['CL_total','CD','CD_pressure','CD_viscous'],stabilization=dict(window_s=.2,threshold_pct=.5,mean_shift=True,RMS_each_window=True,consecutive_passes=2),wave_GCI_removed=True,reason="User lacks compute resources for separate wave accuracy study",no_new_report=True)
(O/'scope_change_calm.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
shutil.copy2(O/'study_plan.json',O/'study_plan_wave_superseded.json')
(O/'study_plan.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
print('Calm macro and postbuild mapping preparation updated.')
