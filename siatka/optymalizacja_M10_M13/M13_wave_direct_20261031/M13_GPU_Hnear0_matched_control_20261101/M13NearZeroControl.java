package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import star.flow.*;import star.vof.*;import star.vis.*;import star.post.*;
import java.nio.file.*;import java.util.*;
/** Isolated GPU M13: accepted calm -> inlet wave. Never reinitialize, remesh, or modify source .sim. */
public class M13NearZeroControl extends StarMacro {
 Simulation s;Path out;Region reg;FvRepresentation mesh;
 ForceReport fx,fz,fp,fv;MaxReport vmax,cfl,amax,pmax;MinReport amin,pmin;
 VolumeIntegralReport water;ArrayList<SurfaceIntegralReport> gauges=new ArrayList<>();
 double t0,dt,period,ramp,H=.000001,lambda=20.,water0;
 final double buoyancy=22.718189111947265,coeffDen=3855.6,span=.02;
 final double[] locations={-34.,-25.,-15.,-10.,-6.,5.,10.,20.,40.};
 String json(Object o){
  if(o==null)return "null";
  if(o instanceof Number)return Double.isFinite(((Number)o).doubleValue())?o.toString():"null";
  if(o instanceof Boolean)return o.toString();
  if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(Object x:((Map<?,?>)o).entrySet()){Map.Entry<?,?> e=(Map.Entry<?,?>)x;j.add(json(e.getKey().toString())+":"+json(e.getValue()));}return j.toString();}
  return "\""+o.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n")+"\"";
 }
 void save(String file,Map<String,?> info)throws Exception{Files.writeString(out.resolve(file),json(info)+"\n");}
 ForceReport force(String n,double x,double z,ForceReportForceOption.Type t){
  ForceReport r=s.getReportManager().createReport(ForceReport.class);r.setPresentationName(n);
  r.getParts().setObjects(reg.getBoundaryManager().getBoundary("HF_012_wall"));r.setRepresentation(mesh);
  r.getForceOption().setSelected(t);r.getDirection().setComponents(x,0,z);return r;
 }
 MaxReport max(String name,FieldFunction field,NamedObject obj){
  MaxReport r=s.getReportManager().createReport(MaxReport.class);r.setPresentationName(name);
  r.setFieldFunction(field);r.setRepresentation(mesh);r.getParts().setObjects(obj);return r;
 }
 MinReport min(String name,FieldFunction field){
  MinReport r=s.getReportManager().createReport(MinReport.class);r.setPresentationName(name);
  r.setFieldFunction(field);r.setRepresentation(mesh);r.getParts().setObjects(reg);return r;
 }
 FieldFunction waveFn(VofWave w,String pref){
  for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getPresentationName().equals(pref+w.getPresentationName()))return f;
  throw new IllegalStateException("Missing wave FieldFunction: "+pref);
 }
 void stopCheck(){if(Files.exists(out.resolve("STOP"))||Files.exists(out.getParent().resolve("STOP_ALL"))||
  Files.exists(Paths.get("E:/ntnu_mesh_optimization_20261030/STOP_ALL"))||
  Files.exists(Paths.get("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL")))
   throw new IllegalStateException("STOP requested");}
 double[] forces(){
  double d=fx.getReportMonitorValue(),l=fz.getReportMonitorValue(),p=fp.getReportMonitorValue(),v=fv.getReportMonitorValue();
  if(!Double.isFinite(d)||!Double.isFinite(l)||!Double.isFinite(p)||!Double.isFinite(v)||Math.abs(d-p-v)>1e-5*Math.max(1,Math.abs(d)))
   throw new IllegalStateException("Nonfinite/inconsistent foil forces");
  return new double[]{d,l,p,v};
 }

 private final ArrayList<double[]> controlSamples=new ArrayList<>();
 private int controlPasses=0;
 private boolean controlSettled=false;
 private void controlSample(int step,double t,double cl,double cd,double p,double v)throws Exception{
  if(step<=0)return;
  controlSamples.add(new double[]{t,cl,cd,p/coeffDen,v/coeffDen});
  int n=(int)Math.round(.2/dt);while(controlSamples.size()>2*n)controlSamples.remove(0);
  if(step%n!=0||controlSamples.size()!=2*n)return;
  Map<String,Object> result=new LinkedHashMap<>();boolean pass=true;
  double[] oldMean=new double[5],newMean=new double[5];
  for(int col=1;col<=4;col++){
   double a=0,b=0,sa=0,sb=0;
   for(int i=0;i<n;i++){a+=controlSamples.get(i)[col]/n;b+=controlSamples.get(i+n)[col]/n;}
   for(int i=0;i<n;i++){sa+=Math.pow(controlSamples.get(i)[col]-a,2)/n;sb+=Math.pow(controlSamples.get(i+n)[col]-b,2)/n;}
   oldMean[col]=a;newMean[col]=b;
   double shift=100*Math.abs(b-a)/Math.max(Math.abs(b),1e-30);
   double rmsA=100*Math.sqrt(sa)/Math.max(Math.abs(a),1e-30),rmsB=100*Math.sqrt(sb)/Math.max(Math.abs(b),1e-30);
   boolean ok=Double.isFinite(shift)&&Double.isFinite(rmsA)&&Double.isFinite(rmsB)&&Math.abs(a)>1e-10&&Math.abs(b)>1e-10&&shift<.5&&rmsA<.5&&rmsB<.5;
   if(col<=2)pass&=ok;
   result.put(new String[]{"","CL_hydrodynamic","CD_total","CD_pressure_diagnostic","CD_viscous_diagnostic"}[col],Map.of("mean_previous",a,"mean_latest",b,"mean_shift_pct",shift,"rms_previous_pct",rmsA,"rms_latest_pct",rmsB,"pass",ok));
  }
  boolean eligible=step>=6000;
  controlPasses=eligible&&pass?controlPasses+1:0;controlSettled=controlPasses>=2;
  double dp=newMean[3]-oldMean[3],dv=newMean[4]-oldMean[4],norm=Math.max(Math.abs(newMean[2]),1e-30);
  result.put("time_s",t);result.put("step",step);result.put("window_s",.2);
  result.put("primary_pass",pass);result.put("eligible_after2p4s",eligible);result.put("consecutive_eligible_passes",controlPasses);
  result.put("component_abs_sum_over_totalCD",(Math.abs(dp)+Math.abs(dv))/norm);result.put("component_opposing_sign",dp*dv<0);
  result.put("physical_equivalence_accepted",false);result.put("note","Project CL/CD settling only. Must compare against saved calm; continued relaxation is not separated from a boundary mismatch.");
  Files.writeString(out.resolve("control_settling_checks.jsonl"),json(result)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
  save("control_settling_latest.json",result);
 }
 private boolean spatialAttempted=false;
 private void narrowSpatialRead(int step,double t){
  if(step!=10||spatialAttempted)return;spatialAttempted=true;
  Map<String,Object> result=new LinkedHashMap<>();result.put("step",step);result.put("time_s",t);result.put("read_only_reports",true);
  try{
   FieldFunction pos=s.getFieldFunctionManager().getFunction("Position").getComponentFunction(0);
   ThresholdPart zone=s.getPartManager().createThresholdPart();zone.getInputParts().setObjects(reg);zone.setFieldFunction(pos);zone.setRange(new DoubleVector(new double[]{-2,3}));zone.setMode(ThresholdMode.BETWEEN_TAG);
   int valid=0;
   for(FieldFunction field:s.getFieldFunctionManager().getObjects()){
    String name=field.getPresentationName();
    if(!name.equals("Forcing Strength Indicator")&&!name.equals("Damping Strength Indicator"))continue;
    MaxReport r=max("H0 local diagnostic "+name,field,zone);double value=r.getReportMonitorValue();
    boolean available=Double.isFinite(value)&&Math.abs(value)<1e100;
    result.put(name,Map.of("raw_max",value,"available",available));if(available)valid++;
   }
   result.put("valid_indicators",valid);result.put("automatic_acceptance",false);
  }catch(Exception ex){result.put("diagnostic_error",ex.toString());result.put("automatic_acceptance",false);}
  try{save("narrow_forcing_after_steps.json",result);}catch(Exception ignored){}
 }

 public void execute(){
  s=getActiveSimulation();out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_M13_WAVE_OUT"))).toAbsolutePath().normalize();
  try{
   String isolate="E:/ntnu_mesh_optimization_20261030/M13_wave_direct_20261031/";
   if(!out.toString().replace("\\","/").startsWith(isolate)||!s.getSessionPath().replace("\\","/").equals(out.resolve("input.sim").toString().replace("\\","/")))
    throw new IllegalStateException("Disposable M13 input/output identity mismatch");
   if(Files.exists(out.resolve("history.csv")))throw new IllegalStateException("Existing attempt; never overwrite");
   if(s.getNumberOfGpgpus()!=1)throw new IllegalStateException("Exactly one GPU required");
   dt=Double.parseDouble(System.getenv("NTNU_M13_WAVE_DT"));
   int steps=Integer.parseInt(System.getenv("NTNU_M13_WAVE_STEPS")),inner=Integer.parseInt(System.getenv("NTNU_M13_WAVE_INNER"));
   double budget=Double.parseDouble(System.getenv("NTNU_M13_WAVE_BUDGET"));
   if(dt!=.0004||inner!=10||steps!=10000||budget<600||budget>10000)throw new IllegalStateException("Pilot settings outside contract");
   stopCheck();reg=s.getRegionManager().getRegion("fluid");mesh=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(mesh.getCellCount()!=309441)throw new IllegalStateException("Wrong M13 mesh");
   t0=s.getSolution().getPhysicalTime();
   if(Math.abs(t0-3.8992)>1e-7)throw new IllegalStateException("Accepted M13 calm checkpoint mismatch");
   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   VofWaveModel wm=(VofWaveModel)pc.getModelManager().getModel(VofWaveModel.class);
   FlatVofWave calm=(FlatVofWave)wm.getVofWaveManager().getVofWave("Calm");
   if(!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(calm))
    throw new IllegalStateException("Wave already active in M13 source");
   if(!String.valueOf(reg.getBoundaryManager().getBoundary("DOMAIN.outlet").getConditions().get(BackflowSpecification.class).getReversedFlowPressureOption().getSelectedElement()).equals("ENVIRONMENTAL"))
    throw new IllegalStateException("Outlet backflow setting unexpected");
   s.getSimulationIterator().getAutoSave().setEnabled(false);s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
   for(SolutionHistory h:s.get(SolutionHistoryManager.class).getSolutionHistories())h.setAutoRecord(false);
   for(Monitor m:s.getMonitorManager().getObjects())if(m instanceof ReportMonitor)((ReportMonitor)m).setEnabled(false);
   for(Report r:s.getReportManager().getObjects())if(r instanceof ForceReport){((ForceReport)r).getParts().setObjects(reg.getBoundaryManager().getBoundary("HF_012_wall"));((ForceReport)r).setRepresentation(mesh);}
   fx=force("Wave_M13_Fx",1,0,ForceReportForceOption.Type.PRESSURE_AND_SHEAR);fz=force("Wave_M13_Fz",0,1,ForceReportForceOption.Type.PRESSURE_AND_SHEAR);
   fp=force("Wave_M13_FxPressure",1,0,ForceReportForceOption.Type.PRESSURE);fv=force("Wave_M13_FxViscous",1,0,ForceReportForceOption.Type.SHEAR);
   FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater"),pressure=s.getFieldFunctionManager().getFunction("Pressure");
   vmax=max("Wave_M13_MaxVelocity",s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction(),reg);
   cfl=max("Wave_M13_CFL",s.getFieldFunctionManager().getFunction("CourantNumber"),reg);
   amin=min("Wave_M13_MinAlpha",alpha);amax=max("Wave_M13_MaxAlpha",alpha,reg);
   pmin=min("Wave_M13_MinPressure",pressure);pmax=max("Wave_M13_MaxPressure",pressure,reg);
   water=s.getReportManager().createReport(VolumeIntegralReport.class);water.setFieldFunction(alpha);water.setRepresentation(mesh);water.getParts().setObjects(reg);
   double[] f0=forces();water0=water.getReportMonitorValue();
   if(!Double.isFinite(water0)||water0<30||water0>45||!Double.isFinite(vmax.getReportMonitorValue())||vmax.getReportMonitorValue()>50)
    throw new IllegalStateException("Unhealthy M13 calm checkpoint");
   for(double x:locations){
    PlaneSection plane=s.getPartManager().createPlaneSection();plane.getInputParts().setObjects(reg);
    plane.setOrigin(new DoubleVector(new double[]{x,.01,2}));plane.setOrientation(new DoubleVector(new double[]{1,0,0}));
    SurfaceIntegralReport g=s.getReportManager().createReport(SurfaceIntegralReport.class);g.setFieldFunction(alpha);g.setRepresentation(mesh);g.getParts().setObjects(plane);g.setSmooth(false);gauges.add(g);
   }
   wm.setEnableTheoryComparison(true);
   FifthOrderVofWave wave=wm.getVofWaveManager().createVofWave(FifthOrderVofWave.class,"M13_Matched_NearZero_Inlet_Control");
   wave.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);
   wave.getVofWaveSpecification().getWaveLength().setValue(lambda);wave.getWaterDepth().setValue(24);
   wave.getWaveHeight().setValue(H);wave.getPointOnLevel().setComponents(0,0,2);
   wave.getVerticalDirection().setComponents(0,0,1);wave.getAdvancingDirection().setComponents(1,0,0);
   wave.getCurrent().setComponents(18,0,0);wave.getWind().setComponents(18,0,0);wave.setFirstWaveFront(false);
   double rawPeriodBeforeBinding=wave.getWavePeriod().getValue();
   // The STAR wave period may not be initialized until the inlet functions are bound.
   // Use a separately labeled linear dispersion estimate ONLY for the 2-period inlet-ramp duration.
   // The FifthOrder wave object itself still defines all imposed wave physics.
   period=20.0/23.612;
   if(!Double.isFinite(period)||period<.5||period>1.5)throw new IllegalStateException("Invalid analytic startup period");
   save("wave_period_initial_audit.json",Map.of("native_period_before_binding_s",rawPeriodBeforeBinding,
     "ramp_planning_period_s",period,"lambda_m",lambda,"reason","Native period not reliable before wave bindings; not a statement of physical wave period validity"));
   ramp=2*period;String tau="min(1.0,max(0.0,($Time-<"+t0+" s>)/<"+ramp+" s>))";
   wave.getWaveHeight().setDefinition("<0.000001 m>+<0.0 m>*0.5*(1.0-cos(3.141592653589793*"+tau+"))");
   Boundary inlet=reg.getBoundaryManager().getBoundary("DOMAIN.inlet");
   inlet.getValues().get(VelocityProfile.class).setMethod(FunctionVectorProfileMethod.class);
   inlet.getValues().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).setFieldFunction(waveFn(wave,"Velocity of "));
   VolumeFractionProfile vp=inlet.getValues().get(VolumeFractionProfile.class);
   vp.setMethod(CompositeNMinus1ArrayProfileMethod.class);
   vp.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).setMethod(FunctionScalarProfileMethod.class);
   vp.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(waveFn(wave,"Volume Fraction of Heavy Fluid of "));
   reg.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(wave);
   if(!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(wave))throw new IllegalStateException("Wave not activated");
   for(Object x:s.getSolverStoppingCriterionManager().getChildren()){
    if(x instanceof PhysicalTimeStoppingCriterion||x instanceof StepStoppingCriterion)((SolverStoppingCriterion)x).setIsUsed(false);
    if(x instanceof InnerIterationStoppingCriterion){((InnerIterationStoppingCriterion)x).setMaximumNumberInnerIterations(inner);((SolverStoppingCriterion)x).setIsUsed(true);}
   }
   ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
   us.getTimeStep().setValue(dt);us.getTimeDiscretizationOption().setSelected(TimeDiscretizationOption.Type.SECOND_ORDER);
   Map<String,Object> setup=new LinkedHashMap<>();setup.put("source","M13 accepted calm final.sim; source copy only");
   setup.put("cells",309441);setup.put("foil_present",true);setup.put("wave_inlet_only",true);setup.put("experiment_type","matched_nearzero_wave_control");setup.put("not_wave_propagation_test",true);setup.put("forcing_spatial_proof_pending",true);
   setup.put("t0",t0);setup.put("dt_s",dt);setup.put("GPU",1);setup.put("lambda_m",lambda);setup.put("H_m",H);setup.put("wave_period_s",period);
   setup.put("ramp_s",ramp);setup.put("period_for_ramp_is_estimate",true);setup.put("control_H_m",H);setup.put("control_min_duration_s",2.4);setup.put("control_max_duration_s",4.0);setup.put("water0_m3",water0);
   setup.put("CL_hydro_pre_switch",(f0[1]-buoyancy)/coeffDen);setup.put("CD_pre_switch",f0[0]/coeffDen);
   setup.put("global_initialization",false);setup.put("scientific_accepted",false);
   setup.put("pressure_top","M13 original unchanged");save("wave_setup_audit.json",setup);
   s.saveState(out.resolve("wave_bound_pre_step.sim").toString());
   long startWall=System.nanoTime();int count=0;String endState="target_reached";
   try(var hist=Files.newBufferedWriter(out.resolve("history.csv"));var gauge=Files.newBufferedWriter(out.resolve("gauges.csv"))){
    hist.write("time_s,step,wall_s,CL_hydrodynamic,CD_total,Fx_N,Fz_N,Fx_pressure_N,Fx_viscous_N,max_CFL,max_speed_m_s,water_volume_m3,alpha_min,alpha_max,p_min_Pa,p_max_Pa,target_H_m\n");hist.flush();
    gauge.write("time_s,x_m,eta_actual_m\n");gauge.flush();
    for(int step=0;step<=steps;step++){
     stopCheck();if(step>0){s.getSimulationIterator().step(1);count=step;}
     double t=s.getSolution().getPhysicalTime(),elapsed=(System.nanoTime()-startWall)*1e-9;
     double[] f=forces();double v=vmax.getReportMonitorValue(),CFL=cfl.getReportMonitorValue(),w=water.getReportMonitorValue();
     double a=amin.getReportMonitorValue(),A=amax.getReportMonitorValue(),p=pmin.getReportMonitorValue(),P=pmax.getReportMonitorValue(),h=wave.getWaveHeight().getValue();
     double cl=(f[1]-buoyancy)/coeffDen,cd=f[0]/coeffDen;
     hist.write(t+","+step+","+elapsed+","+cl+","+cd+","+f[0]+","+f[1]+","+f[2]+","+f[3]+","+CFL+","+v+","+w+","+a+","+A+","+p+","+P+","+h+"\n");hist.flush();
     if(!Double.isFinite(t)||!Double.isFinite(CFL)||!Double.isFinite(v)||!Double.isFinite(w)||!Double.isFinite(a)||!Double.isFinite(A)||!Double.isFinite(p)||!Double.isFinite(P)||
      !Double.isFinite(h)||CFL>25||v>50||a<-.00001||A>1.00001||Math.abs(w-water0)>1.0||p< -1e7||P>1e7||Math.abs(t-t0-step*dt)>dt*.2)
      throw new IllegalStateException("M13 pilot numerical/VOF guard at step "+step);
     controlSample(step,t,cl,cd,f[2],f[3]);narrowSpatialRead(step,t);
     if(step%10==0){
      for(int i=0;i<locations.length;i++){double eta=gauges.get(i).getReportMonitorValue()/span-24;
       if(Double.isFinite(eta)&&Math.abs(eta)<1.5)gauge.write(t+","+locations[i]+","+eta+"\n");}
      gauge.flush();
      Map<String,Object> pg=new LinkedHashMap<>();
      pg.put("step",step);pg.put("t_s",t);pg.put("CL_hydro",cl);pg.put("CD_total",cd);pg.put("CFL",CFL);pg.put("water_m3",w);pg.put("max_speed_m_s",v);
      pg.put("target_height_m",h);pg.put("arrival","NEARZERO_CONTROL_NO_WAVE_ARRIVAL_CLAIM");save("progress.json",pg);
     }
     if(step>0&&step%1000==0)s.saveState(out.resolve(String.format(Locale.ROOT,"checkpoint_t%.4f.sim",t)).toString());
     if(controlSettled){endState="control_primary_settled";break;}
     if(elapsed>budget){endState="wall_budget";break;}
    }
   }
   s.saveState(out.resolve("wave_pilot_final.sim").toString());
   save("completed.json",Map.of("status",endState,"steps",count,"time_s",s.getSolution().getPhysicalTime(),"propagation_validated",false,"periodic_forces_validated",false,"global_initialization",false));
  }catch(Exception err){try{save("macro_error.json",Map.of("error",err.toString(),"at",java.time.OffsetDateTime.now().toString()));}catch(Exception ignore){}throw new RuntimeException(err);}
 }
}
