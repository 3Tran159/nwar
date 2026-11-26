package macro;
import star.common.*;
import star.vis.*;
import star.base.neo.*;
import java.io.*;
import java.util.*;
import java.lang.reflect.*;
import java.nio.file.*;

public class AuditVisuals extends StarMacro {
  private PrintWriter out;
  private String val(Object x) {
    if(x == null) return "<null>";
    String t = String.valueOf(x).replace("\r"," ").replace("\n"," ");
    return t.length()>600?t.substring(0,600):t;
  }
  private String call(Object o, String m) {
    try { Method x=o.getClass().getMethod(m); return val(x.invoke(o)); }
    catch(Throwable e) { return "ERR:"+e.getClass().getSimpleName(); }
  }
  private void info(String name,Object o) {
    out.println(name+"  CLASS="+o.getClass().getName());
    for(String fn:new String[]{"getModeEnum","getFieldFunction","getRepresentation","getParts","getInputParts",
      "getVisible","getWidth","getLineWidth","getScalarDisplayQuantity","getStreamColorModeEnum",
      "getColorModeEnum","getColorMode","getDisplayMode","getLegend","getCurrentView","getView","getInput",
      "getDisplayerMode","getVectorField","getColorModeEnum","getPartSurfaces","getNumPoints","getOrigin","getNormal",
      "getOpacity","getOutline","getSceneTransparency","getInputPartsInput"}) {
      String v=call(o,fn); if(!v.startsWith("ERR:"))out.println("    "+fn+" = "+v);
    }
  }
  public void execute(){
    Simulation s=getActiveSimulation();
    try {
      Path target=Paths.get("E:/ntnu_cfd_night_20261028/visualisations_20261029/d002_audit.txt");
      out=new PrintWriter(Files.newBufferedWriter(target));
      out.println("SOURCE "+s.getSessionPath());
      out.println("ITER "+s.getSimulationIterator().getCurrentIteration());
      out.println("TIME "+s.getSolution().getPhysicalTime());
      out.println("-- PARTS --");
      for(Object p:s.getPartManager().getObjects()){
        info("PART "+((NamedObject)p).getPresentationName(),p);
        if(p instanceof StreamPart) {
          StreamPart sp=(StreamPart)p;
          out.println("    LINE_MODE "+sp.getModeEnum()+"  VECTOR "+val(sp.getFieldFunction()));
          LineSeed sd=sp.getLineSeed();
          if(sd!=null){
            out.println("    P1 "+val(sd.getPoint1())+" P2 "+val(sd.getPoint2())+" N "+sd.getResolution());
            out.println("    CSYS "+val(sd.getCoordinateSystem()));
          }
        }
      }
      out.println("-- SCENES --");
      for(Object x:s.getSceneManager().getObjects()){
        SceneBase sc=(SceneBase)x;
        info("SCENE "+sc.getPresentationName(),sc);
        for(Object dis:sc.getDisplayerManager().getObjects()){
          info("  DISP "+((NamedObject)dis).getPresentationName(),dis);
        }
      }
      out.flush();out.close();
      s.println("AUDIT_VISUALS_DONE");
    }catch(Throwable e) {
      if(out!=null){e.printStackTrace(out);out.close();}
      throw new RuntimeException(e);
    }
  }
}
