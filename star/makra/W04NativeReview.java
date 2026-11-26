package macro;
import star.common.*;import star.vof.*;
import java.nio.file.*;import java.util.*;
/** Read native C01 configuration on a disposable copy: zero steps, no remesh or state save. */
public class W04NativeReview extends StarMacro {
 static String json(Object o){
  if(o==null)return "null";
  if(o instanceof Number)return Double.isFinite(((Number)o).doubleValue())?o.toString():"null";
  if(o instanceof Boolean)return o.toString();
  if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(var e:((Map<?,?>)o).entrySet())j.add(json(e.getKey().toString())+":"+json(e.getValue()));return j.toString();}
  if(o instanceof Collection){StringJoiner j=new StringJoiner(",","[","]");for(Object v:(Collection<?>)o)j.add(json(v));return j.toString();}
  return "\""+o.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";
 }
 static Object inspect(Object o,int depth){
  if(o==null||o instanceof Number||o instanceof String||o instanceof Boolean||o instanceof Enum)return o;
  if(depth==0)return o.toString();
  if(o instanceof Collection){ArrayList<Object> a=new ArrayList<>();for(Object v:(Collection<?>)o)a.add(inspect(v,depth-1));return a;}
  Map<String,Object>d=new LinkedHashMap<>();d.put("class",o.getClass().getName());d.put("text",o.toString());
  String methods="getPresentationName|getSelected|getSelectedElement|getMethod|getQuantity|getValue|getSIValue|getDefinition|getFieldFunction|getFunctionName|getRawVector|getComponents|getCurrentVector|getWindVector|getPointOnLevelVector|getGravityVector|getWaterDepth|getWaveHeight|getWavePeriod|getWaveLength|getVofWaveSpecification|getSpecificationOption|getHeavyFluidDensity|getLightFluidDensity|getForcingVofWave|getCorner1|getCorner2|getCoordinate";
  for(var m:o.getClass().getMethods())if(m.getParameterCount()==0&&m.getName().matches(methods))try{d.put(m.getName(),inspect(m.invoke(o),depth-1));}catch(Exception ex){d.put(m.getName(),"UNAVAILABLE:"+ex.getClass().getSimpleName());}
  return d;
 }
 public void execute(){
  Simulation s=getActiveSimulation();Path out=Paths.get(Objects.requireNonNull(System.getenv("NWAR_REVIEW_OUT"))).toAbsolutePath().normalize();
  try{
   if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim")))throw new IllegalStateException("Disposable audit input required");
   if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("CPU-only audit required");
   double t=s.getSolution().getPhysicalTime();
   if(Math.abs(t-4.699199999999548)>1e-8)throw new IllegalStateException("Accepted C01 time required");
   s.getSimulationIterator().getAutoSave().setEnabled(false);s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
   Region r=s.getRegionManager().getRegion("fluid");FvRepresentation mesh=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   Map<String,Object> result=new LinkedHashMap<>();result.put("time_s",t);result.put("cells",mesh.getCellCount());
   ArrayList<Object> region=new ArrayList<>();
   for(Object v:r.getValues().getChildren())if(v.getClass().getSimpleName().matches(".*(Wave|Forcing|Damping).*"))region.add(inspect(v,5));
   for(Object v:r.getConditions().getChildren())if(v.getClass().getSimpleName().matches(".*(Wave|Forcing|Damping).*"))region.add(inspect(v,4));
   result.put("region_wave_settings",region);
   ArrayList<Object> boundaries=new ArrayList<>();
   for(Boundary b:r.getBoundaryManager().getBoundaries()){
    Map<String,Object> item=new LinkedHashMap<>();item.put("name",b.getPresentationName());item.put("type",b.getBoundaryType().getClass().getName());ArrayList<Object> settings=new ArrayList<>();
    for(Object v:b.getValues().getChildren())if(v.getClass().getSimpleName().matches(".*(Wave|Forcing|Damping).*"))settings.add(inspect(v,5));
    for(Object v:b.getConditions().getChildren())if(v.getClass().getSimpleName().matches(".*(Wave|Forcing|Damping).*"))settings.add(inspect(v,4));
    item.put("wave_settings",settings);boundaries.add(item);
   }result.put("boundaries",boundaries);
   ArrayList<Object> waves=new ArrayList<>();for(Object w:pc.getModelManager().getModel(VofWaveModel.class).getVofWaveManager().getObjects())waves.add(inspect(w,4));result.put("waves",waves);
   result.put("steps_taken",0);result.put("no_initialization",true);result.put("no_remesh",true);result.put("no_state_save",true);result.put("time_after_s",s.getSolution().getPhysicalTime());
   Files.writeString(out.resolve("native_review.json"),json(result)+"\n");
   Files.writeString(out.resolve("completed.json"),json(Map.of("status","zero_step_review_complete","steps",0,"time_s",t))+"\n");
   s.println("W04_REVIEW_ZERO_STEPS_COMPLETE");
  }catch(Exception ex){try{Files.writeString(out.resolve("macro_error.json"),json(Map.of("error",ex.toString())));}catch(Exception ignored){}throw new RuntimeException(ex);}
 }
}
