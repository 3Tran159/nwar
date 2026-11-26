package macro;
import star.common.*;
import star.vis.*;
import star.base.neo.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public class D002Vertical5mm extends StarMacro {
  public void execute() {
    Simulation s=getActiveSimulation();
    Path source=Paths.get("E:/ntnu_cfd_night_20261028/D002/checkpoint_visualisation.sim");
    Path target=Paths.get("E:/ntnu_cfd_night_20261028/D002/checkpoint_visualisation_5mm.sim");
    Path record=Paths.get("E:/ntnu_cfd_night_20261028/visualisations_20261029/D002_actions.txt");
    List<String> log=new ArrayList<>();
    try {
      if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(source))
        throw new IllegalStateException("Only D002 user visualization is allowed as source");
      if(Files.exists(target))throw new IllegalStateException("Output already exists: "+target);
      s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
      s.getSimulationIterator().getAutoSave().setEnabled(false);
      Scene scene=null;
      for(SceneBase obj:s.getSceneManager().getObjects())
        if(obj.getPresentationName().equals("streamlines")) scene=(Scene)obj;
      if(scene==null)throw new IllegalStateException("Missing streamlines scene");
      StreamDisplayer display=null;
      for(DisplayerBase disp:scene.getDisplayerManager().getObjects())
        if(disp instanceof StreamDisplayer)display=(StreamDisplayer)disp;
      if(display==null)throw new IllegalStateException("Missing streamlines displayer");
      List<StreamPart> parts=new ArrayList<>();
      for(Part p:s.getPartManager().getObjects())
        if(p instanceof StreamPart)parts.add((StreamPart)p);
      if(parts.size()<7)throw new IllegalStateException("Expected seven existing line stream parts, got "+parts.size());
      FieldFunction velocity=parts.get(0).getFieldFunction();
      Region fluid=s.getRegionManager().getRegion("fluid");
      for(int k=0;k<=10;k++){
        double z=k*0.005;
        StreamPart found=null;
        for(StreamPart sp:parts)if(sp.getModeEnum()==SeedMode.LINE && 
          Math.abs(sp.getLineSeed().getPoint1().get(2)-z)<0.000001)found=sp;
        if(found!=null){
          LineSeed line=found.getLineSeed();
          if(line.getResolution()!=60)line.setResolution(60);
          log.add("REUSED "+found.getPresentationName()+" z="+z);
        }else{
          StreamPart p=s.getPartManager().createStreamPart();
          p.setPresentationName(String.format(java.util.Locale.ROOT,"NTNU_Stream_Z_%03d_mm",Math.round(z*1000)));
          p.setMode(SeedMode.LINE);
          p.setInputPartsCollection(Collections.singletonList(fluid));
          p.setFieldFunction(velocity);
          LineSeed line=p.getLineSeed();
          line.setPoint1(new DoubleVector(new double[]{-1.5,5.5,z}));
          line.setPoint2(new DoubleVector(new double[]{-1.5,0,z}));
          line.setResolution(60);
          parts.add(p);
          log.add("CREATED "+p.getPresentationName()+" z="+z+" n="+line.getResolution());
        }
      }
      List<NamedObject> all=new ArrayList<>();
      for(StreamPart p:parts)all.add(p);
      display.setDisplayerParts(all);
      display.setMode(StreamDisplayerMode.TUBES);
      display.setWidth(0.002);
      display.setColorMode(StreamColorMode.SCALAR);
      log.add("SELECTED_PARTS "+all.size()+" scene="+scene.getPresentationName()+" disp="+display.getPresentationName());
      log.add("ITER "+s.getSimulationIterator().getCurrentIteration()+" TIME "+s.getSolution().getPhysicalTime());
      s.saveState(target.toString());
      log.add("SAVED "+target.toString()+" bytes="+Files.size(target));
      try {
        Path png=Paths.get("E:/ntnu_cfd_night_20261028/visualisations_20261029/D002_streamlines_5mm.png");
        scene.printAndWait(png.toString(),1,1920,1080,true,false);
        log.add("PNG "+png.toString()+" bytes="+Files.size(png));
      }catch(Throwable ex){log.add("PNG_EXPORT_WARNING "+ex.toString());}
      Files.write(record,log);
      s.println("NTNU_D002_VERTICAL_5MM_DONE "+target);
    } catch(Throwable e){
      log.add("ERROR "+e.toString());
      try{Files.write(record,log);}catch(Exception ignored){}
      throw new RuntimeException(e);
    }
  }
}
