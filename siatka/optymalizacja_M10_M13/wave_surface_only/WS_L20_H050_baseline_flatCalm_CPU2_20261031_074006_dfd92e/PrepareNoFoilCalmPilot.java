package macro;
import star.common.*;
import star.base.neo.*;
import star.base.report.*;
import star.flow.*;
import star.vof.*;
import star.vis.*;
import star.post.*;
import java.nio.file.*;
import java.util.*;

/** Separate CPU-only flat-water no-foil preflight on a disposable exact-mesh source. */
public class PrepareNoFoilCalmPilot extends StarMacro {
 private Simulation s;
 private Path out;
 private Region fluid;
 private FvRepresentation fv;
 private double dt, startWall;
 private String json(Object x) {
  if(x==null)return "null";
  if(x instanceof Number||x instanceof Boolean)return x.toString();
  if(x instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(Object e:((Map<?,?>)x).entrySet()) {var kv=(Map.Entry<?,?>)e;j.add(json(kv.getKey().toString())+":"+json(kv.getValue()));}return j.toString();}
  if(x instanceof Iterable){StringJoiner j=new StringJoiner(",","[","]");for(Object a:(Iterable<?>)x)j.add(json(a));return j.toString();}
  return "\""+x.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";
 }
 private FieldFunction waveField(String prefix) {
  ArrayList<FieldFunction> found=new ArrayList<>();
  for(FieldFunction f:s.getFieldFunctionManager().getObjects()) {
   if(f.getPresentationName().equals(prefix+" of Calm"))found.add(f);
  }
  if(found.size()!=1)throw new IllegalStateException("Expected exactly one flat Calm field "+prefix+" of Calm; found "+found.size());
  return found.get(0);
 }
 private MaxReport max(FieldFunction ff,NamedObject part) {
  MaxReport r=s.getReportManager().createReport(MaxReport.class);
  r.setFieldFunction(ff);r.getParts().setObjects(part);r.setRepresentation(fv);return r;
 }
 private double gauge(PlaneSection pl,FieldFunction alpha){
  SurfaceIntegralReport r=s.getReportManager().createReport(SurfaceIntegralReport.class);
  r.setFieldFunction(alpha);r.getParts().setObjects(pl);r.setRepresentation(fv);r.setSmooth(false);
  double value=r.getReportMonitorValue()/.02-24.;
  s.getReportManager().removeObjects(List.of(r));
  return value;
 }
 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_NOFOIL_OUT"))).toAbsolutePath().normalize();
  try {
   Path expected=out.resolve("input.sim").toAbsolutePath().normalize();
   if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(expected))
    throw new IllegalStateException("Disposable input identity failed");
   if(Files.exists(out.resolve("history.csv")))throw new IllegalStateException("Attempt has already been used");
   if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("GPU job not permitted");
   dt=Double.parseDouble(System.getenv("NTNU_NOFOIL_DT"));
   int steps=Integer.parseInt(System.getenv("NTNU_NOFOIL_STEPS"));
   if(Math.abs(dt-.001)>1e-12||steps<200||steps>500)throw new IllegalStateException("Pilot budget/step mismatch");
   fluid=s.getRegionManager().getRegion("fluid");
   fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(fv.getCellCount()!=53200||Math.abs(s.getSolution().getPhysicalTime())>1e-10)
    throw new IllegalStateException("Expected exact L20 baseline grid with 53200 cells at t=0");
   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   VofWaveModel wm=(VofWaveModel)pc.getModelManager().getModel(VofWaveModel.class);
   FlatVofWave calm=(FlatVofWave)wm.getVofWaveManager().getVofWave("Calm");
   FieldFunction vel=waveField("Velocity"),pressure=waveField("Hydrostatic Pressure of Heavy Fluid"),frac=waveField("Volume Fraction of Heavy Fluid");
   pc.getInitialConditions().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).setFieldFunction(vel);
   pc.getInitialConditions().get(InitialPressureProfile.class).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(pressure);
   pc.getInitialConditions().get(VolumeFractionProfile.class).getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(frac);
   Boundary inlet=fluid.getBoundaryManager().getBoundary("DOMAIN.inlet");
   Boundary outlet=fluid.getBoundaryManager().getBoundary("DOMAIN.outlet");
   Boundary bottom=fluid.getBoundaryManager().getBoundary("DOMAIN.bottom");
   inlet.getValues().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).setFieldFunction(vel);
   inlet.getValues().get(VolumeFractionProfile.class).getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(frac);
   outlet.getValues().get(StaticPressureProfile.class).setMethod(FunctionScalarProfileMethod.class);
   outlet.getValues().get(StaticPressureProfile.class).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(pressure);
   outlet.getValues().get(VolumeFractionProfile.class).setMethod(CompositeNMinus1ArrayProfileMethod.class);
   outlet.getValues().get(VolumeFractionProfile.class).getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).setMethod(FunctionScalarProfileMethod.class);
   outlet.getValues().get(VolumeFractionProfile.class).getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(frac);
   outlet.getConditions().get(BackflowSpecification.class).getReversedFlowPressureOption().setSelected(ReversedFlowPressureOption.Type.ENVIRONMENTAL);
   bottom.setBoundaryType(WallBoundary.class);
   bottom.getConditions().get(WallShearStressOption.class).setSelected(WallShearStressOption.Type.SLIP);
   fluid.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(calm);
   if(!fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(calm))
    throw new IllegalStateException("Calm region forcing not selected");
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
   for(SolutionHistory h:s.get(SolutionHistoryManager.class).getSolutionHistories())h.setAutoRecord(false);
   for(Object x:s.getSolverStoppingCriterionManager().getChildren()){
    if(x instanceof PhysicalTimeStoppingCriterion||x instanceof StepStoppingCriterion)((SolverStoppingCriterion)x).setIsUsed(false);
    if(x instanceof InnerIterationStoppingCriterion){((InnerIterationStoppingCriterion)x).setMaximumNumberInnerIterations(10);((SolverStoppingCriterion)x).setIsUsed(true);}
   }
   ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
   us.getTimeStep().setValue(dt);
   us.getTimeDiscretizationOption().setSelected(TimeDiscretizationOption.Type.SECOND_ORDER);
   // The reference input is wave-filled at t=0. Clear only the DISPOSABLE copy and initialize flat calm water.
   s.getSolution().clearSolutionWithoutMeshReset();
   s.getSolution().initializeSolution();
   if(Math.abs(s.getSolution().getPhysicalTime())>1e-10)throw new IllegalStateException("Initialization unexpectedly advanced time");
   FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater");
   PlaneSection[] planes=new PlaneSection[5];double[] xs={-20.,-10.,0.,10.,20.};
   for(int j=0;j<planes.length;j++){
    planes[j]=s.getPartManager().createPlaneSection();
    planes[j].setPresentationName("IndependentFlatCalmGauge_"+j);
    planes[j].getInputParts().setObjects(fluid);
    planes[j].setOrigin(new DoubleVector(new double[]{xs[j],20.01,2.}));
    planes[j].setOrientation(new DoubleVector(new double[]{1,0,0}));
   }
   MaxReport maxVelocity=max(s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction(),fluid);
   MaxReport maxCFL=max(s.getFieldFunctionManager().getFunction("CourantNumber"),fluid);
   ThresholdPart interfacePart=s.getPartManager().createThresholdPart();
   interfacePart.getInputParts().setObjects(fluid);
   interfacePart.setFieldFunction(alpha);
   interfacePart.setRange(new DoubleVector(new double[]{.01,.99}));
   interfacePart.setMode(ThresholdMode.BETWEEN_TAG);
   MaxReport interfaceCFL=max(s.getFieldFunctionManager().getFunction("CourantNumber"),interfacePart);
   VolumeIntegralReport water=s.getReportManager().createReport(VolumeIntegralReport.class);
   water.setFieldFunction(alpha);water.getParts().setObjects(fluid);water.setRepresentation(fv);
   Map<String,Object> init=new LinkedHashMap<>();
   init.put("cells",fv.getCellCount());init.put("reinitialized_disposable_copy",true);
   init.put("wave_stage","flat calm before any inlet incident wave");
   init.put("forcing_wave",calm.getPresentationName());init.put("flat_initial_function",frac.getFunctionName());
   init.put("initial_time_s",s.getSolution().getPhysicalTime());init.put("GPU",s.getNumberOfGpgpus());
   init.put("dt_s",dt);init.put("steps_planned",steps);init.put("water_volume_m3",water.getReportMonitorValue());
   ArrayList<Double> etas=new ArrayList<>();
   for(PlaneSection p:planes)etas.add(gauge(p,alpha));
   init.put("initial_eta_m",etas);
   if(Math.abs(water.getReportMonitorValue()-38.4)>0.05)
    throw new IllegalStateException("Flat initialization water volume mismatch");
   for(double eta:etas)if(!Double.isFinite(eta)||Math.abs(eta)>0.015)
    throw new IllegalStateException("Flat initialization gauge mismatch eta="+eta);
   Files.writeString(out.resolve("initial_flat_audit.json"),json(init));
   s.saveState(out.resolve("calm_initial.sim").toString());
   long start=System.nanoTime();String status="target_reached";int done=0;
   try(var h=Files.newBufferedWriter(out.resolve("history.csv"));var g=Files.newBufferedWriter(out.resolve("gauges.csv"))) {
    h.write("time_s,step,wall_s,max_speed_m_s,max_CFL,interface_CFL,water_volume_m3\n");
    g.write("time_s,x_m,eta_actual_m\n");
    for(int step=0;step<=steps;step++){
     if(step>0){
      if(Files.exists(out.resolve("STOP"))||Files.exists(Paths.get("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL")))
      {status="stopped_by_marker";break;}
      s.getSimulationIterator().step(1);done=step;
     }
     double t=s.getSolution().getPhysicalTime(),v=maxVelocity.getReportMonitorValue(),c=maxCFL.getReportMonitorValue(),
       ci=interfaceCFL.getReportMonitorValue(),w=water.getReportMonitorValue(),elapsed=(System.nanoTime()-start)*1e-9;
     h.write(t+","+step+","+elapsed+","+v+","+c+","+ci+","+w+"\n");h.flush();
     if(!Double.isFinite(v)||!Double.isFinite(c)||!Double.isFinite(ci)||!Double.isFinite(w)||v>50||c>25||ci>1.05||Math.abs(t-step*dt)>dt*.1)
      {status="stability_guard";break;}
     if(step%10==0){
      for(int j=0;j<xs.length;j++) {
       double eta=gauge(planes[j],alpha);
       if(!Double.isFinite(eta)||Math.abs(eta)>.10){status="free_surface_guard";break;}
       g.write(t+","+xs[j]+","+eta+"\n");
      }
      g.flush();
      Files.writeString(out.resolve("progress.json"),json(Map.of("stage","no_foil_flat_calm","time_s",t,"steps",step,"wall_s",elapsed,"max_speed_m_s",v,"interface_CFL",ci)));
     }
     if(!status.equals("target_reached"))break;
     if(step>0&&step%200==0)s.saveState(out.resolve(String.format(Locale.ROOT,"checkpoint_t%.3f.sim",t)).toString());
     if(elapsed>2200){status="wall_budget";break;}
    }
   }
   s.saveState(out.resolve("calm_pilot_final.sim").toString());
   Files.writeString(out.resolve("completed.json"),json(Map.of("status",status,"time_s",s.getSolution().getPhysicalTime(),"steps",done,"stage","flat calm only; wave not activated; this alone does not certify settled calm")));
  }catch(Exception e){try{Files.writeString(out.resolve("macro_error.txt"),e.toString());}catch(Exception ignored){}throw new RuntimeException(e);}
 }
}
