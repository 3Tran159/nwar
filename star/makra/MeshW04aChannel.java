package macro;

import java.nio.file.*;
import java.util.*;
import star.base.neo.*;
import star.base.report.*;
import star.common.*;
import star.flow.*;
import star.meshing.*;
import star.sweptmesher.*;

/** Build and verify the foil-free Q2D wave tank using the native STAR mesher. */
public class MeshW04aChannel extends StarMacro {
    private static final Map<String,String> BOUNDARIES = Map.of(
        "inlet","DOMAIN.inlet", "outlet","DOMAIN.outlet",
        "top","DOMAIN.top", "bottom","DOMAIN.bottom",
        "span_source","Q2D_span_source", "span_target","Q2D_span_target");

    @Override public void execute() {
        Simulation sim = getActiveSimulation();
        Path out = Path.of(Objects.requireNonNull(System.getenv("NWAR_CHANNEL_MESH_OUT"))).toAbsolutePath().normalize();
        try {
            if (!Path.of(sim.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim"))
                || sim.getNumberOfGpgpus() != 0 || Files.exists(out.resolve("W04a_channel_native.sim")))
                throw new IllegalStateException("Use a new disposable CPU batch copy of W04a.");

            MeshOperationManager operations = sim.get(MeshOperationManager.class);
            SubtractPartsOperation fluid = (SubtractPartsOperation) operations.getObject("Q2D_fluid");
            DirectedMeshOperation directed = (DirectedMeshOperation) operations.getObject("Q2D_directed");
            SimpleBlockPart box = (SimpleBlockPart) sim.get(SimulationPartManager.class).getPartManager().getPart("Q2D_domain");
            var inputs = fluid.getInputGeometryObjects().getObjects();
            if (inputs.size()!=1 || !inputs.contains(box))
                throw new IllegalStateException("Q2D_fluid must have only the rectangular domain as input.");
            Region region = sim.getRegionManager().getRegion("fluid");
            sim.getSolution().clearSolutionWithoutMeshReset();
            box.setCorners(new DoubleVector(new double[]{-70,.01,-22}), new DoubleVector(new double[]{90,.03,8}));
            box.rebuildSimpleShapePart();
            fluid.execute();
            MeshPart part = (MeshPart) sim.get(SimulationPartManager.class).getPartManager().getPart("Q2D_fluid");
            if (part.getPartSurfaces().size()!=BOUNDARIES.size())
                throw new IllegalStateException("Expected six surfaces on the foil-free block.");
            region.getPartGroup().setObjects(part);
            Map<String, Boundary> boundaries = new HashMap<>();
            for (Map.Entry<String,String> item : BOUNDARIES.entrySet()) {
                PartSurface surface = part.getPartSurfaceManager().getPartSurface("Q2D_domain."+item.getKey());
                Boundary boundary = region.getBoundaryManager().getBoundary(item.getValue());
                boundary.getPartSurfaceGroup().setObjects(surface);
                boundaries.put(item.getKey(),boundary);
            }

            DirectedAutoSourceMesh auto = (DirectedAutoSourceMesh) directed.getDirectedSurfaceMeshBaseManager().getObject("Q2D_polygon_prisms");
            if (!directed.editDirectedMeshOperation())
                throw new IllegalStateException("Native directed mesh operation could not be edited.");
            try {
                auto.updateAutoSourceMesh();
            } finally {
                directed.stopEditingDirectedMeshOperation();
            }
            directed.execute();

            FvRepresentation mesh = (FvRepresentation) sim.getRepresentationManager().getObject("Volume Mesh");
            long cells = mesh.getCellCount();
            NeoProperty report = mesh.generateMeshReport(List.of(region));
            Files.writeString(out.resolve("mesh_report.txt"),report.toFormattedString());
            for (String key : List.of("NegativeVolumeCells","UnclosedCells","DegeneratedFeCells"))
                if (!(report.get(key) instanceof Number) || ((Number)report.get(key)).longValue()!=0)
                    throw new IllegalStateException("Mesh quality gate failed: "+key);

            UserFieldFunction unity = sim.getFieldFunctionManager().createFieldFunction();
            unity.setFunctionName("NWAR_W04a_ChannelUnity");
            unity.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
            unity.setDefinition("1");
            VolumeIntegralReport volume = sim.getReportManager().createReport(VolumeIntegralReport.class);
            volume.setRepresentation(mesh); volume.setFieldFunction(unity); volume.getParts().setObjects(region);
            double m3 = volume.getReportMonitorValue();
            double inlet = position(sim,mesh,boundaries.get("inlet"),0);
            double outlet = position(sim,mesh,boundaries.get("outlet"),0);
            double centerY = position(sim,mesh,region,1);
            if (cells<=0 || !near(m3,96.) || !near(inlet,-70.) || !near(outlet,90.) || !near(centerY,.02))
                throw new IllegalStateException("Native volume mesh did not match the rectangular channel: "+cells+", "+m3+", "+inlet+", "+outlet+", "+centerY);

            Boundary oldWall = (Boundary) region.getBoundaryManager().getObject("HF_012_wall");
            if (oldWall != null && !oldWall.getPartSurfaceGroup().getObjects().isEmpty())
                throw new IllegalStateException("A geometry surface is still mapped to the old foil boundary.");
            sim.saveState(out.resolve("W04a_channel_native.sim").toString());
            Files.writeString(out.resolve("mesh_verified.json"),String.format(Locale.ROOT,
                "{\"native_star_mesh\":true,\"foil_free\":true,\"cells\":%d,\"volume_m3\":%.10f,\"inlet_x_m\":%.8f,\"outlet_x_m\":%.8f,\"center_y_m\":%.8f}%n",
                cells,m3,inlet,outlet,centerY));
        } catch (Exception error) {
            try { Files.writeString(out.resolve("mesh_error.txt"),error.toString()); } catch (Exception ignored) {}
            throw new RuntimeException(error);
        }
    }

    private static boolean near(double actual,double expected) {
        return Double.isFinite(actual)&&Math.abs(actual-expected)<1e-5;
    }

    private static double position(Simulation sim,FvRepresentation mesh,NamedObject part,int axis) {
        MinReport min = sim.getReportManager().createReport(MinReport.class);
        MaxReport max = sim.getReportManager().createReport(MaxReport.class);
        for (ScalarReport report : List.of(min,max)) {
            report.setRepresentation(mesh);
            report.setFieldFunction(sim.getFieldFunctionManager().getFunction("Position").getComponentFunction(axis));
            report.getParts().setObjects(part);
        }
        double low=min.getReportMonitorValue(),high=max.getReportMonitorValue();
        if (!near(low,high)) throw new IllegalStateException("Expected one coordinate on "+part.getPresentationName());
        return low;
    }
}
