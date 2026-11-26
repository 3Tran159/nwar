"""Build scenes on a saved checkpoint copy before the authorized recovery."""
from common import *
from pre_w04 import PRE,calm_folders
from worker import rt,native,owned_lock
from prepare_w04_geometry import CP,JAVAC
import subprocess

def main():
 assert not native(),'An existing native session must not be disturbed'
 parent=calm_folders()[-1];checkpoint=read(parent/'latest_checkpoint.json')
 source=Path(checkpoint['path']);time_s=checkpoint['time_s']
 assert source.is_file() and source.resolve().is_relative_to(parent.resolve())
 assert not (parent/'completed.json').exists() and read(parent/'stage_result.json').get('source_unchanged') is True
 assert not any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS+[PRE/'STOP',DATA/'PAUSE'])
 assert rt.resource_problem() is None,rt.resource_problem()
 macro=HERE/'NwarCheckpointScenes.java'
 p=subprocess.run([JAVAC,'-cp',CP,'-d',str(HERE/'compiled'),str(macro)],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise RuntimeError(p.stderr)
 out=PRE/('scene_setup_'+datetime.now().strftime('%Y%m%d_%H%M%S'));owned=[];token=uuid.uuid4().hex
 try:
  for path in SOLVER_LOCKS:owned_lock(path,token,'PRE_W04_checkpoint_scenes');owned.append(path)
  write(PRE/'scene_preparation.json',dict(status='preparing',folder=str(out),source=str(source),source_time_s=time_s,pid=os.getpid(),birth=birth(os.getpid()),at=now()))
  original_options=rt.guard.saved_options
  rt.guard.saved_options=lambda workers:original_options(workers)+['-graphics','mesa_swr','-rthreads','1']
  rt.stage(out,source,macro,env={'NWAR_SCENE_OUT':str(out),'NWAR_CHECKPOINT_TIME':str(time_s)},workers=1,gpu=False,mask=48,budget_s=900,protect_main=False,phase='PRE_W04_scene_setup_no_steps')
  receipt=read(out/'scene_receipt.json');assert receipt.get('passed') and receipt['steps_advanced']==0 and abs(receipt['time_s']-time_s)<1e-9
  assert (out/'final.sim').is_file() and (out/'physics_before.txt').read_bytes()==(out/'physics_after.txt').read_bytes()
  write(PRE/'scene_preparation.json',dict(status='ready',folder=str(out),source=str(source),source_time_s=time_s,checkpoint=str(out/'final.sim'),checkpoint_sha256=sha(out/'final.sim'),at=now(),receipt=receipt))
  print(json.dumps(read(PRE/'scene_preparation.json')),flush=True)
 finally:
  if not native():
   for path in reversed(owned):
    if read(path).get('token')==token:path.unlink()

if __name__=='__main__':main()
