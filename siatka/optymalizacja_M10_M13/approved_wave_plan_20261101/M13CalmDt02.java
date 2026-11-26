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

public class M13CalmDt02 extends StarMacro {
  private final double CL_OFFSET=22.718189111947265/3855.6;
  private Scene liveScene; private long lastPreview=0; private int previewIndex=0,priorCount=0;
  private Simulation s; private Path out; private Region fluid; private Boundary foil; private FvRepresentation fv;
  private MinReport yMin; private MaxReport yMax;
  private ForceReport fx,fz,pressure,shear; private MaxReport vmax,cfl,interfaceCfl; private AreaAverageReport yplus;
  private double dt,target,startTime; private final double window=.2; private int inner;
  private VolumeIntegralReport massBudget,waterBudget;private ArrayList<MassFlowReport> fluxBudget=new ArrayList<>();
  private ArrayList<double[]> samples=new ArrayList<>();private int consecutivePasses=0;
  public void execute() {
    s=getActiveSimulation();
    out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_STAB_OUT")));
    try {
      dt=Double.parseDouble(System.getenv("NTNU_STAB_DT"));
      if(Math.abs(dt-.0002)>1e-12)throw new IllegalStateException("Approved sensitivity dt0.2ms required");
      target=Double.parseDouble(System.getenv("NTNU_STAB_TARGET"));
      inner=Integer.parseInt(System.getenv("NTNU_STAB_INNER"));
      long expectedCells=Long.parseLong(System.getenv("NTNU_STAB_CELLS"));
      double expectedStart=Double.parseDouble(System.getenv("NTNU_STAB_START"));
      boolean initialize="true".equals(System.getenv("NTNU_STAB_INIT"));
      String order=System.getenv("NTNU_STAB_ORDER");
      double budget=Double.parseDouble(System.getenv("NTNU_STAB_BUDGET"));
      if(Files.exists(out.resolve("history.csv"))) throw new IllegalStateException("History exists; use a new attempt directory");
      s.getSimulationIterator().getAutoSave().setEnabled(false);
      s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
      for(SolutionHistory h:s.get(SolutionHistoryManager.class).getSolutionHistories())h.setAutoRecord(false);
      for(Monitor inherited:s.getMonitorManager().getObjects())if(inherited instanceof ReportMonitor)((ReportMonitor)inherited).setEnabled(false);
      fluid=s.getRegionManager().getRegion("fluid"); foil=fluid.getBoundaryManager().getBoundary("HF_012_wall");
      fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
      // Rebind inherited monitors after a region was replaced by an audited CGNS import.
      for(Report rep:s.getReportManager().getObjects()){
        if(rep instanceof ForceReport){((ForceReport)rep).getParts().setObjects(foil);((ForceReport)rep).setRepresentation(fv);}
        if(rep instanceof MaxReport && rep.getPresentationName().equals("Maximum Velocity")){((MaxReport)rep).getParts().setObjects(fluid);((MaxReport)rep).setRepresentation(fv);}
      }
      if(fv.getCellCount()!=expectedCells)throw new IllegalStateException("Mesh identity mismatch: "+fv.getCellCount());
      if(s.getNumberOfGpgpus()!=1)throw new IllegalStateException("Exactly one GPU required for the accelerated mesh campaign");
      startTime=s.getSolution().getPhysicalTime();
      if(Math.abs(startTime-expectedStart)>dt*.1)throw new IllegalStateException("Unexpected restart time "+startTime);
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

      if(Math.abs(rho-1000)>1e-6)throw new IllegalStateException("Unexpected reference density");
      if(initialize)throw new IllegalStateException("Calm GCI must continue saved fields without initialization");
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
      audit.put("models",pc.getModelManager().getObjects().toString());audit.put("purpose","Approved M13 matched calm reference dt0.2ms; unchanged mesh/physics, no incident wave/reinitialization");
      Files.writeString(out.resolve("setup.json"),json(audit));
      s.saveState(out.resolve("restart_prepared.sim").toString());
      massBudget=s.getReportManager().createReport(VolumeIntegralReport.class);massBudget.setFieldFunction(s.getFieldFunctionManager().getFunction("Density"));massBudget.getParts().setObjects(fluid);massBudget.setRepresentation(fv);
      waterBudget=s.getReportManager().createReport(VolumeIntegralReport.class);waterBudget.setFieldFunction(vf);waterBudget.getParts().setObjects(fluid);waterBudget.setRepresentation(fv);
      for(Boundary b:fluid.getBoundaryManager().getBoundaries()){MassFlowReport report=s.getReportManager().createReport(MassFlowReport.class);report.getParts().setObjects(b);report.setRepresentation(fv);fluxBudget.add(report);}
      Files.writeString(out.resolve("conservation.csv"),"time_s,mass_kg,water_volume_m3,net_outward_mass_kg_s,inward_mass_kg_s\n");

      Files.writeString(out.resolve("calm_audit.json"),json(Map.of("incident_wave_height_m",0,"source_wave",selectedWave.getPresentationName(),"type",selectedWave.getClass().getSimpleName(),"reinitialized",false,"start_time_s",startTime,"pressure_AMG_tolerance",pressureTol,"VOF_AMG_tolerance",vofTol,"GPU_count",s.getNumberOfGpgpus())));
      recordBudget();
      // Deliberately no old dt0.4ms history in dt0.2ms settling windows.
      if(System.getenv("NTNU_STAB_PRIOR_HISTORY")!=null&&!System.getenv("NTNU_STAB_PRIOR_HISTORY").isBlank())throw new IllegalStateException("No mixed-dt prior history");
      setupPreview();
      preview(startTime,fx.getReportMonitorValue(),fz.getReportMonitorValue(),pressure.getReportMonitorValue(),shear.getReportMonitorValue());
      long start=System.nanoTime();int steps=0;String state="target_reached";
      try(var w=Files.newBufferedWriter(out.resolve("history.csv"));var vw=Files.newBufferedWriter(out.resolve("vof_substeps.csv"))) {
        vw.write("physical_time_s,VOF_substeps,flow_interface_CFL,flow_CFL_divided_by_substeps\n");
        w.write("wall_seconds,step,iteration,physical_time_s,dt_s,Fx_slice_N,Fz_slice_N,pressure_drag_N,viscous_drag_N,CD,CL_total,max_velocity_m_s,max_CFL,interface_max_CFL,mean_yplus,min_yplus,max_yplus,CL\n");
        while(s.getSolution().getPhysicalTime()<target-dt*.1) {
          if(Files.exists(out.resolve("STOP"))||Files.exists(out.getParent().resolve("STOP_ALL"))||Files.exists(Paths.get("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL"))) {state="stopped_by_marker";break;}
          if((System.nanoTime()-start)*1e-9>budget) {state="wall_budget";break;}
          double before=s.getSolution().getPhysicalTime();s.getSimulationIterator().step(1);steps++;
          double t=s.getSolution().getPhysicalTime(),d=fx.getReportMonitorValue(),l=fz.getReportMonitorValue(),p=pressure.getReportMonitorValue(),v=shear.getReportMonitorValue();
          double speed=vmax.getReportMonitorValue(),co=cfl.getReportMonitorValue(),ci=interfaceCfl.getReportMonitorValue(),yp=yplus.getReportMonitorValue();
          double wall=(System.nanoTime()-start)*1e-9,q=.5*rho*18*18*.0238;
          w.write(wall+","+steps+","+s.getSimulationIterator().getCurrentIteration()+","+t+","+dt+","+d+","+l+","+p+","+v+","+d/q+","+l/q+","+speed+","+co+","+ci+","+yp+","+yMin.getReportMonitorValue()+","+yMax.getReportMonitorValue()+","+(l/q-CL_OFFSET)+"\n");w.flush();

          int vofSteps=s.getSolverManager().getSolver(star.vof.SegregatedVofSolver.class).getSubStepCount();
          vw.write(t+","+vofSteps+","+ci+","+(ci/Math.max(1,vofSteps))+"\n");vw.flush();
          if(!Double.isFinite(d)||!Double.isFinite(l)||!Double.isFinite(speed)||!Double.isFinite(co)||!Double.isFinite(ci)||speed>50||(t>.02&&Math.abs(d)>2000)||Math.abs(d)>20000||Math.abs(l)>20000||t<=before) {state="stability_guard";break;}
          if(co>Double.parseDouble(System.getenv().getOrDefault("NTNU_GCI_MAX_CFL","1e8"))||ci>Double.parseDouble(System.getenv().getOrDefault("NTNU_GCI_INTERFACE_CFL","1e8"))){state="CFL_guard";break;}
          if(Math.abs(d-p-v)>Math.max(.01,Math.abs(d)*1e-4))throw new IllegalStateException("Pressure/shear force sum failed");
          if(steps%10==0)Files.writeString(out.resolve("progress.json"),json(Map.of("time_s",t,"steps",steps,"wall_s",wall,"CD",d/q,"CL",l/q-CL_OFFSET,"CFL",co,"interface_CFL",ci)));
          recordBudget();
          samples.add(new double[]{t,d/q,l/q-CL_OFFSET,p/q,v/q});
          if(steps%50==0&&(System.nanoTime()-lastPreview)*1e-9>=120)preview(t,d,l,p,v);
          if(samples.size()>2*(int)Math.round(window/dt)+10)samples.remove(0);
          if(steps%Math.max(1,(int)Math.round(.5/dt))==0) {
            String name=String.format(Locale.ROOT,"checkpoint_t%.3f.sim",t);
            s.saveState(out.resolve(name).toString());
            Files.writeString(out.resolve("latest_checkpoint.json"),json(Map.of("path",out.resolve(name).toString(),"time_s",t)));
          }
          if("true".equals(System.getenv("NTNU_CALM_SETTLE"))&&(steps+priorCount)%(int)Math.round(window/dt)==0){
            boolean pass=settlingPass();consecutivePasses=pass?consecutivePasses+1:0;
            if(consecutivePasses>=2){state="stabilized";break;}
          }
        }
      }
      for(Object x:s.getSolverStoppingCriterionManager().getChildren())if(x instanceof PhysicalTimeStoppingCriterion) {
        ((PhysicalTimeStoppingCriterion)x).getMaximumTime().setValue(s.getSolution().getPhysicalTime()+.05);((SolverStoppingCriterion)x).setIsUsed(true);
      }
      s.saveState(out.resolve("final.sim").toString());
      Files.writeString(out.resolve("latest_checkpoint.json"),json(Map.of("path",out.resolve("final.sim").toString(),"time_s",s.getSolution().getPhysicalTime())));
      preview(s.getSolution().getPhysicalTime(),fx.getReportMonitorValue(),fz.getReportMonitorValue(),pressure.getReportMonitorValue(),shear.getReportMonitorValue());
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
    for(MassFlowReport r:fluxBudget){double f=r.getReportMonitorValue();if(!Double.isFinite(f))throw new IllegalStateException("Nonfinite mass flux");net+=f;if(f<0)inward-=f;}
    if(!Double.isFinite(mass)||!Double.isFinite(water)||mass<=0||water<0)throw new IllegalStateException("Invalid mass/phase integral");
    Files.writeString(out.resolve("conservation.csv"),s.getSolution().getPhysicalTime()+","+mass+","+water+","+net+","+inward+"\n",StandardOpenOption.APPEND);
  }
  private boolean settlingPass()throws Exception{
    int n=(int)Math.round(window/dt);
    if(Math.abs(n*dt-window)>1e-10)throw new IllegalStateException("Settling window must contain an integer number of constant time steps");
    if(samples.size()<2*n)return false;
    int end=samples.size();Map<String,Object> check=new LinkedHashMap<>();boolean pass=true;
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
      if(col<=2)pass&=ok;check.put(keys[col-1],Map.of("previous_mean",previous,"latest_mean",latest,"mean_change_pct",change,"previous_RMS_pct",rmsOld,"latest_RMS_pct",rmsNew,"latest_peak_to_peak_pct",100*(high-low)/Math.max(Math.abs(latest),1e-30),"relative_test_resolved",resolved,"pass",ok));
    }
    check.put("lift_convention","hydrodynamic_lift_v1");check.put("time_s",samples.get(end-1)[0]);check.put("pass",pass);check.put("consecutive_passes",pass?consecutivePasses+1:0);
    check.put("criterion","Project-primary CLhydro and CDtotal only: two adjacent full0.2s windows, mean shift and RMS<0.5%, two checks0.2s apart. Pressure/viscous are diagnostics, NOT independent acceptance gates. Not a legacy four-way pass or GCI.");
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
