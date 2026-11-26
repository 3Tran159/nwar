from pathlib import Path
H=Path(__file__).resolve().parent;O=H/'gci_w01a_20261030'
t=(H/'gci_m09_20261030/ContinueGCI.java').read_text().replace('ContinueGCI','ContinueWaveGCI')
a=t.index('      if(initialize){');b=t.index('      ImplicitUnsteadySolver unsteady=',a)
t=t[:a]+'      if(initialize)throw new IllegalStateException("Wave GCI must continue saved fields without initialization");\n'+t[b:]
anchor='      double rho=calm.getHeavyFluidDensity().getSIValue();'
extra=r'''
      ManagedVofWave selectedWave=fluid.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
      if(!(selectedWave instanceof FifthOrderVofWave))throw new IllegalStateException("A computed W01a wave checkpoint is required, not the calm-only handoff");
      FifthOrderVofWave activeWave=(FifthOrderVofWave)selectedWave;
      double expectedPeriod=Double.parseDouble(System.getenv("NTNU_GCI_WAVE_PERIOD"));
      if(Math.abs(activeWave.getWaveHeight().getValue()-.5)>1e-7||Math.abs(activeWave.getWaterDepth().getValue()-24)>1e-8||Math.abs(activeWave.getVofWaveSpecification().getWaveLength().getValue()-20)>1e-8)throw new IllegalStateException("W01a wave definition mismatch or ramp incomplete");
      double pressureTol=s.getSolverManager().getSolver(star.segregatedflow.SegregatedFlowSolver.class).getPressureSolver().getAMGLinearSolver().getConvergeTol();
      double vofTol=s.getSolverManager().getSolver(SegregatedVofSolver.class).getAMGLinearSolver().getConvergeTol();
      if(Math.abs(pressureTol-.01)>1e-10||Math.abs(vofTol-.1)>1e-10)throw new IllegalStateException("Current W01a linear-solver settings differ");
'''
assert t.count(anchor)==1;t=t.replace(anchor,anchor+extra)
anchor='      recordBudget();\n      long start='
extra=r'''
      double[] gaugeXs={-10,-5,2.5,5,10,15,20};
      ArrayList<SurfaceIntegralReport> gauges=new ArrayList<>();
      for(double x:gaugeXs){
        PlaneSection p=s.getPartManager().createPlaneSection();p.getInputParts().setObjects(fluid);
        p.setOrigin(new DoubleVector(new double[]{x,.02,2}));p.setOrientation(new DoubleVector(new double[]{1,0,0}));
        SurfaceIntegralReport g=s.getReportManager().createReport(SurfaceIntegralReport.class);
        g.setFieldFunction(vf);g.setRepresentation(fv);g.getParts().setObjects(p);g.setSmooth(false);gauges.add(g);
      }
      Files.writeString(out.resolve("wave_gauges.csv"),"physical_time_s,x_m,eta_m\n");
'''
assert t.count(anchor)==1;t=t.replace(anchor,extra+anchor)
anchor='          int vofSteps=s.getSolverManager()'
extra=r'''
          if(steps==1){
            double period=activeWave.getWavePeriod().getValue();
            if(!Double.isFinite(period)||period<=0||Math.abs(period/expectedPeriod-1)>1e-6)throw new IllegalStateException("Wave period/phase clock differs after cache update");
            Files.writeString(out.resolve("wave_audit.json"),json(Map.of("height_m",activeWave.getWaveHeight().getValue(),"wavelength_m",20,"depth_m",24,"period_s",period,"start_time_s",startTime,"pressure_AMG_tolerance",pressureTol,"VOF_AMG_tolerance",vofTol,"source_wave",activeWave.getPresentationName(),"reinitialized",false)));
          }
          if(steps==1||steps%5==0){
            StringBuilder line=new StringBuilder();
            for(int gi=0;gi<gauges.size();gi++){
              double eta=gauges.get(gi).getReportMonitorValue()/.02-24;
              if(!Double.isFinite(eta)||Math.abs(eta)>1.5||!gauges.get(gi).getErrorLog().isBlank())throw new IllegalStateException("Invalid wave gauge");
              line.append(t).append(",").append(gaugeXs[gi]).append(",").append(eta).append("\n");
            }
            Files.writeString(out.resolve("wave_gauges.csv"),line.toString(),StandardOpenOption.APPEND);
          }
'''
assert t.count(anchor)==1;t=t.replace(anchor,extra+anchor)
t=t.replace('speed>90','speed>50')
t=t.replace('Math.round(.2/dt)','Math.round(expectedPeriod/dt)') # one checkpoint per complete nominal wave period
t=t.replace('Continuation without resetting solution; stabilization screen, not validation','W01a wave continuation from a common computed checkpoint; phase-matched spatial verification, no reinitialization')
(O/'ContinueWaveGCI.java').write_text(t,encoding='utf-8')
m=(O/'MapW01Solution.java').read_text().replace('Math.abs(start-.02)>1e-8','Math.abs(start-Double.parseDouble(System.getenv().getOrDefault("NTNU_MAP_EXPECTED_START","0.02")))>1e-8')
(O/'MapW01Solution.java').write_text(m,encoding='utf-8')
print('Prepared continuation of existing W01a wave fields, with gauges and wave-clock/settings guards. No wave initialization.')
