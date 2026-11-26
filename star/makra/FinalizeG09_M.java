package macro;
import star.common.*;import star.flow.*;import star.base.neo.*;import java.nio.file.*;import java.util.*;
public class FinalizeG09_M extends StarMacro {
public void execute(){
Simulation s=getActiveSimulation();Path out=Paths.get("C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/mesh_study_20261030/gci_m09_20261030/G09_M");
try{
Files.createDirectories(out);
s.getImportManager().importMeshFiles(List.of("C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/mesh_study_20261030/gci_m09_20261030/G09_M_raw/mesh_exact.CGNS"));
Region old=s.getRegionManager().getRegion("fluid"),fresh=s.getRegionManager().getRegion("fluid 2");
fresh.setPhysicsContinuum(old.getPhysicsContinuum());
List<String> audit=new ArrayList<>();
for(Boundary b:old.getBoundaryManager().getBoundaries()){
 Boundary n=fresh.getBoundaryManager().getBoundary(b.getPresentationName());
 String name=n.getPresentationName();n.copyProperties(b);n.setPresentationName(name);
 if(!n.getBoundaryType().getClass().equals(b.getBoundaryType().getClass()))throw new IllegalStateException("Boundary type mismatch");
 audit.add(name+" : "+n.getBoundaryType().getClass().getName());
}
String inlet=fresh.getBoundaryManager().getBoundary("DOMAIN.inlet").getValues().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).getFieldFunction().getPresentationName();
if(!inlet.equals("Velocity of Calm"))throw new IllegalStateException("Inlet velocity was not preserved: "+inlet);
if(!fresh.getPhysicsContinuum().getPresentationName().equals("water+air"))throw new IllegalStateException("Physics continuum mismatch");
s.getRegionManager().removeObjects(List.of(old));fresh.setPresentationName("fluid");
FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
if(fv.getCellCount()!=402842)throw new IllegalStateException("Unexpected cell count after removing old region: "+fv.getCellCount());
NeoProperty report=fv.generateMeshReport(List.of(fresh));Files.writeString(out.resolve("precheck_mesh_report.txt"),report.toFormattedString());
Files.write(out.resolve("boundary_transfer_audit.txt"),audit);
for(star.base.report.Report rep:s.getReportManager().getObjects()){
 if(rep instanceof ForceReport){((ForceReport)rep).getParts().setObjects(fresh.getBoundaryManager().getBoundary("HF_012_wall"));((ForceReport)rep).setRepresentation(fv);}
 if(rep instanceof star.base.report.MaxReport && rep.getPresentationName().equals("Maximum Velocity")){((star.base.report.MaxReport)rep).getParts().setObjects(fresh);((star.base.report.MaxReport)rep).setRepresentation(fv);}
}
s.saveState(out.resolve("clean_import.sim").toString());
StarScript script=new StarScript(s,Paths.get("C:/Users/ThinkPad/Documents/ChatGPT/ntnu science/mesh_study_20261030/gci_m09_20261030/AuditFinalG09_M.java").toFile());script.play();
if(script.getInterruptedByException())throw new IllegalStateException("Quality audit failed");
Files.writeString(out.resolve("finalization_ok.txt"),"Physics and boundary settings transferred; original warped region removed; independent quality audit exported.");
}catch(Exception e){try{Files.writeString(out.resolve("finalize_error.txt"),e.toString());}catch(Exception ignored){}throw new RuntimeException(e);}
}}
