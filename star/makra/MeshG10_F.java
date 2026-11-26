package macro;
import star.common.*;import star.meshing.*;import star.sweptmesher.*;import star.prismmesher.*;import star.base.neo.*;import java.nio.file.*;import java.util.*;
public class MeshG10_F extends StarMacro {
public void execute(){Simulation s=getActiveSimulation();Path out=Paths.get("C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/mesh_study_20261030/gci_w01a_20261030/G10_F_raw");
try{
Files.createDirectories(out);s.getSolution().clearSolutionWithoutMeshReset();
DirectedMeshOperation dm=(DirectedMeshOperation)s.get(MeshOperationManager.class).getObject("Q2D_directed");
DirectedAutoSourceMesh auto=(DirectedAutoSourceMesh)dm.getDirectedSurfaceMeshBaseManager().getObject("Q2D_polygon_prisms");
dm.editDirectedMeshOperation();double base=0.12765957446808512;
auto.getDefaultValues().get(BaseSize.class).setValue(base);
auto.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(0.00018237082066869305/base*100);
auto.getDefaultValues().get(PrismWallThickness.class).setValue(7.519683883165456e-07);
auto.getDefaultValues().get(NumPrismLayers.class).setNumLayers(94);
auto.getDefaultValues().get(PrismThickness.class).setRelativeSizeValue(.01546/base*100);
SurfaceCustomMeshControl foil=(SurfaceCustomMeshControl)auto.getCustomMeshControls().getObject("Q2D_foil_size");
foil.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(0.0014589665653495444/base*100);
foil.getCustomValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(0.00014589665653495443/base*100);
((VolumeCustomMeshControl)auto.getCustomMeshControls().getObject("Q2D_near_foil")).getCustomValues().get(VolumeControlSize.class).setRelativeSize(0.004559270516717326/base*100);
((VolumeCustomMeshControl)auto.getCustomMeshControls().getObject("Q2D_free_surface")).getCustomValues().get(VolumeControlSize.class).setRelativeSize(0.01021276595744681/base*100);
((VolumeCustomMeshControl)auto.getCustomMeshControls().getObject("Q2D_protected_middle_M09")).getCustomValues().get(VolumeControlSize.class).setRelativeSize(0.07294832826747721/base*100);
for(DirectedMeshPartCollection pc:dm.getDirectedMeshPartCollectionManager().getObjects()){pc.setTargetSmoothOption(false);pc.setEnhanceCellQualityOption(false);}
long start=System.nanoTime();auto.updateAutoSourceMesh();dm.stopEditingDirectedMeshOperation();dm.execute();
double wall=(System.nanoTime()-start)*1e-9;
s.saveState(out.resolve("mesh_before_audit.sim").toString());
StarScript audit=new StarScript(s,Paths.get("C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/mesh_study_20261030/gci_w01a_20261030/AuditRawG10_F.java").toFile());audit.play();if(audit.getInterruptedByException())throw new IllegalStateException("Mesh audit macro failed");
}catch(Exception e){try{Files.writeString(out.resolve("error.txt"),e.toString());}catch(Exception x){}throw new RuntimeException(e);}
}}
