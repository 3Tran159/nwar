"""Prepare fresh test workspaces; no solver process is started."""
from pathlib import Path
import importlib.util,json,subprocess,sys,os
BASE=Path('E:/NWAR_portable_20261103/NWAR_Windows_2602_2606')
QA=Path(os.environ.get('NWAR_QA_DIR',str(BASE.parent/'QA')))
QA.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('portable_launcher',BASE/'start_nwar.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
results=[]
for release in ('2602','2606'):
    found=next(x for x in launcher.installations() if x['release']==release)
    config=dict(found,workspace_root=str(QA/'workspaces'),license_mode='system',license_server='',power_session=False)
    app,env=launcher.prepare(config)
    print('Checking portable dependencies and provenance:',release,flush=True)
    run=subprocess.run([str(BASE/'runtime/python.exe'),str(Path(__file__).parent/'test_portable.py')],cwd=app,env=env,capture_output=True,text=True,encoding='utf8',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    (QA/('offline_'+release+'.log')).write_text(run.stdout+'\n'+run.stderr,encoding='utf8')
    if run.returncode:print(run.stdout,run.stderr);sys.exit(run.returncode)
    print('Offline checks passed:',release,flush=True)
    launched=launcher.launch(config,open_browser=False,port=18782 if release=='2602' else 18783)
    results.append(launched)
    (QA/'servers.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    print(json.dumps(launched),flush=True)
