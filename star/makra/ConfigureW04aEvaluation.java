package macro;

import java.nio.file.*;
import java.util.*;
import star.base.neo.*;
import star.base.report.*;
import star.common.*;
import star.flow.*;
import star.vof.*;

/** Configure the foil-free W04a propagation case on a disposable CPU copy. */
public class ConfigureW04aEvaluation extends StarMacro {
    private static final String NAME = "W04a - first order diagnostic";
    private static final String OUTPUT = "W04a_wave_evaluation_H0p28_L2.sim";
    private static final double HEIGHT = .28, LENGTH = 2, DEPTH = 24, LEVEL = 2, CURRENT = 18;
    private static final double PERIOD = LENGTH / (CURRENT + Math.sqrt(9.81 * LENGTH / (2 * Math.PI)));
    private static final String RAMP = "<0.0000005 m>+<"+(HEIGHT/2-.0000005)+" m>*0.5*(1-cos(3.141592653589793*min(1,max(0,$Time/<" + (2*PERIOD) + " s>))))";

    @Override public void execute() {
        Simulation s = getActiveSimulation();
        Path out = Path.of(Objects.requireNonNull(System.getenv("NWAR_W04A_OUT"))).toAbsolutePath().normalize();
        boolean verify = "1".equals(System.getenv("NWAR_W04A_VERIFY"));
        try {
            require(s.getNumberOfGpgpus()==0 && Path.of(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim")), "Expected an independent CPU batch copy");
            Region region = s.getRegionManager().getRegion("fluid");
            FvRepresentation mesh = (FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
            require(mesh.getCellCount()==329946, "Unexpected W04a mesh");
            Boundary foil = (Boundary)region.getBoundaryManager().getObject("HF_012_wall");
            require(foil==null || foil.getPartSurfaceGroup().getObjects().isEmpty(), "Foil is still attached");
            PhysicsContinuum pc = (PhysicsContinuum)s.getContinuumManager().getContinuum("water+air");
            VofWaveModel model = pc.getModelManager().getModel(VofWaveModel.class);
            FlatVofWave calm = (FlatVofWave)model.getVofWaveManager().getVofWave("Calm");
            Boundary inlet = boundary(region,"DOMAIN.inlet"), outlet = boundary(region,"DOMAIN.outlet");
            Boundary top = boundary(region,"DOMAIN.top"), bottom = boundary(region,"DOMAIN.bottom");
            ImplicitUnsteadySolver solver = s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
            FirstOrderVofWave wave;
            if (verify) {
                wave = (FirstOrderVofWave)region.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
            } else {
                require(!Files.exists(out.resolve(OUTPUT)), "Output already exists");
                s.getSimulationIterator().getAutoSave().setEnabled(false);
                s.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
                model.setEnableTheoryComparison(true);
                calm.setHeavyFluidDensity(1000); calm.setLightFluidDensity(1.2);
                calm.getPointOnLevel().setComponents(0,0,LEVEL);
                calm.getVerticalDirection().setComponents(0,0,1);
                calm.getCurrent().setComponents(CURRENT,0,0); calm.getWind().setComponents(CURRENT,0,0);
                wave = model.getVofWaveManager().createVofWave(FirstOrderVofWave.class, NAME);
                wave.setHeavyFluidDensity(1000); wave.setLightFluidDensity(1.2);
                wave.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);
                wave.setWaveLength(LENGTH);
                wave.setDeepWaterApproximation(false);
                wave.getVofWaveDepthSpecification().getWaterDepth().setValue(DEPTH);
                wave.getPointOnLevel().setComponents(-70,0,LEVEL);
                wave.getVerticalDirection().setComponents(0,0,1);
                wave.getAdvancingDirection().setComponents(1,0,0);
                wave.getCurrent().setComponents(CURRENT,0,0); wave.getWind().setComponents(CURRENT,0,0);
                wave.setFirstWaveFront(false);
                wave.setAmplitude(HEIGHT/2);
                wave.getAmplitude().setDefinition(RAMP);

                region.getConditions().get(VofWaveZoneOption.class).setSelected(VofWaveZoneOptionEnum.FORCING_DAMPING);
                region.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(wave);
                for (Boundary b : region.getBoundaryManager().getBoundaries()) {
                    b.getConditions().get(VofWaveForcingBoundaryOption.class).setSelected(b.equals(inlet) ? VofWaveForcingBoundaryOption.Type.YES : VofWaveForcingBoundaryOption.Type.NO);
                    b.getConditions().get(VofWaveDampingBoundaryOption.class).setSelected(b.equals(outlet) ? VofWaveDampingBoundaryOption.Type.YES : VofWaveDampingBoundaryOption.Type.NO);
                }
                inlet.getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(4);
                outlet.getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(8);
                inlet.setBoundaryType(InletBoundary.class);
                velocity(inlet.getValues().get(VelocityProfile.class), field(s,wave,"Velocity"));
                fraction(inlet.getValues().get(VolumeFractionProfile.class), field(s,wave,"Volume Fraction of Heavy Fluid"));
                FieldFunction calmFraction = field(s,calm,"Volume Fraction of Heavy Fluid");
                FieldFunction calmPressure = field(s,calm,"Hydrostatic Pressure of Heavy Fluid");
                for (Boundary b : List.of(top,outlet)) {
                    b.setBoundaryType(PressureBoundary.class);
                    scalar(b.getValues().get(StaticPressureProfile.class),calmPressure);
                    fraction(b.getValues().get(VolumeFractionProfile.class),calmFraction);
                }
                bottom.getConditions().get(WallShearStressOption.class).setSelected(WallShearStressOption.Type.SLIP);
                for (String side : List.of("Q2D_span_source","Q2D_span_target")) boundary(region,side).setBoundaryType(SymmetryBoundary.class);
                velocity(pc.getInitialConditions().get(VelocityProfile.class),field(s,calm,"Velocity"));
                scalar(pc.getInitialConditions().get(InitialPressureProfile.class),calmPressure);
                fraction(pc.getInitialConditions().get(VolumeFractionProfile.class),calmFraction);
                solver.getTimeStep().setValue(.0004);
                solver.getTimeDiscretizationOption().setSelected(TimeDiscretizationOption.Type.SECOND_ORDER);
                addGauges(s,region,mesh);
                s.getSolution().clearSolutionWithoutMeshReset();
                s.getSolution().initializeSolution();
            }
            double savedTime = s.getSolution().getPhysicalTime();
            boolean initialized = s.getSolution().isInitialized();
            require(near(savedTime,0) && (verify || initialized), "Unexpected time/initialization: t="+savedTime+", initialized="+initialized);
            require(region.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave().equals(wave), "Wrong forcing wave");
            require(near(wave.getWaveLength().getSIValue(),LENGTH) && near(wave.getVofWaveDepthSpecification().getWaterDepth().getSIValue(),DEPTH), "Wave parameter readback mismatch");
            require(wave.getAmplitude().getDefinition().equals(RAMP), "Amplitude ramp readback mismatch");
            require(inlet.getValues().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).getFieldFunction().equals(field(s,wave,"Velocity")), "Wrong inlet velocity function");
            require(fractionField(inlet.getValues().get(VolumeFractionProfile.class)).equals(field(s,wave,"Volume Fraction of Heavy Fluid")), "Wrong inlet phase fraction function");
            require(region.getConditions().get(VofWaveZoneOption.class).getSelected()==VofWaveZoneOptionEnum.FORCING_DAMPING
                    && near(inlet.getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().getSIValue(),4)
                    && near(outlet.getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().getSIValue(),8), "Wave-zone readback mismatch");
            for (Boundary b : List.of(top,outlet))
                require(b.getBoundaryType() instanceof PressureBoundary && b.getValues().get(StaticPressureProfile.class)
                    .getMethod(FunctionScalarProfileMethod.class).getFieldFunction().equals(field(s,calm,"Hydrostatic Pressure of Heavy Fluid"))
                    && fractionField(b.getValues().get(VolumeFractionProfile.class)).equals(field(s,calm,"Volume Fraction of Heavy Fluid")), "Pressure or backflow phase readback mismatch");
            require(near(solver.getTimeStep().getSIValue(),.0004), "Time step readback mismatch");
            if (!verify) s.saveState(out.resolve(OUTPUT).toString());
            Files.writeString(out.resolve(verify ? "reopened_verified.txt" : "setup_verified.txt"),
                "W04a, native FirstOrderVofWave. H="+HEIGHT+" m, lambda="+LENGTH+" m, diagnostic only.\n"
                + "Cells=329946, t=0 s, calm initial profiles at z=2 m, zero solver steps. Native initialized flag: "+initialized+".\n"
                + "Current and wind: +18 m/s in x. Water depth: 24 m. Time step: 0.0004 s.\n"
                + "Wave velocity and water fraction at inlet. Inlet forcing: 4 m. Outlet damping: 8 m.\n"
                + "Calm hydrostatic pressure and phase fraction at top and outlet.\n");
        } catch (Exception error) {
            try { Files.writeString(out.resolve("setup_error.txt"),error.toString()); } catch (Exception ignored) {}
            throw new RuntimeException(error);
        }
    }

    private static void addGauges(Simulation s, Region region, FvRepresentation mesh) {
        FieldFunction alpha = s.getFieldFunctionManager().getFunction("VolumeFractionwater");
        for (int x : new int[]{-64,-54,0,60}) {
            String tag = x<0 ? "m"+(-x) : "p"+x;
            var cut = s.getPartManager().createPlaneSection();
            cut.setPresentationName("W04a gauge x="+x+" m");
            cut.getInputParts().setObjects(region);
            cut.setOrigin(new DoubleVector(new double[]{x,.02,2}));
            cut.setOrientation(new DoubleVector(new double[]{1,0,0}));
            SurfaceIntegralReport area = s.getReportManager().createReport(SurfaceIntegralReport.class);
            area.setPresentationName("W04aWaterArea_"+tag);
            area.setFieldFunction(alpha); area.setRepresentation(mesh); area.getParts().setObjects(cut); area.setSmooth(false);
            ExpressionReport eta = s.getReportManager().createReport(ExpressionReport.class);
            eta.setPresentationName("W04a eta x="+x+" m");
            eta.setDefinition("${W04aWaterArea_"+tag+"}/<0.02 m>-<24 m>");
            eta.createMonitor();
        }
    }
    private static boolean near(double a,double b) { return Double.isFinite(a)&&Math.abs(a-b)<1e-8; }
    private static void require(boolean test,String msg) { if(!test) throw new IllegalStateException(msg); }
    private static Boundary boundary(Region region,String name) {
        Boundary b = region.getBoundaryManager().getBoundary(name);
        require(b!=null && !b.getPartSurfaceGroup().getObjects().isEmpty(),"Missing channel surface: "+name);
        return b;
    }
    private static FieldFunction field(Simulation s,VofWave wave,String name) {
        return s.getFieldFunctionManager().getObjects().stream()
            .filter(f -> f.getPresentationName().equals(name+" of "+wave.getPresentationName())).findFirst().orElseThrow();
    }
    private static void velocity(VelocityProfile profile,FieldFunction field) {
        profile.setMethod(FunctionVectorProfileMethod.class);
        profile.getMethod(FunctionVectorProfileMethod.class).setFieldFunction(field);
    }
    private static void scalar(ScalarProfile profile,FieldFunction field) {
        profile.setMethod(FunctionScalarProfileMethod.class);
        profile.getMethod(FunctionScalarProfileMethod.class).setFieldFunction(field);
    }
    private static void fraction(VolumeFractionProfile profile,FieldFunction field) {
        profile.setMethod(CompositeNMinus1ArrayProfileMethod.class);
        var water = profile.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0);
        water.setMethod(FunctionScalarProfileMethod.class);
        water.getMethod(FunctionScalarProfileMethod.class).setFieldFunction(field);
    }
    private static FieldFunction fractionField(VolumeFractionProfile profile) {
        return profile.getMethod(CompositeNMinus1ArrayProfileMethod.class).getProfile(0)
            .getMethod(FunctionScalarProfileMethod.class).getFieldFunction();
    }
}
