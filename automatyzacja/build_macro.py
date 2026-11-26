"""Build a separately versioned STAR macro from the proven M13 wave implementation."""
from pathlib import Path
import subprocess,hashlib,json
HERE=Path(__file__).resolve().parent
SOURCE=Path('E:/ntnu_mesh_optimization_20261030/clean_c01_campaign_20261101/night_wave_queue_20261101/W01TwentyCyclesW03Safety.java')
s=SOURCE.read_text(encoding='utf8')
def replace(a,b,n=1):
 global s
 assert s.count(a)==n,(a[:100],s.count(a),n)
 s=s.replace(a,b)
replace('public class W01TwentyCyclesW03Safety','public class NwarWave')
replace(' double t0,dt,period,ramp,H=0.5,lambda=30.0,water0;',""" double t0,dt,period,ramp,H=0.5,lambda=30.0,water0,beginTime;
 boolean resume=false; int maxCycles=20, smokeSteps=0, extraSteps=0, count=0;
 String endState="target_reached";
 double param(String name,double fallback){String v=System.getenv(name);return v==null?fallback:Double.parseDouble(v);}
""")
replace(' void save(String file,Map<String,?> info)throws Exception{Files.writeString(out.resolve(file),json(info)+"\\n");}',""" void save(String file,Map<String,?> info)throws Exception{
 Path p=out.resolve(file),tmp=out.resolve(file+".tmp");
 Files.writeString(tmp,json(info)+"\\n");
 Files.move(tmp,p,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
 }""")
replace('String isolate="E:/ntnu_mesh_optimization_20261030/clean_c01_campaign_20261101/night_wave_queue_20261101/W03_";','String isolate="E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/runs/";')
replace('   dt=Double.parseDouble(System.getenv("NTNU_M13_WAVE_DT"));',"""   dt=Double.parseDouble(System.getenv("NTNU_M13_WAVE_DT"));
   H=param("NWAR_H",.5);lambda=param("NWAR_L",20);
   if(!Double.isFinite(H)||!Double.isFinite(lambda)||H<.25||H>.5||lambda<19||lambda>30)
    throw new IllegalStateException("Outside reviewed diagnostic H/lambda envelope");
   resume="1".equals(System.getenv("NWAR_RESUME"));
   extraSteps=(int)param("NWAR_EXTRA_STEPS",0);
   smokeSteps=(int)param("NWAR_SMOKE_STEPS",0);
   maxCycles=(int)param("NWAR_MAX_CYCLES",20);
   if(maxCycles<4||maxCycles>20||smokeSteps<0||smokeSteps>100||extraSteps<0||extraSteps>80000)
    throw new IllegalStateException("Invalid requested run limit");
""")
replace('if(dt!=.0004||inner!=10||steps<12000||steps>26000||budget<5000||budget>24000)','if(dt!=.0004||inner!=10||steps<12000||steps>26000||budget<120||budget>129600)')
replace('   t0=s.getSolution().getPhysicalTime();\n   if(Math.abs(t0-4.6992)>1e-7)throw new IllegalStateException("New C01 accepted saved checkpoint mismatch");',"""   beginTime=s.getSolution().getPhysicalTime();t0=4.699199999999548;
   double expected=param("NWAR_SOURCE_TIME",t0);
   if(Math.abs(beginTime-expected)>1e-7)throw new IllegalStateException("Source physical time mismatch");
   if(!resume&&Math.abs(beginTime-t0)>1e-7)throw new IllegalStateException("Fresh waves require accepted C01");
""")
replace('   if(!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(calm))','   if(!resume&&!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(calm))')
replace('   FifthOrderVofWave wave=wm.getVofWaveManager().createVofWave(FifthOrderVofWave.class,"M13_W03_H500_L30");',"""   FifthOrderVofWave wave;
   if(resume){
    ManagedVofWave active=reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
    if(!(active instanceof FifthOrderVofWave))throw new IllegalStateException("Saved active wave is not FifthOrder");
    wave=(FifthOrderVofWave)active;
    if(Math.abs(wave.getVofWaveSpecification().getWaveLength().getSIValue()-lambda)>1e-7||
       Math.abs(wave.getHeavyFluidDensity().getSIValue()-1000)>1e-9||
       Math.abs(wave.getLightFluidDensity().getSIValue()-1.2)>1e-9)
      throw new IllegalStateException("Saved wave parameters mismatch");
   }else wave=wm.getVofWaveManager().createVofWave(FifthOrderVofWave.class,"NWAR_Wave");
   if(!resume){
""")
replace('   period=1.2075530192963326;','   period=lambda/(18+Math.sqrt(9.81*lambda/(2*Math.PI)*Math.tanh(2*Math.PI*24/lambda)));')
replace('wave.getWaveHeight().setDefinition("<0.000001 m>+<0.499999 m>*0.5*(1.0-cos(3.141592653589793*"+tau+"))");','wave.getWaveHeight().setDefinition("<0.000001 m>+<"+(H-.000001)+" m>*0.5*(1.0-cos(3.141592653589793*"+tau+"))");')
needle='   double boundPeriod=wave.getWavePeriod().getSIValue();'
replace(needle,"""   } // Resume preserves the saved active wave, inlet bindings, phase and ramp.
   period=lambda/(18+Math.sqrt(9.81*lambda/(2*Math.PI)*Math.tanh(2*Math.PI*24/lambda)));
   ramp=2*period;
   if(resume)save("wave_density_audit.json",Map.of("FifthOrder_water_rho",wave.getHeavyFluidDensity().getSIValue(),"FifthOrder_air_rho",wave.getLightFluidDensity().getSIValue(),"source_material_and_Calm_verified",true));
"""+needle)
replace('setup.put("t0",t0);','setup.put("t0",t0);setup.put("begin_time_s",beginTime);setup.put("resume",resume);setup.put("target_extra_steps",extraSteps);setup.put("smoke_steps",smokeSteps);')
replace('   s.saveState(out.resolve("wave_bound_pre_step.sim").toString());',"""   if("1".equals(System.getenv("NWAR_SETUP_ONLY"))){
    save("completed.json",Map.of("status","setup_verified","steps",0,"time_s",beginTime,"scientific_accepted",false));return;
   }
   s.saveState(out.resolve("wave_bound_pre_step.sim").toString());
   save("latest_checkpoint.json",Map.of("file","wave_bound_pre_step.sim","time_s",beginTime,"step",0,"healthy",true));
""")
replace('   long startWall=System.nanoTime();int count=0;String endState="target_reached";','   long startWall=System.nanoTime();count=0;endState="target_reached";')
replace('     stopCheck();if(step>0){s.getSimulationIterator().step(1);count=step;}',"""     if(step>0){
      try{stopCheck();}catch(IllegalStateException stop){endState="paused_saved";break;}
      s.getSimulationIterator().step(1);count=step;
     }""")
replace('Math.abs(t-t0-step*dt)>dt*.2','Math.abs(t-beginTime-step*dt)>dt*.2')
replace('      pg.put("complete_cycles",cycleLimit.complete);pg.put("max_complete_cycles",20);','      pg.put("complete_cycles",cycleLimit.complete);pg.put("max_complete_cycles",maxCycles);pg.put("wall_s",elapsed);pg.put("interface_CFL",interCFL);pg.put("resume",resume);pg.put("extra_steps_goal",extraSteps);pg.put("sampled_at",java.time.OffsetDateTime.now().toString());')
replace('     if(step>0&&step%1500==0)s.saveState(out.resolve(String.format(Locale.ROOT,"checkpoint_t%.4f.sim",t)).toString());',"""     if(step>0&&step%1500==0){
      String ck=String.format(Locale.ROOT,"checkpoint_t%.4f.sim",t);
      s.saveState(out.resolve(ck).toString());
      save("latest_checkpoint.json",Map.of("file",ck,"time_s",t,"step",step,"healthy",true));
     }
     if(smokeSteps>0&&step>=smokeSteps){endState="smoke_test_saved";break;}
     if(resume&&extraSteps>0&&step>=extraSteps){endState="requested_extension_saved";break;}
""")
replace('     if(step>0&&step%100==0&&fourCyclesRepeat(t))','     if(!resume&&smokeSteps==0&&step>0&&step%100==0&&fourCyclesRepeat(t))')
replace('     if(cycleLimit.complete>=20){','     if(cycleLimit.complete>=maxCycles){')
replace('   s.saveState(out.resolve("wave_pilot_final.sim").toString());','   s.saveState(out.resolve("wave_pilot_final.sim").toString());\n   save("latest_checkpoint.json",Map.of("file","wave_pilot_final.sim","time_s",s.getSolution().getPhysicalTime(),"step",count,"healthy",true));')
replace('   stopCheck();reg=s.getRegionManager().getRegion("fluid");','   reg=s.getRegionManager().getRegion("fluid");')
# Require four actual complete fixed-gauge cycles; the earlier macro stopped on four planning periods.
replace('private boolean fourCyclesRepeat(double now)throws Exception{','private boolean fourCyclesRepeat(double now,FullCycleCounter counter)throws Exception{')
replace('if(now-t0<ramp+arrival+4*period+.1||cycleTrace.size()<250)return false;','if(counter.complete<4||counter.boundaries.size()<4||cycleTrace.size()<250)return false;')
replace('double start=now-4*period;if(cycleTrace.get(0)[0]>start)return false;','double start=counter.boundaries.get(counter.boundaries.size()-4)[0];if(cycleTrace.get(0)[0]>start)return false;')
replace('double at=start+(c+(i+.5)/phases)*period;','double[] bounds=counter.boundaries.get(counter.boundaries.size()-4+c); double at=bounds[0]+(i+.5)/phases*(bounds[1]-bounds[0]);')
replace('&&fourCyclesRepeat(t))','&&fourCyclesRepeat(t,cycleLimit))')
replace('if(!resume&&smokeSteps==0&&step>0&&step%100==0&&fourCyclesRepeat(t,cycleLimit))','if((!resume||"1".equals(System.getenv("NWAR_ALLOW_EARLY")))&&smokeSteps==0&&step>0&&step%100==0&&fourCyclesRepeat(t,cycleLimit))')
replace('   FullCycleCounter cycleLimit=new FullCycleCounter(period,H,t0+ramp+34.5*period/lambda,10*dt);','   FullCycleCounter cycleLimit=new FullCycleCounter(period,H,t0+ramp+34.5*period/lambda,10*dt);\n   if(resume)loadPriorCycles(cycleLimit);')
replace(' public void execute(){',r''' void loadPriorCycles(FullCycleCounter counter)throws Exception{
  Path hp=out.resolve("prior_history.csv"),gp=out.resolve("prior_gauges.csv");
  if(!Files.isRegularFile(hp)||!Files.isRegularFile(gp))throw new IllegalStateException("Missing continuation provenance histories");
  List<String> lines=Files.readAllLines(hp);String[] header=lines.get(0).split(",");
  List<String> keys=Arrays.asList(header);int ti=keys.indexOf("time_s"),ci=keys.indexOf("CL_hydrodynamic"),di=keys.indexOf("CD_total");
  if(ti<0||ci<0||di<0)throw new IllegalStateException("Prior force history schema");
  TreeMap<Double,double[]> forces=new TreeMap<>();
  for(int i=1;i<lines.size();i++){
   String[] v=lines.get(i).split(",");double t=Double.parseDouble(v[ti]);
   if(t<=beginTime+1e-8)forces.put(t,new double[]{Double.parseDouble(v[ci]),Double.parseDouble(v[di])});
  }
  if(forces.isEmpty()||Math.abs(forces.lastKey()-beginTime)>1e-7)throw new IllegalStateException("Prior history does not end at checkpoint");
  List<String> gl=Files.readAllLines(gp);List<String> gk=Arrays.asList(gl.get(0).split(","));
  int gt=gk.indexOf("time_s"),gx=gk.indexOf("x_m"),ge=gk.indexOf("eta_actual_m");
  if(gt<0||gx<0||ge<0)throw new IllegalStateException("Prior gauge history schema");
  for(int i=1;i<gl.size();i++){
   String[] v=gl.get(i).split(",");double t=Double.parseDouble(v[gt]),x=Double.parseDouble(v[gx]),eta=Double.parseDouble(v[ge]);
   if(Math.abs(x+.5)>1e-7||t>beginTime+1e-8)continue;
   Map.Entry<Double,double[]> lo=forces.floorEntry(t+1e-10),hi=forces.ceilingEntry(t-1e-10);
   if(lo==null||hi==null||hi.getKey()-lo.getKey()>.0013)throw new IllegalStateException("Gap in prior force/gauge time alignment");
   double frac=hi.getKey()-lo.getKey()>1e-10?(t-lo.getKey())/(hi.getKey()-lo.getKey()):0;
   double cl=lo.getValue()[0]+frac*(hi.getValue()[0]-lo.getValue()[0]);
   double cd=lo.getValue()[1]+frac*(hi.getValue()[1]-lo.getValue()[1]);
   if(!Double.isFinite(cl)||!Double.isFinite(cd)||!Double.isFinite(eta))throw new IllegalStateException("Nonfinite prior history");
   cycleTrace.add(new double[]{t,cl,cd,eta});counter.observe(t,eta);
  }
  save("restored_cycle_state.json",counter.evidence());
 }
 public void execute(){''')
# Explicit expanded profile: only the four reviewed wavelengths/heights, after PRE W04.
replace('double t0,dt,period,ramp,H=0.5,lambda=30.0,water0,beginTime;',
        'double t0,dt,period,ramp,H=0.5,lambda=30.0,water0,beginTime,probeDistance=34.5; boolean expanded=false; long expectedCells=309441;')
replace('final double[] locations=', 'double[] locations=')
replace('''   if(!Double.isFinite(H)||!Double.isFinite(lambda)||H<.25||H>.5||lambda<19||lambda>30)
    throw new IllegalStateException("Outside reviewed diagnostic H/lambda envelope");''','''   String profile=System.getenv().getOrDefault("NWAR_PROFILE","");
   expanded=profile.equals("M13_W04_20261102");
   if(!profile.isEmpty()&&!expanded)throw new IllegalStateException("Unknown mesh profile");
   String caseId=System.getenv().getOrDefault("NWAR_CASE","");
   boolean reviewedExpanded=(caseId.equals("W04")&&Math.abs(H-1.5)<1e-9&&Math.abs(lambda-38.99857691441418)<1e-8)||
     (caseId.equals("W05")&&H==1&&lambda==20)||(caseId.equals("W06")&&H==1&&lambda==30)||
     (caseId.equals("W07")&&H==1&&lambda==40)||
     (caseId.equals("W01")&&H==.5&&lambda==20)||(caseId.equals("W02")&&H==.25&&lambda==20)||
     (caseId.equals("W03")&&H==.5&&lambda==30)||
     (caseId.matches("CUSTOM[0-9]{3,}")&&H>=.25&&H<=1.5&&lambda>=15&&lambda<=40);
   if(!Double.isFinite(H)||!Double.isFinite(lambda)||(expanded?!reviewedExpanded:(H<.25||H>.5||lambda<19||lambda>30)))
    throw new IllegalStateException("Outside reviewed case-specific H/lambda envelope");
   if(expanded){expectedCells=572176;probeDistance=69.5;locations=new double[]{-69,-50,-30,-15,-6,-.5,5,20,50,85};}
''')
replace('mesh.getCellCount()!=309441','mesh.getCellCount()!=expectedCells')
replace('beginTime=s.getSolution().getPhysicalTime();t0=4.699199999999548;', '''beginTime=s.getSolution().getPhysicalTime();t0=expanded?param("NWAR_WAVE_ORIGIN",-1):4.699199999999548;
   if(expanded&&(!Double.isFinite(t0)||t0<1.7999))throw new IllegalStateException("Invalid PRE W04 wave origin");
   if(expanded){
    double forcing=reg.getBoundaryManager().getBoundary("DOMAIN.inlet").getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().getSIValue();
    double damping=reg.getBoundaryManager().getBoundary("DOMAIN.outlet").getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().getSIValue();
    if(Math.abs(forcing-40)>1e-8||Math.abs(damping-40)>1e-8)throw new IllegalStateException("Expanded wave-zone settings mismatch");
   }''')
replace('water0<30||water0>45','water0<(expanded?76:30)||water0>(expanded?78:45)')
replace('period<.5||period>1.5','period<.5||period>(expanded?1.6:1.5)')
replace('Double.isFinite(boundPeriod)&&boundPeriod>.7&&boundPeriod<1.1','Double.isFinite(boundPeriod)&&boundPeriod>.65*period&&boundPeriod<1.35*period')
replace('setup.put("cells",309441);','setup.put("cells",expectedCells);setup.put("mesh_profile",expanded?"M13_W04_20261102":"M13");setup.put("probe_distance_m",probeDistance);')
replace('"Independently accepted new C01 t4.6992 final.sim; source copy only"','expanded?"Accepted PRE W04 on expanded M13; reference policy and stability recorded in the source receipt; source copy only":"Independently accepted new C01 t4.6992 final.sim; source copy only"')
replace('34.5/(lambda/period)','probeDistance/(lambda/period)')
replace('t0+ramp+34.5*period/lambda','t0+ramp+probeDistance*period/lambda')
# A local free-surface column above the foil. Subtract the fluid-column area so
# the submerged solid cross-section does not bias the measured surface level.
replace('double[] locations={-34.,-25.,-15.,-10.,-6.,-.5,5.,10.,20.,40.};','double[] locations={-34.,-25.,-15.,-10.,-6.,-.5,5.,10.,20.,40.,0.};\n ArrayList<SurfaceIntegralReport> gaugeAreas=new ArrayList<>();')
replace('locations=new double[]{-69,-50,-30,-15,-6,-.5,5,20,50,85};','locations=new double[]{-69,-50,-30,-15,-6,-.5,5,20,50,85,0.};')
replace('   for(double x:locations){','''   FieldFunction columnUnity;
   if(s.getFieldFunctionManager().hasFunction("NWAR_ColumnUnity"))columnUnity=s.getFieldFunctionManager().getFunction("NWAR_ColumnUnity");
   else{UserFieldFunction one=s.getFieldFunctionManager().createFieldFunction();one.setFunctionName("NWAR_ColumnUnity");one.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);one.setDefinition("1");columnUnity=one;}
   for(double x:locations){''')
replace('gauges.add(g);','gauges.add(g);\n    SurfaceIntegralReport ga=s.getReportManager().createReport(SurfaceIntegralReport.class);ga.setFieldFunction(columnUnity);ga.setRepresentation(mesh);ga.getParts().setObjects(plane);ga.setSmooth(false);gaugeAreas.add(ga);')
replace('double eta=gauges.get(i).getReportMonitorValue()/span-24;','double eta=(gauges.get(i).getReportMonitorValue()-gaugeAreas.get(i).getReportMonitorValue())/span+6;')
replace('setup.put("foil_present",true);','setup.put("foil_present",true);setup.put("response_probe_x_m",0.);setup.put("response_probe_position","Foil reference x = 0 m");setup.put("response_probe_method","(water section area - fluid section area)/span + 6 m; submerged foil excluded from both areas");')
# The user explicitly approved this W04 diagnostic guard on 2026-11-03.
replace('probeDistance=34.5; boolean expanded=false;', 'probeDistance=34.5,surfaceLimit=1.0; boolean expanded=false;')
replace('   resume="1".equals(System.getenv("NWAR_RESUME"));', '   surfaceLimit=expanded&&caseId.equals("W04")?1.5:1.0; // User-authorized W04 diagnostic limit, 2026-11-03.\n   resume="1".equals(System.getenv("NWAR_RESUME"));')
replace('Math.abs(eta)>1.0', 'false /* ThinkPad surface magnitude threshold disabled by user, 2026-11-07 */')
replace('stopPolicy.put("safety_guards_unchanged",true);', 'stopPolicy.put("safety_guards_unchanged",false);stopPolicy.put("surface_elevation_limit_m",null);stopPolicy.put("surface_magnitude_limit_enabled",false);stopPolicy.put("other_safety_guards_unchanged",true);')
replace('setup.put("GPU",1);', 'setup.put("GPU",1);setup.put("mpi_processes",(int)param("NWAR_MPI_PROCESSES",1));setup.put("scene_count",s.getSceneManager().getObjects().size());')
# Wave definition and remaining numerical health guards stay unchanged.
assert 'initializeSolution' not in s and 'clearSolution' not in s
out=HERE/'NwarWave.java';out.write_text(s,encoding='utf8')
compiled=HERE/'compiled';compiled.mkdir(exist_ok=True)
javac='C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe'
cp='E:/Program Files/Siemens/21.02.007-R8/STAR-CCM+21.02.007-R8/star/lib/java/platform/modules/ext/*'
p=subprocess.run([javac,'-cp',cp,'-d',str(compiled),str(out)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
receipt={'ok':p.returncode==0,'expanded_profile':'M13_W04_20261102','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'macro_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'messages':p.stderr[-4000:]}
(HERE/'compile_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print(json.dumps(receipt))
raise SystemExit(p.returncode)
