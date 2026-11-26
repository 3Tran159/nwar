package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.vof.*;
import java.util.*;import java.nio.file.*;
/** Disposable copied session only. No solver iteration, initialization, save, or BC changes. */
public class AuditWaveSetupZeroStep extends StarMacro {
 private Path out;
 private String j(Object x){if(x==null)return "null";if(x instanceof Number)return Double.isFinite(((Number)x).doubleValue())?x.toString():"null";if(x instanceof Boolean)return x.toString();if(x instanceof Map){StringJoiner z=new StringJoiner(",","{","}");for(Object e:((Map<?,?>)x).entrySet()){var q=(Map.Entry<?,?>)e;z.add(j(q.getKey().toString())+":"+j(q.getValue()));}return z.toString();}if(x instanceof Iterable){StringJoiner z=new StringJoiner(",","[","]");for(Object e:(Iterable<?>)x)z.add(j(e));return z.toString();}return "\""+x.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";}
 private Object call(Object a,String name){try{return a.getClass().getMethod(name).invoke(a);}catch(Exception e){return "UNAVAILABLE:"+e.getClass().getSimpleName();}}
 private String label(Object x){return x instanceof NamedObject?((NamedObject)x).getPresentationName():String.valueOf(x);}
 public void execute(){
  Simulation s=getActiveSimulation();Map<String,Object> z=new LinkedHashMap<>();
  try{
   out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_ZERO_STEP_AUDIT_OUT")));
   if(!out.toString().replace('\\','/').startsWith("E:/ntnu_mesh_optimization_20261030/wave_surface_only/failure_diagnostic_20261031_2323/"))throw new IllegalStateException("Wrong output");
   if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim").toAbsolutePath().normalize()))throw new IllegalStateException("Disposable source copy required");
   if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("CPU audit only");
   double t=s.getSolution().getPhysicalTime();z.put("time_start_s",t);z.put("solver_steps",0);z.put("simulation_save",false);
   ArrayList<Object> ms=new ArrayList<>();
   for(Monitor m:s.getMonitorManager().getObjects()){
    Map<String,Object> q=new LinkedHashMap<>();q.put("name",m.getPresentationName());q.put("class",m.getClass().getName());q.put("enabled",m.getEnabled());
    if(m instanceof ResidualMonitor){PlotableMonitor pm=(PlotableMonitor)m;q.put("normalization",String.valueOf(pm.getNormalizeOption().getSelectedElement()));q.put("normalization_factor",pm.getNormalizationType().getNormalizationFactor());q.put("auto_index",pm.getAutoNormalizeIndex());MonitorData d=pm.getAllSamples(s.getMonitorManager().getIterationMonitor());double[] x=d.getXValues(),y=d.getYValues();q.put("sample_count",y.length);q.put("last_value_api",y.length>0?y[y.length-1]:null);String fn=m.getPresentationName().replaceAll("[^A-Za-z0-9_-]","_")+"_samples.csv";StringBuilder csv=new StringBuilder("iteration,value_api\n");for(int k=0;k<Math.min(x.length,y.length);k++)csv.append(x[k]).append(',').append(y[k]).append('\n');Files.writeString(out.resolve(fn),csv.toString(),StandardOpenOption.CREATE_NEW);q.put("csv",fn);}
    if(m instanceof ReportMonitor){Report r=((ReportMonitor)m).getReport();q.put("report",r==null?null:r.getPresentationName());}
    ms.add(q);
   }
   z.put("monitors",ms);ArrayList<Object> rs=new ArrayList<>();
   for(Report r:s.getReportManager().getObjects()){
    Map<String,Object> q=new LinkedHashMap<>();q.put("name",r.getPresentationName());q.put("class",r.getClass().getName());Object parts=call(call(r,"getParts"),"getObjects");if(parts instanceof Collection){ArrayList<String> names=new ArrayList<>();for(Object p:(Collection<?>)parts)names.add(label(p));q.put("parts",names);}else q.put("parts_info",String.valueOf(parts));q.put("field_function",label(call(r,"getFieldFunction")));q.put("representation",label(call(r,"getRepresentation")));rs.add(q);
   }
   z.put("reports",rs);
   Files.writeString(out.resolve("monitor_audit.json"),j(z)+"\n",StandardOpenOption.CREATE_NEW);
   // Only analytical-wave object and a postprocessing report are created in memory.
   // No wave is attached to a boundary or region; no physical state is changed.
   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   VofWaveModel wm=(VofWaveModel)pc.getModelManager().getModel(VofWaveModel.class);
   FifthOrderVofWave wave=wm.getVofWaveManager().createVofWave(FifthOrderVofWave.class,"ZERO_STEP_PERIOD_AUDIT");
   wave.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);wave.getVofWaveSpecification().getWaveLength().setValue(20);wave.getWaterDepth().setValue(24);wave.getWaveHeight().setValue(.5);wave.getPointOnLevel().setComponents(0,0,2);wave.getVerticalDirection().setComponents(0,0,1);wave.getAdvancingDirection().setComponents(1,0,0);wave.getCurrent().setComponents(18,0,0);wave.getWind().setComponents(18,0,0);wave.setFirstWaveFront(false);
   Map<String,Object> p=new LinkedHashMap<>();p.put("lambda_m",20);p.put("H_m",.5);p.put("depth_m",24);p.put("current_m_s",18);p.put("period_immediate_s",wave.getVofWaveSpecification().getWavePeriod().getValue());
   FieldFunction velocity=null;for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getPresentationName().equals("Velocity of ZERO_STEP_PERIOD_AUDIT"))velocity=f;
   if(velocity==null)throw new IllegalStateException("Analytical wave velocity field missing");
   MaxReport report=s.getReportManager().createReport(MaxReport.class);report.setFieldFunction(velocity.getMagnitudeFunction());report.setRepresentation((FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh"));report.getParts().setObjects(s.getRegionManager().getRegion("fluid").getBoundaryManager().getBoundary("DOMAIN.inlet"));
   p.put("wave_velocity_report_m_s",report.getReportMonitorValue());p.put("period_after_analytical_report_s",wave.getVofWaveSpecification().getWavePeriod().getValue());p.put("time_end_s",s.getSolution().getPhysicalTime());p.put("zero_solver_steps_verified",Math.abs(s.getSolution().getPhysicalTime()-t)<1e-14);p.put("no_BC_changes",true);
   Files.writeString(out.resolve("period_evaluation_audit.json"),j(p)+"\n",StandardOpenOption.CREATE_NEW);s.println("ZERO_STEP_AUDIT_COMPLETE_NO_STEPS_NO_SAVE");
  }catch(Exception e){try{Files.writeString(out.resolve("audit_error.json"),j(Map.of("error",e.toString(),"steps_requested",0))+"\n",StandardOpenOption.CREATE_NEW);}catch(Exception ignored){}throw new RuntimeException(e);}
 }
}
