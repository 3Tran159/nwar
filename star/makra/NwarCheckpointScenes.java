package macro;
import star.common.*;
import star.base.neo.*;
import star.vis.*;
import star.vof.*;
import java.nio.file.*;
import java.util.*;

/** Postprocessing only, on a disposable checkpoint copy. Never advances the solution. */
public class NwarCheckpointScenes extends StarMacro {
 private Simulation s; private Region fluid; private FvRepresentation fv;
 private FieldFunction velocity,elevation; private IsoPart surface,trace; private PlaneSection mid; private StreamPart lines;
 public void execute(){
  s=getActiveSimulation();
  try{
   Path out=Paths.get(Objects.requireNonNull(System.getenv("NWAR_SCENE_OUT"))).toAbsolutePath().normalize();
   if(!out.toString().replace('\\','/').startsWith("E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/PRE_W04_20261102/scene_setup_"))throw new IllegalStateException("Dedicated scene output required");
   if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim")))throw new IllegalStateException("Disposable input required");
   double time=s.getSolution().getPhysicalTime(),expected=Double.parseDouble(System.getenv("NWAR_CHECKPOINT_TIME"));
   int iteration=s.getSimulationIterator().getCurrentIteration();
   if(Math.abs(time-expected)>1e-8)throw new IllegalStateException("Checkpoint time mismatch");
   fluid=s.getRegionManager().getRegion("fluid");fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(fv.getCellCount()!=572176)throw new IllegalStateException("Checkpoint mesh mismatch");
   String before=physics();
   FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater");
   velocity=s.getFieldFunctionManager().getFunction("Velocity");
   elevation=s.getFieldFunctionManager().getFunction("Position").getComponentFunction(2);
   mid=s.getPartManager().createPlaneSection();mid.setPresentationName("NWAR - Midspan y=0.02 m");
   mid.getInputParts().setObjects(fluid);mid.setOrigin(new DoubleVector(new double[]{0,.02,0}));mid.setOrientation(new DoubleVector(new double[]{0,1,0}));
   surface=s.getPartManager().createIsoPart();surface.setPresentationName("NWAR - Free surface alpha_water=0.5");
   surface.getInputParts().setObjects(fluid);surface.setFieldFunction(alpha);surface.setMode(IsoPart.SINGLE);surface.getSingleIsoValue().setValue(.5);
   trace=s.getPartManager().createIsoPart();trace.setPresentationName("NWAR - Free-surface contour on midspan");
   trace.getInputParts().setObjects(mid);trace.setFieldFunction(alpha);trace.setMode(IsoPart.SINGLE);trace.getSingleIsoValue().setValue(.5);
   lines=s.getPartManager().createStreamPart();lines.setPresentationName("NWAR - Instantaneous foil streamlines");
   lines.getInputParts().setObjects(fluid);lines.setFieldFunction(velocity);lines.setMode(StreamPart.LINESEED);
   lines.getLineSeed().setPoint1(new DoubleVector(new double[]{-2,.02,-1.5}));lines.getLineSeed().setPoint2(new DoubleVector(new double[]{-2,.02,3.2}));lines.getLineSeed().setResolution(55);
   lines.getIntegrator().setDirection(StreamPart.BOTH);lines.getIntegrator().setMaxPropagation(32);lines.getIntegrator().setMaximumNumberOfSteps(2400);
   Scene overview=scene("NWAR 01 - Wave elevation and velocity",10,0,24,false);
   Scene near=scene("NWAR 02 - Wave and foil streamlines",1.5,2.5,5.3,true);
   Scene foil=scene("NWAR 03 - Foil velocity and streamlines",.6,0,1.4,true);
   for(Scene scene:List.of(overview,near,foil))scene.initializeAndWait();
   overview.printAndWait(out.resolve("wave_elevation_velocity.png").toString(),1,1800,650,true,false);
   near.printAndWait(out.resolve("wave_foil_streamlines.png").toString(),1,1600,900,true,false);
   foil.printAndWait(out.resolve("foil_velocity_streamlines.png").toString(),1,1600,900,true,false);
   if(!before.equals(physics())||Math.abs(s.getSolution().getPhysicalTime()-time)>1e-12||s.getSimulationIterator().getCurrentIteration()!=iteration)throw new IllegalStateException("Physical state changed during scene setup");
   Files.writeString(out.resolve("physics_before.txt"),before);Files.writeString(out.resolve("physics_after.txt"),physics());
   s.saveState(out.resolve("final.sim").toString());
   Files.writeString(out.resolve("scene_receipt.json"),"{\"passed\":true,\"time_s\":"+time+",\"iteration\":"+iteration+",\"steps_advanced\":0,\"fields_cleared\":false,\"physics_changed\":false,\"cells\":572176,\"water_isovalue\":0.5,\"surface_colour\":\"Position Z [m]\",\"plane_y_m\":0.02,\"velocity_colour\":\"Velocity magnitude [m/s]\",\"streamlines\":\"Instantaneous, both directions from a line upstream of the foil\",\"scenes\":[\"NWAR 01 - Wave elevation and velocity\",\"NWAR 02 - Wave and foil streamlines\",\"NWAR 03 - Foil velocity and streamlines\"]}");
   Files.writeString(out.resolve("completed.json"),"{\"status\":\"scene_prepared\",\"time_s\":"+time+",\"steps\":0}");
  }catch(Exception e){throw new RuntimeException(e);}
 }
 private String physics(){
  PhysicsContinuum pc=(PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
  FlatVofWave calm=(FlatVofWave)pc.getModelManager().getModel(VofWaveModel.class).getVofWaveManager().getVofWave("Calm");
  StringBuilder b=new StringBuilder();
  b.append("time=").append(s.getSolution().getPhysicalTime()).append("\niteration=").append(s.getSimulationIterator().getCurrentIteration()).append("\ncells=").append(fv.getCellCount());
  b.append("\ndt=").append(s.getSolverManager().getSolver(ImplicitUnsteadySolver.class).getTimeStep().getSIValue());
  b.append("\ncurrent=").append(calm.getCurrent().getDefinition()).append("\nwind=").append(calm.getWind().getDefinition());
  b.append("\nrho_water=").append(calm.getHeavyFluidDensity().getSIValue()).append("\nmodels=").append(pc.getModelManager().getObjects());
  for(Boundary boundary:fluid.getBoundaryManager().getBoundaries())b.append("\n").append(boundary.getPresentationName()).append(":").append(boundary.getBoundaryType().getClass().getName());
  return b.toString();
 }
 private Scene scene(String name,double x,double z,double scale,boolean streamlines){
  Scene sc=s.getSceneManager().createScene(name);
  sc.setBackgroundColorMode(BackgroundColorMode.SOLID);sc.getSolidBackgroundColor().setColor(new DoubleVector(new double[]{1,1,1}));
  ScalarDisplayer speed=sc.getDisplayerManager().createScalarDisplayer("Midspan velocity magnitude");
  speed.setRepresentation(fv);speed.getInputParts().setObjects(mid);speed.getScalarDisplayQuantity().setFieldFunction(velocity.getMagnitudeFunction());
  speed.getScalarDisplayQuantity().setAutoRange(false);speed.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{0,30}));speed.setOpacity(.8);
  legend(speed.getLegend(),"Velocity magnitude [m/s]",.03);
  ScalarDisplayer height=sc.getDisplayerManager().createScalarDisplayer("Free-surface position Z");
  height.setRepresentation(fv);height.getInputParts().setObjects(surface,trace);height.getScalarDisplayQuantity().setFieldFunction(elevation);
  height.getScalarDisplayQuantity().setAutoRange(false);height.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{0,8}));height.setLineWidth(4);
  legend(height.getLegend(),"Free-surface position Z [m]",.58);
  PartDisplayer edge=sc.getDisplayerManager().createPartDisplayer("Free-surface outline");edge.setRepresentation(fv);edge.getInputParts().setObjects(surface);edge.setSurface(false);edge.setOutline(true);edge.setDisplayerColor(new DoubleVector(new double[]{.1,.2,.2}));edge.setLineWidth(2);
  if(streamlines){
   StreamDisplayer flow=sc.getDisplayerManager().createStreamDisplayer("Instantaneous flow around foil");
   flow.setRepresentation(fv);flow.getInputParts().setObjects(lines);flow.setFieldFunction(velocity);
   flow.getScalarDisplayQuantity().setFieldFunction(velocity.getMagnitudeFunction());flow.setColorMode(StreamColorMode.CONSTANT);flow.setLineWidth(1.3);flow.getLegend().setVisible(false);
  }
  PartDisplayer body=sc.getDisplayerManager().createPartDisplayer("Foil");body.setRepresentation(fv);body.getInputParts().setObjects(fluid.getBoundaryManager().getBoundary("HF_012_wall"));
  body.setSurface(true);body.setOutline(true);body.setDisplayerColor(new DoubleVector(new double[]{.15,.17,.2}));body.setLineWidth(2);
  CurrentView view=sc.getCurrentView();view.setProjectionMode(VisProjectionMode.PARALLEL);view.setFocalPoint(new DoubleVector(new double[]{x,.02,z}));view.setPosition(new DoubleVector(new double[]{x,-250,z}));view.setViewUp(new DoubleVector(new double[]{0,0,1}));view.setParallelScale(scale);
  return sc;
 }
 private void legend(Legend l,String title,double x){l.setDataName(title);l.setPositionCoordinate(new DoubleVector(new double[]{x,.04}));l.setWidth(.36);l.setHeight(.025);l.setTitleHeight(.018);l.setLabelHeight(.017);l.setNumberOfLabels(5);l.setLabelFormat("%.1f");}
}
