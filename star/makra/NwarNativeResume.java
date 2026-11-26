package macro;
import java.nio.file.*;
import java.util.*;
import star.common.*;
import star.base.neo.*;
import star.vof.*;
import star.vis.*;
import star.post.*;

/** Zero-step preparation of a native continuation with a separate field segment. */
public class NwarNativeResume extends StarMacro {
 public void execute() {
  Simulation s=getActiveSimulation();
  Path out=Path.of(System.getenv("NWAR_NATIVE_RESUME_OUT"));
  double expected=Double.parseDouble(System.getenv("NWAR_NATIVE_RESUME_TIME"));
  double target=Double.parseDouble(System.getenv("NWAR_NATIVE_RESUME_TARGET"));
  double dt=Double.parseDouble(System.getenv("NWAR_NATIVE_RESUME_DT"));
  int stride=Integer.parseInt(System.getenv("NWAR_NATIVE_RESUME_STRIDE"));
  int start=Integer.parseInt(System.getenv("NWAR_NATIVE_RESUME_START"));
  String filename=System.getenv("NWAR_NATIVE_RESUME_WAKE");
  double time=s.getSolution().getPhysicalTime();int iteration=s.getSimulationIterator().getCurrentIteration();
  int scenes=s.getSceneManager().getObjects().size();
  if(Math.abs(time-expected)>1e-7||scenes!=30||dt!=.0004||stride<1
      ||!filename.matches("wake_[a-f0-9]{16}\\.simh")||Files.exists(out.resolve(filename))
      ||Files.exists(out.resolve("native_ready.sim")))throw new IllegalStateException("Native continuation source or destination mismatch");
  Region reg=s.getRegionManager().getRegion("fluid");
  ManagedVofWave wave=reg.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
  if(!(wave instanceof FifthOrderVofWave)||Math.abs(((FifthOrderVofWave)wave).getVofWaveSpecification().getWaveLength().getSIValue()-15)>1e-7)
   throw new IllegalStateException("Unexpected saved wave");
  Map<SolverStoppingCriterion,Boolean> rules=new LinkedHashMap<>();boolean physical=false;
  for(SolverStoppingCriterion rule:s.getSolverStoppingCriterionManager().getObjects()){
   rules.put(rule,rule.getIsUsed());
   if(rule instanceof PhysicalTimeStoppingCriterion){
    if(!rule.getIsUsed()||Math.abs(((PhysicalTimeStoppingCriterion)rule).getMaximumTime().getSIValue()-target)>1e-7)
     throw new IllegalStateException("Native target changed");
    physical=true;
   }
  }
  if(!physical)throw new IllegalStateException("Missing native physical-time stop");
  int inherited=0;
  for(SolutionHistory h:s.get(SolutionHistoryManager.class).getSolutionHistories()){h.setAutoRecord(false);inherited++;}
  FieldFunctionManager fields=s.getFieldFunctionManager();
  UserFieldFunction box=fields.createFieldFunction();box.setPresentationName("NWAR resumed wake recording mask");
  box.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
  box.setDefinition("($${Position}[0] >= -1.0 && $${Position}[0] <= 12.0 && $${Position}[2] >= -3.0 && $${Position}[2] <= 3.5) ? 1.0 : 0.0");
  ThresholdPart cells=s.getPartManager().createThresholdPart();cells.setPresentationName("NWAR resumed wake box");
  cells.getInputParts().setObjects(reg);cells.setFieldFunction(box);cells.setRange(new DoubleVector(new double[]{.5,1.5}));cells.setMode(ThresholdMode.BETWEEN_TAG);
  PlaneSection plane=s.getPartManager().createPlaneSection();plane.setPresentationName("NWAR resumed midspan wake");
  plane.getInputParts().setObjects(cells);plane.setOrigin(new DoubleVector(new double[]{0,.02,0}));plane.setOrientation(new DoubleVector(new double[]{0,1,0}));
  SolutionHistory wake=s.get(SolutionHistoryManager.class).createForFile(out.resolve(filename).toString(),false);
  wake.setAutoRecord(false);wake.setAddReportFieldFunctions(false);wake.setCompressionMode(CompressionMode.ZLIB_1);
  wake.getInputs().setObjects(plane);wake.setFunctions(List.of(fields.getFunction("Velocity"),fields.getFunction("VorticityVector"),fields.getFunction("Pressure"),fields.getFunction("VolumeFractionwater")));
  StarUpdate update=wake.getUpdate();update.setUpdateMode(StarUpdateModeOption.TIMESTEP);
  update.getTimeStepUpdateFrequency().setTimeSteps(stride);update.getTimeStepUpdateFrequency().setStart(start);wake.setAutoRecord(true);
  for(var entry:rules.entrySet())if(entry.getKey().getIsUsed()!=entry.getValue())throw new IllegalStateException("A native stopping rule changed");
  if(Math.abs(s.getSolution().getPhysicalTime()-time)>1e-12||s.getSimulationIterator().getCurrentIteration()!=iteration||s.getSceneManager().getObjects().size()!=scenes)
   throw new IllegalStateException("Zero-step native preparation advanced or changed scenes");
  try{
   s.saveState(out.resolve("native_ready.sim").toString());
   Files.writeString(out.resolve("native_resume_prepared.json"),"{\"passed\":true,\"time_s\":"+time+",\"steps_advanced\":0,\"scene_count\":"+scenes+",\"inherited_histories_disabled\":"+inherited+",\"wake_file\":\""+filename+"\",\"stopping_rules_preserved\":true}\n");
  }catch(java.io.IOException e){throw new RuntimeException(e);}
 }
}
