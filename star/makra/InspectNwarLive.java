package macro;
import star.common.*;
import star.vis.*;
import java.nio.file.*;

/** Read-only inspection of the already running session; never steps or saves. */
public class InspectNwarLive extends StarMacro {
 public void execute() {
  Simulation s=getActiveSimulation();
  try {
   String session=s.getSessionPath().replace('\\','/');
   if(!session.startsWith("E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/PRE_W04_20261102/"))throw new IllegalStateException("Unexpected live simulation");
   StringBuilder b=new StringBuilder("session="+session+"\ntime_s="+s.getSolution().getPhysicalTime()+"\n");
   for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getFunctionName().matches("(?i).*(position|centroid|volumefractionwater|velocity).*"))b.append("field="+f.getFunctionName()+" "+f.getClass().getSimpleName()+"\n");
   for(Scene sc:s.getSceneManager().getScenes())b.append("scene="+sc.getPresentationName()+"\n");
   for(Region r:s.getRegionManager().getRegions())b.append("region="+r.getPresentationName()+"\n");
   Files.writeString(Paths.get("C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/nwar_automation/qa/live_scene_probe.txt"),b.toString());
   s.println("NWAR read-only live scene inspection complete.");
  }catch(Exception e){throw new RuntimeException(e);}
 }
}
