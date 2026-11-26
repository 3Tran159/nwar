from pathlib import Path
import subprocess,json,hashlib
O=Path(__file__).resolve().parent
src=O/'ContinueCalmGCI.java';p=O/'ContinueCalmGPU.java'
t=src.read_text()
t=t.replace('public class ContinueCalmGCI extends StarMacro','public class ContinueCalmGPU extends StarMacro',1)
needle='if(s.getNumberOfGpgpus()!=0)throw new IllegalStateException("CPU-only execution required for mesh GCI");'
assert t.count(needle)==1
t=t.replace(needle,'if(s.getNumberOfGpgpus()!=1)throw new IllegalStateException("Exactly one GPU required for the accelerated mesh campaign");')
p.write_text(t,encoding='utf-8')
base='E:/Program Files/Siemens/21.02.007-R8/STAR-CCM+21.02.007-R8/star/lib/java'
cp=';'.join(base+'/'+x for x in ['platform/modules/ext/*','platform/modules/*','platform/core/*'])
classes=O/'gpu_macro_classes';classes.mkdir(exist_ok=True)
r=subprocess.run(['C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe','--release','17','-cp',cp,'-d',str(classes),str(p)],capture_output=True,text=True)
(O/'gpu_macro_compile.log').write_text(r.stdout+r.stderr)
receipt={'status':'javac_passed' if r.returncode==0 else 'failed','source_CPU_macro_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'GPU_macro_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'changes':['class name','require one GPU'],'physics_and_diagnostics_unchanged':True}
(O/'gpu_macro_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if r.returncode:print(r.stderr)
raise SystemExit(r.returncode)
