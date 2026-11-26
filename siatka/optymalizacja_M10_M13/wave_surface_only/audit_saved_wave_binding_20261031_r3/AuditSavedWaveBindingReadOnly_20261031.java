package macro;
import star.common.*;
import star.base.neo.*;
import star.vof.*;
import star.flow.*;
import java.util.*;
public class AuditSavedWaveBindingReadOnly_20261031 extends StarMacro {
  public void execute() {
    Simulation sim=getActiveSimulation();
    sim.println("AUDIT_ONLY_SOURCE_PHYSICAL_T "+sim.getSolution().getPhysicalTime());
    PhysicsContinuum continuum=(PhysicsContinuum)sim.getContinuumManager().getContinuum("water+air");
    VofWaveModel model=(VofWaveModel)continuum.getModelManager().getModel(VofWaveModel.class);
    Region region=sim.getRegionManager().getRegion("fluid");
    ManagedVofWave binding=region.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
    sim.println("AUDIT_REGION_FORCING_CLASS "+(binding==null?"null":binding.getClass().getName()));
    sim.println("AUDIT_REGION_FORCING_NAME "+(binding==null?"null":binding.getPresentationName()));
    for (ManagedVofWave wav:model.getVofWaveManager().getObjects()) {
      sim.println("AUDIT_WAVE_CLASS "+wav.getClass().getName());
      sim.println("AUDIT_WAVE_NAME "+wav.getPresentationName());
      if(wav instanceof FifthOrderVofWave) {
        FifthOrderVofWave fifth=(FifthOrderVofWave)wav;
        sim.println("AUDIT_FIFTH_HEIGHT_DEFINITION "+fifth.getWaveHeight().getDefinition());
        sim.println("AUDIT_FIFTH_WAVELENGTH "+fifth.getVofWaveSpecification().getWaveLength().getValue());
      }
    }
    Boundary inlet=region.getBoundaryManager().getBoundary("DOMAIN.inlet");
    sim.println("AUDIT_INLET_FORCING "+inlet.getConditions().get(VofWaveForcingBoundaryOption.class).getSelectedElement());
    sim.println("AUDIT_INLET_VELOCITY_PROFILE_METHOD "+inlet.getValues().get(VelocityProfile.class).getMethod().getClass().getName());
    sim.println("AUDIT_COMPLETE_NO_STEPS_NO_SAVE");
  }
}
