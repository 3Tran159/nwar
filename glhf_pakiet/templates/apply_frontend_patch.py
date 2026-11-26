"""Hot-update static UI only. Does not import the application or inspect/control jobs."""
from pathlib import Path,PurePosixPath
import argparse,datetime,hashlib,json,os,shutil,time,uuid

STATIC=frozenset(('index.html','style.css','app.js','wave_view.js','history_chart.js','convergence_chart.js'))
PATCH=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(root,name):
 p=PurePosixPath(name)
 if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:raise ValueError('Unsafe path')
 dest=root.joinpath(*p.parts)
 if not dest.resolve().is_relative_to(root.resolve()):raise ValueError('Path leaves target folder')
 return dest
def replace(temp,target):
 for attempt in range(10):
  try:os.replace(temp,target);return
  except PermissionError:
   if attempt==9:raise
   time.sleep(.05*(attempt+1))
def apply(base,patch=PATCH,extra_roots=(),dry_run=False):
 base=Path(base).resolve();patch=Path(patch).resolve();spec=read(patch/'frontend_manifest.json')
 if not (base/'runtime/python.exe').is_file():raise ValueError('Extract the patch beside app, assets and runtime.')
 roots=[base/'workspaces',*map(Path,extra_roots)]
 if (base/'launcher.json').is_file():
  configured=read(base/'launcher.json').get('workspace_root')
  if configured:roots.append(Path(configured))
 apps=[base/'app']
 for root in roots:
  for release in ('2602','2606'):
   work=Path(root)/release
   if (work/'app').is_dir():
    if read(work/'settings.json').get('release')!=release:raise ValueError('Cannot verify workspace release: '+str(work))
    if (work/'app').resolve() not in [p.resolve() for p in apps]:apps.append(work/'app')
 manifest_path=base/'package_manifest.json';manifest=read(manifest_path)
 if manifest.get('package')!='NWAR Windows 2602/2606':raise ValueError('Unsupported portable package')
 pending=[]
 for entry in spec['files']:
  name=entry['name']
  if name not in STATIC:raise ValueError('Only the six static UI files are permitted')
  payload=safe(patch/'payload',name)
  if digest(payload)!=entry['sha256']:raise ValueError('Payload checksum failed: '+name)
  for app in apps:
   target=safe(app,name)
   if target.is_symlink():raise ValueError('Linked UI files are not supported')
   current=digest(target) if target.exists() else None
   if current==entry['sha256']:continue
   if current not in entry['allowed_before_sha256']:raise ValueError('Unknown local UI revision; preserved: '+str(target))
   pending.append((target,payload,current))
 result=dict(frontend_only=True,files_to_update=len(pending),apps=list(map(str,apps)),dry_run=dry_run,processes_started=0,processes_stopped=0,backend_changed=False)
 if dry_run or not pending:return dict(result,already_applied=not pending)
 stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
 backup=base/'.nwar_frontend_backups'/stamp;backup.mkdir(parents=True)
 snapshots={};written=[]
 try:
  for index,(target,payload,expected) in enumerate(pending):
   copy=backup/(str(index)+'_'+target.name);shutil.copy2(target,copy)
   if digest(copy)!=expected:raise ValueError('UI changed during backup')
   snapshots[target]=copy
  shutil.copy2(manifest_path,backup/'package_manifest.json')
  for target,payload,expected in pending:
   if digest(target)!=expected:raise ValueError('UI changed during installation')
   temp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
   try:shutil.copy2(payload,temp);replace(temp,target);written.append(target)
   finally:temp.unlink(missing_ok=True)
  # Inventory bookkeeping only; no application settings or result files are edited.
  records={x['path']:x for x in manifest['files']}
  for name in STATIC:
   target=base/'app'/name;key='app/'+name
   records[key]=dict(path=key,sha256=digest(target),bytes=target.stat().st_size)
  manifest['files']=list(records.values());manifest['total_bytes']=sum(x['bytes'] for x in manifest['files'])
  temp=manifest_path.with_name('package_manifest.json.'+uuid.uuid4().hex+'.tmp')
  try:temp.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8');replace(temp,manifest_path)
  finally:temp.unlink(missing_ok=True)
  for target,payload,expected in pending:
   if digest(target)!=digest(payload):raise ValueError('Installed UI checksum failed')
 except Exception:
  for target in reversed(written):
   temp=target.with_name(target.name+'.rollback.'+uuid.uuid4().hex+'.tmp')
   shutil.copy2(snapshots[target],temp);replace(temp,target)
  if (backup/'package_manifest.json').exists():shutil.copy2(backup/'package_manifest.json',manifest_path)
  raise
 result.update(passed=True,backup=str(backup))
 (backup/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,default=PATCH.parent);p.add_argument('--workspace-root',type=Path,action='append',default=[]);p.add_argument('--check',action='store_true');a=p.parse_args()
 try:print(json.dumps(apply(a.package,extra_roots=a.workspace_root,dry_run=a.check),indent=2));print('UI ready. Refresh the browser with Ctrl+F5. Solver and service remain running.')
 except Exception as ex:print('UI patch not applied: '+str(ex));raise SystemExit(1)
