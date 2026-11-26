package macro;
import star.common.*;
import star.base.neo.*;
import star.base.report.*;
import star.flow.*;
import star.vof.*;
import star.material.*;
import star.vis.*;
import star.post.*;
import java.nio.file.*;
import java.util.*;

public class PreW04GlobalRamp extends StarMacro {
  private final double CL_OFFSET=22.718189111947265/3855.6;
  private Scene liveScene; private long lastPreview=0; private int previewIndex=0,priorCount=0;
  private Simulation s; private Path out; private Region fluid; private Boundary foil; private FvRepresentation fv;
  private MinReport yMin; private MaxReport yMax;
  private ForceReport fx,fz,pressure,shear; private MaxReport vmax,cfl,interfaceCfl; private AreaAverageReport yplus;
  private double dt,target,startTime; private final double window=.2; private int inner;
  private VolumeIntegralReport massBudget,waterBudget;private ArrayList<MassFlowReport> fluxBudget=new ArrayList<>();
  private double waterAtRestart=Double.NaN;
  private double balanceWater,balanceMass,balanceTime=Double.NaN,balanceFlux,balanceIntegral=0,expectedWater=Double.NaN;
  private double calmWaveLevelMax=Double.NaN;
  private ArrayList<String> boundaryFluxNames=new ArrayList<>();
  private ArrayList<double[]> samples=new ArrayList<>();private int consecutivePasses=0,compatiblePasses=0;private boolean compatibleNow=false;
  public void execute() {
    s=getActiveSimulation();
    out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_STAB_OUT")));
    try {
      dt=Double.parseDouble(System.getenv("NTNU_STAB_DT"));
      target=Double.parseDouble(System.getenv("NTNU_STAB_TARGET"));
      inner=Integer.parseInt(System.getenv("NTNU_STAB_INNER"));
      long expectedCells=Long.parseLong(System.getenv("NTNU_STAB_CELLS"));
      double expectedStart=Double.parseDouble(System.getenv("NTNU_STAB_START"));
      boolean initialize="true".equals(System.getenv("NTNU_STAB_INIT"));
      String order=System.getenv("NTNU_STAB_ORDER");
      double budget=Double.parseDouble(System.getenv("NTNU_STAB_BUDGET"));
      out=out.toAbsolutePath().normalize();
      if(!out.toString().replace("\\","/").startsWith("E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/PRE_W04_20261102/") ||
         !Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim")))throw new IllegalStateException("Disposable new C01 input required");
      if(dt!=.0004||inner!=10||expectedCells<=309441||expectedCells>1500000||(System.getenv().containsKey("PRE_W04_NIGHT_FALLBACK_MS")?(!Double.isFinite(target)||target<=expectedStart||target>Math.max(8.0,expectedStart+8.0)+1e-8):target!=8.0)||!order.equals("SECOND_ORDER"))throw new IllegalStateException("Clean C01 contract mismatch");
      if(Files.exists(out.resolve("history.csv"))) throw new IllegalStateException("History exists; use a new attempt directory");
      s.getSimulationIterator().getAutoSave().setEnabled(false);
      s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
      for(SolutionHistory h:s.get(SolutionHistoryManager.class).getSolutionHistories())h.setAutoRecord(false);
      for(Monitor inherited:s.getMonitorManager().getObjects())if(inherited instanceof ReportMonitor)((ReportMonitor)inherited).setEnabled(false);
      fluid=s.getRegionManager().getRegion("fluid"); foil=fluid.getBoundaryManager().getBoundary("HF_012_wall");
      fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
      // Saved expanded mesh and all physical fields are retained.
      // Rebind inherited monitors after a region was replaced by an audited CGNS import.
      for(Report rep:s.getReportManager().getObjects()){
        if(rep instanceof ForceReport){((ForceReport)rep).getParts().setObjects(foil);((ForceReport)rep).setRepresentation(fv);}
        if(rep instanceof MaxReport && rep.getPresentationName().equals("Maximum Velocity")){((MaxReport)rep).getParts().setObjects(fluid);((MaxReport)rep).setRepresentation(fv);}
      }
      if(fv.getCellCount()!=expectedCells)throw new IllegalStateException("Mesh identity mismatch: "+fv.getCellCount());
      if(s.getNumberOfGpgpus()!=1)throw new IllegalStateException("Exactly one GPU required for the accelerated mesh campaign");
      startTime=s.getSolution().getPhysicalTime();
      // Fresh initialization below resets physical time on this disposable copy only.
      PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
      FlatVofWave calm=(FlatVofWave)pc.getModelManager().getModel(VofWaveModel.class).getVofWaveManager().getVofWave("Calm");
      double rho=calm.getHeavyFluidDensity().getSIValue();
      ManagedVofWave selectedWave=fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
      if(!(selectedWave instanceof FlatVofWave)||!selectedWave.equals(calm))throw new IllegalStateException("Saved calm W01a fields required; incident wave must be inactive");
      Boundary outlet=fluid.getBoundaryManager().getBoundary("DOMAIN.outlet"),bed=fluid.getBoundaryManager().getBoundary("DOMAIN.bottom");
      if(!String.valueOf(outlet.getConditions().get(BackflowSpecification.class).getReversedFlowPressureOption().getSelectedElement()).equals("ENVIRONMENTAL")||!String.valueOf(bed.getConditions().get(WallShearStressOption.class).getSelectedElement()).equals("SLIP"))throw new IllegalStateException("W01a boundary mismatch");
      double pressureTol=s.getSolverManager().getSolver(star.segregatedflow.SegregatedFlowSolver.class).getPressureSolver().getAMGLinearSolver().getConvergeTol();
      double vofTol=s.getSolverManager().getSolver(SegregatedVofSolver.class).getAMGLinearSolver().getConvergeTol();
      if(Math.abs(pressureTol-.01)>1e-10||Math.abs(vofTol-.1)>1e-10)throw new IllegalStateException("Current W01a linear-solver settings differ");

      // Native material and wave densities are set to the original C01 contract below.
      // Preserve mapped C01 fields. Only PRE W04 history is new; C01 remains the Q reference.
      List<String> sourceScenes=new ArrayList<>();for(SceneBase scene:s.getSceneManager().getObjects())sourceScenes.add(scene.getPresentationName());
      if(initialize)configureFreshCalm(pc,calm);else verifySavedC01Calm(pc,calm);
      configureGlobalRamp(initialize);rho=1000;
      List<String> keptScenes=new ArrayList<>();for(SceneBase scene:s.getSceneManager().getObjects())keptScenes.add(scene.getPresentationName());
      if(!sourceScenes.equals(keptScenes))throw new IllegalStateException("Native scene inventory changed during initialization");
      save("scene_retention.json",Map.of("preserved",true,"source_scene_names",sourceScenes,"scene_names",keptScenes,"scene_count",keptScenes.size(),"fresh_fields",initialize));
      startTime=s.getSolution().getPhysicalTime();
      if(Math.abs(startTime-expectedStart)>1e-8||fv.getCellCount()!=expectedCells)throw new IllegalStateException("Mapped original C01 checkpoint or expanded mesh mismatch");
      ImplicitUnsteadySolver unsteady=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
      unsteady.getTimeStep().setValue(dt);
      unsteady.getTimeDiscretizationOption().setSelected(TimeDiscretizationOption.Type.valueOf(order));
      for(Object x:s.getSolverStoppingCriterionManager().getChildren()) {
        if(x instanceof PhysicalTimeStoppingCriterion||x instanceof StepStoppingCriterion)((SolverStoppingCriterion)x).setIsUsed(false);
        if(x instanceof InnerIterationStoppingCriterion) {((InnerIterationStoppingCriterion)x).setMaximumNumberInnerIterations(inner);((SolverStoppingCriterion)x).setIsUsed(true);}
      }
      fx=force("Stab_Drag",new double[]{1,0,0},ForceReportForceOption.Type.PRESSURE_AND_SHEAR);
      fz=force("Stab_Lift",new double[]{0,0,1},ForceReportForceOption.Type.PRESSURE_AND_SHEAR);
      pressure=force("Stab_PressureDrag",new double[]{1,0,0},ForceReportForceOption.Type.PRESSURE);
      shear=force("Stab_ViscousDrag",new double[]{1,0,0},ForceReportForceOption.Type.SHEAR);
      vmax=max("Stab_MaxVelocity",s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction(),fluid);
      cfl=max("Stab_MaxCFL",s.getFieldFunctionManager().getFunction("CourantNumber"),fluid);
      yplus=s.getReportManager().createReport(AreaAverageReport.class);yplus.setPresentationName("Stab_MeanYplus");
      yplus.setFieldFunction(s.getFieldFunctionManager().getFunction("WallYplus"));yplus.getParts().setObjects(foil);yplus.setRepresentation(fv);
      yMin=s.getReportManager().createReport(MinReport.class);yMax=s.getReportManager().createReport(MaxReport.class);
      for(ScalarReport r:List.of(yMin,yMax)){r.setFieldFunction(s.getFieldFunctionManager().getFunction("WallYplus"));r.getParts().setObjects(foil);r.setRepresentation(fv);}
      FieldFunction vf=null;
      for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getFunctionName().contains("VolumeFraction")&&f.getFunctionName().contains("water")) {vf=f;break;}
      if(vf==null)throw new IllegalStateException("Water volume fraction unavailable");
      ThresholdPart inter=s.getPartManager().createThresholdPart();inter.setPresentationName("Stab_Interface");
      inter.getInputParts().setObjects(fluid);inter.setFieldFunction(vf);inter.setRange(new DoubleVector(new double[]{.01,.99}));inter.setMode(ThresholdMode.BETWEEN_TAG);
      interfaceCfl=max("Stab_InterfaceCFL",s.getFieldFunctionManager().getFunction("CourantNumber"),inter);
      List<String> bounds=new ArrayList<>();
      for(Boundary b:fluid.getBoundaryManager().getBoundaries())bounds.add(b.getPresentationName()+": "+b.getBoundaryType().getClass().getName());
      Map<String,Object> audit=new LinkedHashMap<>();
      audit.put("lift_convention","hydrodynamic_lift_v1");audit.put("buoyancy_N",22.718189111947265);audit.put("preview_cadence_wall_s",120);
      audit.put("cells",fv.getCellCount());audit.put("start_time_s",startTime);audit.put("target_time_s",target);audit.put("dt_s",dt);
      audit.put("order",order);audit.put("inner_iterations",inner);audit.put("gpu_count",s.getNumberOfGpgpus());audit.put("rho",rho);
      audit.put("current",calm.getCurrentVector().toString());audit.put("wind",calm.getWindVector().toString());audit.put("waterline",calm.getPointOnLevelVector().toString());
      audit.put("boundaries",bounds);audit.put("reference_area_m2",.0238);audit.put("span_m",.02);
      audit.put("models",pc.getModelManager().getObjects().toString());audit.put("purpose","PRE W04: fresh flat water from rest, 1 s whole-domain momentum/current/wind ramp to 18 m/s, original C01 remains the sole Q reference; 0.2 s stability and 0.5% C01 gates");audit.put("fresh_fields",initialize);audit.put("air_density",1.2);audit.put("prior_history_used",false);audit.put("restart_from_saved_fields",!initialize);audit.put("C01_reference","E:/ntnu_mesh_optimization_20261030/clean_c01_campaign_20261101/C01_warm_M13_steady_rho1000_air1p2_20261101/final.sim");audit.put("startup_current_ramp_s",1.0);audit.put("settling_eligible_after_s",1.6);audit.put("constant_reference_velocity_m_s",18);audit.put("initialization","whole_domain_momentum_ramp");audit.put("observation_only",Boolean.parseBoolean(System.getenv().getOrDefault("PRE_W04_OBSERVE_ONLY","false")));audit.put("startup_acceleration_scope","whole fluid region, water and air");
      Files.writeString(out.resolve("setup.json"),json(audit));
      s.saveState(out.resolve("restart_prepared.sim").toString());
      massBudget=s.getReportManager().createReport(VolumeIntegralReport.class);massBudget.setFieldFunction(s.getFieldFunctionManager().getFunction("Density"));massBudget.getParts().setObjects(fluid);massBudget.setRepresentation(fv);
      waterBudget=s.getReportManager().createReport(VolumeIntegralReport.class);waterBudget.setFieldFunction(vf);waterBudget.getParts().setObjects(fluid);waterBudget.setRepresentation(fv);
      for(Boundary b:fluid.getBoundaryManager().getBoundaries()){MassFlowReport report=s.getReportManager().createReport(MassFlowReport.class);report.getParts().setObjects(b);report.setRepresentation(fv);fluxBudget.add(report);boundaryFluxNames.add(b.getPresentationName());}
      Files.writeString(out.resolve("conservation.csv"),"time_s,mass_kg,water_volume_m3,net_outward_mass_kg_s,inward_mass_kg_s\n");
      Files.writeString(out.resolve("boundary_flux.csv"),"time_s,boundary,mixture_mass_flow_kg_s\n");
      // Use audited source raw volume as expected reference. The loaded-field report is validated AFTER a real step.
      waterAtRestart=initialize?waterBudget.getReportMonitorValue():Double.parseDouble(System.getenv("PRE_W04_EXPECTED_WATER"));
      if(!Double.isFinite(waterAtRestart)||waterAtRestart<=0||waterAtRestart>=95.9976842322)throw new IllegalStateException("Fresh water inventory mismatch");
      save("baseline_inventory_audit.json",Map.of("water_m3",waterAtRestart,"start_time_s",startTime,"allowed_drift_m3",.25,"source_data_only",!initialize));

      Files.writeString(out.resolve("calm_audit.json"),json(Map.of("incident_wave_height_m",0,"source_wave",selectedWave.getPresentationName(),"type",selectedWave.getClass().getSimpleName(),"reinitialized",initialize,"start_time_s",startTime,"pressure_AMG_tolerance",pressureTol,"VOF_AMG_tolerance",vofTol,"GPU_count",s.getNumberOfGpgpus())));
      if(System.getenv("NTNU_STAB_PRIOR_HISTORY")!=null)throw new IllegalStateException("Different-dt prior history cannot be mixed; source history remains separate");
      prepareHealthAndGauges(vf);
      prepareGlobalVelocityProbes(vf);
      String seed=System.getenv("PRE_W04_BALANCE_SEED");
      if(seed!=null){String[] b=seed.split(",");if(b.length!=5)throw new IllegalStateException("Invalid conservation seed");
        balanceWater=Double.parseDouble(b[0]);balanceMass=Double.parseDouble(b[1]);balanceTime=Double.parseDouble(b[2]);balanceFlux=Double.parseDouble(b[3]);balanceIntegral=Double.parseDouble(b[4]);
        if(Math.abs(balanceTime-startTime)>1e-8)throw new IllegalStateException("Conservation seed time mismatch");}
      Files.writeString(out.resolve("mass_balance.csv"),"time_s,water_m3,expected_water_from_flux_m3,water_closure_error_m3,mass_closure_error_kg,integrated_net_outflow_kg\n");
      long start=System.nanoTime();int steps=0;String state="target_reached";
      try(var w=Files.newBufferedWriter(out.resolve("history.csv"));var vw=Files.newBufferedWriter(out.resolve("vof_substeps.csv"))) {
        vw.write("physical_time_s,VOF_substeps,flow_interface_CFL,flow_CFL_divided_by_substeps\n");
        w.write("wall_s,step,iteration,time_s,dt_s,Fx_N,Fz_N,pressure_drag_N,viscous_drag_N,CD_total,CL_total,max_speed_m_s,max_CFL,interface_CFL,mean_yplus,min_yplus,max_yplus,CL_hydrodynamic\n");
        if(!initialize){String boundary=Files.readString(Paths.get(System.getenv("PRE_W04_BOUNDARY_ROW"))).strip();
        if(Math.abs(Double.parseDouble(boundary.split(",")[3])-startTime)>1e-8)throw new IllegalStateException("History boundary time mismatch");
        w.write(boundary+"\n");w.flush();}
        while(s.getSolution().getPhysicalTime()<target-dt*.1) {
          if(Files.exists(out.resolve("STOP"))||Files.exists(out.getParent().resolve("STOP"))||Files.exists(out.getParent().resolve("STOP_ALL"))||Files.exists(Paths.get("E:/ntnu_mesh_optimization_20261030/STOP_ALL"))||Files.exists(Paths.get("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL"))) {state="stopped_by_marker";break;}
          if((System.nanoTime()-start)*1e-9>budget) {state="wall_budget";break;}
          double before=s.getSolution().getPhysicalTime();s.getSimulationIterator().step(1);steps++;
          double t=s.getSolution().getPhysicalTime();
          removeGlobalSourceAfterRamp(t);
          recordGlobalVelocity(steps,t);
          if(steps==1){
            double actual=inletImposedSpeed.getReportMonitorValue();
            double waterMeasured=waterBudget.getReportMonitorValue();
            save("first_step_inlet_readback.json",Map.of("time_s",t,
              "inlet_report_m_s",Double.isFinite(actual)?actual:-999,
              "water_volume_m3",Double.isFinite(waterMeasured)?waterMeasured:-999,
              "source_checkpoint_time_s",startTime,"expected_m_s",rampSpeed(t)));
            if(!Double.isFinite(actual)||Math.abs(actual-rampSpeed(t))>1e-5)throw new IllegalStateException("Actual inlet speed differs from startup ramp: "+actual);
            if(!Double.isFinite(waterMeasured)||Math.abs(waterMeasured-waterAtRestart)>.25)throw new IllegalStateException("First-step water-volume mismatch");
          }
          double d=fx.getReportMonitorValue(),l=fz.getReportMonitorValue(),p=pressure.getReportMonitorValue(),v=shear.getReportMonitorValue();
          double speed=vmax.getReportMonitorValue(),co=cfl.getReportMonitorValue(),ci=interfaceCfl.getReportMonitorValue(),yp=yplus.getReportMonitorValue();
          double wall=(System.nanoTime()-start)*1e-9,q=.5*rho*18*18*.0238;
          w.write(wall+","+steps+","+s.getSimulationIterator().getCurrentIteration()+","+t+","+dt+","+d+","+l+","+p+","+v+","+d/q+","+l/q+","+speed+","+co+","+ci+","+yp+","+yMin.getReportMonitorValue()+","+yMax.getReportMonitorValue()+","+(l/q-CL_OFFSET)+"\n");w.flush();

          int vofSteps=s.getSolverManager().getSolver(star.vof.SegregatedVofSolver.class).getSubStepCount();
          vw.write(t+","+vofSteps+","+ci+","+(ci/Math.max(1,vofSteps))+"\n");vw.flush();
          if(!Double.isFinite(d)||!Double.isFinite(l)||!Double.isFinite(speed)||!Double.isFinite(co)||Double.isInfinite(ci)||speed>50||(t>startTime+.02&&Math.abs(d)>2000)||Math.abs(d)>20000||Math.abs(l)>20000||t<=before) {state="stability_guard";break;}
          if(co>Double.parseDouble(System.getenv().getOrDefault("NTNU_GCI_MAX_CFL","1e8"))||ci>Double.parseDouble(System.getenv().getOrDefault("NTNU_GCI_INTERFACE_CFL","1e8"))){state="CFL_guard";break;}
          if(Math.abs(d-p-v)>Math.max(.01,Math.abs(d)*1e-4))throw new IllegalStateException("Pressure/shear force sum failed");
          if(steps%10==0)Files.writeString(out.resolve("progress.json"),json(Map.of("time_s",t,"steps",steps,"wall_s",wall,"CD",d/q,"CL",l/q-CL_OFFSET,"CFL",co,"interface_CFL",ci)));
          recordBudget();if(!recordHealth(steps)){state="field_health_guard";break;}
          samples.add(new double[]{t,d/q,l/q-CL_OFFSET,p/q,v/q});
          // Full force history is saved every step; no expensive live scene render.
          if(samples.size()>2*(int)Math.round(window/dt)+10)samples.remove(0);
          if(steps%Math.max(1,(int)Math.round(.5/dt))==0) {
            String name=String.format(Locale.ROOT,"checkpoint_t%.3f.sim",t);
            s.saveState(out.resolve(name).toString());
            Files.writeString(out.resolve("latest_checkpoint.json"),json(Map.of("path",out.resolve(name).toString(),"time_s",t)));
          }
          if("true".equals(System.getenv("NTNU_CALM_SETTLE"))&&Math.round(t/dt)%(int)Math.round(window/dt)==0){
            boolean pass=settlingPass();consecutivePasses=pass?consecutivePasses+1:0;
            compatiblePasses=pass&&compatibleNow?compatiblePasses+1:0;
            if(compatiblePasses>=2&&(!Boolean.parseBoolean(System.getenv().getOrDefault("PRE_W04_OBSERVE_ONLY","false"))||System.getenv().containsKey("PRE_W04_NIGHT_FALLBACK_MS"))){state="calm_gate_passed";break;}
            if(consecutivePasses>=2&&!compatibleNow&&(!Boolean.parseBoolean(System.getenv().getOrDefault("PRE_W04_OBSERVE_ONLY","false"))||(System.getenv().containsKey("PRE_W04_NIGHT_FALLBACK_MS")&&System.currentTimeMillis()>=Long.parseLong(System.getenv("PRE_W04_NIGHT_FALLBACK_MS"))))){state="stable_reference_mismatch";break;}
          }
        }
      }
      for(Object x:s.getSolverStoppingCriterionManager().getChildren())if(x instanceof PhysicalTimeStoppingCriterion) {
        ((PhysicalTimeStoppingCriterion)x).getMaximumTime().setValue(s.getSolution().getPhysicalTime()+.05);((SolverStoppingCriterion)x).setIsUsed(true);
      }
      if(state.equals("calm_gate_passed") && globalSourceEnabled)throw new IllegalStateException("Startup forcing still active at acceptance");
      if(state.equals("calm_gate_passed")){calm.getCurrent().setComponents(18,0,0);calm.getWind().setComponents(18,0,0);}
      s.saveState(out.resolve("final.sim").toString());
      Files.writeString(out.resolve("latest_checkpoint.json"),json(Map.of("path",out.resolve("final.sim").toString(),"time_s",s.getSolution().getPhysicalTime())));
      // Preserve the native checkpoint and scientific CSV evidence.
      exportFields(vf);
      XyzInternalTable vectors=s.getTableManager().createTable(XyzInternalTable.class);vectors.getParts().setObjects(fluid);vectors.setRepresentation(fv);vectors.setExtractVertexData(false);
      FieldFunction vel=s.getFieldFunctionManager().getFunction("Velocity");
      vectors.setFieldFunctions(List.of(vel.getComponentFunction(0),vel.getComponentFunction(1),vel.getComponentFunction(2),s.getFieldFunctionManager().getFunction("Pressure"),vf,s.getFieldFunctionManager().getFunction("CourantNumber")));
      vectors.extract();vectors.export(out.resolve("velocity_vectors.csv").toString());
      Files.writeString(out.resolve("EXPORT_OK.json"),json(Map.of("time_s",s.getSolution().getPhysicalTime(),"cells",fv.getCellCount(),"status",state)));
      Files.writeString(out.resolve("completed.json"),json(Map.of("status",state,"steps",steps,"time_s",s.getSolution().getPhysicalTime(),"solver_wall_s",(System.nanoTime()-start)*1e-9)));
    } catch(Exception e) {
      try {Files.writeString(out.resolve("macro_error.txt"),e.toString());}catch(Exception ignored){}
      throw new RuntimeException(e);
    }
  }


  private double rampSpeed(double t){return 18*.5*(1-Math.cos(Math.PI*Math.min(1,Math.max(0,t))));}
  private void save(String file,Map<String,?> info)throws Exception{Files.writeString(out.resolve(file),json(info)+"\n");}
  private FieldFunction flatField(String prefix){
    FieldFunction found=null;
    for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getPresentationName().equals(prefix+" of Calm")){
      if(found!=null)throw new IllegalStateException("Duplicate Calm field "+prefix);found=f;
    }
    if(found==null)throw new IllegalStateException("Missing Calm field "+prefix);return found;
  }
  private void setFraction(VolumeFractionProfile p,FieldFunction f){
    p.setMethod(CompositeNMinus1ArrayProfileMethod.class);
    ScalarProfile water=p.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0);
    water.setMethod(FunctionScalarProfileMethod.class);water.getMethod(FunctionScalarProfileMethod.class).setFieldFunction(f);
  }
  private Map<String,Object> setPhaseDensity(PhysicsContinuum pc,String name,double density){
    EulerianMultiPhaseModel multi=pc.getModelManager().getModel(EulerianMultiPhaseModel.class);
    Phase phase=multi.getPhaseManager().getPhase(name);
    if(phase==null)throw new IllegalStateException("Missing phase "+name);
    // Phase material model is discovered natively instead of assuming a liquid/gas model class.
    ArrayList<MaterialModel> candidates=new ArrayList<>();ArrayList<String> modelNames=new ArrayList<>();
    for(Model model:phase.getModelManager().getObjects()){modelNames.add(model.getClass().getName()+":"+model.getPresentationName());if(model instanceof MaterialModel)candidates.add((MaterialModel)model);}
    try{save("native_phase_models_"+name+".json",Map.of("phase",name,"models",modelNames,"material_model_count",candidates.size()));}catch(Exception ex){throw new IllegalStateException(ex);}
    if(candidates.size()!=1)throw new IllegalStateException("Expected exactly one native phase material model for "+name+"; got "+modelNames);
    Material material=candidates.get(0).getMaterial();
    ConstantDensityProperty prop=material.getMaterialProperties().getMaterialProperty(ConstantDensityProperty.class);
    if(!(prop.getMethod() instanceof ConstantMaterialPropertyMethod))throw new IllegalStateException("Unexpected nonconstant native density "+name);
    ConstantMaterialPropertyMethod method=(ConstantMaterialPropertyMethod)prop.getMethod();double before=method.getQuantity().getSIValue();
    method.getQuantity().setValue(density);double after=method.getQuantity().getSIValue();
    if(!Double.isFinite(after)||Math.abs(after-density)>1e-9)throw new IllegalStateException("Native density readback mismatch "+name);
    return Map.of("phase",name,"material",material.getPresentationName(),"density_method",method.getClass().getName(),"before_kg_m3",before,"after_kg_m3",after,"phase_index",multi.getPhaseManager().getPhaseIndex(phase));
  }
  private void verifySavedC01Calm(PhysicsContinuum pc,FlatVofWave calm)throws Exception{
    EulerianMultiPhaseModel multi=pc.getModelManager().getModel(EulerianMultiPhaseModel.class);
    Map<String,Object> audit=new LinkedHashMap<>();
    audit.put("source_fields_preserved",true);audit.put("reinitialized",false);
    audit.put("input_time_s",s.getSolution().getPhysicalTime());
    for(String name:List.of("water","air")){
      Phase ph=multi.getPhaseManager().getPhase(name);
      if(ph==null)throw new IllegalStateException("Missing saved phase "+name);
      ArrayList<MaterialModel> models=new ArrayList<>();
      for(Model mod:ph.getModelManager().getObjects())if(mod instanceof MaterialModel)models.add((MaterialModel)mod);
      if(models.size()!=1)throw new IllegalStateException("Phase material identification failed "+name);
      Material mat=models.get(0).getMaterial();
      ConstantDensityProperty property=mat.getMaterialProperties().getMaterialProperty(ConstantDensityProperty.class);
      if(!(property.getMethod() instanceof ConstantMaterialPropertyMethod))throw new IllegalStateException("Nonconstant phase density "+name);
      double nativeRho=((ConstantMaterialPropertyMethod)property.getMethod()).getQuantity().getSIValue();
      double target=name.equals("water")?1000.0:1.2;
      if(Math.abs(nativeRho-target)>1e-9)throw new IllegalStateException("Saved material rho mismatch "+name);
      audit.put(name+"_material_density_kg_m3",nativeRho);
    }
    double water=calm.getHeavyFluidDensity().getSIValue(),air=calm.getLightFluidDensity().getSIValue();
    if(Math.abs(water-1000)>1e-9||Math.abs(air-1.2)>1e-9)throw new IllegalStateException("Saved Calm wave density mismatch");
    if(!fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(calm))throw new IllegalStateException("Calm not selected in saved fluid region");
    if(!calm.getCurrent().getDefinition().equals("[<18 m/s>*0.5*(1.0-cos(3.141592653589793*min(1.0,max(0.0,$Time/<1 s>)))),<0 m/s>,<0 m/s>]")||!calm.getWind().getDefinition().equals("[<18 m/s>*0.5*(1.0-cos(3.141592653589793*min(1.0,max(0.0,$Time/<1 s>)))),<0 m/s>,<0 m/s>]"))throw new IllegalStateException("Saved startup ramp changed");
    audit.put("wave_water_density_kg_m3",water);audit.put("wave_air_density_kg_m3",air);
    audit.put("saved_current_vector",calm.getCurrentVector().toString());audit.put("saved_wind_vector",calm.getWindVector().toString());
    audit.put("start_time_s",s.getSolution().getPhysicalTime());audit.put("target_dt_s",0.0004);
    audit.put("geometry_cells",fv.getCellCount());
    save("density_configuration_audit.json",audit);
  }
  private void configureFreshCalm(PhysicsContinuum pc,FlatVofWave calm)throws Exception{
    Map<String,Object> a=new LinkedHashMap<>();a.put("input_time_s",startTime);a.put("material_water",setPhaseDensity(pc,"water",1000));a.put("material_air",setPhaseDensity(pc,"air",1.2));
    EulerianMultiPhaseModel phases=pc.getModelManager().getModel(EulerianMultiPhaseModel.class);
    if(phases.getPhaseManager().getPhaseIndex(phases.getPhaseManager().getPhase("water"))!=0)throw new IllegalStateException("Water must be first volume-fraction phase");
    a.put("Calm_rho_before",List.of(calm.getHeavyFluidDensity().getSIValue(),calm.getLightFluidDensity().getSIValue()));
    calm.setHeavyFluidDensity(1000);calm.setLightFluidDensity(1.2);calm.getPointOnLevel().setComponents(0,0,2);calm.getVerticalDirection().setComponents(0,0,1);// Same target U=18, but start quiescent and ramp smoothly over 1 physical second.
    String currentRamp="[<18 m/s>*0.5*(1.0-cos(3.141592653589793*min(1.0,max(0.0,$Time/<1 s>)))),<0 m/s>,<0 m/s>]";
    calm.getCurrent().setDefinition(currentRamp);calm.getWind().setDefinition(currentRamp);
    a.put("startup_current_ramp_s",1.0);a.put("initial_current_m_s",0.0);a.put("target_current_m_s",18.0);a.put("startup_current_definition",currentRamp);a.put("settling_eligibility_after_s",2.0);
    if(Math.abs(calm.getHeavyFluidDensity().getSIValue()-1000)>1e-9||Math.abs(calm.getLightFluidDensity().getSIValue()-1.2)>1e-9)throw new IllegalStateException("Calm density mismatch");
    pc.getReferenceValues().get(Gravity.class).setComponents(0,0,-9.81);pc.getReferenceValues().get(ReferenceAltitude.class).setComponents(0,0,2);pc.getReferenceValues().get(ReferencePressure.class).setValue(101325);
    FieldFunction velocity=flatField("Velocity"),pressure=flatField("Hydrostatic Pressure of Heavy Fluid"),fraction=flatField("Volume Fraction of Heavy Fluid");
    VelocityProfile initV=pc.getInitialConditions().get(VelocityProfile.class);initV.setMethod(FunctionVectorProfileMethod.class);initV.getMethod(FunctionVectorProfileMethod.class).setFieldFunction(velocity);
    InitialPressureProfile initP=pc.getInitialConditions().get(InitialPressureProfile.class);initP.setMethod(FunctionScalarProfileMethod.class);initP.getMethod(FunctionScalarProfileMethod.class).setFieldFunction(pressure);
    setFraction(pc.getInitialConditions().get(VolumeFractionProfile.class),fraction);
    Boundary inlet=fluid.getBoundaryManager().getBoundary("DOMAIN.inlet");VelocityProfile v=inlet.getValues().get(VelocityProfile.class);v.setMethod(FunctionVectorProfileMethod.class);v.getMethod(FunctionVectorProfileMethod.class).setFieldFunction(velocity);setFraction(inlet.getValues().get(VolumeFractionProfile.class),fraction);
    for(String name:List.of("DOMAIN.outlet","DOMAIN.top")){Boundary b=fluid.getBoundaryManager().getBoundary(name);StaticPressureProfile p=b.getValues().get(StaticPressureProfile.class);p.setMethod(FunctionScalarProfileMethod.class);p.getMethod(FunctionScalarProfileMethod.class).setFieldFunction(pressure);setFraction(b.getValues().get(VolumeFractionProfile.class),fraction);}
    fluid.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(calm);
    inlet.getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(40);
    fluid.getBoundaryManager().getBoundary("DOMAIN.outlet").getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(40);
    a.put("Calm_rho_after",List.of(calm.getHeavyFluidDensity().getSIValue(),calm.getLightFluidDensity().getSIValue()));a.put("U_m_s",18);a.put("waterline_z_m",2);a.put("gravity",pc.getReferenceValues().get(Gravity.class).getSIVector().toString());a.put("reference_pressure_Pa",pc.getReferenceValues().get(ReferencePressure.class).getSIValue());
    a.put("wave_zone_option",fluid.getConditions().get(VofWaveZoneOption.class).getSelected().toString());
    ArrayList<Object> bounds=new ArrayList<>();for(Boundary b:fluid.getBoundaryManager().getBoundaries()){
      Map<String,Object> z=new LinkedHashMap<>();z.put("boundary",b.getPresentationName());z.put("type",b.getBoundaryType().getClass().getName());z.put("forcing",b.getConditions().get(VofWaveForcingBoundaryOption.class).getSelectedElement().toString());z.put("damping",b.getConditions().get(VofWaveDampingBoundaryOption.class).getSelectedElement().toString());bounds.add(z);
    }a.put("boundaries",bounds);a.put("forcing_length_m",40);a.put("damping_length_m",40);a.put("wave_initialization",false);a.put("normalization_rho",1000);a.put("reference_area",.0238);a.put("force_denominator",3855.6);a.put("buoyancy_removed_once_N",22.718189111947265);
    save("density_configuration_audit.json",a);
    s.getSolution().clearSolution(Solution.Clear.History,Solution.Clear.Fields,Solution.Clear.Trn);
    s.getSolution().initializeSolution();
    if(Math.abs(s.getSolution().getPhysicalTime())>1e-12||fv.getCellCount()!=572176)throw new IllegalStateException("Fresh fields changed mesh or did not reset time");
    a.put("initialized_t_s",s.getSolution().getPhysicalTime());a.put("initialized",true);a.put("old_solution_and_history_cleared_on_copy_only",true);a.put("cells",fv.getCellCount());save("density_configuration_audit.json",a);
  }

  private boolean globalSourceEnabled=false;
  private UserFieldFunction globalAcceleration,globalMomentum;
  private final ArrayList<SurfaceIntegralReport> globalWaterUx=new ArrayList<>();
  private MaxReport globalSourceMax;

  private void configureGlobalRamp(boolean fresh)throws Exception{
    MomentumUserSourceOption option=fluid.getConditions().get(MomentumUserSourceOption.class);
    if(fresh && !String.valueOf(option.getSelectedElement()).equals("NONE"))
      throw new IllegalStateException("Unexpected existing momentum source; original physics must be preserved");
    for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getFunctionName().equals("NWARWholeDomainAcceleration"))globalAcceleration=(UserFieldFunction)f;
    if(globalAcceleration==null)globalAcceleration=s.getFieldFunctionManager().createFieldFunction();
    globalAcceleration.setPresentationName("NWAR whole-domain startup acceleration");
    globalAcceleration.setFunctionName("NWARWholeDomainAcceleration");
    globalAcceleration.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
    globalAcceleration.setDimensions(Dimensions.Builder().length(1).time(-2).build());
    globalAcceleration.setDefinition("($Time < <1 s>) ? (<18 m/s>*3.141592653589793/<2 s>*sin(3.141592653589793*max(0.0,$Time/<1 s>))) : <0 m/s^2>");
    option.setSelected(MomentumUserSourceOption.Type.SPECIFIED);
    MomentumUserSource source=fluid.getValues().get(MomentumUserSource.class);
    Dimensions dims=source.getDimensions();
    if(!dims.equals(Dimensions.Builder().force(1).volume(-1).build()) &&
       !dims.equals(Dimensions.Builder().mass(1).length(-2).time(-2).build()))
      throw new IllegalStateException("Momentum source is not force per volume: "+dims);
    for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getFunctionName().equals("NWARWholeDomainMomentum"))globalMomentum=(UserFieldFunction)f;
    if(globalMomentum==null)globalMomentum=s.getFieldFunctionManager().createFieldFunction();
    globalMomentum.setPresentationName("NWAR startup rho dUdt, whole fluid region");
    globalMomentum.setFunctionName("NWARWholeDomainMomentum");
    globalMomentum.getTypeOption().setSelected(FieldFunctionTypeOption.Type.VECTOR);
    globalMomentum.setDimensions(dims);
    globalMomentum.setDefinition("[$Density*${NWARWholeDomainAcceleration},0,0]");
    source.setMethod(FunctionVectorProfileMethod.class);
    source.getMethod(FunctionVectorProfileMethod.class).setFieldFunction(globalMomentum);
    MomentumUserSourceJacobianVector derivative=fluid.getValues().get(MomentumUserSourceJacobianVector.class);
    derivative.setMethod(ConstantVectorProfileMethod.class);
    derivative.getMethod(ConstantVectorProfileMethod.class).getQuantity().setComponents(0,0,0);
    globalSourceEnabled=true;
    save("global_ramp_configuration.json",Map.of(
      "scheme","rho_dUdt_whole_fluid_region","region",fluid.getPresentationName(),
      "duration_s",1.0,"target_speed_m_s",18.0,"fresh_fields",fresh,
      "acceleration_definition",globalAcceleration.getDefinition(),
      "momentum_definition",globalMomentum.getDefinition(),"momentum_dimensions",dims.toString(),
      "water_and_air",true,"force_removed_after_ramp",true));
    removeGlobalSourceAfterRamp(s.getSolution().getPhysicalTime());
  }

  private void removeGlobalSourceAfterRamp(double t)throws Exception{
    if(globalSourceEnabled && t>=1.0-1e-9){
      fluid.getConditions().get(MomentumUserSourceOption.class).setSelected(MomentumUserSourceOption.Type.NONE);
      if(!String.valueOf(fluid.getConditions().get(MomentumUserSourceOption.class).getSelectedElement()).equals("NONE"))
        throw new IllegalStateException("Startup momentum source could not be removed");
      globalSourceEnabled=false;
      save("global_ramp_completed.json",Map.of("time_s",t,"momentum_source_option","NONE",
        "extra_force_active",false,"target_speed_m_s",18.0,"C01_reference_unchanged",true));
    }
  }

  private void prepareGlobalVelocityProbes(FieldFunction alpha)throws Exception{
    UserFieldFunction waterUx=s.getFieldFunctionManager().createFieldFunction();
    waterUx.setPresentationName("NWAR water-weighted axial velocity");
    waterUx.setFunctionName("NWARWaterWeightedUx");
    waterUx.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
    waterUx.setDimensions(Dimensions.Builder().velocity(1).build());
    waterUx.setDefinition("${"+alpha.getFunctionName()+"}*$$Velocity[0]");
    for(double x:gx){
      PlaneSection plane=s.getPartManager().createPlaneSection();plane.getInputParts().setObjects(fluid);
      plane.setOrigin(new DoubleVector(new double[]{x,.02,2}));
      plane.setOrientation(new DoubleVector(new double[]{1,0,0}));
      SurfaceIntegralReport q=s.getReportManager().createReport(SurfaceIntegralReport.class);
      q.setRepresentation(fv);q.getParts().setObjects(plane);q.setFieldFunction(waterUx);q.setSmooth(false);globalWaterUx.add(q);
    }
    globalSourceMax=max("NWAR max startup force per volume",globalMomentum.getMagnitudeFunction(),fluid);
    Files.writeString(out.resolve("global_ramp_velocity.csv"),"time_s,x_m,water_mean_Ux_m_s,target_U_m_s,acceleration_m_s2,max_momentum_source_N_m3,source_enabled\n");
  }

  private void recordGlobalVelocity(int step,double t)throws Exception{
    if(step!=1 && step%10!=0)return;
    double target=rampSpeed(t),acc=t<1?18*Math.PI*.5*Math.sin(Math.PI*t):0;
    double source=globalSourceMax.getReportMonitorValue();
    for(int i=0;i<gx.length;i++){
      double area=probes.get(i).getReportMonitorValue(),ux=globalWaterUx.get(i).getReportMonitorValue()/area;
      if(!Double.isFinite(ux)||!Double.isFinite(source)||area<=0)throw new IllegalStateException("Invalid whole-domain ramp readback");
      Files.writeString(out.resolve("global_ramp_velocity.csv"),t+","+gx[i]+","+ux+","+target+","+acc+","+source+","+globalSourceEnabled+"\n",StandardOpenOption.APPEND);
    }
  }

  private MinReport alphaMin,pressureMin,densityMin;private MaxReport alphaMax,pressureMax,densityMax,inletImposedSpeed;
  private final double[] gx={-25,-10,-6,-.5,5,10,20,40};private final ArrayList<SurfaceIntegralReport> probes=new ArrayList<>();
  private MinReport minField(FieldFunction f){MinReport q=s.getReportManager().createReport(MinReport.class);q.setRepresentation(fv);q.getParts().setObjects(fluid);q.setFieldFunction(f);return q;}
  private void prepareHealthAndGauges(FieldFunction alpha)throws Exception{
    FieldFunction p=s.getFieldFunctionManager().getFunction("Pressure"),rho=s.getFieldFunctionManager().getFunction("Density");
    inletImposedSpeed=max("C01 actual imposed inlet speed",flatField("Velocity").getMagnitudeFunction(),fluid.getBoundaryManager().getBoundary("DOMAIN.inlet"));
    alphaMin=minField(alpha);alphaMax=max("C01 alphaMax",alpha,fluid);pressureMin=minField(p);pressureMax=max("C01 pressureMax",p,fluid);densityMin=minField(rho);densityMax=max("C01 densityMax",rho,fluid);
    for(double x:gx){PlaneSection plane=s.getPartManager().createPlaneSection();plane.getInputParts().setObjects(fluid);plane.setOrigin(new DoubleVector(new double[]{x,.02,2}));plane.setOrientation(new DoubleVector(new double[]{1,0,0}));SurfaceIntegralReport q=s.getReportManager().createReport(SurfaceIntegralReport.class);q.setRepresentation(fv);q.getParts().setObjects(plane);q.setFieldFunction(alpha);q.setSmooth(false);probes.add(q);}
    Files.writeString(out.resolve("gauges.csv"),"time_s,x_m,eta_actual_m\n");Files.writeString(out.resolve("field_health.csv"),"time_s,alpha_min,alpha_max,p_min_Pa,p_max_Pa,rho_min,rho_max,inlet_imposed_speed_m_s\n");
      save("pre_step_evidence.json",Map.of(
        "loaded_physical_time_s",s.getSolution().getPhysicalTime(),
        "source_checkpoint_m3",waterAtRestart,
        "field_checks_deferred_until_first_actual_step",true,
        "native_materials_verified",true,
        "fresh_global_ramp",true,
        "source_rho1000_air1p2",true));

  }
  private boolean recordHealth(int step)throws Exception{
    if(step%10!=0)return true;double t=s.getSolution().getPhysicalTime(),a=alphaMin.getReportMonitorValue(),A=alphaMax.getReportMonitorValue(),p=pressureMin.getReportMonitorValue(),P=pressureMax.getReportMonitorValue(),r=densityMin.getReportMonitorValue(),R=densityMax.getReportMonitorValue();
    Files.writeString(out.resolve("field_health.csv"),t+","+a+","+A+","+p+","+P+","+r+","+R+","+inletImposedSpeed.getReportMonitorValue()+"\n",StandardOpenOption.APPEND);
    calmWaveLevelMax=0;
    for(int i=0;i<gx.length;i++){
      double eta=probes.get(i).getReportMonitorValue()/.02-24;
      if(!Double.isFinite(eta))return false;
      calmWaveLevelMax=Math.max(calmWaveLevelMax,Math.abs(eta));
      Files.writeString(out.resolve("gauges.csv"),t+","+gx[i]+","+eta+"\n",StandardOpenOption.APPEND);
    }
    double nowWater=waterBudget.getReportMonitorValue();
    save("water_readiness.json",Map.of("time_s",t,"ramp_complete",t>=1.0-1e-9,"water_m3",nowWater,
      "initial_water_m3",balanceWater,"water_difference_m3",nowWater-balanceWater,"max_abs_eta_m",calmWaveLevelMax,
      "ready_for_wave",t>=1.0-1e-9&&Math.abs(nowWater-balanceWater)<=.25&&calmWaveLevelMax<=.75,
      "startup_level_changes_stop_solver",false));
    if(!Double.isFinite(nowWater)||!Double.isFinite(expectedWater)||Math.abs(nowWater-expectedWater)>.25){
      save("field_guard.json",Map.of("reason","water_balance_closure","time_s",t,"water_m3",nowWater,"expected_from_flux_m3",expectedWater,"error_limit_m3",.25));return false;}
    double imposedU=inletImposedSpeed.getReportMonitorValue();if(!Double.isFinite(imposedU)||Math.abs(imposedU-rampSpeed(t))>.00001)return false;
    return Double.isFinite(a)&&Double.isFinite(A)&&Double.isFinite(p)&&Double.isFinite(P)&&Double.isFinite(r)&&Double.isFinite(R)&&a>=-1e-5&&A<=1.00001&&r>=1.199&&R<=1000.01&&p>-1e7&&P<1e7;
  }

 private Scene waveLiveScene;
 private long lastFrameNanos=0;
 private int frameNumber=0,frameFailures=0;
 private MaxReport visualInterfaceCfl;
 private void prepareLiveScene(){
  try{
   FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater");
   FieldFunction vel=s.getFieldFunctionManager().getFunction("Velocity");
   PlaneSection mid=s.getPartManager().createPlaneSection();mid.setPresentationName("C01 Live midspan");
   mid.getInputParts().setObjects(fluid);mid.setOrigin(new DoubleVector(new double[]{0,.02,0}));mid.setOrientation(new DoubleVector(new double[]{0,1,0}));
   waveLiveScene=s.getSceneManager().createScene("C01 Live foil - surface - instantaneous streamlines");
   ScalarDisplayer volume=waveLiveScene.getDisplayerManager().createScalarDisplayer("Water fraction [0..1]");
   volume.setRepresentation(fv);volume.getInputParts().setObjects(mid);volume.getScalarDisplayQuantity().setFieldFunction(alpha);
   volume.getScalarDisplayQuantity().setAutoRange(false);volume.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{0,1}));
   IsoPart surface=s.getPartManager().createIsoPart();surface.setPresentationName("C01 Live alpha 0.5");
   surface.getInputParts().setObjects(fluid);surface.setFieldFunction(alpha);surface.setMode(IsoPart.SINGLE);surface.getSingleIsoValue().setValue(.5);
   PartDisplayer surfaceLine=waveLiveScene.getDisplayerManager().createPartDisplayer("Computed free surface");
   surfaceLine.setRepresentation(fv);surfaceLine.getInputParts().setObjects(surface);surfaceLine.setOutline(true);surfaceLine.setSurface(true);
   StreamPart st=s.getPartManager().createStreamPart();st.setPresentationName("C01 Live velocity streamlines");
   st.getInputParts().setObjects(fluid);st.setFieldFunction(vel);st.setMode(StreamPart.LINESEED);
   st.getLineSeed().setPoint1(new DoubleVector(new double[]{-2,.02,-.8}));st.getLineSeed().setPoint2(new DoubleVector(new double[]{-2,.02,2.9}));st.getLineSeed().setResolution(50);
   st.getIntegrator().setDirection(StreamPart.BOTH);st.getIntegrator().setMaxPropagation(24);st.getIntegrator().setMaximumNumberOfSteps(1800);
   StreamDisplayer sd=waveLiveScene.getDisplayerManager().createStreamDisplayer("Instantaneous velocity [m/s]");
   sd.setRepresentation(fv);sd.getInputParts().setObjects(st);sd.getScalarDisplayQuantity().setFieldFunction(vel.getMagnitudeFunction());
   sd.getScalarDisplayQuantity().setAutoRange(false);sd.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{0,30}));
   PartDisplayer foil=waveLiveScene.getDisplayerManager().createPartDisplayer("C01 M13 foil");foil.setRepresentation(fv);
   foil.getInputParts().setObjects(fluid.getBoundaryManager().getBoundary("HF_012_wall"));foil.setSurface(true);foil.setOutline(true);
   CurrentView view=waveLiveScene.getCurrentView();view.setProjectionMode(VisProjectionMode.PARALLEL);
   view.setFocalPoint(new DoubleVector(new double[]{4,.02,.9}));view.setPosition(new DoubleVector(new double[]{4,-100,.9}));view.setViewUp(new DoubleVector(new double[]{0,0,1}));view.setParallelScale(4.0);
   waveLiveScene.initializeAndWait();
   ThresholdPart inter=s.getPartManager().createThresholdPart();inter.setPresentationName("M13 visual interface-CFL diagnostic");
   inter.getInputParts().setObjects(fluid);inter.setFieldFunction(alpha);inter.setRange(new DoubleVector(new double[]{.01,.99}));inter.setMode(ThresholdMode.BETWEEN_TAG);
   visualInterfaceCfl=max("M13 interface-CFL read-only",s.getFieldFunctionManager().getFunction("CourantNumber"),inter);
  }catch(Exception e){waveLiveScene=null;try{save("visualization_error.json",Map.of("phase","setup","error",e.toString(),"physics_changed",false));}catch(Exception ignored){}}
 }
 private void captureLiveFrame(double t){
  if(waveLiveScene==null||frameFailures>=2)return;
  long now=System.nanoTime();if(lastFrameNanos!=0&&(now-lastFrameNanos)*1e-9<120)return;
  lastFrameNanos=now;
  try{
   String name="live_foil_wave_"+(frameNumber++%2)+".png";
   Path temp=out.resolve("live_foil_wave_pending.png"),image=out.resolve(name);
   waveLiveScene.printAndWait(temp.toString(),1,1400,700,true,false);
   String sha=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(temp)));
   Files.move(temp,image,StandardCopyOption.REPLACE_EXISTING);
   Map<String,Object> meta=new LinkedHashMap<>();meta.put("time_s",t);meta.put("image",name);meta.put("sha256",sha);
   meta.put("generated_at",java.time.OffsetDateTime.now().toString());meta.put("cadence_wall_s",120);
   meta.put("fields","water volume fraction, native alpha=0.5 surface, instantaneous velocity streamlines, C01 M13 foil");
   meta.put("render_wall_s",(System.nanoTime()-now)*1e-9);meta.put("same_solver_frame",true);meta.put("source_run",out.getFileName().toString());
   meta.put("interface_CFL",visualInterfaceCfl==null?Double.NaN:visualInterfaceCfl.getReportMonitorValue());
   Path tmp=out.resolve("live_foil_wave_frame.tmp");Files.writeString(tmp,json(meta));Files.move(tmp,out.resolve("live_foil_wave_frame.json"),StandardCopyOption.REPLACE_EXISTING);
  }catch(Exception e){frameFailures++;try{save("visualization_error.json",Map.of("phase","frame","time_s",t,"error",e.toString(),"failed_frames",frameFailures,"physics_changed",false));}catch(Exception ignored){}}
 }

  private void loadPrior()throws Exception {
    String path=System.getenv("NTNU_STAB_PRIOR_HISTORY");if(path==null||path.isBlank())return;
    List<String> lines=Files.readAllLines(Paths.get(path));if(lines.size()<2)return;
    String[] header=lines.get(0).split(",");Map<String,Integer> index=new HashMap<>();
    for(int i=0;i<header.length;i++)index.put(header[i],i);
    double previous=Double.NaN;
    for(int i=1;i<lines.size();i++){
      String[] v=lines.get(i).split(",");double t=Double.parseDouble(v[index.get("physical_time_s")]),h=Double.parseDouble(v[index.get("dt_s")]);
      if(Math.abs(h-dt)>1e-10||t>startTime+1e-8||Double.isFinite(previous)&&Math.abs(t-previous-dt)>1e-8)throw new IllegalStateException("Prior history discontinuity");
      double cd=Double.parseDouble(v[index.get("CD")]),cl=Double.parseDouble(v[index.get("CL_total")])-CL_OFFSET;
      double p=Double.parseDouble(v[index.get("pressure_drag_N")])/3855.6,vv=Double.parseDouble(v[index.get("viscous_drag_N")])/3855.6;
      samples.add(new double[]{t,cd,cl,p,vv});previous=t;priorCount++;
    }
    if(Math.abs(previous-startTime)>1e-8)throw new IllegalStateException("Prior history does not end at checkpoint");
    while(samples.size()>2*(int)Math.round(window/dt)+10)samples.remove(0);
  }
  private void setupPreview(){
    try{
      PlaneSection mid=s.getPartManager().createPlaneSection();mid.setPresentationName("Mesh live midspan");mid.getInputParts().setObjects(fluid);mid.setOrigin(new DoubleVector(new double[]{0,.02,0}));mid.setOrientation(new DoubleVector(new double[]{0,1,0}));
      liveScene=s.getSceneManager().createScene("Mesh live speed");
      ScalarDisplayer d=liveScene.getDisplayerManager().createScalarDisplayer("Speed [m/s]");d.setRepresentation(fv);d.getInputParts().setObjects(mid);d.getScalarDisplayQuantity().setFieldFunction(s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction());d.getScalarDisplayQuantity().setAutoRange(false);d.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{0,30}));
      PartDisplayer wall=liveScene.getDisplayerManager().createPartDisplayer("Foil");wall.setRepresentation(fv);wall.getInputParts().setObjects(foil);wall.setSurface(true);wall.setOutline(true);
      CurrentView cv=liveScene.getCurrentView();cv.setProjectionMode(VisProjectionMode.PARALLEL);cv.setFocalPoint(new DoubleVector(new double[]{.7,.02,0}));cv.setPosition(new DoubleVector(new double[]{.7,-100,0}));cv.setViewUp(new DoubleVector(new double[]{0,0,1}));cv.setParallelScale(.9);
      liveScene.initializeAndWait();
    }catch(Exception e){liveScene=null;try{Files.writeString(out.resolve("preview_error.txt"),e.toString());}catch(Exception ignored){}}
  }
  private void preview(double t,double drag,double lift,double p,double v){
    if(liveScene==null)return;
    long began=System.nanoTime();
    try{
      String name="live_velocity_"+(previewIndex++%2)+".png";Path image=out.resolve(name);
      liveScene.printAndWait(image.toString(),1,960,480,true,false);
      String digest=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(image)));
      Map<String,Object> meta=new LinkedHashMap<>();meta.put("time_s",t);meta.put("image",name);meta.put("sha256",digest);meta.put("field","Velocity magnitude");meta.put("units","m/s");meta.put("range",List.of(0,30));meta.put("CL",lift/3855.6-CL_OFFSET);meta.put("CD",drag/3855.6);meta.put("CD_pressure",p/3855.6);meta.put("CD_viscous",v/3855.6);meta.put("lift_convention","hydrodynamic_lift_v1");meta.put("render_wall_s",(System.nanoTime()-began)*1e-9);meta.put("cadence_wall_s",120);
      Path tmp=out.resolve("live_preview.tmp");Files.writeString(tmp,json(meta));Files.move(tmp,out.resolve("live_preview.json"),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }catch(Exception e){try{Files.writeString(out.resolve("preview_error.txt"),e.toString());}catch(Exception ignored){}}
    lastPreview=System.nanoTime();
  }

  private void recordBudget()throws Exception {
    double mass=massBudget.getReportMonitorValue(),water=waterBudget.getReportMonitorValue(),net=0,inward=0;
    for(int j=0;j<fluxBudget.size();j++){
      double f=fluxBudget.get(j).getReportMonitorValue();
      if(!Double.isFinite(f))throw new IllegalStateException("Nonfinite mass flux");
      net+=f;if(f<0)inward-=f;
      Files.writeString(out.resolve("boundary_flux.csv"),s.getSolution().getPhysicalTime()+","+boundaryFluxNames.get(j)+","+f+"\n",StandardOpenOption.APPEND);
    }
    if(!Double.isFinite(mass)||!Double.isFinite(water)||mass<=0||water<0)throw new IllegalStateException("Invalid mass/phase integral");
    Files.writeString(out.resolve("conservation.csv"),s.getSolution().getPhysicalTime()+","+mass+","+water+","+net+","+inward+"\n",StandardOpenOption.APPEND);
    double bt=s.getSolution().getPhysicalTime();
    if(Double.isNaN(balanceTime)){balanceWater=water;balanceMass=mass;}
    else{double gap=bt-balanceTime;if(Math.abs(gap-dt)>dt*.1)throw new IllegalStateException("Conservation time gap");balanceIntegral+=(net+balanceFlux)*.5*gap;}
    balanceTime=bt;balanceFlux=net;expectedWater=balanceWater-balanceIntegral/(1000.0-1.2);
    Files.writeString(out.resolve("mass_balance.csv"),bt+","+water+","+expectedWater+","+(water-expectedWater)+","+(mass-balanceMass+balanceIntegral)+","+balanceIntegral+"\n",StandardOpenOption.APPEND);
  }
  private boolean settlingPass()throws Exception{
    int n=(int)Math.round(window/dt);
    if(Math.abs(n*dt-window)>1e-10)throw new IllegalStateException("Settling window must contain an integer number of constant time steps");
    if(samples.size()<2*n)return false;
    int end=samples.size();Map<String,Object> check=new LinkedHashMap<>();boolean pass=true;compatibleNow=true;
    String[] keys={"CD","CL","CD_pressure","CD_viscous"};
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
      if(col<=2){
          pass&=ok;double reference=col==1?0.007002316911710474:0.31565950495122014;
          double deviation=100*Math.abs(latest-reference)/Math.abs(reference);
          compatibleNow &= Double.isFinite(deviation)&&deviation<=.5;
          check.put(keys[col-1]+"_C01_pct",deviation);
        }
        check.put(keys[col-1],Map.of("previous_mean",previous,"latest_mean",latest,"mean_change_pct",change,"previous_RMS_pct",rmsOld,"latest_RMS_pct",rmsNew,"latest_peak_to_peak_pct",100*(high-low)/Math.max(Math.abs(latest),1e-30),"relative_test_resolved",resolved,"pass",ok));
    }
    boolean eligible=s.getSolution().getPhysicalTime()>=1.6-1e-9;
    double inventory=waterBudget.getReportMonitorValue();
    boolean waterReady=eligible&&Double.isFinite(inventory)&&Math.abs(inventory-balanceWater)<=.25&&Double.isFinite(calmWaveLevelMax)&&calmWaveLevelMax<=.75;
    check.put("water_inventory_m3",inventory);check.put("water_difference_m3",inventory-balanceWater);
    check.put("max_abs_eta_m",calmWaveLevelMax);check.put("water_ready_for_wave",waterReady);
    pass &= waterReady;
      check.put("eligible",eligible);check.put("compatible_with_original_C01",compatibleNow);check.put("reference_CD",0.007002316911710474);check.put("reference_CL",0.31565950495122014);
      check.put("consecutive_compatible",pass&&eligible&&compatibleNow?compatiblePasses+1:0);
      pass &= eligible;
      check.put("lift_convention","hydrodynamic_lift_v1");check.put("time_s",samples.get(end-1)[0]);check.put("pass",pass);check.put("consecutive_passes",pass?consecutivePasses+1:0);
    check.put("criterion","Two full adjacent 0.2s windows; mean shift and RMS <0.5% separately for CLhydro and CDtotal; two consecutive checks 0.2s apart. Pressure/viscous diagnostic only. Fresh PRE W04 history; both means must also agree with original C01 within 0.5%. Original C01 remains the Q reference.");
    Files.writeString(out.resolve("settling_check.json"),json(check));
    Files.writeString(out.resolve("settling_checks.jsonl"),json(check)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);return pass;
  }
  private ForceReport force(String name,double[] dir,ForceReportForceOption.Type type) {
    ForceReport f=s.getReportManager().createReport(ForceReport.class);f.setPresentationName(name);f.getDirection().setComponents(dir[0],dir[1],dir[2]);f.getParts().setObjects(foil);f.setRepresentation(fv);f.getForceOption().setSelected(type);return f;
  }
  private MaxReport max(String name,FieldFunction ff,NamedObject part) {
    MaxReport r=s.getReportManager().createReport(MaxReport.class);r.setPresentationName(name);r.setFieldFunction(ff);r.getParts().setObjects(part);r.setRepresentation(fv);return r;
  }
  private void exportFields(FieldFunction vf)throws Exception {
    fx.printReport(out.resolve("drag_pressure_shear.txt").toString(),false);fz.printReport(out.resolve("lift_pressure_shear.txt").toString(),false);
    XyzInternalTable wall=s.getTableManager().createTable(XyzInternalTable.class);wall.getParts().setObjects(foil);wall.setRepresentation(fv);wall.setExtractVertexData(false);
    wall.setFieldFunctions(List.of(s.getFieldFunctionManager().getFunction("Pressure"),s.getFieldFunctionManager().getFunction("WallYplus")));wall.extract();wall.export(out.resolve("foil_fields.csv").toString());
    XyzInternalTable cells=s.getTableManager().createTable(XyzInternalTable.class);cells.getParts().setObjects(fluid);cells.setRepresentation(fv);cells.setExtractVertexData(false);
    cells.setFieldFunctions(List.of(vf,s.getFieldFunctionManager().getFunction("Pressure"),s.getFieldFunctionManager().getFunction("CourantNumber"),s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction()));cells.extract();cells.export(out.resolve("fluid_fields.csv").toString());
    for(Monitor m:s.getMonitorManager().getObjects())try{m.export(out.resolve("monitor_"+m.getPresentationName().replaceAll("[^A-Za-z0-9_-]","_")+".csv").toString());}catch(Exception ignored){}
  }
  private static String json(Object o) {
    if(o==null)return "null";if(o instanceof Number)return Double.isFinite(((Number)o).doubleValue())?o.toString():"null";if(o instanceof Boolean)return o.toString();
    if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(var e:((Map<?,?>)o).entrySet())j.add(json(e.getKey().toString())+":"+json(e.getValue()));return j.toString();}
    if(o instanceof Collection){StringJoiner j=new StringJoiner(",","[","]");for(Object x:(Collection<?>)o)j.add(json(x));return j.toString();}
    return "\""+o.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";
  }
}
