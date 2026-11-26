"""One isolated read-only native audit of the accepted C01 checkpoint."""
from common import *
import subprocess
from worker import native,owned_lock,rt

def main():
 out=HERE/'reviews'/'W04_20261102';out.mkdir(parents=True,exist_ok=True)
 macro=HERE/'W04NativeReview.java';compiled=out/'compiled';compiled.mkdir(exist_ok=True)
 cp='E:/Program Files/Siemens/21.02.007-R8/STAR-CCM+21.02.007-R8/star/lib/java/platform/modules/ext/*'
 compiler='C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe'
 p=subprocess.run([compiler,'-cp',cp,'-d',str(compiled),str(macro)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
 write(out/'compile_receipt.json',dict(ok=p.returncode==0,macro_sha256=sha(macro),messages=p.stderr[-3000:]))
 if p.returncode:raise RuntimeError(p.stderr)
 assert not native(),'A solver is active; do not disturb it'
 assert not any(j['status'] in ('queued','running','preflight','pausing') for j in jobs()),'Queue must be idle'
 assert not any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS),'A STOP or resource reservation is active'
 assert sha(SOURCE)==SOURCE_SHA,'Accepted C01 checksum mismatch'
 assert not rt.resource_problem(),rt.resource_problem()
 folder=DATA/'reviews'/'W04_native_20261102';folder.parent.mkdir(parents=True,exist_ok=True)
 assert not folder.exists(),'Preserve existing audit; do not overwrite'
 token=uuid.uuid4().hex;owned=[]
 try:
  for p in SOLVER_LOCKS:owned_lock(p,token,'W04_zero_step_review');owned.append(p)
  assert not native(),'A solver started while reserving resources'
  write(out/'preflight.json',dict(at=now(),source=str(SOURCE),source_sha256=SOURCE_SHA,macro_sha256=sha(macro),steps=0,CPU_workers=1,GPU=0))
  rt.stage(folder,SOURCE,macro,env={'NWAR_REVIEW_OUT':str(folder)},workers=1,gpu=False,mask=1<<22,budget_s=300,protect_main=False,phase='W04_zero_step_review')
  stage=read(folder/'stage_result.json');review=read(folder/'native_review.json')
  assert stage.get('exit_code')==0 and stage.get('source_unchanged') is True
  assert review.get('steps_taken')==0 and review['time_s']==review['time_after_s']
  assert sha(SOURCE)==SOURCE_SHA
  write(out/'native_review.json',review)
  write(out/'native_receipt.json',dict(passed=True,at=now(),steps=0,source_unchanged=True,source_sha256=SOURCE_SHA,native_folder=str(folder),review_sha256=sha(folder/'native_review.json')))
  print(json.dumps(dict(passed=True,output=str(out),steps=0,source_unchanged=True)))
 finally:
  if not native():
   for p in reversed(owned):
    if read(p).get('token')==token:p.unlink()

if __name__=='__main__':main()
