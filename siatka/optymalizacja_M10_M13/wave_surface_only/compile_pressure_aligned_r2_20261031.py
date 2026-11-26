from pathlib import Path
import subprocess,hashlib,json,datetime
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
P=W/"wave_pressure_aligned_prepared_20261031"
m=P/"WaveFromOwnCalmPressureAligned.java"
assert m.exists() and (P/"compile_receipt.json").exists()
assert "StaticPressureProfile" in m.read_text(encoding="utf-8")
javac=Path(r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe")
cp=r"E:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
q=subprocess.run([str(javac),"-cp",cp,"-d",str(P/"compiled"),str(m)],capture_output=True,text=True,timeout=90)
out=P/"compile_receipt_r2.json"
assert not out.exists()
data={"at":datetime.datetime.now().astimezone().isoformat(),"status":"javac_pass" if q.returncode==0 else "compile_failed","class_exists":(P/"compiled"/"macro"/"WaveFromOwnCalmPressureAligned.class").exists(),"macro_sha256":hashlib.sha256(m.read_bytes()).hexdigest(),"only_api_typename_corrected":"PressureProfile to StaticPressureProfile","prior_failure_receipt_preserved":True,"errors":q.stderr[-1700:]}
out.write_text(json.dumps(data,indent=2),encoding="utf-8")
print(json.dumps(data,ensure_ascii=False))
assert data["status"]=="javac_pass" and data["class_exists"]