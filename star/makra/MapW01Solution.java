package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.mapping.*;
import java.nio.file.*;import java.util.*;
public class MapW01Solution extends StarMacro {
 Simulation s;Region fluid;FvRepresentation fv;
 public void execute(){
  s=getActiveSimulation();Path out=Paths.get(System.getenv("NTNU_MAP_OUT"));
  try{
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
   fluid=s.getRegionManager().getRegion("fluid");fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(fv.getCellCount()!=317277)throw new IllegalStateException("Expected the saved W01a checkpoint");
   double start=s.getSolution().getPhysicalTime();if(Math.abs(start-Double.parseDouble(System.getenv().getOrDefault("NTNU_MAP_EXPECTED_START","0.02")))>1e-8)throw new IllegalStateException("Unexpected restart time");
   Map<String,Object> before=metrics();
   PhysicsContinuum pc=fluid.getPhysicsContinuum();
   SolutionInterpolationModel model=pc.getModelManager().getModel(SolutionInterpolationModel.class);
   model.getSolutionInterpolationMethod().setSelected(SolutionInterpolationMethod.Type.MAPPER);
   model.setLegacyMatchingCellMethod(false);
   s.getImportManager().importMeshFiles(List.of(System.getenv("NTNU_MAP_MESH")));
   Region donor=s.getRegionManager().getRegion("fluid 2");
   s.getMeshManager().replaceMesh(fluid,donor,true);
   for(Region r:new ArrayList<Region>(s.getRegionManager().getRegions()))if(r.getPresentationName().equals("fluid 2"))s.getRegionManager().removeObjects(List.of(r));
   long expected=Long.parseLong(System.getenv("NTNU_MAP_CELLS"));
   if(fv.getCellCount()!=expected)throw new IllegalStateException("Mapped mesh cell-count mismatch: "+fv.getCellCount());
   if(Math.abs(s.getSolution().getPhysicalTime()-start)>1e-10)throw new IllegalStateException("Physical time was reset");
   for(star.post.SolutionHistory h:s.get(star.post.SolutionHistoryManager.class).getSolutionHistories())h.setAutoRecord(false);
   Map<String,Object> after=metrics();
   double massChange=Math.abs(((Number)after.get("mass")).doubleValue()/((Number)before.get("mass")).doubleValue()-1);
   double waterChange=Math.abs(((Number)after.get("water")).doubleValue()/((Number)before.get("water")).doubleValue()-1);
   boolean pass=massChange<.001&&waterChange<.001&&((Number)after.get("alpha_min")).doubleValue()>-1e-6&&((Number)after.get("alpha_max")).doubleValue()<1+1e-6&&((Number)after.get("max_speed")).doubleValue()<90;
   if(after.containsKey("TurbulentKineticEnergy_min"))pass &= ((Number)after.get("TurbulentKineticEnergy_min")).doubleValue()>=0;
   if(after.containsKey("SpecificDissipationRate_min"))pass &= ((Number)after.get("SpecificDissipationRate_min")).doubleValue()>0;
   Files.writeString(out.resolve("mapping_audit.json"),json(Map.of("before",before,"after",after,"mass_relative_change",massChange,"water_relative_change",waterChange,"pass",pass,"method","Higher-order stencil, replace mesh in original region; no initialization","time_s",start,"cells",expected)));
   if(!pass)throw new IllegalStateException("Solution interpolation audit failed");
   s.saveState(out.resolve("mapped.sim").toString());
  }catch(Exception e){try{Files.writeString(out.resolve("mapping_error.txt"),e.toString());}catch(Exception x){}throw new RuntimeException(e);}
 }
 Map<String,Object> metrics(){
  FieldFunction vf=null;
  for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getFunctionName().contains("VolumeFraction")&&f.getFunctionName().contains("water")){vf=f;break;}
  if(vf==null)throw new IllegalStateException("Missing water fraction");
  Map<String,Object> m=new LinkedHashMap<>();
  m.put("mass",integral(s.getFieldFunctionManager().getFunction("Density")));m.put("water",integral(vf));
  m.put("alpha_min",extreme(vf,false));m.put("alpha_max",extreme(vf,true));
  m.put("max_speed",extreme(s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction(),true));
  m.put("pressure_min",extreme(s.getFieldFunctionManager().getFunction("Pressure"),false));
  m.put("pressure_max",extreme(s.getFieldFunctionManager().getFunction("Pressure"),true));
  for(String name:List.of("TurbulentKineticEnergy","SpecificDissipationRate"))if(s.getFieldFunctionManager().hasFunction(name)){m.put(name+"_min",extreme(s.getFieldFunctionManager().getFunction(name),false));m.put(name+"_max",extreme(s.getFieldFunctionManager().getFunction(name),true));}
  for(Object v:m.values())if(!Double.isFinite(((Number)v).doubleValue()))throw new IllegalStateException("Nonfinite mapped field");
  return m;
 }
 double integral(FieldFunction f){VolumeIntegralReport r=s.getReportManager().createReport(VolumeIntegralReport.class);r.setFieldFunction(f);r.getParts().setObjects(fluid);r.setRepresentation(fv);double v=r.getReportMonitorValue();if(!r.getErrorLog().isBlank())throw new IllegalStateException(r.getErrorLog());return v;}
 double extreme(FieldFunction f,boolean max){ScalarReport r=max?s.getReportManager().createReport(MaxReport.class):s.getReportManager().createReport(MinReport.class);r.setFieldFunction(f);r.getParts().setObjects(fluid);r.setRepresentation(fv);double v=r.getReportMonitorValue();if(!r.getErrorLog().isBlank())throw new IllegalStateException(r.getErrorLog());return v;}
 static String json(Object o){if(o==null)return "null";if(o instanceof Number)return Double.isFinite(((Number)o).doubleValue())?o.toString():"null";if(o instanceof Boolean)return o.toString();if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(var e:((Map<?,?>)o).entrySet())j.add(json(e.getKey().toString())+":"+json(e.getValue()));return j.toString();}return "\""+o.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n")+"\"";}
}
