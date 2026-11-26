from pathlib import Path
import json,hashlib,subprocess,datetime
O=Path(__file__).resolve().parent
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
buoyancy=22.718189111947265
convention=dict(id='hydrodynamic_lift_v1',quantity='CL',formula='CL = CL_total - buoyancy_N / qS_N',buoyancy_N=buoyancy,qS_N=3855.6,CL_offset=buoyancy/3855.6,rho_kg_m3=1000,gravity_m_s2=9.81,span_m=.02,displaced_volume_m3=buoyancy/(1000*9.81),scope='Fully submerged fixed foil in calm water; common nominal geometry correction for every M-series mesh',evidence='F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/build_dashboard_before_24m_wave_scope.py',user_instruction='Exclude buoyancy from CL, including settling and mesh GCI. Raw CL_total retained in source histories.')
(O/'lift_convention.json').write_text(json.dumps(convention,indent=2))
p=O/'calm_analysis.py';s=p.read_text();(O/('calm_analysis_before_lift_'+stamp+'.py.txt')).write_text(s)
s=s.replace("KEYS=['CD','CL_total','CD_pressure','CD_viscous']","KEYS=['CD','CL','CD_pressure','CD_viscous']\nCL_OFFSET=22.718189111947265/3855.6")
s=s.replace("r=dict(row);r['CD_pressure']","r=dict(row);r['CL']=r['CL_total']-CL_OFFSET;r['CD_pressure']")
s=s.replace("return dict(time_s=", "return dict(lift_convention='hydrodynamic_lift_v1',time_s=")
p.write_text(s)

p=O/'ContinueCalmGPULive.java'
s=(O/'ContinueCalmGPU.java').read_text().replace('public class ContinueCalmGPU','public class ContinueCalmGPULive')
s=s.replace('private Simulation s;', 'private final double CL_OFFSET=22.718189111947265/3855.6;\n  private Scene liveScene; private long lastPreview=0; private int previewIndex=0,priorCount=0;\n  private Simulation s;')
s=s.replace('recordBudget();\n      long start=', 'recordBudget();\n      loadPrior();\n      setupPreview();\n      preview(startTime,fx.getReportMonitorValue(),fz.getReportMonitorValue(),pressure.getReportMonitorValue(),shear.getReportMonitorValue());\n      long start=',1)
s=s.replace('mean_yplus,min_yplus,max_yplus\\n','mean_yplus,min_yplus,max_yplus,CL\\n')
s=s.replace('yMax.getReportMonitorValue()+"\\n"', 'yMax.getReportMonitorValue()+","+(l/q-CL_OFFSET)+"\\n"')
s=s.replace('"CL_total",l/q,"CFL"', '"CL",l/q-CL_OFFSET,"CFL"')
s=s.replace('samples.add(new double[]{t,d/q,l/q,p/q,v/q});','samples.add(new double[]{t,d/q,l/q-CL_OFFSET,p/q,v/q});\n          if(steps%50==0&&(System.nanoTime()-lastPreview)*1e-9>=120)preview(t,d,l,p,v);')
s=s.replace('&&steps%(int)Math.round(window/dt)==0','&&(steps+priorCount)%(int)Math.round(window/dt)==0')
s=s.replace('String[] keys={"CD","CL_total",','String[] keys={"CD","CL",')
s=s.replace('check.put("time_s",','check.put("lift_convention","hydrodynamic_lift_v1");check.put("time_s",')
s=s.replace('      exportFields(vf);','      preview(s.getSolution().getPhysicalTime(),fx.getReportMonitorValue(),fz.getReportMonitorValue(),pressure.getReportMonitorValue(),shear.getReportMonitorValue());\n      exportFields(vf);')
s=s.replace('audit.put("cells",','audit.put("lift_convention","hydrodynamic_lift_v1");audit.put("buoyancy_N",22.718189111947265);audit.put("preview_cadence_wall_s",120);\n      audit.put("cells",',1)
extra=r'''
  private void loadPrior()throws Exception {
    String path=System.getenv("NTNU_STAB_PRIOR_HISTORY");if(path==null||path.isBlank())return;
    List<String> lines=Files.readAllLines(Paths.get(path));if(lines.size()<2)return;
    String[] header=lines.get(0).split(",");Map<String,Integer> index=new HashMap<>();
    for(int i=0;i<header.length;i++)index.put(header[i],i);
    double previous=Double.NaN;
    for(int i=1;i<lines.size();i++){
      String[] v=lines.get(i).split(",");double t=Double.parseDouble(v[index.get("physical_time_s")]),h=Double.parseDouble(v[index.get("dt_s")]);
      if(Math.abs(h-dt)>1e-10||t>startTime+1e-8||Double.isFinite(previous)&&Math.abs(t-previous-dt)>1e-8)throw new IllegalStateException("Prior history discontinuity");
      double cd=Double.parseDouble(v[index.get("CD")]),cl=Double.parseDouble(v[index.get("CL_total")])-CL_OFFSET;
      double p=Double.parseDouble(v[index.get("pressure_drag_N")])/3855.6,vv=Double.parseDouble(v[index.get("viscous_drag_N")])/3855.6;
      samples.add(new double[]{t,cd,cl,p,vv});previous=t;priorCount++;
    }
    if(Math.abs(previous-startTime)>1e-8)throw new IllegalStateException("Prior history does not end at checkpoint");
    while(samples.size()>2*(int)Math.round(window/dt)+10)samples.remove(0);
  }
  private void setupPreview(){
    try{
      PlaneSection mid=s.getPartManager().createPlaneSection();mid.setPresentationName("Mesh live midspan");mid.getInputParts().setObjects(fluid);mid.setOrigin(new DoubleVector(new double[]{0,.02,0}));mid.setOrientation(new DoubleVector(new double[]{0,1,0}));
      liveScene=s.getSceneManager().createScene("Mesh live speed");
      ScalarDisplayer d=liveScene.getDisplayerManager().createScalarDisplayer("Speed [m/s]");d.setRepresentation(fv);d.getInputParts().setObjects(mid);d.getScalarDisplayQuantity().setFieldFunction(s.getFieldFunctionManager().getFunction("Velocity").getMagnitudeFunction());d.getScalarDisplayQuantity().setAutoRange(false);d.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{0,30}));
      PartDisplayer wall=liveScene.getDisplayerManager().createPartDisplayer("Foil");wall.setRepresentation(fv);wall.getInputParts().setObjects(foil);wall.setSurface(true);wall.setOutline(true);
      CurrentView cv=liveScene.getCurrentView();cv.setProjectionMode(VisProjectionMode.PARALLEL);cv.setFocalPoint(new DoubleVector(new double[]{.7,.02,0}));cv.setPosition(new DoubleVector(new double[]{.7,-100,0}));cv.setViewUp(new DoubleVector(new double[]{0,0,1}));cv.setParallelScale(.9);
      liveScene.initializeAndWait();
    }catch(Exception e){liveScene=null;try{Files.writeString(out.resolve("preview_error.txt"),e.toString());}catch(Exception ignored){}}
  }
  private void preview(double t,double drag,double lift,double p,double v){
    if(liveScene==null)return;
    long began=System.nanoTime();
    try{
      String name="live_velocity_"+(previewIndex++%2)+".png";Path image=out.resolve(name);
      liveScene.printAndWait(image.toString(),1,960,480,true,false);
      String digest=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(image)));
      Map<String,Object> meta=new LinkedHashMap<>();meta.put("time_s",t);meta.put("image",name);meta.put("sha256",digest);meta.put("field","Velocity magnitude");meta.put("units","m/s");meta.put("range",List.of(0,30));meta.put("CL",lift/3855.6-CL_OFFSET);meta.put("CD",drag/3855.6);meta.put("CD_pressure",p/3855.6);meta.put("CD_viscous",v/3855.6);meta.put("lift_convention","hydrodynamic_lift_v1");meta.put("render_wall_s",(System.nanoTime()-began)*1e-9);meta.put("cadence_wall_s",120);
      Path tmp=out.resolve("live_preview.tmp");Files.writeString(tmp,json(meta));Files.move(tmp,out.resolve("live_preview.json"),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }catch(Exception e){try{Files.writeString(out.resolve("preview_error.txt"),e.toString());}catch(Exception ignored){}}
    lastPreview=System.nanoTime();
  }
'''
s=s.replace('  private void recordBudget()',extra+'\n  private void recordBudget()')
p.write_text(s)
base='E:/Program Files/Siemens/21.02.007-R8/STAR-CCM+21.02.007-R8/star/lib/java'
cp=';'.join(base+'/'+x for x in ['platform/modules/ext/*','platform/modules/*','platform/core/*'])
classes=O/'gpu_macro_classes';classes.mkdir(exist_ok=True)
r=subprocess.run(['C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe','--release','17','-cp',cp,'-d',str(classes),str(p)],capture_output=True,text=True)
(O/'gpu_live_macro_compile.log').write_text(r.stdout+r.stderr)
receipt=dict(status='javac_passed' if r.returncode==0 else 'failed',GPU_macro_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),changes=['Hydrodynamic CL for settling; raw CL_total retained','Read-only saved-step native velocity image every 120 wall seconds','Reuse prior matching force history'],physics_unchanged=True)
(O/'gpu_live_macro_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if r.returncode:print(r.stderr)
raise SystemExit(r.returncode)
