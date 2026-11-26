from pathlib import Path
import hashlib,json,os,uuid,shutil
root=Path(r"E:\ntnu_mesh_optimization_20261030")
rb=root/"AUTONOMOUS_RECOVERY_PROMPT.md"
pf=root/"plan.json"
p=json.loads(pf.read_text(encoding="utf-8-sig"))
actual=hashlib.sha256(rb.read_bytes()).hexdigest()
assert "## H. Powtarzalna awaria" in rb.read_text(encoding="utf-8-sig"),"Rule missing"
assert p["version"]=="light-mesh-watch-4-adaptive-recovery"
backup=root/("plan_pre_hash_fix_"+uuid.uuid4().hex[:8]+".json")
shutil.copy2(pf,backup)
old=p["recovery_policy"]["runbook_sha256"]
p["recovery_policy"]["runbook_sha256"]=actual
tmp=pf.with_name("plan."+uuid.uuid4().hex+".tmp")
tmp.write_bytes((json.dumps(p,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
os.replace(tmp,pf)
assert json.loads(pf.read_text(encoding="utf-8"))["recovery_policy"]["runbook_sha256"]==hashlib.sha256(rb.read_bytes()).hexdigest()
print(json.dumps({"hash_verified":True,"runbook_sha256":actual,"old_plan_sha256":old,"backup":str(backup)},ensure_ascii=False))
