from pathlib import Path
import importlib.util,zipfile,json,shutil
ROOT=Path('E:/NWAR_portable_20261103');BASE=ROOT/'NWAR_Windows_2602_2606';QA=ROOT/'QA_frontend';HOT=QA/'live_package'
spec=importlib.util.spec_from_file_location('launcher_hot',BASE/'start_nwar.py');launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
HOT.mkdir(exist_ok=True);(HOT/'runtime').mkdir(exist_ok=True);(HOT/'runtime/python.exe').write_bytes(b'QA placeholder; actual shared runtime used by servers')
with zipfile.ZipFile(ROOT/'NWAR_Windows_2602_2606.zip') as z:
 (HOT/'package_manifest.json').write_bytes(z.read('NWAR_Windows_2602_2606/package_manifest.json'))
 for release in ['2602','2606']:
  app=QA/'live_workspaces'/release/'app'
  if app.exists():raise ValueError('Existing QA workspace preserved')
  app.mkdir(parents=True)
  for name in z.namelist():
   prefix='NWAR_Windows_2602_2606/app/'
   if name.startswith(prefix) and not name.endswith('/'):
    target=app/name[len(prefix):];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
 shutil.copytree(QA/'live_workspaces/2602/app',HOT/'app')
(HOT/'launcher.json').write_text(json.dumps(dict(workspace_root=str(QA/'live_workspaces'))),encoding='utf8')
servers=[]
for release,port in [('2602',20782),('2606',20783)]:
 installation=next(i for i in launcher.installations() if i['release']==release)
 config=dict(installation,workspace_root=str(QA/'live_workspaces'),license_mode='system',license_server='',power_session=False)
 servers.append(launcher.launch(config,open_browser=False,port=port))
(QA/'hot_servers.json').write_text(json.dumps(servers,indent=2),encoding='utf8')
print(json.dumps(servers))
