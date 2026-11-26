package macro;
import star.common.*;
import star.base.report.*;
import java.util.*;
/** Strictly read-only physics diagnostic: no iterator, initialization, save or boundary changes. */
public class AuditWavePressureReadOnly_20261031 extends StarMacro {
  private double maximum(Simulation s,FieldFunction f,Region r,FvRepresentation v) {
    MaxReport q=s.getReportManager().createReport(MaxReport.class);
    q.setFieldFunction(f);q.setRepresentation(v);q.getParts().setObjects(r);
    return q.getReportMonitorValue();
  }
  private double minimum(Simulation s,FieldFunction f,Region r,FvRepresentation v) {
    MinReport q=s.getReportManager().createReport(MinReport.class);
    q.setFieldFunction(f);q.setRepresentation(v);q.getParts().setObjects(r);
    return q.getReportMonitorValue();
  }
  public void execute() {
    Simulation s=getActiveSimulation();
    if(!s.getSessionPath().endsWith("input.sim"))throw new IllegalStateException("Expected disposable input.sim");
    if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("Read-only CPU only");
    Region f=s.getRegionManager().getRegion("fluid");
    FvRepresentation v=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
    FieldFunction pres=s.getFieldFunctionManager().getFunction("Pressure");
    FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater");
    FieldFunction speed=s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction();
    if(pres==null||alpha==null||speed==null)throw new IllegalStateException("Required physical fields missing");
    s.println("PRESSURE_AUDIT_START time="+s.getSolution().getPhysicalTime()+" cells="+v.getCellCount());
    s.println("PRESSURE_AUDIT_P_MIN "+minimum(s,pres,f,v));
    s.println("PRESSURE_AUDIT_P_MAX "+maximum(s,pres,f,v));
    s.println("PRESSURE_AUDIT_V_MIN "+minimum(s,speed,f,v));
    s.println("PRESSURE_AUDIT_V_MAX "+maximum(s,speed,f,v));
    s.println("PRESSURE_AUDIT_WATERFRACTION_MIN "+minimum(s,alpha,f,v));
    s.println("PRESSURE_AUDIT_WATERFRACTION_MAX "+maximum(s,alpha,f,v));
    s.println("PRESSURE_AUDIT_COMPLETE_NO_STEPS_NO_SAVE");
  }
}