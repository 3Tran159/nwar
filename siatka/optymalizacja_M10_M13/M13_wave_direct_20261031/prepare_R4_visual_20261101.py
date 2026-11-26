"""One-time R4 from clean, saved R3V. Preparation only, no CFD solver starts."""
from pathlib import Path
import json,hashlib,subprocess,sys
from datetime import datetime
P=Path(r"E:\ntnu_mesh_optimization_20261030\M13_wave_direct_20261031")
PRIOR=P/"M13_GPU_W20_H050_continuation_R3V_20261101"
OLD_JAVA=P/"M13ContinueWaveR3Visual.java"
NEW_JAVA=P/"M13ContinueWaveR4Visual.java"
OLD_RUN=P/"run_m13_wave_visual_continuation_20261101.py"
NEW_RUN=P/"run_m13_wave_R4_visual_continuation_20261101.py"
RECEIPT=P/"m13_wave_R4_compile_receipt.json"
CLASS=P/"compiled_r4visual"
OUT=P/"M13_GPU_W20_H050_continuation_R4V_20261101"
def js(p):
 try:return json.loads(p.read_text(encoding="utf-8-sig"))
 except (OSError,ValueError):return {}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not any(x.exists() for x in (NEW_JAVA,NEW_RUN,RECEIPT,CLASS,OUT)),"R4 already prepared or started, do not duplicate"
assert js(PRIOR/"stage_result.json").get("exit_code")==0 and js(PRIOR/"stage_result.json").get("source_unchanged") is True
assert js(PRIOR/"completed.json").get("status")=="target_reached" and js(PRIOR/"completed.json").get("steps")==12000
assert js(PRIOR/"continuation_result.json").get("status")=="saved_exploratory"
assert (PRIOR/"wave_pilot_final.sim").is_file() and (PRIOR/"wave_pilot_final.sim").stat().st_size>500000000
r=OLD_JAVA.read_text(encoding="utf-8")
a="public class M13ContinueWaveR3Visual extends StarMacro"
b="public class M13ContinueWaveR4Visual extends StarMacro"
assert r.count(a)==1
r=r.replace(a,b,1)
assert "initializeSolution()" not in r and "clearSolution()" not in r
NEW_JAVA.write_text(r,encoding="utf-8")
CLASS.mkdir(exist_ok=False)
javac=r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
cp=r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
res=subprocess.run([javac,"-cp",cp,"-d",str(CLASS),str(NEW_JAVA)],capture_output=True,text=True,timeout=90)
rec={"at":datetime.now().astimezone().isoformat(),"status":"javac_pass" if res.returncode==0 else "compile_fail","source":str(OLD_JAVA),"source_sha256":sha(OLD_JAVA),"new_macro":str(NEW_JAVA),"new_sha256":sha(NEW_JAVA),"compiler_stderr":res.stderr[-650:],"start_run":False,"scope":"One class-name change from R3V; same BC/VOF/wave/dt/inner steps/guards, new independent R4 output, no initial field reset."}
RECEIPT.write_text(json.dumps(rec,indent=2,ensure_ascii=False),encoding="utf-8")
assert res.returncode==0 and (CLASS/"macro"/"M13ContinueWaveR4Visual.class").is_file(),rec
t=OLD_RUN.read_text(encoding="utf-8")
subs=[
 ('PRIOR=P/"M13_GPU_W20_H050_pilot_20261031_r2"','PRIOR=P/"M13_GPU_W20_H050_continuation_R3V_20261101"'),
 ('MACRO=P/"M13ContinueWaveR3Visual.java"','MACRO=P/"M13ContinueWaveR4Visual.java"'),
 ('OUT=P/"M13_GPU_W20_H050_continuation_R3V_20261101"','OUT=P/"M13_GPU_W20_H050_continuation_R4V_20261101"'),
 ('P/"m13_wave_visual_compile_receipt.json"','P/"m13_wave_R4_compile_receipt.json"'),
 ('(P/"compiled_r3visual"/"macro"/"M13ContinueWaveR3Visual.class").is_file()','(P/"compiled_r4visual"/"macro"/"M13ContinueWaveR4Visual.class").is_file()'),
 ('accepted=rt.read(PRIOR/"pilot_result.json")','accepted=rt.read(PRIOR/"continuation_result.json")'),
 ('accepted.get("pilot_saved") is True','accepted.get("status")=="saved_exploratory" and accepted.get("source_unchanged") is True'),
 ('"R2 source process still alive"','"R3V source process still alive"'),
 ('P/"M13_wave_visual_continuation_status.json"','P/"M13_wave_R4_continuation_status.json"'),
 ('old_R2_unmodified=True','old_R3V_unmodified=True'),
 ('phase="M13_foil_wave_R3_continuation"','phase="M13_foil_wave_R4_continuation"'),
 ('"event":"M13_wave_R3_continuation_result"','"event":"M13_wave_R4_continuation_result"'),
]
for a,b in subs:
 assert t.count(a)>=1,(a,t.count(a))
 t=t.replace(a,b)
t=t.replace('Conditional long M13 GPU foil+wave continuation from a verified finished R2 pilot.','Conditional R4 M13 GPU foil+wave continuation from verified saved R3V.')
t=t.replace('Short startup pilot must not be misclassified','Unvalidated R3V propagation must not be misclassified')
assert 'PRIOR=P/"M13_GPU_W20_H050_continuation_R3V_20261101"' in t
assert 'MACRO=P/"M13ContinueWaveR4Visual.java"' in t
assert 'OUT=P/"M13_GPU_W20_H050_continuation_R4V_20261101"' in t
assert 'run_m13_wave_visual_continuation_20261101.py' not in t
compile(t,str(NEW_RUN),'exec')
NEW_RUN.write_text(t,encoding="utf-8")
print(json.dumps({"prepared":True,"compiled":True,"R3V_source_preserved":True,"R4_macro_sha256":rec["new_sha256"],"runner":str(NEW_RUN),"solver_started":False}))
