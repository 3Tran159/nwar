"""Prepare separate, explicitly approved matched calm/wave dt0.2ms experiments. No launches."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'approved_wave_plan_20261101';P=R/'M13_wave_direct_20261031'
C=R/'M13_farfield15_20261031'/'M13_GPU_calm_dt0004'/'ContinueCalmGPULive.java';W=P/'M13_GPU_W20_H050_continuation_R4V_20261101'/'M13ContinueWaveR4Visual.java'
assert not (D/'sensitivity_compile_receipt.json').exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def patch(text,a,b):
 assert text.count(a)==1,(a,text.count(a))
 return text.replace(a,b,1)
calm=C.read_text(encoding='utf8')
calm=patch(calm,'public class ContinueCalmGPULive extends StarMacro','public class M13CalmDt02 extends StarMacro')
calm=patch(calm,'pass&=ok;check.put(','if(col<=2)pass&=ok;check.put(')
calm=patch(calm,'"lift_convention","hydrodynamic_lift_v1"','"lift_convention","hydrodynamic_lift_v1"') if calm.count('"lift_convention","hydrodynamic_lift_v1"')==1 else calm
calm=patch(calm,'Two adjacent non-overlapping 0.2 s windows; absolute relative mean shift and within-window RMS must each be <0.5% for CL, CD total, CD pressure and CD viscous. Require two successive passing checks 0.2 s apart. Near-zero coefficients cannot pass an unresolved relative test. Stabilization is not itself a GCI result.','Project-primary CLhydro and CDtotal only: two adjacent full0.2s windows, mean shift and RMS<0.5%, two checks0.2s apart. Pressure/viscous are diagnostics, NOT independent acceptance gates. Not a legacy four-way pass or GCI.')
calm=patch(calm,'dt=Double.parseDouble(System.getenv("NTNU_STAB_DT"));','dt=Double.parseDouble(System.getenv("NTNU_STAB_DT"));\n      if(Math.abs(dt-.0002)>1e-12)throw new IllegalStateException("Approved sensitivity dt0.2ms required");')
calm=patch(calm,'"Calm-water W01a mesh convergence, saved fields, no incident wave, no reinitialization"','"Approved M13 matched calm reference dt0.2ms; unchanged mesh/physics, no incident wave/reinitialization"')
calm=patch(calm,'loadPrior();','// Deliberately no old dt0.4ms history in dt0.2ms settling windows.\n      if(System.getenv("NTNU_STAB_PRIOR_HISTORY")!=null&&!System.getenv("NTNU_STAB_PRIOR_HISTORY").isBlank())throw new IllegalStateException("No mixed-dt prior history");')
wave=W.read_text(encoding='utf8');wave=patch(wave,'public class M13ContinueWaveR4Visual extends StarMacro','public class M13WaveDt02 extends StarMacro')
wave=patch(wave,'dt!=.0004||inner!=10||steps<400||steps>12000||budget<600||budget>14400','dt!=.0002||inner!=10||steps<400||steps>30000||budget<600||budget>30000')
wave=patch(wave,'setup.put("t0",t0);','setup.put("t0",t0);setup.put("setting_change_exclusion_end_s",t0+period);setup.put("sensitivity_dt_previous_s",.0004);setup.put("ramp_period_is_estimate",true);')
wave=patch(wave,'"M13 foil+wave already-computed checkpoint; copied and continued"','"Approved dt0.2ms sensitivity from saved R4V field; no wave reset, no physics/mesh changes"')
for text in (calm,wave):
 assert 's.getSolution().initializeSolution()' not in text and '.clearSolution(' not in text
paths=[D/'M13CalmDt02.java',D/'M13WaveDt02.java']
for dest,text in zip(paths,(calm,wave)):
 assert not dest.exists();dest.write_text(text,encoding='utf8')
out=D/'compiled_sensitivity';out.mkdir()
q=subprocess.run([r'C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe','-cp',r'E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*','-d',str(out),*[str(p) for p in paths]],capture_output=True,text=True,timeout=90)
receipt={'at':datetime.now().astimezone().isoformat(),'status':'javac_pass' if q.returncode==0 else 'compile_failed','macros':{p.name:sha(p) for p in paths},'source_calm_sha256':sha(C),'source_wave_sha256':sha(W),'sole_numerical_change':'dt0.4ms to0.2ms; same309441cell M13,physics,BC,second-order,10inner','primary_calm_stopping_rule':'already approved CL/CD only; component diagnostics retained','wave_discard':'one planning period after dt change, then inspect cycle drift; not automatic certification','runner_not_yet_launched':True,'stderr':q.stderr[-1500:]}
(D/'sensitivity_compile_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
assert q.returncode==0,receipt
print(json.dumps({'compiled':True,'macros':[p.name for p in paths],'no_solver_started':True}))
