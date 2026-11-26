package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import star.flow.*;import star.vof.*;import star.vis.*;import star.post.*;import star.material.*;
import java.nio.file.*;import java.util.*;
/** Isolated GPU M13: accepted calm -> inlet wave. Never reinitialize, remesh, or modify source .sim. */
public class NwarWave extends StarMacro {
 Simulation s;Path out;Region reg;FvRepresentation mesh;
 ForceReport fx,fz,fp,fv;MaxReport vmax,cfl,amax,pmax;MinReport amin,pmin;
 VolumeIntegralReport water;ArrayList<SurfaceIntegralReport> gauges=new ArrayList<>();
 double t0,dt,period,ramp,H=0.5,lambda=30.0,water0,beginTime,probeDistance=34.5,surfaceLimit=1.0; boolean expanded=false; long expectedCells=309441;
 boolean surfaceMagnitudeEnabled=false; // User-authorized ThinkPad rule, 2026-11-07.
 boolean resume=false; int maxCycles=5, smokeSteps=0, extraSteps=0, count=0;
 String endState="target_reached";
 double param(String name,double fallback){String v=System.getenv(name);return v==null?fallback:Double.parseDouble(v);}

 final double buoyancy=22.718189111947265,coeffDen=3855.6,span=.02;
 double[] locations={-34.,-25.,-15.,-10.,-6.,-.5,5.,10.,20.,40.,0.};
 ArrayList<SurfaceIntegralReport> gaugeAreas=new ArrayList<>();
 ReportMonitor nativeMonitor(String key,Report report,int stride){
  ReportMonitor monitor=report.createMonitor();
  monitor.setPresentationName("NWAR native "+key);
  monitor.getTriggerOption().setSelected(MonitorTriggerOption.TIME_STEP);
  monitor.getStarUpdate().getTimeStepUpdateFrequency().setTimeSteps(stride);
  monitor.setEnabled(true);
  return monitor;
 }
 void nativeBound(ReportMonitor monitor,boolean maximum,double limit){
  MonitorIterationStoppingCriterion rule=s.getSolverStoppingCriterionManager().createIterationStoppingCriterion(monitor);
  rule.getCriterionOption().setSelected(maximum?MonitorIterationStoppingCriterionOption.MAXIMUM:MonitorIterationStoppingCriterionOption.MINIMUM);
  ((MonitorIterationStoppingCriterionLimitType)rule.getCriterionType()).getLimit().setValue(limit);
  rule.setInnerIterationCriterion(false);rule.setOuterIterationCriterion(true);
  rule.getLogicalOption().setSelected(SolverStoppingCriterionLogicalOption.OR);rule.setIsUsed(true);
 }
 void prepareNative(String caseId,MaxReport interfaceCfl)throws Exception{
  if(resume||!expanded||!(caseId.equals("W04c")||caseId.equals("W04e")||caseId.equals("W04g")||caseId.equals("W04h")||caseId.equals("W04k")))throw new IllegalStateException("Native production requires a reviewed W04c, W04e, W04g, W04h or W04k wave");
  double wakeStart=t0+ramp+probeDistance*period/lambda;
  double end=Math.ceil((wakeStart+6.25*period)/(20*dt))*20*dt;
  PhysicalTimeStoppingCriterion physicalTime=null;
  for(SolverStoppingCriterion criterion:s.getSolverStoppingCriterionManager().getObjects())
   if(criterion instanceof PhysicalTimeStoppingCriterion)physicalTime=(PhysicalTimeStoppingCriterion)criterion;
  if(physicalTime==null)throw new IllegalStateException("Missing native physical-time stop");
  physicalTime.setMaximumTime(end);
  if(Math.abs(physicalTime.getMaximumTime().getSIValue()-end)>1e-9)throw new IllegalStateException("Unexpected native time limit");
  physicalTime.getLogicalOption().setSelected(SolverStoppingCriterionLogicalOption.OR);physicalTime.setIsUsed(true);
  nativeMonitor("Fx_N",fx,1);nativeMonitor("Fz_N",fz,1);
  nativeMonitor("Fx_pressure_N",fp,1);nativeMonitor("Fx_viscous_N",fv,1);
  ExpressionReport forceBalance=s.getReportManager().createReport(ExpressionReport.class);
  forceBalance.setPresentationName("NWAR native force balance");
  forceBalance.setDefinition("abs("+fx.getReferenceString()+" - "+fp.getReferenceString()+" - "+fv.getReferenceString()+")/max(<1 N>,abs("+fx.getReferenceString()+"))");
  if(!Double.isFinite(forceBalance.getReportMonitorValue()))throw new IllegalStateException("Native force balance readback failed");
  nativeBound(nativeMonitor("force_balance",forceBalance,1),true,1e-5);
  nativeBound(nativeMonitor("max_CFL",cfl,1),true,25);
  nativeBound(nativeMonitor("interface_CFL",interfaceCfl,1),true,2.2);
  nativeBound(nativeMonitor("max_speed_m_s",vmax,1),true,50);
  nativeBound(nativeMonitor("alpha_min",amin,1),false,-.00001);
  nativeBound(nativeMonitor("alpha_max",amax,1),true,1.00001);
  nativeBound(nativeMonitor("p_min_Pa",pmin,1),false,-1e7);
  nativeBound(nativeMonitor("p_max_Pa",pmax,1),true,1e7);
  ReportMonitor inventory=nativeMonitor("water_volume_m3",water,1);
  nativeBound(inventory,true,water0+.8);nativeBound(inventory,false,water0-.8);
  for(int i=0;i<locations.length;i++){
   Report liquid=gauges.get(i),area=gaugeAreas.get(i);
   ExpressionReport eta=s.getReportManager().createReport(ExpressionReport.class);
   eta.setPresentationName("NWAR native surface "+i);
   eta.setUnits((Units)s.getUnitsManager().getObject("m"));
   eta.setDefinition("("+liquid.getReferenceString()+" - "+area.getReferenceString()+")/<"+span+" m> + <6 m>");
   double check=eta.getReportMonitorValue(),expected=(liquid.getReportMonitorValue()-area.getReportMonitorValue())/span+6;
   if(!Double.isFinite(check)||Math.abs(check-expected)>1e-8)throw new IllegalStateException("Native gauge readback mismatch at "+locations[i]);
   ReportMonitor probe=nativeMonitor("eta_"+i,eta,10);
   if(surfaceMagnitudeEnabled){nativeBound(probe,true,surfaceLimit);nativeBound(probe,false,-surfaceLimit);}
  }
  SolutionHistory wake=wakeHistory(reg,"wake.simh");
  int wakeStride=Math.max(1,(int)Math.round(Math.max(.01,period/64)/dt));
  StarUpdate update=wake.getUpdate();
  update.setUpdateMode(StarUpdateModeOption.TIMESTEP);
  update.getTimeStepUpdateFrequency().setTimeSteps(wakeStride);
  update.getTimeStepUpdateFrequency().setStart((int)Math.ceil(wakeStart/dt));
  wake.setAutoRecord(true);
  AutoSave auto=s.getSimulationIterator().getAutoSave();
  auto.getTriggerOption().setSelected(AutoSaveTriggerOption.TIME_STEP);
  auto.getTimeStepUpdateFrequency().setTimeSteps(20);
  auto.setMaxAutosavedFiles(2);auto.setEnabled(true);auto.setAutoSaveBatch(true);
  Map<String,Object> plan=new LinkedHashMap<>();
  plan.put("start_s",beginTime);plan.put("target_s",end);plan.put("dt_s",dt);
  plan.put("surface_limit_m",surfaceMagnitudeEnabled?surfaceLimit:null);plan.put("surface_magnitude_limit_enabled",surfaceMagnitudeEnabled);plan.put("probe_positions_m",Arrays.toString(locations));
  plan.put("checkpoint_stride",20);plan.put("wake_start_s",wakeStart);plan.put("wake_stride",wakeStride);
  save("native_plan.json",plan);
  s.saveState(out.resolve("native_ready.sim").toString());
 }
 String json(Object o){
  if(o==null)return "null";
  if(o instanceof Number)return Double.isFinite(((Number)o).doubleValue())?o.toString():"null";
  if(o instanceof Boolean)return o.toString();
  if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(Object x:((Map<?,?>)o).entrySet()){Map.Entry<?,?> e=(Map.Entry<?,?>)x;j.add(json(e.getKey().toString())+":"+json(e.getValue()));}return j.toString();}
  return "\""+o.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\r","\\r").replace("\n","\\n").replace("\t","\\t")+"\"";
 }
 void save(String file,Map<String,?> info)throws Exception{
 Path p=out.resolve(file),tmp=Files.createTempFile(out,file+".",".tmp");
 try{
  Files.writeString(tmp,json(info)+"\n");
  for(int attempt=0;;attempt++){
   try{Files.move(tmp,p,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);break;}
   catch(java.nio.file.AccessDeniedException locked){if(attempt>=9)throw locked;Thread.sleep(50L*(attempt+1));}
  }
 }finally{try{Files.deleteIfExists(tmp);}catch(java.io.IOException cleanup){System.err.println("NWAR metadata temp retained: "+tmp.getFileName());}}
 }
 int progressWriteFailures=0;
 void saveProgress(Map<String,?> info)throws Exception{
 try{
  save("progress.json",info);
  if(progressWriteFailures>0){
   System.err.println("NWAR progress status write recovered after "+progressWriteFailures+" failed update(s); history remained recorded.");
   try{save("progress_write_warning.json",Map.of("active",false,"failed_updates",progressWriteFailures,"at",java.time.OffsetDateTime.now().toString()));}catch(java.io.IOException ignored){}
   progressWriteFailures=0;
  }
 }catch(java.io.IOException unavailable){
  progressWriteFailures++;
  System.err.println("NWAR progress status write unavailable; continuing with flushed history: "+unavailable);
  try{save("progress_write_warning.json",Map.of("active",true,"failed_updates",progressWriteFailures,"error",unavailable.toString(),"at",java.time.OffsetDateTime.now().toString()));}catch(java.io.IOException ignored){}
 }
 }
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
 SolutionHistory wakeHistory(Region region,String filename) throws Exception {
  Path path=out.resolve(filename);
  if(Files.exists(path))throw new IllegalStateException("Existing wake history; never overwrite");
  FieldFunctionManager fields=s.getFieldFunctionManager();
  String wakeBox="($${Position}[0] >= -1.0 && $${Position}[0] <= 12.0 && $${Position}[2] >= -3.0 && $${Position}[2] <= 3.5) ? 1.0 : 0.0";
  for(FieldFunction saved:fields.getObjects()){
   if(saved instanceof UserFieldFunction && saved.getPresentationName().startsWith("NWAR wake recording mask"))
    ((UserFieldFunction)saved).setDefinition(wakeBox);
  }
  UserFieldFunction box=fields.createFieldFunction();
  box.setPresentationName("NWAR wake recording mask");
  box.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
  box.setDefinition(wakeBox);
  ThresholdPart cells=s.getPartManager().createThresholdPart();
  cells.setPresentationName("NWAR wake recording box");
  cells.getInputParts().setObjects(region);
  cells.setFieldFunction(box);
  cells.setRange(new DoubleVector(new double[]{0.5,1.5}));
  cells.setMode(ThresholdMode.BETWEEN_TAG);
  PlaneSection plane=s.getPartManager().createPlaneSection();
  plane.setPresentationName("NWAR midspan wake");
  plane.getInputParts().setObjects(cells);
  plane.setOrigin(new DoubleVector(new double[]{0,.02,0}));
  plane.setOrientation(new DoubleVector(new double[]{0,1,0}));
  SolutionHistory history=s.get(SolutionHistoryManager.class).createForFile(path.toString(),false);
  history.setAutoRecord(false);
  history.setAddReportFieldFunctions(false);
  history.setCompressionMode(CompressionMode.ZLIB_1);
  history.getInputs().setObjects(plane);
  history.setFunctions(List.of(fields.getFunction("Velocity"),fields.getFunction("VorticityVector"),
                              fields.getFunction("Pressure"),fields.getFunction("VolumeFractionwater")));
  return history;
 }
 void stopCheck(){if(Files.exists(out.resolve("STOP"))||Files.exists(out.getParent().resolve("STOP"))||Files.exists(out.getParent().resolve("STOP_ALL"))||
  Files.exists(Paths.get("E:/ntnu_mesh_optimization_20261030/clean_c01_campaign_20261101/STOP"))||Files.exists(Paths.get("E:/ntnu_mesh_optimization_20261030/clean_c01_campaign_20261101/STOP_ALL"))||Files.exists(Paths.get("E:/ntnu_mesh_optimization_20261030/STOP_ALL"))||
  Files.exists(Paths.get("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL")))
   throw new IllegalStateException("STOP requested");}
 double[] forces(){
  double d=fx.getReportMonitorValue(),l=fz.getReportMonitorValue(),p=fp.getReportMonitorValue(),v=fv.getReportMonitorValue();
  if(!Double.isFinite(d)||!Double.isFinite(l)||!Double.isFinite(p)||!Double.isFinite(v)||Math.abs(d-p-v)>1e-5*Math.max(1,Math.abs(d)))
   throw new IllegalStateException("Nonfinite/inconsistent foil forces");
  return new double[]{d,l,p,v};
 }
 void verifyNativeMaterials(PhysicsContinuum pc,FlatVofWave calm)throws Exception{
  EulerianMultiPhaseModel multi=pc.getModelManager().getModel(EulerianMultiPhaseModel.class);
  Map<String,Object> rho=new LinkedHashMap<>();
  for(String name:List.of("water","air")){
   Phase ph=multi.getPhaseManager().getPhase(name);
   if(ph==null)throw new IllegalStateException("Missing C01 phase "+name);
   ArrayList<MaterialModel> models=new ArrayList<>();
   for(Model mod:ph.getModelManager().getObjects())if(mod instanceof MaterialModel)models.add((MaterialModel)mod);
   if(models.size()!=1)throw new IllegalStateException("Nonunique native material "+name);
   Material mat=models.get(0).getMaterial();
   ConstantDensityProperty property=mat.getMaterialProperties().getMaterialProperty(ConstantDensityProperty.class);
   if(!(property.getMethod() instanceof ConstantMaterialPropertyMethod))throw new IllegalStateException("Nonconstant source material "+name);
   double val=((ConstantMaterialPropertyMethod)property.getMethod()).getQuantity().getSIValue();
   double target=name.equals("water")?1000.0:1.2;
   if(Math.abs(val-target)>1e-9)throw new IllegalStateException("C01 native material rho mismatch "+name);
   rho.put(name+"_material_density",val);
  }
  double w=calm.getHeavyFluidDensity().getSIValue(),a=calm.getLightFluidDensity().getSIValue();
  if(Math.abs(w-1000)>1e-9||Math.abs(a-1.2)>1e-9)throw new IllegalStateException("C01 Calm function rho mismatch");
  rho.put("Calm_heavy",w);rho.put("Calm_light",a);rho.put("source_fields_preserved",true);
  rho.put("source_time_s",s.getSolution().getPhysicalTime());save("native_C01_rho_readback.json",rho);
 }

 // Saved source steady 18m/s: stop as soon as four consecutive phase-aligned
 // encounter-period cycles repeat in BOTH foil CL/CD and x=-0.5 VOF gauge.
 private final ArrayList<double[]> cycleTrace=new ArrayList<>();
 private double cycleInterp(int col,double query){
   if(cycleTrace.size()<2||query<cycleTrace.get(0)[0]||query>cycleTrace.get(cycleTrace.size()-1)[0])return Double.NaN;
   int lo=0,hi=cycleTrace.size()-1;
   while(hi-lo>1){int mid=(lo+hi)/2;if(cycleTrace.get(mid)[0]<query)lo=mid;else hi=mid;}
   double[] a=cycleTrace.get(lo),b=cycleTrace.get(hi);
   double f=(query-a[0])/(b[0]-a[0]);
   return a[col]+f*(b[col]-a[col]);
 }
 private boolean fourCyclesRepeat(double now,FullCycleCounter counter)throws Exception{
   double arrival=probeDistance/(lambda/period);
   if(counter.complete<5||counter.boundaries.size()<5||cycleTrace.size()<250)return false;
   double start=counter.boundaries.get(1)[0];if(cycleTrace.get(0)[0]>start)return false;
   int phases=48; double[][][] cycle=new double[3][4][phases];
   for(int k=0;k<3;k++)for(int c=0;c<4;c++)for(int i=0;i<phases;i++){
      double[] bounds=counter.boundaries.get(1+c); double at=bounds[0]+(i+.5)/phases*(bounds[1]-bounds[0]);
      cycle[k][c][i]=cycleInterp(k+1,at);
      if(!Double.isFinite(cycle[k][c][i]))return false;
   }
   Map<String,Object> audit=new LinkedHashMap<>();boolean pass=true;
   String[] names={"CL","CD","surface_gauge_x_minus0p5"};
   for(int k=0;k<3;k++){
     double[] means=new double[4],amps=new double[4];double[] phaseMean=new double[phases];
     for(int c=0;c<4;c++){
       double mn=Double.POSITIVE_INFINITY,mx=Double.NEGATIVE_INFINITY;
       for(int i=0;i<phases;i++){double y=cycle[k][c][i];means[c]+=y/phases;mn=Math.min(mn,y);mx=Math.max(mx,y);phaseMean[i]+=y/4.;}
       amps[c]=(mx-mn)/2.;
     }
     double mean=0,amp=0;for(int c=0;c<4;c++){mean+=means[c]/4; amp+=amps[c]/4;}
     double scale=Math.max(Math.max(Math.abs(mean),amp),k==2?H/2:1e-7);
     double mv=0,av=0,rms=0;
     for(int c=0;c<4;c++){
       mv=Math.max(mv,Math.abs(means[c]-mean)/scale);
       av=Math.max(av,Math.abs(amps[c]-amp)/Math.max(amp,1e-7));
       for(int i=0;i<phases;i++)rms+=Math.pow(cycle[k][c][i]-phaseMean[i],2)/(4*phases);
     }
     double waveform=Math.sqrt(rms)/scale;
     boolean ok=(mv<(k==2?.05:.01))&&(av<(k==2?.10:.08))&&(waveform<(k==2?.06:.05));
     if(k==2)ok=ok&&(2*amp>H*.80)&&(2*amp<H*1.20)&&(Math.abs(mean)<.35);
     pass&=ok;
     audit.put(names[k],Map.of("pooled_mean",mean,"mean_spread_fraction",mv,"amplitude",amp,"amplitude_spread_fraction",av,"phase_aligned_RMS_fraction",waveform,"pass",ok));
   }
   if(!pass)return false;
   audit.put("at_time_s",now);audit.put("start_time_s",start);audit.put("period_planning_s",period);audit.put("estimated_arrival_from_inlet_s",arrival);
   audit.put("number_of_full_periods",4);audit.put("recorded_cycles",counter.complete);audit.put("discarded_cycle_numbers",List.of(1));audit.put("analyzed_cycle_numbers",List.of(2,3,4,5));audit.put("cycle_policy_id","five_measured_cycles_discard_first_20261103");audit.put("scientific_caveat","Native measured T and spatial forcing review still required; on-line repeatability is provisional, independently validate raw after saved state");
   audit.put("project_rule","Four consecutive phase-aligned CL/CD cycles: means1%, amplitude8%, waveformRMS5%; x=-0.5 gauge confirms H and phase; all physical guards unchanged");
   save("four_cycle_repeatability_online.json",audit);
   return true;
 }

 // Upper diagnostic cap from measured full probe cycles, independent of force fitting.
 static final class FullCycleCounter {
  final double planningPeriod, height, eligibleAt, maxGap, hysteresis;
  final ArrayList<double[]> warmup=new ArrayList<>();
  final ArrayList<double[]> boundaries=new ArrayList<>();
  double level=Double.NaN, previousT=Double.NaN, previousY=Double.NaN;
  double firstCrossing=Double.NaN, lastCrossing=Double.NaN, lastPeriod=Double.NaN;
  boolean armed=false, crestSinceCrossing=false;
  int complete=0, gaps=0;
  FullCycleCounter(double period,double H,double eligible,double sampleDt){
   if(!(Double.isFinite(period)&&period>0&&Double.isFinite(H)&&H>0&&Double.isFinite(eligible)&&sampleDt>0))
    throw new IllegalArgumentException("Invalid cycle counter configuration");
   planningPeriod=period;height=H;eligibleAt=eligible;
   maxGap=Math.max(.02,3.1*sampleDt);hysteresis=Math.max(1e-5,.02*H);
  }
  void observe(double t,double eta){
   if(!Double.isFinite(t)||!Double.isFinite(eta)||t<eligibleAt||complete>=20)return;
   if(!Double.isFinite(level)){
    if(!warmup.isEmpty()&&(t<=warmup.get(warmup.size()-1)[0]||t-warmup.get(warmup.size()-1)[0]>maxGap))warmup.clear();
    warmup.add(new double[]{t,eta});
    while(warmup.size()>1&&t-warmup.get(0)[0]>2.0*planningPeriod)warmup.remove(0);
    if(warmup.size()<30||t-warmup.get(0)[0]<1.25*planningPeriod)return;
    double low=Double.POSITIVE_INFINITY,high=Double.NEGATIVE_INFINITY;
    for(double[] v:warmup){low=Math.min(low,v[1]);high=Math.max(high,v[1]);}
    if(high-low<.40*height)return;
    // Freeze one level from actual local surface measurements; no force peak shifts.
    level=(low+high)/2.;
    for(double[] v:warmup)consume(v[0],v[1]);
    warmup.clear();
   }else consume(t,eta);
  }
  private void consume(double t,double eta){
   if(Double.isFinite(previousT)){
    if(t<=previousT)return;
    if(t-previousT>maxGap){
     gaps++;armed=false;crestSinceCrossing=false;lastCrossing=Double.NaN;
     previousT=t;previousY=eta;return;
    }
   }
   if(eta<=level-hysteresis)armed=true;
   if(Double.isFinite(lastCrossing)&&eta>=level+hysteresis)crestSinceCrossing=true;
   if(armed&&Double.isFinite(previousT)&&previousY<=level&&eta>level){
    double crossing=previousT+(level-previousY)*(t-previousT)/(eta-previousY);
    if(Double.isFinite(lastCrossing)){
     double T=crossing-lastCrossing;
     if(crestSinceCrossing&&T>=.5*planningPeriod){
      complete++;lastPeriod=T;boundaries.add(new double[]{lastCrossing,crossing});
      lastCrossing=crossing;crestSinceCrossing=false;
     }
    }else{
     lastCrossing=crossing;if(!Double.isFinite(firstCrossing))firstCrossing=crossing;
     crestSinceCrossing=false;
    }
    armed=false;
   }
   previousT=t;previousY=eta;
  }
  Map<String,Object> evidence(){
   Map<String,Object> m=new LinkedHashMap<>();
   m.put("max_complete_cycles",5);m.put("complete_cycles",complete);m.put("phase_probe_x_m",-.5);
   m.put("discard_first_cycles",1);m.put("analysis_cycle_numbers",List.of(2,3,4,5));
   m.put("phase_level_eta_m",Double.isFinite(level)?level:null);
   m.put("first_measured_crossing_s",Double.isFinite(firstCrossing)?firstCrossing:null);
   m.put("last_measured_crossing_s",Double.isFinite(lastCrossing)?lastCrossing:null);
   m.put("last_observed_period_s",Double.isFinite(lastPeriod)?lastPeriod:null);
   m.put("eligible_after_s",eligibleAt);m.put("data_gaps",gaps);
   m.put("method","Fixed local-gauge upward crossings with crest/trough hysteresis; no force fitting");
   m.put("startup_exclusion","Inlet ramp plus existing planning transit estimate; not propagation certification");
   m.put("planning_period_s",planningPeriod);m.put("scientific_accepted",false);
   Map<String,Object> b=new LinkedHashMap<>();
   for(int i=0;i<boundaries.size();i++)b.put("cycle_"+(i+1),Map.of("start_s",boundaries.get(i)[0],"end_s",boundaries.get(i)[1]));
   m.put("measured_boundaries",b);return m;
  }
 }

 void loadPriorCycles(FullCycleCounter counter)throws Exception{
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
 public void execute(){
  s=getActiveSimulation();out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_M13_WAVE_OUT"))).toAbsolutePath().normalize();
  String phase="setup";
  try{
   String isolate="E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/runs/";
   if(!out.toString().replace("\\","/").startsWith(isolate)||!s.getSessionPath().replace("\\","/").equals(out.resolve("input.sim").toString().replace("\\","/")))
    throw new IllegalStateException("Disposable M13 input/output identity mismatch");
   if(Files.exists(out.resolve("history.csv")))throw new IllegalStateException("Existing attempt; never overwrite");
   if(s.getNumberOfGpgpus()!=1)throw new IllegalStateException("Exactly one GPU required");
   dt=Double.parseDouble(System.getenv("NTNU_M13_WAVE_DT"));
   H=param("NWAR_H",.5);lambda=param("NWAR_L",20);
   String profile=System.getenv().getOrDefault("NWAR_PROFILE","");
   expanded=profile.equals("M13_W04_20261102");
   if(!profile.isEmpty()&&!expanded)throw new IllegalStateException("Unknown mesh profile");
   String caseId=System.getenv().getOrDefault("NWAR_CASE","");
   boolean shortWaveDiagnostic=expanded&&caseId.equals("W04b")&&H==1.5&&lambda==10;
   boolean reviewedExpanded=shortWaveDiagnostic||(caseId.equals("W04")&&Math.abs(H-1.5)<1e-9&&Math.abs(lambda-38.99857691441418)<1e-8)||
     (caseId.equals("W04c")&&H==1.5&&lambda==20)||(caseId.equals("W04e")&&H==1.5&&lambda==15)||
     (caseId.equals("W04g")&&H==1.5&&lambda==25)||(caseId.equals("W04h")&&H==.75&&lambda==15)||(caseId.equals("W04k")&&H==.25&&lambda==15)||
     (caseId.equals("W05")&&H==1&&lambda==20)||(caseId.equals("W06")&&H==1&&lambda==30)||
     (caseId.equals("W07")&&H==1&&lambda==40)||
     (caseId.equals("W01")&&H==.5&&lambda==20)||(caseId.equals("W02")&&H==.25&&lambda==20)||
     (caseId.equals("W03")&&H==.5&&lambda==30)||
     (caseId.matches("CUSTOM[0-9]{3,}")&&H>=.25&&H<=1.5&&lambda>=15&&lambda<=40);
   if(!Double.isFinite(H)||!Double.isFinite(lambda)||(expanded?!reviewedExpanded:(H<.25||H>.5||lambda<19||lambda>30)))
    throw new IllegalStateException("Outside reviewed case-specific H/lambda envelope");
   if(expanded){expectedCells=572176;probeDistance=69.5;locations=new double[]{-69,-50,-30,-15,-6,-.5,5,20,50,85,0.};}

   surfaceLimit=expanded&&caseId.equals("W04")?1.5:1.0; // User-authorized W04 diagnostic limit, 2026-11-03.
   resume="1".equals(System.getenv("NWAR_RESUME"));
   extraSteps=(int)param("NWAR_EXTRA_STEPS",0);
   smokeSteps=(int)param("NWAR_SMOKE_STEPS",0);
   maxCycles=(int)param("NWAR_MAX_CYCLES",5);
   if(maxCycles!=5||smokeSteps<0||smokeSteps>100||extraSteps<0||extraSteps>80000)
    throw new IllegalStateException("Invalid requested run limit");

   int steps=Integer.parseInt(System.getenv("NTNU_M13_WAVE_STEPS")),inner=Integer.parseInt(System.getenv("NTNU_M13_WAVE_INNER"));
   double budget=Double.parseDouble(System.getenv("NTNU_M13_WAVE_BUDGET"));
   if(dt!=.0004||inner!=10||steps<12000||steps>26000||budget<120||budget>129600)throw new IllegalStateException("Pilot settings outside contract");
   reg=s.getRegionManager().getRegion("fluid");mesh=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(mesh.getCellCount()!=expectedCells)throw new IllegalStateException("Wrong M13 mesh");
   beginTime=s.getSolution().getPhysicalTime();t0=expanded?param("NWAR_WAVE_ORIGIN",-1):4.699199999999548;
   if(expanded&&(!Double.isFinite(t0)||t0<1.7999))throw new IllegalStateException("Invalid PRE W04 wave origin");
   if(expanded){
    double forcing=reg.getBoundaryManager().getBoundary("DOMAIN.inlet").getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().getSIValue();
    double damping=reg.getBoundaryManager().getBoundary("DOMAIN.outlet").getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().getSIValue();
    if(Math.abs(forcing-40)>1e-8||Math.abs(damping-40)>1e-8)throw new IllegalStateException("Expanded wave-zone settings mismatch");
   }
   double expected=param("NWAR_SOURCE_TIME",t0);
   if(Math.abs(beginTime-expected)>1e-7)throw new IllegalStateException("Source physical time mismatch");
   if(!resume&&Math.abs(beginTime-t0)>1e-7)throw new IllegalStateException("Fresh waves require accepted C01");

   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   VofWaveModel wm=(VofWaveModel)pc.getModelManager().getModel(VofWaveModel.class);
   FlatVofWave calm=(FlatVofWave)wm.getVofWaveManager().getVofWave("Calm");
   verifyNativeMaterials(pc,calm);
   if(!resume&&!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(calm))
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
   ThresholdPart interfaceBand=s.getPartManager().createThresholdPart();
   interfaceBand.getInputParts().setObjects(reg);interfaceBand.setFieldFunction(alpha);
   interfaceBand.setRange(new DoubleVector(new double[]{.01,.99}));interfaceBand.setMode(ThresholdMode.BETWEEN_TAG);
   MaxReport interfaceCfl=max("W01_interface_CFL",s.getFieldFunctionManager().getFunction("CourantNumber"),interfaceBand);
   water=s.getReportManager().createReport(VolumeIntegralReport.class);water.setFieldFunction(alpha);water.setRepresentation(mesh);water.getParts().setObjects(reg);
   double[] f0=forces();water0=water.getReportMonitorValue();
   if(!Double.isFinite(water0)||water0<(expanded?76:30)||water0>(expanded?78:45)||!Double.isFinite(vmax.getReportMonitorValue())||vmax.getReportMonitorValue()>50)
    throw new IllegalStateException("Unhealthy M13 calm checkpoint");
   FieldFunction columnUnity;
   if(s.getFieldFunctionManager().hasFunction("NWAR_ColumnUnity"))columnUnity=s.getFieldFunctionManager().getFunction("NWAR_ColumnUnity");
   else{UserFieldFunction one=s.getFieldFunctionManager().createFieldFunction();one.setFunctionName("NWAR_ColumnUnity");one.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);one.setDefinition("1");columnUnity=one;}
   for(double x:locations){
    PlaneSection plane=s.getPartManager().createPlaneSection();plane.getInputParts().setObjects(reg);
    plane.setOrigin(new DoubleVector(new double[]{x,.01,2}));plane.setOrientation(new DoubleVector(new double[]{1,0,0}));
    SurfaceIntegralReport g=s.getReportManager().createReport(SurfaceIntegralReport.class);g.setFieldFunction(alpha);g.setRepresentation(mesh);g.getParts().setObjects(plane);g.setSmooth(false);gauges.add(g);
    SurfaceIntegralReport ga=s.getReportManager().createReport(SurfaceIntegralReport.class);ga.setFieldFunction(columnUnity);ga.setRepresentation(mesh);ga.getParts().setObjects(plane);ga.setSmooth(false);gaugeAreas.add(ga);
   }
   wm.setEnableTheoryComparison(true);
   FifthOrderVofWave wave;
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

   wave.getHeavyFluidDensity().setValue(1000.0);
   wave.getLightFluidDensity().setValue(1.2);
   if(Math.abs(wave.getHeavyFluidDensity().getSIValue()-1000.0)>1e-9||Math.abs(wave.getLightFluidDensity().getSIValue()-1.2)>1e-9)
    throw new IllegalStateException("New FifthOrder wave density readback incompatible with C01");
   save("wave_density_audit.json",Map.of("FifthOrder_water_rho",wave.getHeavyFluidDensity().getSIValue(),"FifthOrder_air_rho",wave.getLightFluidDensity().getSIValue(),"source_material_and_Calm_verified",true));
   wave.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);
   wave.getVofWaveSpecification().getWaveLength().setValue(lambda);wave.getWaterDepth().setValue(24);
   wave.getWaveHeight().setValue(H);wave.getPointOnLevel().setComponents(0,0,2);
   wave.getVerticalDirection().setComponents(0,0,1);wave.getAdvancingDirection().setComponents(1,0,0);
   wave.getCurrent().setComponents(18,0,0);wave.getWind().setComponents(18,0,0);wave.setFirstWaveFront(false);
   double rawPeriodBeforeBinding=wave.getWavePeriod().getValue();
   // The STAR wave period may not be initialized until the inlet functions are bound.
   // Use a separately labeled linear dispersion estimate ONLY for the 2-period inlet-ramp duration.
   // The FifthOrder wave object itself still defines all imposed wave physics.
   period=lambda/(18+Math.sqrt(9.81*lambda/(2*Math.PI)*Math.tanh(2*Math.PI*24/lambda)));
   if(!Double.isFinite(period)||period<(shortWaveDiagnostic?.45:.5)||period>(expanded?1.6:1.5))throw new IllegalStateException("Invalid analytic startup period");
   save("wave_period_initial_audit.json",Map.of("native_period_before_binding_s",rawPeriodBeforeBinding,
     "ramp_planning_period_s",period,"lambda_m",lambda,"reason","Native period not reliable before wave bindings; not a statement of physical wave period validity"));
   ramp=2*period;String tau="min(1.0,max(0.0,($Time-<"+t0+" s>)/<"+ramp+" s>))";
   wave.getWaveHeight().setDefinition("<0.000001 m>+<"+(H-.000001)+" m>*0.5*(1.0-cos(3.141592653589793*"+tau+"))");
   Boundary inlet=reg.getBoundaryManager().getBoundary("DOMAIN.inlet");
   inlet.getValues().get(VelocityProfile.class).setMethod(FunctionVectorProfileMethod.class);
   inlet.getValues().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).setFieldFunction(waveFn(wave,"Velocity of "));
   VolumeFractionProfile vp=inlet.getValues().get(VolumeFractionProfile.class);
   vp.setMethod(CompositeNMinus1ArrayProfileMethod.class);
   vp.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).setMethod(FunctionScalarProfileMethod.class);
   vp.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(waveFn(wave,"Volume Fraction of Heavy Fluid of "));
   reg.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(wave);
   if(!reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(wave))throw new IllegalStateException("Wave not activated");
   } // Resume preserves the saved active wave, inlet bindings, phase and ramp.
   period=lambda/(18+Math.sqrt(9.81*lambda/(2*Math.PI)*Math.tanh(2*Math.PI*24/lambda)));
   ramp=2*period;
   if(resume)save("wave_density_audit.json",Map.of("FifthOrder_water_rho",wave.getHeavyFluidDensity().getSIValue(),"FifthOrder_air_rho",wave.getLightFluidDensity().getSIValue(),"source_material_and_Calm_verified",true));
   double boundPeriod=wave.getWavePeriod().getSIValue();
   // STAR resolves the nonlinear encounter period lazily: an early getter may return 0.
   // A zero before the first physical step is NOT a physical-dispersion failure.
   // Keep the configured wave length/height, record this value, and validate actual
   // propagation/phase from independent solver gauges after real steps.
   save("wave_period_bound_audit.json",Map.of("native_period_after_binding_s",boundPeriod,
     "native_period_pre_step_available",Double.isFinite(boundPeriod)&&boundPeriod>.65*period&&boundPeriod<1.35*period,
     "ramp_planning_period_s",period,"ramp_duration_s",ramp,"phase_origin_time_s",t0,
     "no_reinitialize",true,"actual_propagation_unverified",true));
   for(Object x:s.getSolverStoppingCriterionManager().getChildren()){
    if(x instanceof PhysicalTimeStoppingCriterion||x instanceof StepStoppingCriterion)((SolverStoppingCriterion)x).setIsUsed(false);
    if(x instanceof InnerIterationStoppingCriterion){((InnerIterationStoppingCriterion)x).setMaximumNumberInnerIterations(inner);((SolverStoppingCriterion)x).setIsUsed(true);}
   }
   ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
   us.getTimeStep().setValue(dt);us.getTimeDiscretizationOption().setSelected(TimeDiscretizationOption.Type.SECOND_ORDER);
   Map<String,Object> setup=new LinkedHashMap<>();setup.put("source",expanded?"Accepted PRE W04 on expanded M13; reference policy and stability recorded in the source receipt; source copy only":"Independently accepted new C01 t4.6992 final.sim; source copy only");
   setup.put("cells",expectedCells);setup.put("mesh_profile",expanded?"M13_W04_20261102":"M13");setup.put("probe_distance_m",probeDistance);setup.put("foil_present",true);setup.put("response_probe_x_m",0.);setup.put("response_probe_position","Foil reference x = 0 m");setup.put("response_probe_method","(water section area - fluid section area)/span + 6 m; submerged foil excluded from both areas");setup.put("wave_inlet_only",true);
   setup.put("t0",t0);setup.put("begin_time_s",beginTime);setup.put("resume",resume);setup.put("target_extra_steps",extraSteps);setup.put("smoke_steps",smokeSteps);setup.put("dt_s",dt);setup.put("GPU",1);setup.put("mpi_processes",(int)param("NWAR_MPI_PROCESSES",1));setup.put("scene_count",s.getSceneManager().getObjects().size());setup.put("lambda_m",lambda);setup.put("H_m",H);setup.put("wave_period_s",period);
   setup.put("ramp_s",ramp);setup.put("water0_m3",water0);
   Map<String,Object> stopPolicy=new LinkedHashMap<>();
   stopPolicy.put("schema","five_measured_cycles_discard_first_20261103");stopPolicy.put("max_complete_cycles",5);
   stopPolicy.put("early_repeatability_cycles",5);stopPolicy.put("analysis_cycle_numbers",List.of(2,3,4,5));stopPolicy.put("discard_first_cycles",1);stopPolicy.put("phase_probe_x_m",-.5);
   stopPolicy.put("closing_sample_margin_s",.1*period);
   stopPolicy.put("legacy_step_limit_active",false);stopPolicy.put("legacy_declared_steps",steps);
   stopPolicy.put("wall_budget_s",budget);stopPolicy.put("safety_guards_unchanged",false);stopPolicy.put("surface_elevation_limit_m",surfaceMagnitudeEnabled?surfaceLimit:null);stopPolicy.put("surface_magnitude_limit_enabled",surfaceMagnitudeEnabled);stopPolicy.put("other_safety_guards_unchanged",true);
   int checkpointStride=shortWaveDiagnostic?250:1500;
   boolean frequentRecovery=shortWaveDiagnostic||"1".equals(System.getenv("NWAR_NIGHT_CHECKPOINTS"));
   int recoveryStride=frequentRecovery?20:checkpointStride;
   ArrayDeque<Path> recentRecoveryCheckpoints=new ArrayDeque<>();
   stopPolicy.put("checkpoint_stride_steps",checkpointStride);
   if(frequentRecovery){
    stopPolicy.put("recovery_checkpoint_stride_steps",recoveryStride);
    stopPolicy.put("recovery_checkpoints_retained",2);
   }
   stopPolicy.put("counter_basis","measured_probe_upcrossings_after_startup_exclusion");
   stopPolicy.put("startup_exclusion","inlet_ramp_plus_existing_planning_transit_estimate");
   setup.put("stopping_policy",stopPolicy);save("stopping_policy.json",stopPolicy);
   FullCycleCounter cycleLimit=new FullCycleCounter(period,H,t0+ramp+probeDistance*period/lambda,10*dt);
   if(resume)loadPriorCycles(cycleLimit);
   setup.put("CL_hydro_pre_switch",(f0[1]-buoyancy)/coeffDen);setup.put("CD_pre_switch",f0[0]/coeffDen);
   setup.put("global_initialization",false);setup.put("scientific_accepted",false);
   setup.put("pressure_top","C01 Calm hydrostatic unchanged");setup.put("accepted_C01_source_SHA","9af4857b948e0494088b5421f8ede100e66344fc2631cc00030406640d7cc295");setup.put("wave_densities","1000/1.2");save("wave_setup_audit.json",setup);
   if("1".equals(System.getenv("NWAR_SETUP_ONLY"))){
    save("completed.json",Map.of("status","setup_verified","steps",0,"time_s",beginTime,"scientific_accepted",false));return;
   }
   if("1".equals(System.getenv("NWAR_NATIVE_PRODUCTION"))){
    phase="native_production_setup";prepareNative(caseId,interfaceCfl);return;
   }
   s.saveState(out.resolve("wave_bound_pre_step.sim").toString());
   save("latest_checkpoint.json",Map.of("file","wave_bound_pre_step.sim","time_s",beginTime,"step",0,"healthy",true));
   // A resumed .sim still owns the previous segment's Solution History basename.
   String wakeFile=resume?"wake_"+out.getFileName()+".simh":"wake.simh";
   SolutionHistory wake=smokeSteps==0?wakeHistory(reg,wakeFile):null;
   int wakeStride=Math.max(1,(int)Math.round(Math.max(.01,period/64)/dt));
   double wakeStart=t0+ramp+probeDistance*period/lambda;
   if(wake!=null)save("wake_history_config.json",Map.of("file",wakeFile,"y_m",.02,
     "x_min_m",-1,"x_max_m",12,"z_min_m",-3,"z_max_m",3.5,"interval_s",wakeStride*dt,
     "start_s",wakeStart,"fields","Velocity, Vorticity, Pressure, VolumeFractionwater"));

   long startWall=System.nanoTime();count=0;endState="target_reached";
   try(var hist=Files.newBufferedWriter(out.resolve("history.csv"));var gauge=Files.newBufferedWriter(out.resolve("gauges.csv"))){
    hist.write("time_s,step,wall_s,CL_hydrodynamic,CD_total,Fx_N,Fz_N,Fx_pressure_N,Fx_viscous_N,max_CFL,max_speed_m_s,water_volume_m3,alpha_min,alpha_max,p_min_Pa,p_max_Pa,target_H_m,interface_CFL\n");hist.flush();
    gauge.write("time_s,x_m,eta_actual_m\n");gauge.flush();
    for(int step=0;step<Integer.MAX_VALUE;step++){ // User cap is measured cycles; legacy step cap is inactive.
     if(step>0){
      try{stopCheck();}catch(IllegalStateException stop){endState="paused_saved";break;}
      phase="solver_step_"+step;
      s.getSimulationIterator().step(1);count=step;
     }
     double t=s.getSolution().getPhysicalTime(),elapsed=(System.nanoTime()-startWall)*1e-9;
     phase="force_and_field_reports_"+step;
     double[] f=forces();double v=vmax.getReportMonitorValue(),CFL=cfl.getReportMonitorValue(),w=water.getReportMonitorValue();
     double a=amin.getReportMonitorValue(),A=amax.getReportMonitorValue(),p=pmin.getReportMonitorValue(),P=pmax.getReportMonitorValue(),h=wave.getWaveHeight().getValue();
     double interCFL=interfaceCfl.getReportMonitorValue();
     double cl=(f[1]-buoyancy)/coeffDen,cd=f[0]/coeffDen;
     hist.write(t+","+step+","+elapsed+","+cl+","+cd+","+f[0]+","+f[1]+","+f[2]+","+f[3]+","+CFL+","+v+","+w+","+a+","+A+","+p+","+P+","+h+","+interCFL+"\n");hist.flush();
     if(!Double.isFinite(t)||!Double.isFinite(CFL)||!Double.isFinite(v)||!Double.isFinite(w)||!Double.isFinite(a)||!Double.isFinite(A)||!Double.isFinite(p)||!Double.isFinite(P)||
      !Double.isFinite(h)||!Double.isFinite(interCFL)||interCFL>2.2||CFL>25||v>50||a<-.00001||A>1.00001||Math.abs(w-water0)>0.8||p< -1e7||P>1e7||Math.abs(t-beginTime-step*dt)>dt*.2)
      throw new IllegalStateException("M13 pilot numerical/VOF guard at step "+step);
     if(step%10==0){
      phase="gauge_reports_"+step;
      for(int i=0;i<locations.length;i++){double eta=(gauges.get(i).getReportMonitorValue()-gaugeAreas.get(i).getReportMonitorValue())/span+6;
       if(!Double.isFinite(eta)||(surfaceMagnitudeEnabled&&Math.abs(eta)>surfaceLimit))throw new IllegalStateException("Unphysical free surface at gauge x="+locations[i]+": eta="+eta);gauge.write(t+","+locations[i]+","+eta+"\n");}
      gauge.flush();
      if(step>0){
        double etaNearFoil=gauges.get(5).getReportMonitorValue()/span-24;
        if(Double.isFinite(etaNearFoil)){cycleTrace.add(new double[]{t,cl,cd,etaNearFoil});cycleLimit.observe(t,etaNearFoil);}
      }
      Map<String,Object> pg=new LinkedHashMap<>();
      pg.put("step",step);pg.put("t_s",t);pg.put("CL_hydro",cl);pg.put("CD_total",cd);pg.put("CFL",CFL);pg.put("water_m3",w);pg.put("max_speed_m_s",v);
      pg.put("target_height_m",h);pg.put("arrival","NOT_YET_CONFIRMED");
      pg.put("complete_cycles",cycleLimit.complete);pg.put("max_complete_cycles",maxCycles);pg.put("wall_s",elapsed);pg.put("interface_CFL",interCFL);pg.put("resume",resume);pg.put("extra_steps_goal",extraSteps);pg.put("sampled_at",java.time.OffsetDateTime.now().toString());
      pg.put("phase_probe_x_m",-.5);pg.put("stop_basis","measured_complete_cycles");
      pg.put("last_cycle_period_s",Double.isFinite(cycleLimit.lastPeriod)?cycleLimit.lastPeriod:null);
      pg.put("last_cycle_end_s",Double.isFinite(cycleLimit.lastCrossing)?cycleLimit.lastCrossing:null);
      saveProgress(pg);
     }
     if(wake!=null&&step%wakeStride==0&&t>=wakeStart){
      phase="wake_snapshot_"+step;
      wake.createSnapshot(String.format(Locale.ROOT,"t_%.6f",t));
     }
     boolean archiveCheckpoint=step%checkpointStride==0;
     if(step>0&&(archiveCheckpoint||step%recoveryStride==0)){
      phase="checkpoint_save_"+step;
      String ck=String.format(Locale.ROOT,"checkpoint_t%.4f.sim",t);
      Path checkpoint=out.resolve(ck);
      s.saveState(checkpoint.toString());
      save("latest_checkpoint.json",Map.of("file",ck,"time_s",t,"step",step,"healthy",true));
      if(!archiveCheckpoint){
       recentRecoveryCheckpoints.addLast(checkpoint);
       while(recentRecoveryCheckpoints.size()>2){
        try{Files.deleteIfExists(recentRecoveryCheckpoints.getFirst());}
        catch(java.io.IOException busy){break;} // Preserve the new checkpoint and retry rotation later.
        recentRecoveryCheckpoints.removeFirst();
       }
      }
     }
     if(smokeSteps>0&&step>=smokeSteps){endState="smoke_test_saved";break;}
     if(resume&&extraSteps>0&&step>=extraSteps){endState="requested_extension_saved";break;}

     if(cycleLimit.complete>=maxCycles&&t>=cycleLimit.boundaries.get(4)[1]+.1*period){
      // Five cycles plus closing samples for the x=0 plot and independent crossings.
      // This margin is not a sixth analysis cycle; only cycles 2–5 are evaluated.
      boolean repeated=fourCyclesRepeat(t,cycleLimit);
      endState=repeated?"five_cycles_repeated":"five_cycles_recorded";
      save("cycle_cap_audit.json",cycleLimit.evidence());break;
     }
     if(elapsed>budget){endState="wall_budget";break;}
    }
   }
   phase="final_save";
   if(wake!=null){
    int frames=wake.getNumberOfStates();
    if(frames>0)wake.createRecordedSolutionView();
    save("wake_history.json",Map.of("file",wakeFile,"frames",frames,"interval_s",wakeStride*dt));
   }
   s.saveState(out.resolve("wave_pilot_final.sim").toString());
   save("latest_checkpoint.json",Map.of("file","wave_pilot_final.sim","time_s",s.getSolution().getPhysicalTime(),"step",count,"healthy",true));
   save("cycle_counter_final.json",cycleLimit.evidence());
   save("completed.json",Map.of("status",endState,"steps",count,"time_s",s.getSolution().getPhysicalTime(),"propagation_validated",false,"periodic_forces_validated",false,"global_initialization",false,"max_complete_cycles",5,"complete_cycles",cycleLimit.complete,"phase_probe_x_m",-.5));
  }catch(Exception err){
   java.io.StringWriter trace=new java.io.StringWriter();
   err.printStackTrace(new java.io.PrintWriter(trace));
   try{save("macro_error.json",Map.of("error",err.toString(),"phase",phase,"stack_trace",trace.toString(),"at",java.time.OffsetDateTime.now().toString()));}catch(Exception ignore){}
   throw new RuntimeException(err);
  }
 }
}
