"""Bounded real-solver verification: 10 new steps, saved pause, exact continuation.
Runs only after existing external solvers release their locks. Never controls them.
"""
from common import *
import subprocess

RECEIPT=HERE/'selftest.json'
def state(status,**kw):
 write(RECEIPT,dict(at=now(),status=status,**kw))
def worker():
 owner=read(DATA/'worker.lock')
 if owner.get('birth') and birth(owner.get('pid'))==owner['birth']:return
 with (DATA/'selftest_worker.log').open('a') as log:
  subprocess.Popen([str(PYTHON),str(HERE/'worker.py')],cwd=HERE,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
def wait_job(id,pause_at=None):
 requested=False
 while True:
  j=job(id)
  if j['status'] in ('completed','paused','failed','needs_review','needs_attention','cancelled','interrupted','preflight_blocked'):return j
  if pause_at and not requested and j['status']=='running':
   pg=read(Path(j['folder'])/'progress.json')
   if pg.get('step',0)>=pause_at:
    if (DATA/'PAUSE').exists():raise RuntimeError('Pause already requested outside the test; preserved.')
    write(DATA/'PAUSE',dict(origin='selftest',job=id,at=now()))
    (Path(j['folder'])/'STOP').touch()
    update(id,status='pausing',message='Test: żądanie bezpiecznej pauzy po 10 krokach.')
    state('testing_pause',job=id);requested=True
  time.sleep(.5 if pause_at else 5)
def main():
 current=read(RECEIPT)
 if current.get('status')=='passed':return
 first='5873921a9db143fd'
 if current.get('status')=='resume_authorized_by_user':
  first=current['first_job'];second=current['second_job'];j1=job(first);j2=job(second)
  if j1['status']!='completed' or j2['status']!='paused':raise RuntimeError('Expected completed start and saved paused extension.')
 else:
  state('waiting_for_existing_solver',first_job=first,scope='10 fresh steps + 20 total extension steps including real saved pause/resume')
  worker();j1=wait_job(first)
  if j1['status']!='completed':raise RuntimeError('Fresh smoke did not complete: '+j1['status'])
  if (DATA/'PAUSE').exists():raise RuntimeError('An external pause request is active; not cleared by self-test.')
  second=enqueue('W03','extend',parent_id=first,smoke=20,request_key='selftest_real_pause_20261102')
  state('testing_extension',first_job=first,second_job=second);worker();j2=wait_job(second,10)
  if j2['status']!='paused':raise RuntimeError('Expected saved pause; got '+j2['status'])
  marker=read(DATA/'PAUSE')
  if marker.get('origin')!='selftest' or marker.get('job')!=second:raise RuntimeError('User pause takes precedence; test will not resume.')
 third=enqueue('W03','resume',parent_id=second,request_key='selftest_real_resume_20261102')
 (DATA/'PAUSE').unlink(missing_ok=True)
 state('testing_resume',first_job=first,second_job=second,third_job=third);worker();j3=wait_job(third)
 if j3['status']!='completed':raise RuntimeError('Resume did not complete: '+j3['status'])
 d1=read(Path(j1['folder'])/'completed.json');d2=read(Path(j2['folder'])/'completed.json');d3=read(Path(j3['folder'])/'completed.json')
 assert d1['steps']==10 and d2['steps']+d3['steps']==20
 assert abs(d3['time_s']-(T0+30*.0004))<1e-7
 assert sha(SOURCE)==SOURCE_SHA
 for j in (j1,j2,j3):
  folder=Path(j['folder']);integrity=read(folder/'final_integrity.json')
  assert integrity['sha256']==sha(folder/'wave_pilot_final.sim')
  assert read(folder/'stage_result.json')['source_unchanged'] is True
 state('passed',first_job=first,second_job=second,third_job=third,new_steps=10,extension_steps=d2['steps']+d3['steps'],pause_saved=True,resume_contiguous=True,C01_source_unchanged=True,macro_sha256=read(HERE/'compile_receipt.json')['macro_sha256'],scientific_result=False)
if __name__=='__main__':
 try:main()
 except Exception as e:
  old=read(RECEIPT);state('failed',error=str(e),previous=old);raise
