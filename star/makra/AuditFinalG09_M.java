package macro;
import star.common.*;import star.meshing.*;import star.prismmesher.*;import star.base.neo.*;import star.base.report.*;import star.vis.*;import java.nio.file.*;import java.util.*;
public class AuditFinalG09_M extends StarMacro {
private Path out;private Simulation s;private List<String> notes=new ArrayList<>();
public void execute(){s=getActiveSimulation();out=Paths.get("C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/mesh_study_20261030/gci_m09_20261030/G09_M");
try{Region reg=s.getRegionManager().getRegion("fluid");FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");long cells=fv.getCellCount();
 Map<String,Object> metrics=new LinkedHashMap<>();metrics.put("cell_count",cells);metrics.put("mesh_time_s",0);
 NeoProperty report=fv.generateMeshReport(List.of(reg));Files.writeString(out.resolve("mesh_report_properties.txt"),report.toFormattedString());
 for(String key:List.of("NegativeVolumeCells","UnclosedCells","DegeneratedFeCells"))metrics.put(key,report.get(key));
 scalar(metrics,"min_cell_quality",new String[]{"CellQuality"},false,reg,fv);scalar(metrics,"min_volume_change",new String[]{"VolumeChange"},false,reg,fv);scalar(metrics,"min_face_validity",new String[]{"FaceValidity"},false,reg,fv);scalar(metrics,"max_skewness_angle_deg",new String[]{"SkewnessAngle"},true,reg,fv);
 diagnostics(metrics,"CellQuality",.01,false,reg,fv);diagnostics(metrics,"VolumeChange",.01,false,reg,fv);diagnostics(metrics,"SkewnessAngle",80,true,reg,fv);notes.add("Directed sweep does not retain PrismLayerNumber metadata; audit layered topology separately.");
 FieldFunction y=s.getFieldFunctionManager().getFunction("Position").getComponentFunction(1);
 MinReport ymin=s.getReportManager().createReport(MinReport.class);MaxReport ymax=s.getReportManager().createReport(MaxReport.class);
 for(ScalarReport q:List.of(ymin,ymax)){q.setFieldFunction(y);q.getParts().setObjects(reg);q.setRepresentation(fv);}
 double yl=ymin.getReportMonitorValue(),yh=ymax.getReportMonitorValue();metrics.put("centroid_y_min_m",yl);metrics.put("centroid_y_max_m",yh);metrics.put("centroid_y_range_m",yh-yl);
 notes.add("Centroid y mismatch needs topology inspection before flow.");
 XyzInternalTable tab=s.getTableManager().createTable(XyzInternalTable.class);tab.setRepresentation(fv);tab.getParts().setObjects(reg);tab.setExtractVertexData(false);tab.setFieldFunctions(List.of(s.getFieldFunctionManager().getFunction("CellQuality"),s.getFieldFunctionManager().getFunction("PrismLayerNumber")));tab.extract();tab.export(out.resolve("mesh_cells.csv").toString());
 ImportManager im=s.getImportManager();im.setFormatType(SolutionExportFormat.Type.CGNS);im.export(out.resolve("mesh.CGNS").toString(),List.of(reg),List.of(s.getFieldFunctionManager().getFunction("CellQuality")),List.of());
 s.saveState(out.resolve("mesh.sim").toString());
 Files.writeString(out.resolve("measurement.json"),json(Map.of("case_id","G09_M","status","mesh_generated","metrics",metrics,"notes",notes)));
 }catch(Exception e){try{Files.writeString(out.resolve("audit_error.txt"),e.toString());}catch(Exception x){}throw new RuntimeException(e);}
}
  private void scalar(Map<String,Object> metrics,String key,String[] names,boolean maximum,NamedObject reg,FvRepresentation fv){
    try{
      FieldFunction f=null;for(String name:names)if(s.getFieldFunctionManager().hasFunction(name)){f=s.getFieldFunctionManager().getFunction(name);break;}
      if(f==null){notes.add("Unavailable field for "+key);return;}
      ScalarReport report=maximum?s.getReportManager().createReport(MaxReport.class):s.getReportManager().createReport(MinReport.class);
      report.setPresentationName("NTNU_"+key);report.setFieldFunction(f);report.getParts().setObjects(reg);report.setRepresentation(fv);
      double value=report.monitoredValue();String errors=report.getErrorLog();
      report.printReport(out.resolve(key+".txt").toString(),false);
      if(!Double.isFinite(value)||!errors.isBlank()){notes.add(key+" report error: "+errors);return;}
      // STAR 21.02 SkewnessAngle is dimensionless, with numerical values already in degrees.
      metrics.put(key,value);notes.add(key+" field="+f.getFunctionName()+" population="+reg.getPresentationName()+" units="+report.getUnits());
    }catch(Exception e){notes.add(key+" unavailable: "+e);}
  }
  private void prismAudit(Map<String,Object> metrics,Region region,FvRepresentation fv){
    try{
      Boundary foil=(Boundary)region.getBoundaryManager().getObject("HF_012_wall");
      scalar(metrics,"min_foil_prism_layers",new String[]{"PrismLayerNumber"},false,foil,fv);
      scalar(metrics,"max_foil_prism_layers",new String[]{"PrismLayerNumber"},true,foil,fv);
      scalar(metrics,"min_foil_prism_total_thickness_m",new String[]{"PrismCellThickness"},false,foil,fv);
      scalar(metrics,"max_foil_prism_total_thickness_m",new String[]{"PrismCellThickness"},true,foil,fv);
      for(String mode:List.of("any","full_15")){
        UserFieldFunction mask=s.getFieldFunctionManager().createFieldFunction();mask.setPresentationName("NTNU_coverage_"+mode);mask.setFunctionName("NTNU_coverage_"+mode);
        mask.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
        mask.setDefinition("${PrismLayerNumber} >= "+(mode.equals("any")?"0.5":"14.5")+" ? 1.0 : 0.0");
        AreaAverageReport area=s.getReportManager().createReport(AreaAverageReport.class);area.setPresentationName("NTNU_foil_area_coverage_"+mode);
        area.setFieldFunction(mask);area.setRepresentation(fv);area.getParts().setObjects(foil);
        double fraction=area.monitoredValue();area.printReport(out.resolve("foil_coverage_"+mode+".txt").toString(),false);
        if(!Double.isFinite(fraction)||!area.getErrorLog().isBlank())throw new IllegalStateException(area.getErrorLog());
        metrics.put("foil_area_fraction_"+mode+"_prism_layers",fraction);
      }
      FieldFunction layer=s.getFieldFunctionManager().getFunction("PrismLayerNumber");
      ThresholdPart first=s.getPartManager().createThresholdPart();first.setPresentationName("NTNU_first_prism_layer");
      first.getInputParts().setObjects(region);first.setFieldFunction(layer);first.setRange(new DoubleVector(new double[]{0.5,1.5}));first.setMode(ThresholdMode.BETWEEN_TAG);
      scalar(metrics,"min_first_prism_cell_thickness_m",new String[]{"PrismCellThickness"},false,first,fv);
      scalar(metrics,"max_first_prism_cell_thickness_m",new String[]{"PrismCellThickness"},true,first,fv);
      diagnostics(metrics,"PrismLayerNumber",14.5,false,foil,fv);
      notes.add("Prism layer-number and thickness fields are STAR geometry diagnostics; coverage is foil-area-weighted, not achieved y-plus.");
    }catch(Exception e){notes.add("Prism diagnostics incomplete: "+e);}
  }
  private void diagnostics(Map<String,Object> metrics,String name,double cutoff,boolean above,NamedObject reg,FvRepresentation fv){
    try{
      if(!s.getFieldFunctionManager().hasFunction(name))return;
      FieldFunction f=s.getFieldFunctionManager().getFunction(name);
      ThresholdPart part=s.getPartManager().createThresholdPart();part.setPresentationName("NTNU_diagnostic_"+name);
      part.getInputParts().setObjects(reg);part.setFieldFunction(f);part.setRange(new DoubleVector(new double[]{cutoff,cutoff}));
      part.setMode(above?ThresholdMode.ABOVE_TAG:ThresholdMode.BELOW_TAG);
      ElementCountReport report=s.getReportManager().createReport(ElementCountReport.class);report.setPresentationName("NTNU_count_"+name);
      report.setRepresentation(fv);report.getParts().setObjects(part);double count=report.getReportMonitorValue();
      if(!report.getErrorLog().isBlank()||!Double.isFinite(count))throw new IllegalStateException(report.getErrorLog());
      metrics.put("diagnostic_"+name+(above?"_above_":"_below_")+cutoff,count);
      if(count>0&&count<=100000){
        XyzInternalTable table=s.getTableManager().createTable(XyzInternalTable.class);table.setPresentationName("NTNU_cells_"+name);
        table.getParts().setObjects(part);table.setFieldFunctions(List.of(f));table.setRepresentation(fv);table.setExtractVertexData(false);
        table.extract();table.export(out.resolve("diagnostic_"+name+".csv").toString());
      }
      notes.add("Diagnostic "+name+(above?" > ":" < ")+cutoff+": "+count+" elements in "+reg.getPresentationName()+"; review trigger, not universal acceptance limit");
    }catch(Exception e){notes.add("Local diagnostic "+name+" unavailable: "+e);}
  }
  private static String json(Object o) {
    if(o==null)return "null";
    if(o instanceof Number){double x=((Number)o).doubleValue();return Double.isFinite(x)?o.toString():"null";}
    if(o instanceof Boolean)return o.toString();
    if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(Object x:((Map<?,?>)o).entrySet()){Map.Entry<?,?> e=(Map.Entry<?,?>)x;j.add(json(e.getKey().toString())+":"+json(e.getValue()));}return j.toString();}
    if(o instanceof Collection){StringJoiner j=new StringJoiner(",","[","]");for(Object x:(Collection<?>)o)j.add(json(x));return j.toString();}
    String t=o.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\r","\\r").replace("\n","\\n").replace("\t","\\t");
    return "\""+t+"\"";
  }
}