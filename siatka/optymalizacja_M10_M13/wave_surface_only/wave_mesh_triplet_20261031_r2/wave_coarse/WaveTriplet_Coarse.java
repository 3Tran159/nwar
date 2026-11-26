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

/**
 * Isolated no-foil first upstream-inlet wave propagation pilot.
 * Starts at the independently saved, already-computed flat-current t=0.4 s state.
 * Never initializes, resets, clears, or modifies source .sim or old C01 wave campaign.
 * Finite physical-wave results are a diagnostic, not automatic propagation acceptance.
 */
public class WaveTriplet_Coarse extends StarMacro {
 private Simulation s;
 private Path out;
 private Region fluid;
 private FvRepresentation fv;
 private final double t0=.6, dt=.001, duration=2*.8472673206891129;
 private final double[] xs={-34.,-25.,-15.,-10.,0.,10.,20.,40.};
 private String json(Object x) {
  if(x==null)return "null";
  if(x instanceof Number){double v=((Number)x).doubleValue();return Double.isFinite(v)?x.toString():"null";}
  if(x instanceof Boolean)return x.toString();
  if(x instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(Object e:((Map<?,?>)x).entrySet()){var kv=(Map.Entry<?,?>)e;j.add(json(kv.getKey().toString())+":"+json(kv.getValue()));}return j.toString();}
  if(x instanceof Iterable){StringJoiner j=new StringJoiner(",","[","]");for(Object a:(Iterable<?>)x)j.add(json(a));return j.toString();}
  return "\""+x.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";
 }
 private void save(String name,Object x)throws Exception{
  Files.writeString(out.resolve(name),json(x)+"\n",StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);
 }
 private FieldFunction waveField(VofWave w,String prefix){
  ArrayList<FieldFunction> found=new ArrayList<>();
  for(FieldFunction f:s.getFieldFunctionManager().getObjects())
   if(f.getPresentationName().equals(prefix+w.getPresentationName()))found.add(f);
  if(found.size()!=1)throw new IllegalStateException("Wave field "+prefix+w.getPresentationName()+" count "+found.size());
  return found.get(0);
 }
 private MaxReport max(FieldFunction f,NamedObject part){
  MaxReport r=s.getReportManager().createReport(MaxReport.class);
  r.setFieldFunction(f);r.setRepresentation(fv);r.getParts().setObjects(part);return r;
 }
 private double gauge(PlaneSection p,FieldFunction a){
  SurfaceIntegralReport r=s.getReportManager().createReport(SurfaceIntegralReport.class);
  r.setFieldFunction(a);r.setRepresentation(fv);r.getParts().setObjects(p);r.setSmooth(false);
  double value=r.getReportMonitorValue()/.02-24.;
  s.getReportManager().removeObjects(List.of(r));
  return value;
 }
 private FifthOrderVofWave createWave(VofWaveModel wm){
  FifthOrderVofWave w=wm.getVofWaveManager().createVofWave(FifthOrderVofWave.class,"IndependentNoFoil_L20_H050_InletRamp");
  w.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);
  w.getVofWaveSpecification().getWaveLength().setValue(20);
  w.getWaterDepth().setValue(24);
  w.getWaveHeight().setValue(.5);
  w.getPointOnLevel().setComponents(0,0,2);
  w.getVerticalDirection().setComponents(0,0,1);
  w.getAdvancingDirection().setComponents(1,0,0);
  w.getCurrent().setComponents(18,0,0);
  w.getWind().setComponents(18,0,0);
  w.setFirstWaveFront(false);
  String tau="min(1.0,max(0.0,($Time-<0.6 s>)/<"+duration+" s>))";
  w.getWaveHeight().setDefinition("<0.000001 m>+<0.499999 m>*0.5*(1.0-cos(3.141592653589793*"+tau+"))");
  return w;
 }
 private double expectedHeight(double t){
  double tau=Math.min(1,Math.max(0,(t-t0)/duration));
  return .000001+.499999*.5*(1-Math.cos(Math.PI*tau));
 }
 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_NOFOIL_WAVE_OUT"))).toAbsolutePath().normalize();
  try {
   if(Files.exists(out.resolve("history.csv")))throw new IllegalStateException("Wave attempt already used");
   Path expected=out.resolve("input.sim").toAbsolutePath().normalize();
   if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(expected))
    throw new IllegalStateException("Input must be disposable copy in own output directory");
   if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("Second GPU not allowed");
   int steps=Integer.parseInt(System.getenv("NTNU_NOFOIL_WAVE_STEPS"));
   if(steps<3||steps>800)throw new IllegalStateException("Bounded step budget 3..800 required");
   if(Math.abs(s.getSolution().getPhysicalTime()-t0)>2e-9)
    throw new IllegalStateException("Expected physical flat-current checkpoint at t=0.4 s");
   fluid=s.getRegionManager().getRegion("fluid");
   fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(fv.getCellCount()!=41200)throw new IllegalStateException("Wrong mesh cell count");
   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   VofWaveModel wm=(VofWaveModel)pc.getModelManager().getModel(VofWaveModel.class);
   FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater");
   MaxReport maxV=max(s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction(),fluid);
   MaxReport maxCFL=max(s.getFieldFunctionManager().getFunction("CourantNumber"),fluid);
   VolumeIntegralReport water=s.getReportManager().createReport(VolumeIntegralReport.class);
   water.setFieldFunction(alpha);water.setRepresentation(fv);water.getParts().setObjects(fluid);
   PlaneSection[] probes=new PlaneSection[xs.length];
   for(int j=0;j<xs.length;j++){
    probes[j]=s.getPartManager().createPlaneSection();
    probes[j].setPresentationName("IndependentWaveGauge_x"+xs[j]);
    probes[j].getInputParts().setObjects(fluid);
    probes[j].setOrigin(new DoubleVector(new double[]{xs[j],20.01,2.0}));
    probes[j].setOrientation(new DoubleVector(new double[]{1,0,0}));
   }
   double initialVolume=water.getReportMonitorValue(),initialSpeed=maxV.getReportMonitorValue();
   ArrayList<Double> initialEta=new ArrayList<>();
   for(PlaneSection p:probes)initialEta.add(gauge(p,alpha));
   if(Math.abs(initialVolume-38.4)>.005||Math.abs(initialSpeed-18)>.05)
    throw new IllegalStateException("Computed calm baseline 18m/s, 38.4m3 mismatch");
   for(double z:initialEta)if(!Double.isFinite(z)||Math.abs(z)>.002)
    throw new IllegalStateException("Pre-wave gauge nonflat eta="+z);
   Boundary inlet=fluid.getBoundaryManager().getBoundary("DOMAIN.inlet");
   Boundary outlet=fluid.getBoundaryManager().getBoundary("DOMAIN.outlet");
   if(!String.valueOf(outlet.getConditions().get(BackflowSpecification.class).getReversedFlowPressureOption().getSelectedElement()).toLowerCase(Locale.ROOT).contains("environment"))
    throw new IllegalStateException("Unexpected outlet backflow strategy");
   if(!String.valueOf(fluid.getBoundaryManager().getBoundary("DOMAIN.bottom").getBoundaryType().getPresentationName()).equals("Wall"))
    throw new IllegalStateException("Expected bottom slip wall");
   wm.setEnableTheoryComparison(true);
   FifthOrderVofWave wave=createWave(wm);
   inlet.getValues().get(VelocityProfile.class).setMethod(FunctionVectorProfileMethod.class);
   inlet.getValues().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).setFieldFunction(waveField(wave,"Velocity of "));
   VolumeFractionProfile vp=inlet.getValues().get(VolumeFractionProfile.class);
   vp.setMethod(CompositeNMinus1ArrayProfileMethod.class);
   vp.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).setMethod(FunctionScalarProfileMethod.class);
   vp.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(waveField(wave,"Volume Fraction of Heavy Fluid of "));
   fluid.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(wave);
   if(!fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(wave))
    throw new IllegalStateException("Wave forcing target mismatch");
   ArrayList<Object> bindings=new ArrayList<>();
   for(Boundary b:fluid.getBoundaryManager().getBoundaries()){
    Map<String,Object> br=new LinkedHashMap<>();
    br.put("name",b.getPresentationName());
    br.put("forcing",String.valueOf(b.getConditions().get(VofWaveForcingBoundaryOption.class).getSelectedElement()));
    br.put("damping",String.valueOf(b.getConditions().get(VofWaveDampingBoundaryOption.class).getSelectedElement()));
    bindings.add(br);
   }
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
   ThresholdPart interfacePart=s.getPartManager().createThresholdPart();
   interfacePart.getInputParts().setObjects(fluid);
   interfacePart.setFieldFunction(alpha);
   interfacePart.setRange(new DoubleVector(new double[]{.01,.99}));
   interfacePart.setMode(ThresholdMode.BETWEEN_TAG);
   MaxReport ciReport=max(s.getFieldFunctionManager().getFunction("CourantNumber"),interfacePart);
   Map<String,Object> setup=new LinkedHashMap<>();
   setup.put("model","FifthOrderVofWave");setup.put("lambda_m",20);setup.put("target_H_m",.5);
   setup.put("startup","previously computed stable flat-current field, then incident wave at upstream inlet; no clear/initialize");
   setup.put("source_t_s",t0);setup.put("dt_s",dt);setup.put("steps",steps);setup.put("inner",10);
   setup.put("baseline_current_m_s",initialSpeed);setup.put("initial_water_volume_m3",initialVolume);
   setup.put("initial_eta_m",initialEta);setup.put("gauge_x_m",Arrays.asList(-34.,-25.,-15.,-10.,0.,10.,20.,40.));
   setup.put("wave_height_definition",wave.getWaveHeight().getDefinition());setup.put("ramp_duration_s",duration);
   setup.put("wave_boundary_bindings",bindings);setup.put("GPU",s.getNumberOfGpgpus());
   setup.put("initialization_performed",false);setup.put("surface_wave_acceptance",false);
   save("wave_setup_audit.json",setup);
   if(Math.abs(s.getSolution().getPhysicalTime()-t0)>2e-9||Math.abs(water.getReportMonitorValue()-initialVolume)>.00001)
    throw new IllegalStateException("Physical state changed before first wave step");
   s.saveState(out.resolve("wave_bound_pre_step.sim").toString());
   long start=System.nanoTime();int done=0;String status="target_reached";
   try(var h=Files.newBufferedWriter(out.resolve("history.csv"));var g=Files.newBufferedWriter(out.resolve("gauges.csv"))){
    h.write("time_s,step,wall_s,max_speed_m_s,max_CFL,interface_CFL,water_volume_m3,target_height_m,actual_wave_height_m,period_s\n");
    g.write("time_s,x_m,eta_actual_m\n");
    for(int step=0;step<=steps;step++){
     if(step>0){
      if(Files.exists(out.resolve("STOP"))||Files.exists(Paths.get("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL"))||
        Files.exists(Paths.get("E:/ntnu_mesh_optimization_20261030/STOP_ALL"))){status="stopped_by_marker";break;}
      s.getSimulationIterator().step(1);done=step;
     }
     double t=s.getSolution().getPhysicalTime(),v=maxV.getReportMonitorValue(),c=maxCFL.getReportMonitorValue(),
      ci=ciReport.getReportMonitorValue(),vol=water.getReportMonitorValue(),elapsed=(System.nanoTime()-start)*1e-9;
     double height=wave.getWaveHeight().getValue(),heightExpected=expectedHeight(t),period=wave.getWavePeriod().getValue();
     h.write(t+","+step+","+elapsed+","+v+","+c+","+ci+","+vol+","+heightExpected+","+height+","+period+"\n");h.flush();
     if(!Double.isFinite(v)||!Double.isFinite(c)||!Double.isFinite(vol)||Double.isInfinite(ci)||
       v>50||c>25||(Double.isFinite(ci)&&ci>1.05)||Math.abs(vol-initialVolume)>1.5||
       Math.abs(t-t0-step*dt)>dt*.1)
       {status="stability_guard";break;}
     if(step>0&&(!Double.isFinite(height)||Math.abs(height-heightExpected)>1e-4||
       !Double.isFinite(period)||period<.5||period>1.5)){status="wave_definition_guard";break;}
     if(step%5==0){
      double highest=0;
      for(int j=0;j<xs.length;j++){
       double eta=gauge(probes[j],alpha);
       if(!Double.isFinite(eta)||Math.abs(eta)>.8){status="gauge_guard";break;}
       highest=Math.max(highest,Math.abs(eta));
       g.write(t+","+xs[j]+","+eta+"\n");
      }
      g.flush();
      if(step%10==0){
       Map<String,Object> pg=new LinkedHashMap<>();
       pg.put("stage","nofoil_upstream_inlet_wave_ramp");pg.put("steps",step);pg.put("time_s",t);
       pg.put("max_speed_m_s",v);pg.put("max_CFL",c);
       pg.put("interface_CFL",Double.isFinite(ci)?Double.valueOf(ci):"NOT_AVAILABLE_EMPTY_THRESHOLD");
       pg.put("water_volume_m3",vol);pg.put("max_abs_gauge_eta_m",highest);
       pg.put("wave_height_m",height);pg.put("expected_wave_height_m",heightExpected);
       pg.put("wave_period_s",period);pg.put("wall_s",elapsed);
       save("progress.json",pg);
      }
     }
     if(!status.equals("target_reached"))break;
     if(step>0&&step%200==0)s.saveState(out.resolve(String.format(Locale.ROOT,"checkpoint_t%.3f.sim",t)).toString());
     if(elapsed>1800){status="wall_budget";break;}
    }
   }
   s.saveState(out.resolve("wave_pilot_final.sim").toString());
   Map<String,Object> result=new LinkedHashMap<>();
   result.put("status",status);result.put("steps",done);result.put("time_s",s.getSolution().getPhysicalTime());
   result.put("stage","incident_wave_ramp_only; no acceptance; downstream arrival not yet established");
   result.put("calm_source_preserved",true);result.put("initialization_performed",false);
   save("completed.json",result);
  }catch(Exception e){
   try{save("macro_error.json",Map.of("error",e.toString(),"time_s",s.getSolution().getPhysicalTime()));}catch(Exception ignored){}
   throw new RuntimeException(e);
  }
 }
}
