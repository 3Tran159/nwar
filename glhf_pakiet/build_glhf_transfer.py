"""Build a small standalone GLHF transfer and continuation patch from portable v3."""
import json
from pathlib import Path
import shutil
import zipfile

from build_package import digest, replace, put, TEMPLATES, LIVE, DEST

ROOT = DEST.parent
NAME = 'NWAR_GLHF_Transfer_v4'
V3 = ROOT/'QA_v3/candidate/app'


def build(output):
    if output.exists():
        raise ValueError('Existing patch is preserved')
    app = output/'engine'
    shutil.copytree(V3, app, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(TEMPLATES/'glhf_transfer.py',app/'glhf_transfer.py')
    shutil.copy2(LIVE/'glhf_bundle.py',app/'glhf_bundle.py')
    path = app/'common.py'
    code = path.read_text(encoding='utf8')
    code = replace(code,'recovery_receipt=None,mpi_processes=None):','recovery_receipt=None,mpi_processes=None,glhf_recovery=None):')
    code = replace(code," if mode!='fresh':\n  if parent_id:",
        """ if glhf_recovery:
  from glhf_transfer import verify_resume
  recovered=verify_resume(glhf_recovery)
  if mode!='resume' or parent_id or smoke or recovered['case_id']!=case_id:
   raise ValueError('Invalid GLHF continuation request.')
  spec.update(source=recovered['checkpoint'],source_sha=recovered['checkpoint_sha256'],
              source_time=recovered['time_s'],parent_segments=recovered['segments'],
              glhf_recovery=str(glhf_recovery),stop_kind='five_cycles',extra_steps=0)
 elif mode!='fresh':
  if parent_id:""")
    put(path, code)
    path = app/'worker.py'
    code = path.read_text(encoding='utf8')
    code = replace(code," if spec.get('checkpoint_recovery'):",""" if spec.get('glhf_recovery'):
  from glhf_transfer import verify_resume
  recovered=verify_resume(spec['glhf_recovery'])
  if (recovered['case_id']!=j['case_id'] or recovered['segments']!=spec['parent_segments']
      or recovered['checkpoint']!=spec['source'] or recovered['checkpoint_sha256']!=spec['source_sha']
      or recovered['time_s']!=spec['source_time'] or spec['stop_kind']!='five_cycles'
      or spec['target_complete_cycles']!=5 or spec.get('extra_steps')):
   raise ValueError('GLHF continuation differs from the verified receipt.')
 if spec.get('checkpoint_recovery'):""")
    code = replace(code,'def main():','def main(only=None):')
    code = replace(code,"   pending.sort(key=lambda j:j['spec'].get('mode')!='resume')",
                   """   if only:
    pending=[j for j in pending if j['id']==only]
   pending.sort(key=lambda j:j['spec'].get('mode')!='resume')""")
    code = replace(code,"p.add_argument('--parent');a=p.parse_args()","p.add_argument('--parent');p.add_argument('--only');a=p.parse_args()")
    code = replace(code,'\n main()','\n main(a.only)')
    put(path, code)
    path = app/'validation.py'
    code = path.read_text(encoding='utf8')
    code = replace(code,"   ok=bool(origin.get('path')", """   glhf=None
   if (part/'glhf_resume.json').exists():
    from glhf_transfer import verify_resume
    glhf=verify_resume(part/'glhf_resume.json')
   ok=bool(origin.get('path')""")
    code = replace(code,"and read(part/'stage_result.json').get('source_unchanged') is True)",
                   "and (read(part/'stage_result.json').get('source_unchanged') is True or (glhf and origin==glhf['original_source'])))")
    code = replace(code,"   else:previous=part/('wave_pilot_extended_final.sim'",
        """   elif glhf:
    previous=Path(glhf['checkpoint'])
    links[-1]['verified_glhf_checkpoint']=dict(path=str(previous),time_s=glhf['time_s'],raw_history_preserved=True)
   else:previous=part/('wave_pilot_extended_final.sim'""")
    put(path,code)
    prefix=r'''@echo off
setlocal
if not exist "%~dp0..\runtime\python.exe" (
 echo Extract the patch folder inside the GLHF NWAR package, beside runtime and assets.
 pause
 exit /b 1
)
set "PYTHONHOME=%~dp0..\runtime"
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
'''
    for action, name in [('export','Export W05.cmd'),('finish','Export and finish W05.cmd')]:
        put(output/name,prefix+f'"%~dp0..\\runtime\\python.exe" "%~dp0engine\\glhf_transfer.py" {action} %*\nset "RC=%ERRORLEVEL%"\npause\nexit /b %RC%\n')
    put(output/'README.txt', """NWAR GLHF transfer v4 — Windows, STAR-CCM+ 2602 and 2606

1. Extract NWAR_GLHF_Transfer_v4 into the existing GLHF NWAR package,
   next to app, assets, runtime, and Start NWAR.cmd.
2. If GLHF has a separate supervisor, stop or disable its scheduling through
   its own controls after any active solver has saved and exited. Leave the
   dashboard open if desired. Wait for the queue to be idle.
3. Run "Export and finish W05.cmd". It copies the latest saved SIM and the
   complete available force/probe history of the selected chain to
   GLHF_exports/GLHF_W05_<run-id>. Then it verifies and queues a continuation
   with the v3 five-cycle solver. The first cycle is excluded from analysis.
   If there are five cycles at the saved endpoint, review the exported result.
4. After completion, run "Export W05.cmd" again. Copy the entire new export
   folder, including manifest.json and checkpoint/latest.sim, to ThinkPad.

For export only, run "Export W05.cmd". Optional CLI arguments:
  --case W07
  --workspace "D:\\path\\to\\workspaces\\2606"
  --output "D:\\path\\to\\exports"

The last plotted time and last saved SIM time may differ. The original CSVs
stay intact. The continuation uses the exact force-history row at the saved
checkpoint. The export reports both times. A missing or unverifiable save,
solver error, manual pause/STOP or occupied solver slot blocks the launch.
If HOLD is shown, send the console message for diagnosis. Do not clear STOP
or delete locks to get past a refusal.

The patch runs its own verified portable v3 application files. It preserves
GLHF's installed app, UI, assets and license settings and uses the existing
workspace queue. The worker is limited to the requested job. In POD mode
enter the key at the hidden prompt. It is not included in the transfer.
""")
    for p in app.glob('*.py'):
        compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')
    manifest = {p.relative_to(output).as_posix():digest(p) for p in output.rglob('*') if p.is_file()}
    put(output/'patch_sha256.json',manifest)
    return output


if __name__=='__main__':
    output=build(ROOT/NAME)
    archive=ROOT/(NAME+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in output.rglob('*'):
            if p.is_file():
                z.write(p,NAME+'/'+p.relative_to(output).as_posix())
    put(archive.with_suffix('.zip.sha256'),digest(archive)+'  '+archive.name+'\n')
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,sha256=digest(archive))))
