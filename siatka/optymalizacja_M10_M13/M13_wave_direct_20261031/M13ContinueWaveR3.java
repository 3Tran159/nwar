package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import star.flow.*;import star.vof.*;import star.vis.*;import star.post.*;
import java.nio.file.*;import java.util.*;
/** Isolated GPU M13: accepted calm -> inlet wave. Never reinitialize, remesh, or modify source .sim. */
public class M13ContinueWaveR3 extends StarMacro {
 Simulation s;Path out;Region reg;FvRepresentation mesh;
 ForceReport fx,fz,fp,fv;MaxReport vmax,cfl,amax,pmax;MinReport amin,pmin;
 VolumeIntegralReport water;ArrayList<SurfaceIntegralReport> gauges=new ArrayList<>();
 double t0,dt,period,ramp,H=.5,lambda=20.,water0;
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
   if(dt!=.0004||inner!=10||steps<400||steps>12000||budget<600||budget>14400)throw new IllegalStateException("Pilot settings outside contract");
   stopCheck();reg=s.getRegionManager().getRegion("fluid");mesh=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(mesh.getCellCount()!=309441)throw new IllegalStateException("Wrong M13 mesh");
   t0=s.getSolution().getPhysicalTime();
   double requiredTime=Double.parseDouble(System.getenv("NTNU_M13_WAVE_START_T"));
   if(Math.abs(t0-requiredTime)>dt*.1||t0<=3.8992)
    throw new IllegalStateException("Continuation checkpoint physical time mismatch");
   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   VofWaveModel wm=(VofWaveModel)pc.getModelManager().getModel(VofWaveModel.class);
   ManagedVofWave sourceWave=reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
   if(!(sourceWave instanceof FifthOrderVofWave)||
       !sourceWave.getPresentationName().contains("M13_Exploratory_Inlet_W20_H050"))
    throw new IllegalStateException("Continuation requires source M13 FifthOrder inlet wave");
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
   // Preserve the already-computed wave, current, inlet forcing, and VOF field unchanged.
   FifthOrderVofWave wave=(FifthOrderVofWave)sourceWave;
   period=20.0/23.612; ramp=2*period;
   if(wave.getWaveHeight().getDefinition()==null||
      !wave.getWaveHeight().getDefinition().contains("$Time"))
    throw new IllegalStateException("Original upstream ramp definition missing");
   Boundary inlet=reg.getBoundaryManager().getBoundary("DOMAIN.inlet");
   if(!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(wave))
    throw new IllegalStateException("Continuation lost original wave binding");
   for(Object x:s.getSolverStoppingCriterionManager().getChildren()){
    if(x instanceof PhysicalTimeStoppingCriterion||x instanceof StepStoppingCriterion)((SolverStoppingCriterion)x).setIsUsed(false);
    if(x instanceof InnerIterationStoppingCriterion){((InnerIterationStoppingCriterion)x).setMaximumNumberInnerIterations(inner);((SolverStoppingCriterion)x).setIsUsed(true);}
   }
   ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
   us.getTimeStep().setValue(dt);us.getTimeDiscretizationOption().setSelected(TimeDiscretizationOption.Type.SECOND_ORDER);
   Map<String,Object> setup=new LinkedHashMap<>();setup.put("source","M13 foil+wave already-computed checkpoint; copied and continued");
   setup.put("cells",309441);setup.put("foil_present",true);setup.put("wave_inlet_only",true);
   setup.put("t0",t0);setup.put("original_inlet_activation_s",3.899199999999636);setup.put("dt_s",dt);setup.put("GPU",1);setup.put("lambda_m",lambda);setup.put("H_m",H);setup.put("wave_period_s",period);
   setup.put("ramp_s",ramp);setup.put("water0_m3",water0);
   setup.put("CL_hydro_at_continuation",(f0[1]-buoyancy)/coeffDen);setup.put("CD_at_continuation",f0[0]/coeffDen);
   setup.put("global_initialization",false);setup.put("inlet_wave_rebound",false);setup.put("scientific_accepted",false);
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
     if(step%10==0){
      for(int i=0;i<locations.length;i++){double eta=gauges.get(i).getReportMonitorValue()/span-24;
       if(Double.isFinite(eta)&&Math.abs(eta)<1.5)gauge.write(t+","+locations[i]+","+eta+"\n");}
      gauge.flush();
      Map<String,Object> pg=new LinkedHashMap<>();
      pg.put("step",step);pg.put("t_s",t);pg.put("CL_hydro",cl);pg.put("CD_total",cd);pg.put("CFL",CFL);pg.put("water_m3",w);pg.put("max_speed_m_s",v);
      pg.put("target_height_m",h);pg.put("arrival","NOT_YET_CONFIRMED");save("progress.json",pg);
     }
     if(step>0&&step%1000==0)s.saveState(out.resolve(String.format(Locale.ROOT,"checkpoint_t%.4f.sim",t)).toString());
     if(elapsed>budget){endState="wall_budget";break;}
    }
   }
   s.saveState(out.resolve("wave_pilot_final.sim").toString());
   save("completed.json",Map.of("status",endState,"steps",count,"time_s",s.getSolution().getPhysicalTime(),"propagation_validated",false,"periodic_forces_validated",false,"global_initialization",false));
  }catch(Exception err){try{save("macro_error.json",Map.of("error",err.toString(),"at",java.time.OffsetDateTime.now().toString()));}catch(Exception ignore){}throw new RuntimeException(err);}
 }
}
