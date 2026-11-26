"""Build a fresh, self-contained portable GLHF package with a verified W05 seed."""
from pathlib import Path
import shutil

import build_package as package


def build():
    original = package.DEST
    root = original.parent
    output = root/'NWAR_GLHF_Clean_2606_v2'
    if output.exists() or output.with_suffix('.zip').exists():
        raise ValueError('The previous clean package is preserved.')
    output.mkdir()
    for name in ('assets', 'runtime', 'lib'):
        shutil.copytree(original/name, output/name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(root/'NWAR_GLHF_Transfer_v4/engine', output/'app',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    runtime = output/'app/portable_runtime.py'
    code = runtime.read_text(encoding='utf8')
    monitor_line = next(line for line in code.splitlines() if "write(folder/'monitor.json'" in line)
    package.put(runtime, package.replace(code, monitor_line,
        "                try:\n    "+monitor_line+"\n"
        "                except OSError as error:\n"
        "                    print('Monitor update deferred: '+redact(str(error)), file=sys.stderr, flush=True)"))
    source = Path('E:/ntnu_mesh_optimization_20261030/nwar_automation_20261102/glhf_imports/GLHF_W05_8c4109896466ec8b3af3')
    if not (source/'dashboard_import.json').is_file():
        raise ValueError('The verified local W05 import is missing.')
    shutil.copytree(source, output/'recovery/W05', ignore=shutil.ignore_patterns('dashboard_import.json'))
    for name in ('Start NWAR.cmd', 'Configure NWAR.cmd', 'Close dashboard.cmd', 'Verify package.cmd',
                 'start_nwar.py', 'asset_provenance.json'):
        shutil.copy2(original/name, output/name)
    for target in (output, output/'app'):
        shutil.copy2(package.TEMPLATES/'glhf_clean_start.py', target)
    shutil.copy2(package.TEMPLATES/'Clean-Old-GLHF-NWAR.ps1', output)
    package.put(output/'Resume W05.cmd', r'''@echo off
setlocal
set "PYTHONHOME=%~dp0runtime"
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"
"%~dp0runtime\python.exe" "%~dp0glhf_clean_start.py"
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
''')
    package.put(output/'CZYTAJ_NAJPIERW.txt', '''NWAR GLHF / clean W05 recovery / STAR-CCM+ 2606

Extract this folder beside the old installation. Use Windows PowerShell.
Preview cleanup:
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\u005cClean-Old-GLHF-NWAR.ps1" -WhatIf
Apply cleanup by running the same command without -WhatIf.
Run outside the old folder. Use -OldRoot if your original path differs.
The cleanup moves the old installation and its internal workspace to a dated backup.
Processes and tasks are matched to the old installation; review any remaining STAR processes.
If an old supervisor was launched separately and is still active, close it before resuming.

Run "Resume W05.cmd". Select STAR-CCM+ 2606 and configure licensing as needed.
The new workspace is inside this package. The saved input is W05 at 14.1056 s,
with three measured cycles already recorded. The target is five measured cycles
on one GPU with one solver process. Cycle 1 is excluded from the analysis.
The dashboard prints its actual local URL. Check that the physical time advances.
If the launcher prints HOLD, retain that message for review.
''')
    package.DEST = output
    package.archive()


if __name__ == '__main__':
    build()
