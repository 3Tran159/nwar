"""Derive PRE W04 macros from the audited C01 calm procedure."""
from common import *
from pre_w04 import PRE,REFERENCE
from prepare_w04_geometry import BASE,CP,JAVAC
import subprocess

def replace(s,a,b):
 assert s.count(a)==1,(a[:90],s.count(a))
 return s.replace(a,b)

def build():
 PRE.mkdir(parents=True,exist_ok=True)
 s=(BASE/'MapW01Solution.java').read_text(encoding='utf8').replace('MapW01Solution','MapPreW04')
 s=replace(s,'import java.nio.file.*;', 'import star.vof.*;import java.nio.file.*;')
 s=replace(s,'try{\n   s.getSimulationIterator()', '''try{
   if(!Paths.get(s.getSessionPath()).toAbsolutePath().normalize().equals(out.resolve("input.sim").toAbsolutePath().normalize()))throw new IllegalStateException("Disposable mapping copy required");
   s.getSimulationIterator()''')
 s=replace(s,'fv.getCellCount()!=317277','fv.getCellCount()!=309441')
 s=replace(s,'Expected the saved W01a checkpoint','Expected original C01 on M13')
 s=replace(s,'Map<String,Object> after=metrics();','''for(Boundary b:fluid.getBoundaryManager().getBoundaries()){
    if(b.getPresentationName().equals("DOMAIN.inlet"))b.getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(40);
    if(b.getPresentationName().equals("DOMAIN.outlet"))b.getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(40);
   }
   Map<String,Object> after=metrics();''')
 s=replace(s,'/((Number)before.get("mass")).doubleValue()-1','/(((Number)before.get("mass")).doubleValue()+38411.52)-1')
 s=replace(s,'/((Number)before.get("water")).doubleValue()-1','/(((Number)before.get("water")).doubleValue()+38.4)-1')
 s=s.replace('mass_relative_change','mass_relative_error_expected_expanded_domain').replace('water_relative_change','water_relative_error_expected_expanded_domain')
 s=replace(s,'Higher-order stencil, replace mesh in original region; no initialization','Higher-order stencil; original C01 fields mapped without initialization; domain adds 38.4 m3 water and 9.6 m3 air; forcing/damping 40 m')
 (PRE/'MapPreW04.java').write_text(s,encoding='utf8')

 s=(CLEAN/'ContinueC01WarmAudited.java').read_text(encoding='utf8').replace('ContinueC01WarmAudited','PreW04Calm')
 s=replace(s,'private int consecutivePasses=0;','private int consecutivePasses=0,compatiblePasses=0;private boolean compatibleNow=false;')
 s=replace(s,'E:/ntnu_mesh_optimization_20261030/clean_c01_campaign_20261101/','E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/PRE_W04_20261102/')
 s=replace(s,'expectedCells!=309441||target!=5.8','expectedCells<=309441||expectedCells>1500000||Math.abs(target-(expectedStart+2.0))>1e-8')
 s=replace(s,'if(Math.abs(startTime-3.8992)>1e-7||fv.getCellCount()!=309441)','if(Math.abs(startTime-expectedStart)>1e-7||fv.getCellCount()!=expectedCells)')
 s=replace(s,'Settled M13 t3.8992 checkpoint or mesh mismatch','Mapped original C01 checkpoint or expanded mesh mismatch')
 s=replace(s,'// Latest explicit user instruction authorizes fresh FIELDS/HISTORY on this copy only.','// Preserve mapped C01 fields. Only PRE W04 history is new; C01 remains the Q reference.')
 s=replace(s,'New independently checked calm C01 from old M13 settled t3.8992 as INITIAL GUESS ONLY, no reinitialization; dt0.4ms, 18m/s, rho1000/1.2; new CL/CD windows and flux/VOF guards','PRE W04: original C01 mapped to expanded mesh; no wave, no reinitialization, no new Q reference; 0.2 s windows and 0.5% stability/C01 gates')
 s=replace(s,'M13_farfield15_20261031/M13_GPU_calm_dt0004/final.sim',SOURCE.as_posix())
 s=replace(s,'audit.put("settling_eligible_after_s",2.0)','audit.put("settling_eligible_after_s",.6)')
 s=replace(s,'waterAtRestart=38.365860030511556;','waterAtRestart=Double.parseDouble(System.getenv("PRE_W04_EXPECTED_WATER"));')
 s=replace(s,'prepareHealthAndGauges(vf);prepareLiveScene();captureLiveFrame(startTime);','prepareHealthAndGauges(vf);')
 s=replace(s,'if(steps%50==0)captureLiveFrame(t);','// Full force history is saved every step; no expensive live scene render.')
 s=replace(s,'lastFrameNanos=0;captureLiveFrame(s.getSolution().getPhysicalTime());','// Preserve the native checkpoint and scientific CSV evidence.')
 s=replace(s,'wall_seconds,step,iteration,physical_time_s,dt_s,Fx_slice_N,Fz_slice_N,pressure_drag_N,viscous_drag_N,CD,CL_total,max_velocity_m_s,max_CFL,interface_max_CFL,mean_yplus,min_yplus,max_yplus,CL',
             'wall_s,step,iteration,time_s,dt_s,Fx_N,Fz_N,pressure_drag_N,viscous_drag_N,CD_total,CL_total,max_speed_m_s,max_CFL,interface_CFL,mean_yplus,min_yplus,max_yplus,CL_hydrodynamic')
 s=replace(s,'if(consecutivePasses>=2){state="stabilized";break;}','''compatiblePasses=pass&&compatibleNow?compatiblePasses+1:0;
            if(compatiblePasses>=2){state="calm_gate_passed";break;}
            if(consecutivePasses>=2&&!compatibleNow){state="stable_reference_mismatch";break;}''')
 s=replace(s,'if(s.getSolution().getPhysicalTime()<startTime+.6-1e-9||samples.size()<2*n)return false;','if(samples.size()<2*n)return false;')
 s=replace(s,'int end=samples.size();Map<String,Object> check=new LinkedHashMap<>();boolean pass=true;','int end=samples.size();Map<String,Object> check=new LinkedHashMap<>();boolean pass=true;compatibleNow=true;')
 s=replace(s,'if(col<=2)pass&=ok;check.put(keys[col-1],','''if(col<=2){
          pass&=ok;double reference=col==1?0.007002316911710474:0.31565950495122014;
          double deviation=100*Math.abs(latest-reference)/Math.abs(reference);
          compatibleNow &= Double.isFinite(deviation)&&deviation<=.5;
          check.put(keys[col-1]+"_C01_pct",deviation);
        }
        check.put(keys[col-1],''')
 s=replace(s,'check.put("lift_convention","hydrodynamic_lift_v1");check.put("time_s",samples.get(end-1)[0]);check.put("pass",pass);','''boolean eligible=s.getSolution().getPhysicalTime()>=startTime+.6-1e-9;
      check.put("eligible",eligible);check.put("compatible_with_original_C01",compatibleNow);check.put("reference_CD",0.007002316911710474);check.put("reference_CL",0.31565950495122014);
      check.put("consecutive_compatible",pass&&eligible&&compatibleNow?compatiblePasses+1:0);
      pass &= eligible;
      check.put("lift_convention","hydrodynamic_lift_v1");check.put("time_s",samples.get(end-1)[0]);check.put("pass",pass);''')
 s=replace(s,'Fresh history; project rule not GCI.','Fresh PRE W04 history; both means must also agree with original C01 within 0.5%. Original C01 remains the Q reference.')
 s=replace(s,'(t>.02&&Math.abs(d)>2000)','(t>startTime+.02&&Math.abs(d)>2000)')
 (PRE/'PreW04Calm.java').write_text(s,encoding='utf8')
 compiled=PRE/'compiled';compiled.mkdir(exist_ok=True)
 files=[PRE/'MapPreW04.java',PRE/'PreW04Calm.java']
 p=subprocess.run([JAVAC,'-cp',CP,'-d',str(compiled),*map(str,files)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
 receipt=dict(ok=p.returncode==0,files={f.name:sha(f) for f in files},messages=p.stderr[-4000:],original_C01_sha256=SOURCE_SHA,reference=REFERENCE)
 write(PRE/'compile_receipt.json',receipt)
 if p.returncode:raise RuntimeError(p.stderr)
 print(json.dumps(receipt))

if __name__=='__main__':build()
