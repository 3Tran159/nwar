"""Prepare one authorized near-zero-wave control. Original M13 and R2 remain immutable."""
from pathlib import Path
from datetime import datetime
import json, hashlib, subprocess
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'approved_wave_plan_20261101';P=R/'M13_wave_direct_20261031'
source=P/'M13InletWavePilotR2.java';target=D/'M13NearZeroControl.java';receipt=D/'h0_control_compile.json'
assert not target.exists() and not receipt.exists(),'Prepared control already exists; inspect rather than overwrite'
original=source.read_bytes();text=original.decode('utf-8')
def replace(a,b):
 global text
 assert text.count(a)==1,(a[:100],text.count(a))
 text=text.replace(a,b,1)
replace('public class M13InletWavePilotR2 extends StarMacro','public class M13NearZeroControl extends StarMacro')
replace('double t0,dt,period,ramp,H=.5,lambda=20.,water0;','double t0,dt,period,ramp,H=.000001,lambda=20.,water0;')
replace('steps<40||steps>1200||budget<300||budget>2400','steps!=10000||budget<600||budget>10000')
replace('<0.499999 m>*0.5','<0.0 m>*0.5')
replace('"M13_Exploratory_Inlet_W20_H050"','"M13_Matched_NearZero_Inlet_Control"')
replace('setup.put("wave_inlet_only",true);','setup.put("wave_inlet_only",true);setup.put("experiment_type","matched_nearzero_wave_control");setup.put("not_wave_propagation_test",true);setup.put("forcing_spatial_proof_pending",true);')
replace('setup.put("ramp_s",ramp);','setup.put("ramp_s",ramp);setup.put("period_for_ramp_is_estimate",true);setup.put("control_H_m",H);setup.put("control_min_duration_s",2.4);setup.put("control_max_duration_s",4.0);')
replace('pg.put("arrival","NOT_YET_CONFIRMED");','pg.put("arrival","NEARZERO_CONTROL_NO_WAVE_ARRIVAL_CLAIM");')
replace('if(step>0&&step%200==0)','if(step>0&&step%1000==0)')
methods=r'''
 private final ArrayList<double[]> controlSamples=new ArrayList<>();
 private int controlPasses=0;
 private boolean controlSettled=false;
 private void controlSample(int step,double t,double cl,double cd,double p,double v)throws Exception{
  if(step<=0)return;
  controlSamples.add(new double[]{t,cl,cd,p/coeffDen,v/coeffDen});
  int n=(int)Math.round(.2/dt);while(controlSamples.size()>2*n)controlSamples.remove(0);
  if(step%n!=0||controlSamples.size()!=2*n)return;
  Map<String,Object> result=new LinkedHashMap<>();boolean pass=true;
  double[] oldMean=new double[5],newMean=new double[5];
  for(int col=1;col<=4;col++){
   double a=0,b=0,sa=0,sb=0;
   for(int i=0;i<n;i++){a+=controlSamples.get(i)[col]/n;b+=controlSamples.get(i+n)[col]/n;}
   for(int i=0;i<n;i++){sa+=Math.pow(controlSamples.get(i)[col]-a,2)/n;sb+=Math.pow(controlSamples.get(i+n)[col]-b,2)/n;}
   oldMean[col]=a;newMean[col]=b;
   double shift=100*Math.abs(b-a)/Math.max(Math.abs(b),1e-30);
   double rmsA=100*Math.sqrt(sa)/Math.max(Math.abs(a),1e-30),rmsB=100*Math.sqrt(sb)/Math.max(Math.abs(b),1e-30);
   boolean ok=Double.isFinite(shift)&&Double.isFinite(rmsA)&&Double.isFinite(rmsB)&&Math.abs(a)>1e-10&&Math.abs(b)>1e-10&&shift<.5&&rmsA<.5&&rmsB<.5;
   if(col<=2)pass&=ok;
   result.put(new String[]{"","CL_hydrodynamic","CD_total","CD_pressure_diagnostic","CD_viscous_diagnostic"}[col],Map.of("mean_previous",a,"mean_latest",b,"mean_shift_pct",shift,"rms_previous_pct",rmsA,"rms_latest_pct",rmsB,"pass",ok));
  }
  boolean eligible=step>=6000;
  controlPasses=eligible&&pass?controlPasses+1:0;controlSettled=controlPasses>=2;
  double dp=newMean[3]-oldMean[3],dv=newMean[4]-oldMean[4],norm=Math.max(Math.abs(newMean[2]),1e-30);
  result.put("time_s",t);result.put("step",step);result.put("window_s",.2);
  result.put("primary_pass",pass);result.put("eligible_after2p4s",eligible);result.put("consecutive_eligible_passes",controlPasses);
  result.put("component_abs_sum_over_totalCD",(Math.abs(dp)+Math.abs(dv))/norm);result.put("component_opposing_sign",dp*dv<0);
  result.put("physical_equivalence_accepted",false);result.put("note","Project CL/CD settling only. Must compare against saved calm; continued relaxation is not separated from a boundary mismatch.");
  Files.writeString(out.resolve("control_settling_checks.jsonl"),json(result)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
  save("control_settling_latest.json",result);
 }
 private boolean spatialAttempted=false;
 private void narrowSpatialRead(int step,double t){
  if(step!=10||spatialAttempted)return;spatialAttempted=true;
  Map<String,Object> result=new LinkedHashMap<>();result.put("step",step);result.put("time_s",t);result.put("read_only_reports",true);
  try{
   FieldFunction pos=s.getFieldFunctionManager().getFunction("Position").getComponentFunction(0);
   ThresholdPart zone=s.getPartManager().createThresholdPart();zone.getInputParts().setObjects(reg);zone.setFieldFunction(pos);zone.setRange(new DoubleVector(new double[]{-2,3}));zone.setMode(ThresholdMode.BETWEEN_TAG);
   int valid=0;
   for(FieldFunction field:s.getFieldFunctionManager().getObjects()){
    String name=field.getPresentationName();
    if(!name.equals("Forcing Strength Indicator")&&!name.equals("Damping Strength Indicator"))continue;
    MaxReport r=max("H0 local diagnostic "+name,field,zone);double value=r.getReportMonitorValue();
    boolean available=Double.isFinite(value)&&Math.abs(value)<1e100;
    result.put(name,Map.of("raw_max",value,"available",available));if(available)valid++;
   }
   result.put("valid_indicators",valid);result.put("automatic_acceptance",false);
  }catch(Exception ex){result.put("diagnostic_error",ex.toString());result.put("automatic_acceptance",false);}
  try{save("narrow_forcing_after_steps.json",result);}catch(Exception ignored){}
 }
'''
replace(' public void execute(){',methods+'\n public void execute(){')
replace('     if(step%10==0){','     controlSample(step,t,cl,cd,f[2],f[3]);narrowSpatialRead(step,t);\n     if(step%10==0){')
replace('     if(elapsed>budget){endState="wall_budget";break;}','     if(controlSettled){endState="control_primary_settled";break;}\n     if(elapsed>budget){endState="wall_budget";break;}')
assert 'initializeSolution(' not in text and 'clearSolution(' not in text
assert 'H=.000001' in text and 'dt!=.0004' in text and 'inner!=10' in text
assert source.read_bytes()==original
compiled=D/'compiled_h0_control';compiled.mkdir(exist_ok=False);target.write_text(text,encoding='utf-8')
javac=r'C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe'
cp=r'E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*'
q=subprocess.run([javac,'-cp',cp,'-d',str(compiled),str(target)],capture_output=True,text=True,timeout=90)
report={'at':datetime.now().astimezone().isoformat(),'status':'javac_pass' if q.returncode==0 else 'compile_failed','source_sha256':hashlib.sha256(original).hexdigest(),'macro_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'only_physical_change_vs_M13_wave':'target wave height from0.5m to1e-6m; current18m/s, mesh, dt0.4ms,10inner, pressure, wave forcing preserved','added_reporting':'CL/CD primary settling, one narrow after-step forcing read; no 77MB audit','max_steps':10000,'min_eligible_time_s':2.4,'compiler_note':q.stderr[-1300:],'no_solver_started':True}
receipt.write_text(json.dumps(report,indent=2),encoding='utf-8')
assert q.returncode==0 and (compiled/'macro'/'M13NearZeroControl.class').exists(),report
print(json.dumps({'compiled':True,'macro':str(target),'original_preserved':True,'no_solver_started':True}))
