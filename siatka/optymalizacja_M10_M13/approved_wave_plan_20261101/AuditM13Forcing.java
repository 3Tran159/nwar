package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.flow.*;import star.vof.*;import star.post.*;import star.vis.*;
import java.nio.file.*;import java.util.*;
/** Zero-step audit on disposable copies. Never initialize, advance, or save simulation state. */
public class AuditM13Forcing extends StarMacro {
 static String json(Object o){
  if(o==null)return "null";if(o instanceof Number)return Double.isFinite(((Number)o).doubleValue())?o.toString():"null";if(o instanceof Boolean)return o.toString();
  if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(var e:((Map<?,?>)o).entrySet())j.add(json(e.getKey().toString())+":"+json(e.getValue()));return j.toString();}
  if(o instanceof Collection){StringJoiner j=new StringJoiner(",","[","]");for(Object a:(Collection<?>)o)j.add(json(a));return j.toString();}
  return "\""+o.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";
 }
 static Object inspect(Object o,int depth){
  if(o==null||o instanceof Number||o instanceof String||o instanceof Boolean||o instanceof Enum)return o;
  if(depth<=0)return o.toString();
  if(o instanceof Collection){ArrayList<Object>a=new ArrayList<>();for(Object x:(Collection<?>)o)a.add(inspect(x,depth-1));return a;}
  Map<String,Object>d=new LinkedHashMap<>();d.put("class",o.getClass().getName());d.put("text",o.toString());
  String names="getPresentationName|getSelected|getMethod|getFieldFunction|getFunctionName|getConstant|getQuantity|getValue|getSIValue|getDefinition|getRawVector|getComponents|getProfiles|getObjects|getForcingVofWave|getWaveForcingLength|getWaveDampingLength|getSelectedElement|getReversedFlowPressureOption|getBackflowVelocityDirectionOption|getBackflowScalarOption|getCurrentVector|getWindVector|getPointOnLevelVector|getGravityVector|getWaterDepth|getWaveHeight|getWavePeriod|getWaveForcingCoefficient|getWaveDampingCoefficient|getWaveForcingStrength|getWaveDampingStrength|getVofWaveSpecification|getWaveLength|getSpecificationOption|getReferencePressure|getHeavyFluidDensity|getLightFluidDensity|getFirstWaveFront";
  for(java.lang.reflect.Method m:o.getClass().getMethods())if(m.getParameterCount()==0&&m.getName().matches(names))try{d.put(m.getName(),inspect(m.invoke(o),depth-1));}catch(Exception ex){d.put(m.getName(),"UNAVAILABLE:"+ex.getClass().getSimpleName());}
  return d;
 }
 public void execute(){Simulation s=getActiveSimulation();Path out=Paths.get(Objects.requireNonNull(System.getenv("NTNU_M13_AUDIT_OUT")));
  try{
   if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim").toAbsolutePath().normalize()))throw new IllegalStateException("Disposable input required");
   if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("Zero-step CPU1 audit required");
   double t=s.getSolution().getPhysicalTime();Region r=s.getRegionManager().getRegion("fluid");FvRepresentation mesh=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(mesh.getCellCount()!=309441)throw new IllegalStateException("Expected M13 cell identity");
   s.getSimulationIterator().getAutoSave().setEnabled(false);s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
   PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
   Map<String,Object> result=new LinkedHashMap<>();result.put("time_s",t);result.put("cells",mesh.getCellCount());result.put("steps_taken",0);
   result.put("models",pc.getModelManager().getObjects().toString());
   ArrayList<Object> refs=new ArrayList<>();for(Object v:pc.getReferenceValues().getChildren())refs.add(inspect(v,4));result.put("physics_reference_values",refs);
   ArrayList<Object> region=new ArrayList<>();for(Object v:r.getValues().getChildren())if(v.getClass().getSimpleName().matches(".*(Wave|Damping|Forcing|Pressure|Gravity).*"))region.add(inspect(v,5));
   for(Object v:r.getConditions().getChildren())if(v.getClass().getSimpleName().matches(".*(Wave|Damping|Forcing|Source).*"))region.add(inspect(v,4));result.put("region_wave",region);
   ArrayList<Object> bounds=new ArrayList<>();
   for(Boundary b:r.getBoundaryManager().getBoundaries()){
    Map<String,Object> item=new LinkedHashMap<>();item.put("name",b.getPresentationName());item.put("type",b.getBoundaryType().getClass().getName());
    ArrayList<Object> values=new ArrayList<>(),cond=new ArrayList<>();
    for(Object v:b.getValues().getChildren())if(v.getClass().getSimpleName().matches(".*(Velocity|VolumeFraction|Pressure|Wave|Backflow|FlowDirection|Turbulence|Intensity|Viscosity).*"))values.add(inspect(v,5));
    for(Object v:b.getConditions().getChildren())if(v.getClass().getSimpleName().matches(".*(Wave|Backflow|FlowDirection|Wall).*"))cond.add(inspect(v,4));
    item.put("values",values);item.put("conditions",cond);
    MassFlowReport m=s.getReportManager().createReport(MassFlowReport.class);m.getParts().setObjects(b);m.setRepresentation(mesh);item.put("mixture_mass_outward_kg_s",m.getReportMonitorValue());bounds.add(item);
   }result.put("boundaries",bounds);
   ArrayList<Object> waves=new ArrayList<>();for(Object wave:pc.getModelManager().getModel(VofWaveModel.class).getVofWaveManager().getObjects())waves.add(inspect(wave,5));result.put("waves",waves);
   ArrayList<Object> solvers=new ArrayList<>();for(Object sol:s.getSolverManager().getChildren())if(sol.getClass().getSimpleName().matches(".*(Vof|Wave|Unsteady|SegregatedFlow).*"))solvers.add(inspect(sol,3));result.put("solver_properties",solvers);
   ArrayList<FieldFunction> fields=new ArrayList<>();ArrayList<Object> fieldAudit=new ArrayList<>();
   for(FieldFunction f:s.getFieldFunctionManager().getObjects()){
    String name=f.getFunctionName()+" "+f.getPresentationName();
    if(!name.matches("(?i).*(forcing|damping|wave.*distance|distance.*wave).*"))continue;
    Map<String,Object>a=new LinkedHashMap<>();a.put("name",f.getFunctionName());a.put("presentation",f.getPresentationName());a.put("class",f.getClass().getName());a.put("type",String.valueOf(f.getTypeOption().getSelectedElement()));
    if(String.valueOf(f.getTypeOption().getSelectedElement()).equals("SCALAR")){
     try{MaxReport max=s.getReportManager().createReport(MaxReport.class);MinReport min=s.getReportManager().createReport(MinReport.class);
      for(ScalarReport v:List.of(max,min)){v.setRepresentation(mesh);v.getParts().setObjects(r);v.setFieldFunction(f);}a.put("min",min.getReportMonitorValue());a.put("max",max.getReportMonitorValue());
      if(fields.size()<16)fields.add(f);
     }catch(Exception ex){a.put("evaluation_error",ex.toString());}
    }fieldAudit.add(a);
   }
   result.put("forcing_field_candidates",fieldAudit);
   FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater"),vel=s.getFieldFunctionManager().getFunction("Velocity");
   fields.add(alpha);fields.add(s.getFieldFunctionManager().getFunction("Pressure"));fields.add(vel.getComponentFunction(0));fields.add(vel.getComponentFunction(2));
   XyzInternalTable tab=s.getTableManager().createTable(XyzInternalTable.class);tab.getParts().setObjects(r);tab.setRepresentation(mesh);tab.setExtractVertexData(false);tab.setFieldFunctions(fields);tab.extract();tab.export(out.resolve("forcing_and_fields.csv").toString());
   double after=s.getSolution().getPhysicalTime();if(after!=t)throw new IllegalStateException("Audit advanced time");
   result.put("no_initialization",true);result.put("no_sim_save",true);result.put("time_after",after);result.put("status","configuration_and_spatial_fields_exported");
   Files.writeString(out.resolve("audit.json"),json(result)+"\n");s.println("M13_FORCING_AUDIT_COMPLETE_ZERO_STEPS");
  }catch(Exception e){try{Files.writeString(out.resolve("audit_error.json"),json(Map.of("error",e.toString())));}catch(Exception ignored){}throw new RuntimeException(e);}
 }
}
