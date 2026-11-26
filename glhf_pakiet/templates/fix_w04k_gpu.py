"""Update only the stopped W04k launcher's GPU preflight, then retry it."""
from pathlib import Path
from datetime import datetime
import hashlib,json,msvcrt,os,shutil,subprocess,sys,uuid

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def atomic(p,content):
 tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(content);tmp.replace(p)
def locate():
 name='NWAR_GLHF_W04k_Resume_20261109';found=[]
 for p in[HERE,*HERE.parents]:
  for candidate in(p,p/name,p/name/name):
   if(candidate/'w04k_transfer.py').is_file()and(candidate/'manifest.json').is_file():
    m=read(candidate/'manifest.json')
    if m.get('case_id')=='W04k'and candidate.resolve()not in found:found.append(candidate.resolve())
 if len(found)!=1:raise ValueError('Extract this fix inside the W04k continuation folder, then run it again.')
 return found[0]
def recover_missing_work(target,fix):
 """Archive only the proven pre-solver missing-directory failure, never a solver attempt."""
 state_dir=target/'state';saved=state_dir/'run_state.json'
 if not saved.is_file():return False
 if any(p.exists()for p in(target/'STOP',state_dir/'PAUSE')):
  raise ValueError('A manual W04k stop/pause is preserved. No startup state was changed.')
 state=read(saved);error=read(state_dir/'error.json');folder=target/'work/W04k'
 message=error.get('message','').replace('\\','/').lower()
 # Windows renders the missing filename with repr(), doubling every backslash.
 # Compare normalized paths rather than treating that escaped representation as a different directory.
 while '//' in message:message=message.replace('//','/')
 manifest=read(target/'manifest.json');source_time=manifest['time_s']
 checks=dict(hold_state=state.get('state')=='HOLD' and error.get('state')=='HOLD',
             missing_directory_error='[winerror 3]'in message,
             missing_path_matches=str(folder).replace('\\','/').lower()in message,
             solver_work_absent=not folder.exists(),
             time_unchanged=abs(state.get('time_s',-1)-source_time)<=1e-7,
             error_time_unchanged=abs(error.get('time_s',-1)-source_time)<=1e-7)
 atomic(state_dir/'startup_fix_diagnostics.json',json.dumps(checks,indent=2).encode('utf8'))
 if not all(checks.values()):
  raise ValueError('Startup evidence preserved. Checks not satisfied: '+', '.join(k for k,v in checks.items()if not v)+'. Details: state/startup_fix_diagnostics.json')
 if sha(target/'seed/checkpoint.sim')!=fix['checkpoint_sha256']:
  raise ValueError('Original checkpoint checksum differs. Startup evidence is preserved.')
 backup=target/'hotfix_backups'/datetime.now().strftime('missing_work_%Y%m%d_%H%M%S_%f')
 backup.mkdir(parents=True)
 for name in('run_state.json','error.json','owner.json'):
  source=state_dir/name
  if source.is_file():source.replace(backup/name)
 (target/'work').mkdir(exist_ok=True)
 atomic(backup/'recovery_receipt.json',json.dumps(dict(reason='missing_work_directory_before_solver_start',
        checkpoint_sha256=fix['checkpoint_sha256'],time_s=source_time,solver_work_folder_existed=False)).encode('utf8'))
 print('RECOVERED: pre-solver folder-creation failure archived; original checkpoint verified and preserved.',flush=True)
 return True

def apply():
 target=locate();fix=read(HERE/'fix_manifest.json');m=read(target/'manifest.json')
 source=HERE/'w04k_transfer.py';driver=target/'w04k_transfer.py'
 if sha(source)!=fix['new_driver_sha256']or m.get('checkpoint_sha256')!=fix['checkpoint_sha256']:
  raise ValueError('GPU fix or W04k checkpoint identity differs; saved data preserved.')
 actual=sha(driver)
 allowed=[fix['old_driver_sha256'],fix['new_driver_sha256'],*fix.get('previous_driver_sha256',[])]
 if actual not in allowed:raise ValueError('A different W04k launcher revision is present; it is preserved.')
 (target/'state').mkdir(exist_ok=True)
 with(target/'state/instance.lock').open('a+b')as lock:
  lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:raise ValueError('W04k panel/controller is still open. Close it only after its solver has saved and exited.')
  try:
   if actual!=fix['new_driver_sha256']:
    previous=driver.read_bytes();old_manifest=(target/'manifest.json').read_bytes()
    backup=target/'hotfix_backups'/datetime.now().strftime('gpu_guard_%Y%m%d_%H%M%S_%f');backup.mkdir(parents=True)
    (backup/'w04k_transfer.py').write_bytes(previous);(backup/'manifest.json').write_bytes(old_manifest)
    m['files']['w04k_transfer.py']=dict(bytes=source.stat().st_size,sha256=fix['new_driver_sha256'])
    m['gpu_preflight_fix']='xml_process_types_desktop_contexts_and_exit_settling_20261109'
    try:
     atomic(driver,source.read_bytes());atomic(target/'manifest.json',json.dumps(m,indent=2).encode('utf8'))
     if sha(driver)!=fix['new_driver_sha256']:raise ValueError('Installed launcher checksum differs.')
    except Exception:
     atomic(driver,previous);atomic(target/'manifest.json',old_manifest);raise
    print('APPLIED: GPU process types are checked, desktop graphics are allowed, and finishing compute jobs have an exit-settling window.',flush=True)
   else:print('GPU fix already applied.',flush=True)
   if fix.get('recover_missing_work'):recover_missing_work(target,fix)
  finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
 return target

if __name__=='__main__':
 try:
  target=apply()
  print('Retrying the existing W04k launcher. If still blocked, the exact PID/name or NVIDIA diagnostic failure will be displayed.',flush=True)
  raise SystemExit(subprocess.call([sys.executable,str(target/'w04k_transfer.py')],cwd=target))
 except Exception as e:print('HOLD: '+str(e),flush=True);raise SystemExit(1)
