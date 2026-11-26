"""Isolated portable offline checks and browser launch; never invokes STAR."""
from pathlib import Path
import importlib.util,json,os,shutil,subprocess,sys
ROOT=Path('E:/NWAR_portable_20261103');BASE=ROOT/'NWAR_Windows_2602_2606';QA=ROOT/'QA_v3'
spec=importlib.util.spec_from_file_location('portable_launcher_v3',BASE/'start_nwar.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
checks={};servers=[]
for release,port in [('2602',19782),('2606',19783)]:
    work=QA/'workspaces'/release;app=work/'app'
    if app.exists():raise ValueError('Existing QA workspace preserved')
    shutil.copytree(QA/'candidate/app',app)
    installation=next(i for i in launcher.installations() if i['release']==release)
    config=dict(installation,workspace_root=str(QA/'workspaces'),license_mode='system',license_server='',power_session=False)
    app,env=launcher.prepare(config)
    result=subprocess.run([str(BASE/'runtime/python.exe'),str(Path(__file__).with_name('test_portable.py'))],cwd=app,env=env,capture_output=True,text=True,encoding='utf8',creationflags=subprocess.CREATE_NO_WINDOW)
    (QA/('offline_'+release+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    if result.returncode:print(result.stdout,result.stderr);raise SystemExit(result.returncode)
    checks[release]=json.loads((work/'offline_checks.json').read_text(encoding='utf8'))
    launched=launcher.launch(config,open_browser=False,port=port);servers.append(launched)
    print(json.dumps(dict(release=release,offline_passed=True,server=launched)))
(QA/'servers.json').write_text(json.dumps(servers,indent=2),encoding='utf8')
(QA/'verification.json').write_text(json.dumps(dict(offline=checks,solver_started=False),indent=2),encoding='utf8')
