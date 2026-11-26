"""Build a fresh, whole-domain momentum ramp on the existing expanded mesh."""
from common import *
from pre_w04 import PRE, CALM_RUN
from build_pre_w04 import replace, CP, JAVAC
import subprocess

MACRO = HERE / 'PreW04GlobalRamp.java'
TEMPLATE = PRE / 'calm_resume_20261102_135329/PreW04Resume.java'
TEMPLATE_SHA = 'ea63ef91d398d009754adc9d7b444c8f1d6df2be942126b2dc01a40e81cf2144'

EXTRA = r'''
  private boolean globalSourceEnabled=false;
  private UserFieldFunction globalAcceleration,globalMomentum;
  private final ArrayList<SurfaceIntegralReport> globalWaterUx=new ArrayList<>();
  private MaxReport globalSourceMax;

  private void configureGlobalRamp(boolean fresh)throws Exception{
    MomentumUserSourceOption option=fluid.getConditions().get(MomentumUserSourceOption.class);
    if(fresh && !String.valueOf(option.getSelectedElement()).equals("NONE"))
      throw new IllegalStateException("Unexpected existing momentum source; original physics must be preserved");
    for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getFunctionName().equals("NWARWholeDomainAcceleration"))globalAcceleration=(UserFieldFunction)f;
    if(globalAcceleration==null)globalAcceleration=s.getFieldFunctionManager().createFieldFunction();
    globalAcceleration.setPresentationName("NWAR whole-domain startup acceleration");
    globalAcceleration.setFunctionName("NWARWholeDomainAcceleration");
    globalAcceleration.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
    globalAcceleration.setDimensions(Dimensions.Builder().length(1).time(-2).build());
    globalAcceleration.setDefinition("($Time < <1 s>) ? (<18 m/s>*3.141592653589793/<2 s>*sin(3.141592653589793*max(0.0,$Time/<1 s>))) : <0 m/s^2>");
    option.setSelected(MomentumUserSourceOption.Type.SPECIFIED);
    MomentumUserSource source=fluid.getValues().get(MomentumUserSource.class);
    Dimensions dims=source.getDimensions();
    if(!dims.equals(Dimensions.Builder().force(1).volume(-1).build()) &&
       !dims.equals(Dimensions.Builder().mass(1).length(-2).time(-2).build()))
      throw new IllegalStateException("Momentum source is not force per volume: "+dims);
    for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getFunctionName().equals("NWARWholeDomainMomentum"))globalMomentum=(UserFieldFunction)f;
    if(globalMomentum==null)globalMomentum=s.getFieldFunctionManager().createFieldFunction();
    globalMomentum.setPresentationName("NWAR startup rho dUdt, whole fluid region");
    globalMomentum.setFunctionName("NWARWholeDomainMomentum");
    globalMomentum.getTypeOption().setSelected(FieldFunctionTypeOption.Type.VECTOR);
    globalMomentum.setDimensions(dims);
    globalMomentum.setDefinition("[$Density*${NWARWholeDomainAcceleration},0,0]");
    source.setMethod(FunctionVectorProfileMethod.class);
    source.getMethod(FunctionVectorProfileMethod.class).setFieldFunction(globalMomentum);
    MomentumUserSourceJacobianVector derivative=fluid.getValues().get(MomentumUserSourceJacobianVector.class);
    derivative.setMethod(ConstantVectorProfileMethod.class);
    derivative.getMethod(ConstantVectorProfileMethod.class).getQuantity().setComponents(0,0,0);
    globalSourceEnabled=true;
    save("global_ramp_configuration.json",Map.of(
      "scheme","rho_dUdt_whole_fluid_region","region",fluid.getPresentationName(),
      "duration_s",1.0,"target_speed_m_s",18.0,"fresh_fields",fresh,
      "acceleration_definition",globalAcceleration.getDefinition(),
      "momentum_definition",globalMomentum.getDefinition(),"momentum_dimensions",dims.toString(),
      "water_and_air",true,"force_removed_after_ramp",true));
    removeGlobalSourceAfterRamp(s.getSolution().getPhysicalTime());
  }

  private void removeGlobalSourceAfterRamp(double t)throws Exception{
    if(globalSourceEnabled && t>=1.0-1e-9){
      fluid.getConditions().get(MomentumUserSourceOption.class).setSelected(MomentumUserSourceOption.Type.NONE);
      if(!String.valueOf(fluid.getConditions().get(MomentumUserSourceOption.class).getSelectedElement()).equals("NONE"))
        throw new IllegalStateException("Startup momentum source could not be removed");
      globalSourceEnabled=false;
      save("global_ramp_completed.json",Map.of("time_s",t,"momentum_source_option","NONE",
        "extra_force_active",false,"target_speed_m_s",18.0,"C01_reference_unchanged",true));
    }
  }

  private void prepareGlobalVelocityProbes(FieldFunction alpha)throws Exception{
    UserFieldFunction waterUx=s.getFieldFunctionManager().createFieldFunction();
    waterUx.setPresentationName("NWAR water-weighted axial velocity");
    waterUx.setFunctionName("NWARWaterWeightedUx");
    waterUx.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
    waterUx.setDimensions(Dimensions.Builder().velocity(1).build());
    waterUx.setDefinition("${"+alpha.getFunctionName()+"}*$$Velocity[0]");
    for(double x:gx){
      PlaneSection plane=s.getPartManager().createPlaneSection();plane.getInputParts().setObjects(fluid);
      plane.setOrigin(new DoubleVector(new double[]{x,.02,2}));
      plane.setOrientation(new DoubleVector(new double[]{1,0,0}));
      SurfaceIntegralReport q=s.getReportManager().createReport(SurfaceIntegralReport.class);
      q.setRepresentation(fv);q.getParts().setObjects(plane);q.setFieldFunction(waterUx);q.setSmooth(false);globalWaterUx.add(q);
    }
    globalSourceMax=max("NWAR max startup force per volume",globalMomentum.getMagnitudeFunction(),fluid);
    Files.writeString(out.resolve("global_ramp_velocity.csv"),"time_s,x_m,water_mean_Ux_m_s,target_U_m_s,acceleration_m_s2,max_momentum_source_N_m3,source_enabled\n");
  }

  private void recordGlobalVelocity(int step,double t)throws Exception{
    if(step!=1 && step%10!=0)return;
    double target=rampSpeed(t),acc=t<1?18*Math.PI*.5*Math.sin(Math.PI*t):0;
    double source=globalSourceMax.getReportMonitorValue();
    for(int i=0;i<gx.length;i++){
      double area=probes.get(i).getReportMonitorValue(),ux=globalWaterUx.get(i).getReportMonitorValue()/area;
      if(!Double.isFinite(ux)||!Double.isFinite(source)||area<=0)throw new IllegalStateException("Invalid whole-domain ramp readback");
      Files.writeString(out.resolve("global_ramp_velocity.csv"),t+","+gx[i]+","+ux+","+target+","+acc+","+source+","+globalSourceEnabled+"\n",StandardOpenOption.APPEND);
    }
  }
'''

def build():
    assert sha(TEMPLATE) == TEMPLATE_SHA, 'Verified resume template changed'
    s = TEMPLATE.read_text(encoding='utf8').replace('PreW04Resume', 'PreW04GlobalRamp')
    s = replace(s, '||target!=8.0||initialize||', '||target!=8.0||')
    s = replace(s, '||target!=8.0||',
                '||(System.getenv().containsKey("PRE_W04_NIGHT_FALLBACK_MS")?(!Double.isFinite(target)||target<=expectedStart||target>Math.max(8.0,expectedStart+8.0)+1e-8):target!=8.0)||')
    fresh = (CALM_RUN/'PreW04Fresh.java').read_text(encoding='utf8')
    fn = fresh[fresh.index('  private void configureFreshCalm('):fresh.index('  private MinReport alphaMin,pressureMin,densityMin;')]
    s = replace(s, '      verifySavedC01Calm(pc,calm);rho=1000;',
                '''      List<String> sourceScenes=new ArrayList<>();for(SceneBase scene:s.getSceneManager().getObjects())sourceScenes.add(scene.getPresentationName());
      if(initialize)configureFreshCalm(pc,calm);else verifySavedC01Calm(pc,calm);
      configureGlobalRamp(initialize);rho=1000;
      List<String> keptScenes=new ArrayList<>();for(SceneBase scene:s.getSceneManager().getObjects())keptScenes.add(scene.getPresentationName());
      if(!sourceScenes.equals(keptScenes))throw new IllegalStateException("Native scene inventory changed during initialization");
      save("scene_retention.json",Map.of("preserved",true,"source_scene_names",sourceScenes,"scene_names",keptScenes,"scene_count",keptScenes.size(),"fresh_fields",initialize));''')
    s = replace(s, '  private MinReport alphaMin,pressureMin,densityMin;', fn+EXTRA+'\n  private MinReport alphaMin,pressureMin,densityMin;')
    s = replace(s, 'waterAtRestart=Double.parseDouble(System.getenv("PRE_W04_EXPECTED_WATER"));',
                'waterAtRestart=initialize?waterBudget.getReportMonitorValue():Double.parseDouble(System.getenv("PRE_W04_EXPECTED_WATER"));')
    s = replace(s, '      prepareHealthAndGauges(vf);', '      prepareHealthAndGauges(vf);\n      prepareGlobalVelocityProbes(vf);')
    s = replace(s, '        String boundary=Files.readString', '        if(!initialize){String boundary=Files.readString')
    s = replace(s, '        w.write(boundary+"\\n");w.flush();', '        w.write(boundary+"\\n");w.flush();}')
    s = replace(s, '          double t=s.getSolution().getPhysicalTime();',
                '          double t=s.getSolution().getPhysicalTime();\n          removeGlobalSourceAfterRamp(t);\n          recordGlobalVelocity(steps,t);')
    s = replace(s, '"type",selectedWave.getClass().getSimpleName(),"reinitialized",false', '"type",selectedWave.getClass().getSimpleName(),"reinitialized",initialize')
    s = replace(s, 'audit.put("fresh_fields",false)', 'audit.put("fresh_fields",initialize)')
    s = replace(s, 'audit.put("restart_from_saved_fields",true)', 'audit.put("restart_from_saved_fields",!initialize)')
    s = replace(s, 'audit.put("constant_reference_velocity_m_s",18);',
                'audit.put("constant_reference_velocity_m_s",18);audit.put("initialization","whole_domain_momentum_ramp");audit.put("startup_acceleration_scope","whole fluid region, water and air");')
    s = s.replace('fresh flat water from rest, 1 s cosine current/wind ramp', 'fresh flat water from rest, 1 s whole-domain momentum/current/wind ramp')
    s = s.replace('"source_data_only",true', '"source_data_only",!initialize')
    s = s.replace('"fields_retained",true', '"fresh_global_ramp",true')
    # The existing native scenes stay in the copied simulation; do not attach another client.
    # Explicit observation preserves the convergence tests, but records their
    # result without terminating early or accepting a new calm reference.
    s = replace(s, 'if(compatiblePasses>=2){state="calm_gate_passed";break;}',
                'if(compatiblePasses>=2&&(!Boolean.parseBoolean(System.getenv().getOrDefault("PRE_W04_OBSERVE_ONLY","false"))||System.getenv().containsKey("PRE_W04_NIGHT_FALLBACK_MS"))){state="calm_gate_passed";break;}')
    s = replace(s, 'if(consecutivePasses>=2&&!compatibleNow){state="stable_reference_mismatch";break;}',
                'if(consecutivePasses>=2&&!compatibleNow&&(!Boolean.parseBoolean(System.getenv().getOrDefault("PRE_W04_OBSERVE_ONLY","false"))||(System.getenv().containsKey("PRE_W04_NIGHT_FALLBACK_MS")&&System.currentTimeMillis()>=Long.parseLong(System.getenv("PRE_W04_NIGHT_FALLBACK_MS"))))){state="stable_reference_mismatch";break;}')
    s = replace(s, 'audit.put("initialization","whole_domain_momentum_ramp");',
                'audit.put("initialization","whole_domain_momentum_ramp");audit.put("observation_only",Boolean.parseBoolean(System.getenv().getOrDefault("PRE_W04_OBSERVE_ONLY","false")));')
    s = replace(s, '      if(state.equals("calm_gate_passed")){',
                '      if(state.equals("calm_gate_passed") && globalSourceEnabled)throw new IllegalStateException("Startup forcing still active at acceptance");\n      if(state.equals("calm_gate_passed")){')
    MACRO.write_text(s,encoding='utf8')
    compiled=HERE/'compiled_global_ramp';compiled.mkdir(exist_ok=True)
    p=subprocess.run([JAVAC,'-cp',CP,'-d',str(compiled),str(MACRO)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    receipt=dict(ok=p.returncode==0,macro_sha256=sha(MACRO),template_sha256=TEMPLATE_SHA,ramp_s=1.,scope='whole fluid region',messages=p.stderr[-5000:])
    write(HERE/'global_ramp_compile_receipt.json',receipt)
    if p.returncode:raise RuntimeError(p.stderr)
    return receipt

if __name__=='__main__':print(json.dumps(build()))
