package macro;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import star.base.neo.DoubleVector;
import star.base.report.MaxReport;
import star.base.report.Monitor;
import star.base.report.ReportMonitor;
import star.common.*;
import star.flow.ForceReport;
import star.flow.ForceReportForceOption;
import star.vis.*;

/** Export at a verified physical time, on a disposable copy of the saved state. */
public class NwarDragPhaseFields extends StarMacro {
    public void execute() {
        Simulation sim = getActiveSimulation();
        try {
            Path output = Path.of(System.getenv("NWAR_FIELD_OUT")).toAbsolutePath().normalize();
            if (!Path.of(sim.getSessionPath()).toAbsolutePath().normalize().equals(output.resolve("input.sim"))) {
                throw new IllegalStateException("Expected the isolated input.sim copy");
            }
            double expected = Double.parseDouble(System.getenv("NWAR_FIELD_TIME"));
            Region fluid = sim.getRegionManager().getRegion("fluid");
            Boundary foil = fluid.getBoundaryManager().getBoundary("HF_012_wall");
            FvRepresentation mesh = (FvRepresentation) sim.getRepresentationManager().getObject("Volume Mesh");
            replay(sim, output, fluid, mesh, expected);
            double time = sim.getSolution().getPhysicalTime();
            FieldFunction pressure = sim.getFieldFunctionManager().getFunction("Pressure");
            FieldFunction velocity = sim.getFieldFunctionManager().getFunction("Velocity");
            ForceReport drag = sim.getReportManager().createReport(ForceReport.class);
            drag.getParts().setObjects(foil);
            drag.setRepresentation(mesh);
            drag.getDirection().setComponents(1, 0, 0);
            drag.getForceOption().setSelected(ForceReportForceOption.Type.PRESSURE_AND_SHEAR);
            double dragN = drag.getReportMonitorValue();
            if (!Double.isFinite(dragN)) throw new IllegalStateException("Nonfinite replay drag");
            Files.writeString(output.resolve("replayed_drag_N.txt"), Double.toString(dragN));

            XyzInternalTable wall = sim.getTableManager().createTable(XyzInternalTable.class);
            wall.getParts().setObjects(foil);
            wall.setRepresentation(mesh);
            wall.setExtractVertexData(false);
            wall.setFieldFunctions(List.of(pressure));
            wall.extract();
            wall.export(output.resolve("foil_pressure.csv").toString());

            PlaneSection mid = sim.getPartManager().createPlaneSection();
            mid.getInputParts().setObjects(fluid);
            mid.setOrigin(new DoubleVector(new double[]{0, .01, 0}));
            mid.setOrientation(new DoubleVector(new double[]{0, 1, 0}));
            XyzInternalTable plane = sim.getTableManager().createTable(XyzInternalTable.class);
            plane.getParts().setObjects(mid);
            plane.setRepresentation(mesh);
            plane.setExtractVertexData(false);
            plane.setFieldFunctions(List.of(velocity.getComponentFunction(0), velocity.getComponentFunction(1),
                    velocity.getComponentFunction(2)));
            plane.extract();
            plane.export(output.resolve("midspan_velocity.csv").toString());

            StreamPart lines = sim.getPartManager().createStreamPart();
            lines.getInputParts().setObjects(fluid);
            lines.setFieldFunction(velocity);
            lines.setMode(StreamPart.LINESEED);
            lines.getLineSeed().setPoint1(new DoubleVector(new double[]{-2, .01, -1.5}));
            lines.getLineSeed().setPoint2(new DoubleVector(new double[]{-2, .01, 1.5}));
            lines.getLineSeed().setResolution(75);
            lines.getIntegrator().setDirection(StreamPart.BOTH);
            lines.getIntegrator().setMaxPropagation(12);
            lines.getIntegrator().setMaximumNumberOfSteps(2400);

            Scene flow = sim.getSceneManager().createScene("Instantaneous streamlines");
            PartDisplayer foilOutline = flow.getDisplayerManager().createPartDisplayer("Foil");
            foilOutline.setRepresentation(mesh);
            foilOutline.getInputParts().setObjects(foil);
            foilOutline.setSurface(true);
            foilOutline.setOutline(true);
            StreamDisplayer stream = flow.getDisplayerManager().createStreamDisplayer("Streamlines");
            stream.setRepresentation(mesh);
            stream.getInputParts().setObjects(lines);
            stream.setFieldFunction(velocity);
            stream.getScalarDisplayQuantity().setFieldFunction(velocity.getMagnitudeFunction());
            stream.getScalarDisplayQuantity().setAutoRange(false);
            stream.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{0, 30}));
            stream.getLegend().setDataName("Velocity magnitude [m/s]");
            print(flow, output.resolve("streamlines.png"), false);

            Scene surface = sim.getSceneManager().createScene("Foil surface pressure");
            ScalarDisplayer wallPressure = surface.getDisplayerManager().createScalarDisplayer("Pressure");
            wallPressure.setRepresentation(mesh);
            wallPressure.getInputParts().setObjects(foil);
            wallPressure.getScalarDisplayQuantity().setFieldFunction(pressure);
            wallPressure.getScalarDisplayQuantity().setAutoRange(false);
            wallPressure.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{
                    Double.parseDouble(System.getenv("NWAR_PRESSURE_MIN_PA")),
                    Double.parseDouble(System.getenv("NWAR_PRESSURE_MAX_PA"))
            }));
            wallPressure.getLegend().setDataName("STAR-CCM+ Pressure [Pa]");
            print(surface, output.resolve("foil_pressure.png"), true);
            Files.writeString(output.resolve("field_time_s.txt"), Double.toString(time));
            Files.writeString(output.resolve("completed.json"),
                    "{\"status\":\"phase_fields_exported\",\"time_s\":" + time + ",\"drag_N\":" + dragN + "}");
        } catch (Exception error) {
            throw new RuntimeException(error);
        }
    }

    private void replay(Simulation sim, Path output, Region fluid, FvRepresentation mesh, double target) throws Exception {
        double source = Double.parseDouble(System.getenv("NWAR_FIELD_SOURCE_TIME"));
        int steps = Integer.parseInt(System.getenv("NWAR_FIELD_STEPS"));
        double dt = .0004;
        if (steps < 0 || steps > 1500 || Math.abs(source + steps * dt - target) > 1e-8
                || Math.abs(sim.getSolution().getPhysicalTime() - source) > 1e-8
                || mesh.getCellCount() != 572176) {
            throw new IllegalStateException("Unexpected replay checkpoint, step count, or mesh");
        }
        sim.getSimulationIterator().getAutoSave().setEnabled(false);
        sim.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
        for (Monitor monitor : sim.getMonitorManager().getObjects()) {
            if (monitor instanceof ReportMonitor) ((ReportMonitor) monitor).setEnabled(false);
        }
        MaxReport cfl = sim.getReportManager().createReport(MaxReport.class);
        cfl.getParts().setObjects(fluid);
        cfl.setRepresentation(mesh);
        cfl.setFieldFunction(sim.getFieldFunctionManager().getFunction("CourantNumber"));
        try (var progress = Files.newBufferedWriter(output.resolve("history.csv"))) {
            progress.write("time_s,step,max_CFL\n");
            for (int step = 0; step <= steps; step++) {
                if (Files.exists(output.resolve("STOP"))) throw new IllegalStateException("STOP requested");
                if (step > 0) sim.getSimulationIterator().step(1);
                double time = sim.getSolution().getPhysicalTime();
                double maxCfl = cfl.getReportMonitorValue();
                if (!Double.isFinite(maxCfl) || maxCfl > 25 || Math.abs(time - source - step * dt) > 1e-8) {
                    throw new IllegalStateException("Replay time or CFL check failed at step " + step);
                }
                progress.write(time + "," + step + "," + maxCfl + "\n");
                progress.flush();
            }
        }
    }

    private void print(Scene scene, Path path, boolean oblique) {
        scene.setBackgroundColorMode(BackgroundColorMode.SOLID);
        scene.getSolidBackgroundColor().setColor(new DoubleVector(new double[]{1, 1, 1}));
        scene.initializeAndWait();
        CurrentView view = scene.getCurrentView();
        view.setProjectionMode(VisProjectionMode.PARALLEL);
        view.setFocalPoint(new DoubleVector(new double[]{.6, .01, 0}));
        view.setPosition(new DoubleVector(oblique ? new double[]{-.2, -1, 2.5} : new double[]{.6, -10, 0}));
        view.setViewUp(new DoubleVector(oblique ? new double[]{0, 1, 0} : new double[]{0, 0, 1}));
        view.setParallelScale(oblique ? .8 : 1.1);
        scene.printAndWait(path.toString(), 1, 1600, 900, true, false);
    }
}
