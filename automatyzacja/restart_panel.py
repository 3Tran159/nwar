"""Reload only the web panel; leave the queue controller and solver untouched."""
from common import *
import subprocess
m=read(DATA/'server.json');pid=m.get('pid')
if m.get('birth') and birth(pid)==m['birth']:
 k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p;k.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
 h=k.OpenProcess(0x1001,False,pid)
 if not h:raise RuntimeError('Cannot access owned web panel')
 try:
  if birth(pid)!=m['birth']:raise RuntimeError('Identity changed')
  if not k.TerminateProcess(h,0):raise RuntimeError('Cannot reload owned web panel')
 finally:k.CloseHandle(h)
time.sleep(.5)
with (DATA/'server.service.log').open('a',encoding='utf8') as log:
 p=subprocess.Popen([str(PYTHON),str(HERE/'server.py')],cwd=HERE,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
print('Panel reloaded; solver controller untouched. Panel PID',p.pid)
