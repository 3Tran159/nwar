package macro;
import star.common.*;
import star.vis.*;
import star.base.neo.*;
import java.awt.Color;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public class MakeVisualGallery extends StarMacro {
  private final List<String> log=new ArrayList<>();
  private Simulation sim;
  private Path root=Paths.get("E:/ntnu_cfd_night_20261028");
  private String id;
  private Region fluid;
  private Boundary foil;
  private FieldFunction velocity,velmag,pressure,zpos;
  private ArrayList<StreamPart> lines=new ArrayList<>();
  private Map<String,Scene> scenes=new LinkedHashMap<>();
  private Part waterIso,qIso;

  private void record(String v){log.add(v);sim.println("[NTNU_GALLERY] "+v);}
  private Part findPart(String name){
    for(Part p:sim.getPartManager().getObjects())if(p.getPresentationName().equals(name))return p;
    return null;
  }
  private Scene findScene(String name){
    for(SceneBase sc:sim.getSceneManager().getObjects())
      if(sc.getPresentationName().equals(name) && sc instanceof Scene)return (Scene)sc;
    return null;
  }
  private Scene create(String name,boolean freeSurface){
    Scene s=findScene(name);
    if(s==null)s=sim.getSceneManager().createScene(name);
    s.setBackgroundColorMode(BackgroundColorMode.SOLID);
    s.getSolidBackgroundColor().setColorColor(new Color(11,21,32));
    DoubleVector fp=new DoubleVector(freeSurface?new double[]{0.4,2.75,2.0}:new double[]{0.4,2.75,0.05});
    DoubleVector pos=new DoubleVector(freeSurface?new double[]{-5.0,9.5,7.0}:new double[]{-5.0,8.5,3.8});
    s.getCurrentView().setInput(fp,pos,new DoubleVector(new double[]{0,0,1}),freeSurface?4.5:3.6,1);
    scenes.put(name,s);return s;
  }
  private PartDisplayer foilDisplay(Scene s){
    PartDisplayer d=s.getDisplayerManager().createPartDisplayer("Hydrofoil - light gray");
    d.setDisplayerParts(Collections.singletonList(foil));
    d.setColorMode(PartColorMode.CONSTANT);
    d.setDisplayerColorColor(new Color(201,210,222));
    d.setSurface(true);
    d.setOutline(false);
    d.setOpacity(0.98);
    return d;
  }
  private ScalarDisplayer scalar(Scene s,String name,NamedObject part,FieldFunction ff){
    ScalarDisplayer d=s.getDisplayerManager().createScalarDisplayer(name);
    d.setDisplayerParts(Collections.singletonList(part));
    d.getScalarDisplayQuantity().setFieldFunction(ff);
    d.getLegend().setVisible(true);
    d.getLegend().setLevels(64);
    return d;
  }
  private void makeStreams(){
    for(Part p:sim.getPartManager().getObjects())if(p instanceof StreamPart){
      StreamPart sp=(StreamPart)p;
      if(sp.getModeEnum()==SeedMode.LINE)lines.add(sp);
    }
    for(int i=0;i<=10;i++){
      double z=0.005*i;StreamPart found=null;
      for(StreamPart sp:lines)if(Math.abs(sp.getLineSeed().getPoint1().get(2)-z)<1e-6
        && Math.abs(sp.getLineSeed().getPoint1().get(0)+1.5)<1e-4)found=sp;
      if(found==null){
        found=sim.getPartManager().createStreamPart();
        found.setPresentationName(String.format(Locale.ROOT,"NTNU_5mm_Z_%03d",i*5));
        found.setMode(SeedMode.LINE);
        found.setInputPartsCollection(Collections.singletonList(fluid));
        found.setFieldFunction(velocity);
        LineSeed sd=found.getLineSeed();
        sd.setPoint1(new DoubleVector(new double[]{-1.5,5.5,z}));
        sd.setPoint2(new DoubleVector(new double[]{-1.5,0,z}));
        sd.setResolution(60);
        lines.add(found);
      }else found.getLineSeed().setResolution(60);
    }
    int good=0;
    for(StreamPart sp:lines)if(sp.getModeEnum()==SeedMode.LINE && Math.abs(sp.getLineSeed().getPoint1().get(0)+1.5)<0.0001)good++;
    record("StreamPart count="+good+", line interval=0.005m, horizontal resolution=60");
  }
  private void makeGallery(){
    Scene s=create("NTNU_5mm_Streamlines",false);
    foilDisplay(s);
    StreamDisplayer stream=s.getDisplayerManager().createStreamDisplayer("Velocity | 5 mm vertical seeds");
    ArrayList<NamedObject> p=new ArrayList<>(); for(StreamPart x:lines)p.add(x);
    stream.setDisplayerParts(p);
    stream.setMode(StreamDisplayerMode.TUBES);
    stream.setWidth(0.002);
    stream.setColorMode(StreamColorMode.SCALAR);
    stream.setFieldFunction(velmag);
    stream.getScalarDisplayQuantity().setFieldFunction(velmag);
    stream.getLegend().setVisible(true);
    stream.getLegend().setLevels(64);
    stream.getScalarDisplayQuantity().setAutoRange(AutoRangeMode.NONE);
    stream.getScalarDisplayQuantity().setRangeMin(10.0);
    stream.getScalarDisplayQuantity().setRangeMax(24.0);
    record("SCENE "+s.getPresentationName()+" tubes=0.002m "+p.size()+" seed lines");

    if(waterIso!=null){
      Scene water=create("NTNU_5mm_Water_Surface",true);
      foilDisplay(water);
      ScalarDisplayer height=scalar(water,"Elevation Z | VOF=0.5",waterIso,zpos);
      height.getLegend().setLevels(64);
      record("SCENE "+water.getPresentationName()+" iso="+waterIso.getPresentationName());
    }

    Scene press=create("NTNU_5mm_Foil_Pressure",false);
    scalar(press,"Pressure on foil",foil,pressure);
    record("SCENE "+press.getPresentationName());

    if(qIso!=null){
      Scene vort=create("NTNU_5mm_Vortices_Q",false);
      foilDisplay(vort);
      scalar(vort,"Q criterion iso | colored velocity",qIso,velmag);
      record("SCENE "+vort.getPresentationName()+" iso="+qIso.getPresentationName());
    }
    Part plane=findPart("section_plane");
    if(plane!=null){
      Scene vels=create("NTNU_5mm_Velocity_Section",false);
      scalar(vels,"Velocity magnitude [m/s] in section",plane,velmag);
      foilDisplay(vels);
      record("SCENE "+vels.getPresentationName());
    }
  }
  public void execute(){
    sim=getActiveSimulation();
    Path input=Paths.get(sim.getSessionPath()).toAbsolutePath().normalize();
    Path out=null;
    try{
      id=input.getParent().getFileName().toString();
      if(!id.matches("D00[1234]"))throw new IllegalStateException("Unexpected case "+id);
      Path expected=root.resolve(id).resolve(id.equals("D002")?"checkpoint_visualisation_5mm.sim":"checkpoint.sim").toAbsolutePath().normalize();
      if(!input.equals(expected))throw new IllegalStateException("Refusing unexpected source: "+input);
      out=root.resolve(id).resolve(id.equals("D002")?"checkpoint_visualisation_gallery.sim":"checkpoint_visualisation_5mm.sim");
      if(Files.exists(out))throw new IllegalStateException("Output already exists: "+out);
      sim.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
      sim.getSimulationIterator().getAutoSave().setEnabled(false);
      fluid=sim.getRegionManager().getRegion("fluid");
      foil=fluid.getBoundaryManager().getBoundary("HF_v2 2.ColoredFace1");
      velocity=sim.getFieldFunctionManager().getFunction("Velocity");
      velmag=velocity.getMagnitudeFunction();
      pressure=sim.getFieldFunctionManager().getFunction("Pressure");
      zpos=sim.getFieldFunctionManager().getFunction("Position").getComponentFunction(2);
      waterIso=findPart("Isosurface");
      qIso=findPart("isosurf vorticity");
      if(qIso==null){
        IsoPart qi=sim.getPartManager().createIsoPart();
        qi.setPresentationName("NTNU_QCriterion_200");
        qi.setInputPartsCollection(Collections.singletonList(fluid));
        qi.setFieldFunction(sim.getFieldFunctionManager().getFunction("QCriterion"));
        qi.getSingleIsoValue().setValue(200.0);
        qIso=qi;
      }
      record("Case="+id+" source="+input+" iter="+sim.getSimulationIterator().getCurrentIteration()+" t="+sim.getSolution().getPhysicalTime());
      makeStreams();
      makeGallery();
      sim.saveState(out.toString());
      record("SAVED "+out+" size="+Files.size(out));
      for(Map.Entry<String,Scene> e:scenes.entrySet()){
        try{
          Path png=root.resolve("visualisations_20261029").resolve(id+"_"+e.getKey()+".png");
          e.getValue().printAndWait(png.toString(),1,1600,900,true,false);
          record("PNG "+png+" bytes="+Files.size(png));
        }catch(Throwable ex){record("EXPORT_WARNING "+e.getKey()+": "+ex.getMessage());}
      }
      record("DONE "+id+" scenes="+scenes.size());
    }catch(Throwable ex){
      record("FATAL "+ex.toString());
      throw new RuntimeException(ex);
    }finally{
      try{Files.write(root.resolve("visualisations_20261029").resolve(id+"_gallery_actions.txt"),log);}catch(Exception ignored){}
    }
  }
}
