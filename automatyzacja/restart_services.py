from common import *
import subprocess
# This maintenance action is allowed ONLY while our solver queue has no active job.
assert not any(j['status'] in ('running','preflight','pausing') for j in jobs())
def stop_owned(path):
 m=read(path);pid=m.get('pid')
 if not m.get('birth') or birth(pid)!=m['birth']:return
 k=ctypes.windll.kernel32;k.OpenProcess.restype=ctypes.c_void_p
 k.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
 h=k.OpenProcess(0x1001,False,pid)
 if not h:raise RuntimeError('Cannot open own service')
 try:
  if birth(pid)!=m['birth']:raise RuntimeError('Identity changed')
  if not k.TerminateProcess(h,0):raise RuntimeError('Cannot close own idle service')
 finally:k.CloseHandle(h)
 print('Closed own idle service',pid)
stop_owned(DATA/'worker.lock');stop_owned(DATA/'server.json')
time.sleep(1)
for script in ('server.py','worker.py'):
 with (DATA/(script+'.maintenance.log')).open('a') as f:
  p=subprocess.Popen([str(PYTHON),str(HERE/script)],cwd=HERE,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 print('Started',script,p.pid)
