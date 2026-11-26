from pathlib import Path
import datetime,shutil
src=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\mesh_study_control_panel.py")
backup=Path(r"E:\ntnu_mesh_optimization_20261030\mesh_study_control_panel_original_20261031_1040.py")
s=src.read_text(encoding="utf8")
assert "http://127.0.0.1:8772" not in s
assert "Resume saved calculation" in s
assert "fetch('/api/mesh-study'" in s
assert "fetch('/api/mesh-study/'+b.dataset.meshAction" in s
shutil.copy2(src,backup)
s=s.replace("Mesh calculation · pause and resume","Mesh calculation queue · pause and resume")
s=s.replace("Resume saved calculation","Resume queue (M11 → M10)")
s=s.replace("Controls M10–M12 mesh tests. Pause finishes the current step and saves the calculated fields.", "Controls the remaining M11 → M10 calm-water queue. Completed M12 will not restart. Pause finishes the current step and saves its calculated fields.")
s=s.replace("let state=null,busy=false;","let state=null,busy=false,token=null;const queueBase='http://127.0.0.1:8772';")
s=s.replace("if(location.protocol==='file:'){note.textContent='Use the local control server to pause or resume: http://127.0.0.1:8771/';return}","if(location.protocol==='file:'){note.textContent='Open the local dashboard at http://127.0.0.1:8771/ to use the queue controls.';return}")
s=s.replace("fetch('/api/mesh-study',{cache:'no-store'})","fetch(queueBase+'/api/mesh-queue',{cache:'no-store'})")
s=s.replace("state=d;show()","state=d;token=d.csrf;show()")
s=s.replace("if(!window.NTNU_LOCAL_TOKEN){msg.textContent='Open http://127.0.0.1:8771/ to use local controls.';return}","if(!token){msg.textContent='Local queue service unavailable. Existing M12 resume is intentionally disabled.';return}")
s=s.replace("fetch('/api/mesh-study/'+b.dataset.meshAction,{method:'POST',headers:{'Content-Type':'application/json','X-NTNU-Control':window.NTNU_LOCAL_TOKEN}","fetch(queueBase+'/api/mesh-queue/'+b.dataset.meshAction,{method:'POST',headers:{'Content-Type':'application/json','X-Mesh-Queue-Token':token}")
assert "fetch('/api/mesh-study" not in s
compile(s,str(src),'exec')
temp=src.with_name("mesh_study_control_panel.py.queue_pending")
temp.write_text(s,encoding="utf8")
temp.replace(src)
print("patched",src,"backup",backup)
