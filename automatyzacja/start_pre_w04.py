"""Idempotent background start of the already-authorized PRE W04 sequence."""
from common import *
from pre_w04 import PRE
import subprocess
PRE.mkdir(exist_ok=True,parents=True)
owner=read(PRE/'controller.json')
if owner.get('birth') and owner['birth']==birth(owner.get('pid')):
 print('PRE W04 controller is already waiting/running.',flush=True)
else:
 assert not (PRE/'calm').exists(),'Existing calm run preserved'
 if (PRE/'state.json').exists():
  import shutil
  shutil.copy2(PRE/'state.json',PRE/('state_before_fresh_'+datetime.now().strftime('%H%M%S')+'.json'))
 with (PRE/'controller.log').open('a',encoding='utf8') as log:
  p=subprocess.Popen([str(PYTHON),'-X','utf8',str(HERE/'run_pre_w04_fresh.py')],cwd=HERE,stdout=log,stderr=log,
                     creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 write(PRE/'controller.json',dict(pid=p.pid,birth=birth(p.pid),at=now(),action='Fresh PRE W04: start from rest, 1 s ramp to 18 m/s; original C01 remains the reference'))
 print(json.dumps(read(PRE/'controller.json')),flush=True)
