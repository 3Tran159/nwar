package macro;
import star.common.*;
import star.base.report.*;
import star.base.neo.*;
import java.util.*;
import java.nio.file.*;
/** Existing failed session only. No solver steps, initialization, saving, deletion or setters. */
public class AuditFailedWaveReadOnly extends StarMacro {
 private final Path out=Paths.get("E:/ntnu_mesh_optimization_20261030/wave_surface_only/failure_diagnostic_20261031_2323");
 private String j(Object x){
  if(x==null)return "null";
  if(x instanceof Number){return Double.isFinite(((Number)x).doubleValue())?x.toString():"null";}
  if(x instanceof Boolean)return x.toString();
  if(x instanceof Map){StringJoiner z=new StringJoiner(",","{","}");for(Object e:((Map<?,?>)x).entrySet()){var q=(Map.Entry<?,?>)e;z.add(j(q.getKey().toString())+":"+j(q.getValue()));}return z.toString();}
  if(x instanceof Iterable){StringJoiner z=new StringJoiner(",","[","]");for(Object e:(Iterable<?>)x)z.add(j(e));return z.toString();}
  return "\""+x.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";
 }
 private Object call(Object a,String name){try{return a.getClass().getMethod(name).invoke(a);}catch(Exception e){return "UNAVAILABLE:"+e.getClass().getSimpleName();}}
 private String label(Object x){return x instanceof NamedObject?((NamedObject)x).getPresentationName():String.valueOf(x);}
 public void execute(){
  Map<String,Object> result=new LinkedHashMap<>();
  try{
   Simulation s=getActiveSimulation();
   String path=s.getSessionPath().replace('\\','/');
   if(!path.startsWith("E:/ntnu_mesh_optimization_20261030/wave_surface_only/WAVE_H050_pressure_aligned_CPU1_20261031_once/"))throw new IllegalStateException("Wrong session, no action");
   double t=s.getSolution().getPhysicalTime();
   if(t<.4||t>.425||s.getNumberOfGpgpus()!=0)throw new IllegalStateException("Unexpected time/backend, no action");
   result.put("session",path);result.put("time_start_s",t);result.put("solver_steps_requested",0);result.put("simulation_saved",false);
   ArrayList<Object> monitors=new ArrayList<>();
   for(Monitor m:s.getMonitorManager().getObjects()){
    Map<String,Object> q=new LinkedHashMap<>();q.put("name",m.getPresentationName());q.put("class",m.getClass().getName());q.put("enabled",m.getEnabled());
    if(m instanceof ResidualMonitor){
     PlotableMonitor pm=(PlotableMonitor)m;
     q.put("normalization_option",String.valueOf(pm.getNormalizeOption().getSelectedElement()));
     q.put("normalization_factor",pm.getNormalizationType().getNormalizationFactor());q.put("auto_normalize_index",pm.getAutoNormalizeIndex());
     MonitorData data=pm.getAllSamples(s.getMonitorManager().getIterationMonitor());double[] xs=data.getXValues(),ys=data.getYValues();
     q.put("sample_count",ys.length);q.put("last_y_api",ys.length>0?ys[ys.length-1]:null);
     StringBuilder csv=new StringBuilder("iteration,value_from_getAllSamples\n");
     for(int k=0;k<Math.min(xs.length,ys.length);k++)csv.append(xs[k]).append(',').append(ys[k]).append('\n');
     String fn=m.getPresentationName().replaceAll("[^A-Za-z0-9_-]","_")+"_samples.csv";
     Files.writeString(out.resolve(fn),csv.toString(),StandardOpenOption.CREATE_NEW);q.put("samples_file",fn);
    }
    if(m instanceof ReportMonitor){Report r=((ReportMonitor)m).getReport();q.put("report",r==null?null:r.getPresentationName());}
    monitors.add(q);
   }
   result.put("monitors",monitors);
   ArrayList<Object> reports=new ArrayList<>();
   for(Report r:s.getReportManager().getObjects()){
    Map<String,Object> q=new LinkedHashMap<>();q.put("name",r.getPresentationName());q.put("class",r.getClass().getName());
    Object selector=call(r,"getParts");Object parts=call(selector,"getObjects");
    if(parts instanceof Collection){ArrayList<String> names=new ArrayList<>();for(Object p:(Collection<?>)parts)names.add(label(p));q.put("parts",names);}else q.put("parts_info",String.valueOf(parts));
    q.put("field_function",label(call(r,"getFieldFunction")));q.put("representation",label(call(r,"getRepresentation")));
    reports.add(q);
   }
   result.put("reports",reports);
   result.put("time_end_s",s.getSolution().getPhysicalTime());
   result.put("status", "read_only_complete_no_steps_no_save");
   Files.writeString(out.resolve("live_session_audit.json"),j(result)+"\n",StandardOpenOption.CREATE_NEW);
   s.println("FAILED_WAVE_AUDIT_COMPLETE_NO_STEPS_NO_SAVE");
  }catch(Exception e){
   result.put("error",e.toString());
   try{Files.writeString(out.resolve("live_session_audit_error.json"),j(result)+"\n",StandardOpenOption.CREATE_NEW);}catch(Exception ignored){}
   throw new RuntimeException(e);
  }
 }
}
