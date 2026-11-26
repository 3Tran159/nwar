"""Build the pinned W04k transfer, without starting STAR or changing the queue."""
from pathlib import Path
import ast,csv,ctypes,hashlib,json,math,os,re,shutil,subprocess,sys,time,uuid,zipfile
HERE=Path(__file__).resolve().parent;LIVE=HERE.parent/'nwar_automation'
sys.path.insert(0,str(LIVE))
from common import read,write,sha,birth,job,now
from native_resource_resume import saved_header
from native_production import native_health_snapshot
ROOT=Path('E:/NWAR_portable_20261103');OUT=ROOT/'NWAR_GLHF_W04k_Resume_20261109'
BACKUP=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_SIM_FINALS/W04k_transfer_20261109')
ID='6a6e7b081fcb4469'

def functions(source,names):
 tree=ast.parse(source)
 return '\n\n'.join(ast.unparse(n)for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name in names)+'\n'
def put(p,text):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
def build():
 j=job(ID);folder=Path(j['folder']);solve=folder/'native_solve';stage=read(solve/'stage_result.json');plan=read(folder/'native_plan.json')
 if OUT.exists()or OUT.with_suffix('.zip').exists():raise ValueError('Existing transfer is preserved.')
 if (stage.get('ownership')!='windows_job_closed'or stage.get('controller_reason')!='user_stop'or stage.get('source_unchanged')is not True
     or birth(read(solve/'process.json').get('pid'))or any(folder.rglob('macro_error.*'))):raise ValueError('W04k stop or solver closure is not verified.')
 candidates=[]
 for p in solve.glob('input_*.sim'):
  s,t,scenes=saved_header(p)
  if scenes!=30 or abs(t-plan['dt_s']*s)>1e-7:raise ValueError('Native checkpoint header differs from its time grid.')
  candidates.append((s,t,p))
 step,t,source=max(candidates,key=lambda a:a[0]);health=native_health_snapshot(solve/'star.log',plan,step)
 if not plan['wake_start_s']<t<plan['target_s']or not 76<health['water_volume_m3']<78:raise ValueError('Checkpoint or water inventory is outside the healthy continuation window.')
 digest=sha(source);before=source.stat();OUT.mkdir();(OUT/'seed').mkdir();engine=OUT/'engine';engine.mkdir();BACKUP.mkdir(parents=True,exist_ok=True)
 saved=BACKUP/f'W04k_saved_t{t:.4f}.sim';shutil.copy2(source,saved)
 if sha(saved)!=digest:raise ValueError('Backup checkpoint copy failed.')
 shutil.copy2(saved,OUT/'seed/checkpoint.sim')
 if sha(OUT/'seed/checkpoint.sim')!=digest:raise ValueError('Transfer checkpoint copy failed.')
 print('Verified checkpoint and backup: '+format(t,'.4f')+' s',flush=True)
 histories=[];fields=BACKUP/'fields';fields.mkdir(exist_ok=True)
 entries=read(folder/'field_history_segments.json')['segments']
 for i,entry in enumerate(entries):
  old=folder/entry['file'];dest=fields/f'segment_{i:02}.simh';initial=old.stat();digest_h=sha(old)
  if dest.exists():raise ValueError('Existing field backup is preserved.')
  shutil.copy2(old,dest)
  if sha(dest)!=digest_h or (old.stat().st_size,old.stat().st_mtime_ns)!=(initial.st_size,initial.st_mtime_ns):raise ValueError('Field-history copy changed during verification.')
  histories.append(dict(entry,file=str(dest),sha256=digest_h,bytes=initial.st_size,valid_through_s=entry.get('valid_through_s',t)))
  print('Preserved field-history segment '+str(i+1)+'/'+str(len(entries)),flush=True)
 for name in ('wave_setup_audit.json','stopping_policy.json','native_C01_rho_readback.json','wave_density_audit.json','native_plan.json','field_history_segments.json'):
  shutil.copy2(folder/name,OUT/'seed'/name)
 shutil.copy2(solve/'stage_result.json',OUT/'seed/original_stop.json')
 original_log=(solve/'star.log').read_text(encoding='utf8')
 put(OUT/'seed/original_native.log',re.sub(r'(?i)(-podkey\s+)\S+',r'\1[REDACTED]',original_log))
 authority=dict(at=now(),authorized=True,action='transfer_user_stopped_W04k_to_GLHF',job_id=ID,checkpoint_step=step,time_s=t,
                checkpoint_sha256=digest,scene_count=30,numerical_health=health,stage_sha256=sha(solve/'stage_result.json'),
                source_preserved=True,solver_tree_closed=True,automatic_retry_on_solver_error=False,
                original_native_log_sha256=sha(solve/'star.log'),transfer_log_credentials_redacted=True)
 write(OUT/'seed/transfer_review.json',authority);write(BACKUP/'transfer_review.json',authority)
 common='''from pathlib import Path
from datetime import datetime
import csv,hashlib,json,math,os,sqlite3,sys,uuid,ctypes,time,threading
HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('NWAR_TRANSFER_ROOT',HERE.parent)).resolve()
DATA=ROOT/'state'
RUNS=ROOT/'work'
STOPS=[ROOT/'STOP',DATA/'PAUSE',DATA/'STOP']
T0=5.799999999999427
'''
 common+=functions((LIVE/'common.py').read_text(encoding='utf8'),{'now','read','write','sha','number','tail','birth','period'})
 put(engine/'common.py',common)
 put(engine/'resource_limits.py',"def memory_reason(free_memory):\n return 'RAM_below8GiB' if free_memory()<8*2**30 else None\n")
 shutil.copy2(LIVE/'w04b_controller.py',engine/'transfer_controller.py')
 for name in('analysis.py','cycle_policy.py'):shutil.copy2(LIVE/name,engine/name)
 native='import csv,math,re\nfrom pathlib import Path\nCHANNELS='+repr(('Fx_N','Fz_N','Fx_pressure_N','Fx_viscous_N','max_CFL','interface_CFL','max_speed_m_s','alpha_min','alpha_max','p_min_Pa','p_max_Pa','water_volume_m3'))+'\n'
 native+=functions((LIVE/'native_production.py').read_text(encoding='utf8'),{'native_samples','save_csv','prepare_history'})
 native+=functions((LIVE/'native_resource_resume.py').read_text(encoding='utf8'),{'saved_header'})
 put(engine/'transfer_native.py',native)
 runtime='from pathlib import Path\nimport ctypes,os,re,subprocess,json\nfrom common import read\n'
 runtime+=functions((HERE/'templates/portable_runtime.py').read_text(encoding='utf8'),{'processes','free_memory','redact'})
 runtime+='''
def launch_settings():
 root=Path(os.environ['NWAR_PACKAGE_ROOT']);work=Path(os.environ['NWAR_WORKSPACE'])
 config=read(work/'settings.json');exe=Path(config['executable'])
 star=next((p for p in exe.parents if (p/'version_info.properties').is_file()),None)
 if not exe.is_file() or exe.name.lower()!='starccm+.exe' or star is None:raise ValueError('Configured STAR executable is missing.')
 version=re.search(r'^base_version=(\\S+)',(star/'version_info.properties').read_text(encoding='utf8'),re.M)
 if config.get('release')!='2606' or not version or not version[1].startswith('21.04.'):raise ValueError('W04k transfer requires STAR-CCM+ 2606.')
 options=['-np','1','-gpgpu','auto:1','-mpi','intel']
 mode=config.get('license_mode','system')
 if mode=='pod':
  key=os.environ.get('NWAR_POD_KEY','')
  if not key:raise ValueError('A configured Power-on-Demand key is required.')
  options+=['-power','-podkey',key]
 elif mode=='server':
  address=config.get('license_server','').strip()
  if not address or '\\n'in address:raise ValueError('Invalid license server setting.')
  options+=['-licpath',address]
  if config.get('power_session'):options+=['-power']
 elif mode!='system':raise ValueError('Unknown license mode.')
 return dict(executable=str(exe),build=version[1]),options
'''
 put(engine/'transfer_runtime.py',runtime)
 macro=(LIVE/'NwarNativeResume.java').read_text(encoding='utf8')
 old='if(!(wave instanceof FifthOrderVofWave)||'
 macro=macro.replace(old,'if(!(wave instanceof FifthOrderVofWave)||Math.abs(((FifthOrderVofWave)wave).getWaveHeight().getSIValue()-.25)>1e-7||')
 export=(LIVE/'NwarNativeExport.java').read_text(encoding='utf8')
 export_body=export[export.index('      for (Monitor monitor:'):export.index('      Files.writeString(out.resolve("final_time.txt")')]
 export_body=export_body.replace('getActiveSimulation()','s')
 macro=macro.replace('import star.post.*;','import star.post.*;\nimport star.base.report.Monitor;\nimport star.base.report.MonitorData;\nimport star.base.report.PlotableMonitor;')
 marker='   s.saveState(out.resolve("native_ready.sim").toString());'
 if macro.count(marker)!=1:raise ValueError('Zero-step macro export insertion changed.')
 macro=macro.replace(marker,'   Path preparedOut=out;out=out.resolve("seed_monitors");Files.createDirectory(out);\n'+export_body+'\n   Files.writeString(out.resolve("final_time.txt"),Double.toString(time));out=preparedOut;\n'+marker)
 put(engine/'NwarNativeResume.java',macro);shutil.copy2(LIVE/'NwarNativeExport.java',engine)
 classes=OUT/'qa/compiled_2606';classes.mkdir(parents=True)
 compiler=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin/javac.exe')
 cp='E:/Program Files/Siemens/21.04.009-R8/STAR-CCM+21.04.009-R8/star/lib/java/platform/modules/ext/*'
 proc=subprocess.run([str(compiler),'-encoding','UTF-8','-cp',cp,'-d',str(classes),str(engine/'NwarNativeResume.java'),str(engine/'NwarNativeExport.java')],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
 write(OUT/'qa/compile.json',dict(at=now(),build='21.04.009',passed=proc.returncode==0,macro_sha256=sha(engine/'NwarNativeResume.java'),messages=proc.stderr))
 if proc.returncode:raise ValueError('2606 native macros did not compile: '+proc.stderr[-1500:])
 shutil.copy2(HERE/'templates/w04k_transfer.py',OUT)
 put(OUT/'Resume W04k.cmd','''@echo off
setlocal
title NWAR W04k native continuation on GLHF
set "NWAR_ROOT=%~dp0"
:findroot
if exist "%NWAR_ROOT%\\runtime\\python.exe" if exist "%NWAR_ROOT%\\launcher.json" goto foundroot
for %%I in ("%NWAR_ROOT%\\..") do set "NWAR_PARENT=%%~fI"
if /I "%NWAR_PARENT%"=="%NWAR_ROOT%" goto missingroot
set "NWAR_ROOT=%NWAR_PARENT%"
goto findroot
:missingroot
echo HOLD: Extract this patch inside the existing NWAR GLHF main folder.
pause
exit /b 1
:foundroot
set "PYTHONHOME=%NWAR_ROOT%\\runtime"
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
"%NWAR_ROOT%\\runtime\\python.exe" "%~dp0w04k_transfer.py"
set "RC=%ERRORLEVEL%"
echo.
echo W04k launcher exited with code %RC%. The window stays open for diagnostics.
pause
exit /b %RC%
'''.replace('\n','\r\n'))
 put(OUT/'CZYTAJ_NAJPIERW.txt',f'''W04k on GLHF / native STAR-CCM+ 2606 continuation

1. Extract this folder inside the existing NWAR GLHF main folder, beside Start NWAR.cmd.
2. Wait for any existing GLHF simulation to save and exit.
3. Open this patch folder and double-click Resume W04k.cmd.

The patch reuses the existing runtime, STAR selection and license settings.
It opens a separate local W04k progress panel; it does not replace the old dashboard or queue.
The console stays open and prints HOLD diagnostics if it cannot start.

Verified input: W04k, H=0.25 m, wavelength=15 m, time {t:.4f} s.
Native target: {plan['target_s']:.4f} s, followed by verification of five measured cycles.
Cycle 1 is excluded; cycles 2-5 must pass the existing health and repeatability checks.
The saved wave phase, mesh, fields, native health guards and 30 scenes are retained.
The surface magnitude cap stays disabled, as authorized for the campaign.
An independent field-history segment is recorded. Earlier segments remain on the ThinkPad backup;
their checksums and valid intervals are in manifest.json. No archived evidence is deleted.

The patch uses one GPU solver process and one CPU logical processor. It never stops another process.
It does not start a second batch client while the native solver is active.
A solver/numerical error leaves HOLD without a blind restart. Repeated clicks cannot create duplicate runs.
On success, results and the final SIM are in work/W04k. Five cycles recorded is distinct from project acceptance.
No other wave is automatically started. Close the panel/console after the solver exits.
''')
 for p in OUT.rglob('*.py'):compile(p.read_text(encoding='utf8'),str(p),'exec')
 after=source.stat()
 if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)or sha(source)!=digest:raise ValueError('Original checkpoint changed.')
 files={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))for p in OUT.rglob('*')if p.is_file()}
 manifest=dict(schema='nwar-native-W04k-continuation-v1',at=now(),case_id='W04k',H_m=.25,lambda_m=15.,
   time_s=t,checkpoint_step=step,initial_step=j['spec']['native_recovery']['initial_step'],checkpoint_sha256=digest,plan=plan,
   original_job_id=ID,source_release='2602',target_release='2606',C01_sha256='9af4857b948e0494088b5421f8ede100e66344fc2631cc00030406640d7cc295',
   PRE_sha256=j['spec']['mesh_profile']['source_sha'],cycle_policy='five_measured_cycles_discard_first_20261103',
   archived_field_history=histories,files=files,local_GPU_started=False,originals_preserved=True)
 write(OUT/'manifest.json',manifest);write(BACKUP/'manifest.json',manifest)
 archive=OUT.with_suffix('.zip')
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=4)as z:
  for p in sorted(OUT.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(OUT.parent),compress_type=zipfile.ZIP_STORED if p.suffix=='.sim'else zipfile.ZIP_DEFLATED)
 with zipfile.ZipFile(archive)as z:
  for name,item in files.items():
   with z.open(OUT.name+'/'+name)as f:
    if hashlib.file_digest(f,'sha256').hexdigest()!=item['sha256']:raise ValueError('ZIP readback differs: '+name)
 archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='ascii')
 print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,time_s=t,step=step,health=health,backup=str(BACKUP)),ensure_ascii=False),flush=True)

if __name__=='__main__':build()
