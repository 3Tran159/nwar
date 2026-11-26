"""Launch the authorized PRE W04 continuation in the background."""
from common import *
from pre_w04 import PRE
import subprocess
owner=read(PRE/'state.json')
assert not (owner.get('birth') and owner['birth']==birth(owner.get('pid'))),'PRE W04 already running'
with (PRE/'resume_controller.log').open('a',encoding='utf8') as log:
 p=subprocess.Popen([str(PYTHON),'-X','utf8',str(HERE/'run_pre_w04_resume.py')],cwd=HERE,stdout=log,stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
write(PRE/'controller.json',dict(pid=p.pid,birth=birth(p.pid),at=now(),action='Continue saved PRE W04 ramp; fields and physics retained'))
print(json.dumps(read(PRE/'controller.json')))
