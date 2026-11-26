package macro;

import star.common.*;
import star.base.neo.*;
import star.base.report.*;
import star.flow.*;
import star.vof.*;
import star.material.*;
import star.multiphase.*;
import star.vis.*;
import java.nio.file.*;
import java.util.*;

/** Read properties and evaluate reports on saved fields. Never initialize, solve, or save a SIM. */
public class NwarSavedMethodAudit extends StarMacro {
  private Simulation s;
  private FvRepresentation fv;
  private final Map<String,Object> out=new LinkedHashMap<>();
  private Path output;

  private String json(Object x) {
    if(x==null)return "null";
    if(x instanceof Number){double v=((Number)x).doubleValue();if(!Double.isFinite(v))throw new IllegalStateException("Nonfinite audit number");return x.toString();}
    if(x instanceof Boolean)return x.toString();
    if(x instanceof Map){List<String> parts=new ArrayList<>();for(Object o:((Map<?,?>)x).entrySet()){Map.Entry<?,?> e=(Map.Entry<?,?>)o;parts.add(json(e.getKey().toString())+":"+json(e.getValue()));}return "{"+String.join(",",parts)+"}";}
    if(x instanceof Collection){List<String> parts=new ArrayList<>();for(Object v:(Collection<?>)x)parts.add(json(v));return "["+String.join(",",parts)+"]";}
    return "\""+x.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r")+"\"";
  }
  private void save()throws Exception{Files.createDirectories(output);Files.writeString(output.resolve("audit.json"),json(out));}
  private double materialValue(Material m,Class<? extends MaterialProperty> type) {
    MaterialProperty prop=m.getMaterialProperties().getMaterialProperty(type);
    if(!(prop.getMethod() instanceof ConstantMaterialPropertyMethod))throw new IllegalStateException("Expected constant material property: "+type.getName());
    return ((ConstantMaterialPropertyMethod)prop.getMethod()).getQuantity().getSIValue();
  }
  private ScalarReport report(Class<? extends ScalarReport> type,FieldFunction f,List<? extends NamedObject> parts,String name) {
    ScalarReport r=s.getReportManager().createReport(type);r.setPresentationName("V3 audit "+name);
    r.setFieldFunction(f);r.getParts().setObjects(parts);r.setRepresentation(fv);r.setSmooth(false);return r;
  }
  private Map<String,Object> maximum(FieldFunction f,List<? extends NamedObject> parts,String label)throws Exception {
    MaxReport r=(MaxReport)report(MaxReport.class,f,parts,label);
    FieldFunction pos=s.getFieldFunctionManager().getFunction("Position");
    FieldFunction wd=s.getFieldFunctionManager().getFunction("WallDistance");
    List<FieldFunction> coll=List.of(pos.getComponentFunction(0),pos.getComponentFunction(1),pos.getComponentFunction(2),wd);
    r.setCollocatedFieldFunctions(coll);
    Map<String,Object> v=new LinkedHashMap<>();v.put("maximum",r.getReportMonitorValue());
    List<Double> xyz=new ArrayList<>();for(int i=0;i<3;i++)xyz.add(r.getCollocatedValue(coll.get(i)));
    v.put("position_m",xyz);v.put("wall_distance_m",r.getCollocatedValue(wd));
    r.printReport(output.resolve(label+".txt").toFile(),false);return v;
  }
  @Override public void execute() {
    s=getActiveSimulation();output=Path.of(System.getenv("NWAR_METHOD_AUDIT_OUT"));
    double before=s.getSolution().getPhysicalTime();
    try {
      Files.createDirectories(output);out.put("saved_time_before_s",before);out.put("case",System.getenv("NWAR_METHOD_AUDIT_CASE"));
      List<Region> regions=new ArrayList<>(s.getRegionManager().getRegions());
      if(regions.size()!=1)throw new IllegalStateException("Expected the one-region saved foil case");
      Region fluid=regions.get(0);PhysicsContinuum pc=fluid.getPhysicsContinuum();
      fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
      out.put("cells",fv.getCellCount());
      List<Boundary> foil=new ArrayList<>();
      for(Boundary b:fluid.getBoundaryManager().getBoundaries())if(b.getPresentationName().toLowerCase().contains("hf_012")||b.getPresentationName().toLowerCase().contains("foil"))foil.add(b);
      if(foil.size()!=1)throw new IllegalStateException("Expected one foil boundary; found "+foil.size());
      out.put("foil_boundary",foil.get(0).getPresentationName());
      List<String> models=new ArrayList<>();Object multi=null;
      for(Model m:pc.getModelManager().getObjects()){models.add(m.getClass().getName());if(m.getClass().getSimpleName().equals("EulerianMultiPhaseModel"))multi=m;}
      out.put("models",models);if(multi==null)throw new IllegalStateException("No Eulerian multiphase model");
      Object manager=multi.getClass().getMethod("getPhaseManager").invoke(multi);
      Map<String,Object> phases=new LinkedHashMap<>();
      for(String name:List.of("water","air")) {
        Phase ph=(Phase)manager.getClass().getMethod("getPhase",String.class).invoke(manager,name);
        List<Material> materials=new ArrayList<>();
        for(Model m:ph.getModelManager().getObjects())if(m instanceof MaterialModel)materials.add(((MaterialModel)m).getMaterial());
        if(materials.size()!=1)throw new IllegalStateException("Nonunique material in "+name);
        Material mat=materials.get(0);phases.put(name,Map.of("material",mat.getPresentationName(),"rho_kg_m3",materialValue(mat,ConstantDensityProperty.class),"mu_Pa_s",materialValue(mat,DynamicViscosityProperty.class)));
      }
      out.put("phases",phases);
      SegregatedVofModel vof=pc.getModelManager().getModel(SegregatedVofModel.class);
      Map<String,Object> vv=new LinkedHashMap<>();vv.put("selected_code",vof.getVolumeFractionUpwindOption().getSelected());vv.put("selected_scheme",vof.getVolumeFractionUpwindOption().getSelectedElement().name());
      vv.put("HRIC_lower",vof.getHRICSchemeParameters().getCFL_l().getSIValue());vv.put("HRIC_upper",vof.getHRICSchemeParameters().getCFL_u().getSIValue());
      vv.put("MHRIC_lower",vof.getMHRICSchemeParameters().getCFL_l().getSIValue());vv.put("MHRIC_upper",vof.getMHRICSchemeParameters().getCFL_u().getSIValue());out.put("vof",vv);
      FieldFunction yp=s.getFieldFunctionManager().getFunction("WallYplus");
      Map<String,Object> y=new LinkedHashMap<>();
      y.put("min",report(MinReport.class,yp,foil,"Yplus min").getReportMonitorValue());
      y.put("area_mean",report(AreaAverageReport.class,yp,foil,"Yplus area mean").getReportMonitorValue());
      y.put("max",report(MaxReport.class,yp,foil,"Yplus max").getReportMonitorValue());
      UserFieldFunction over=s.getFieldFunctionManager().createFieldFunction();over.setFunctionName("V3AuditYplusOverOne");over.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);over.setDefinition("(${WallYplus} > 1.0) ? 1.0 : 0.0");
      y.put("area_percent_gt_1",100.0*report(AreaAverageReport.class,over,foil,"Yplus percent area over one").getReportMonitorValue());
      y.put("mean_definition","surface-area weighted, foil wall faces, unsmoothed saved fields");out.put("yplus",y);
      FieldFunction cfl=s.getFieldFunctionManager().getFunction("CourantNumber");
      out.put("CFL_global_last_step",maximum(cfl,regions,"global_CFL"));
      FieldFunction water=null;for(FieldFunction f:s.getFieldFunctionManager().getObjects()){String n=f.getFunctionName().toLowerCase();if(n.contains("volumefraction")&&n.contains("water")){water=f;break;}}
      if(water==null)throw new IllegalStateException("Missing water fraction field");
      ThresholdPart inter=s.getPartManager().createThresholdPart();inter.setPresentationName("V3 audit interface");inter.getInputParts().setObjects(fluid);inter.setFieldFunction(water);inter.setRange(new DoubleVector(new double[]{.01,.99}));inter.setMode(ThresholdMode.BETWEEN_TAG);
      out.put("CFL_interface_last_step",maximum(cfl,List.of(inter),"interface_CFL"));out.put("interface_region","0.01 <= water volume fraction <= 0.99");
      out.put("saved_time_after_s",s.getSolution().getPhysicalTime());
      if(s.getSolution().getPhysicalTime()!=before)throw new IllegalStateException("Saved physical time advanced");
      out.put("simulation_steps_advanced",0);out.put("passed",true);save();
    }catch(Exception e){out.put("passed",false);out.put("error",e.toString());try{save();}catch(Exception x){s.println("Could not save method audit");}throw new RuntimeException(e);}
  }
}
