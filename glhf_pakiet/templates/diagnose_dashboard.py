"""Read-only portable dashboard/controller report. No app imports or solver calls."""
from pathlib import Path
from urllib.parse import urlparse
import datetime,hashlib,json,sqlite3,urllib.request
BASE=Path(__file__).resolve().parent.parent
def read(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def compact_error(p):
 x=read(p);value=str(x.get('error',''))
 if any(word in value.lower() for word in ['podkey','password','token','license','commandline','command_line']):value='Sensitive error text omitted'
 return dict(at=x.get('at'),error=value[:700]) if x else None
roots=[BASE/'workspaces'];config=read(BASE/'launcher.json')
if config.get('workspace_root'):roots.append(Path(config['workspace_root']))
report=dict(at=datetime.datetime.now().astimezone().isoformat(),read_only=True,workspaces=[])
seen=set()
for root in roots:
 for release in ['2602','2606']:
  work=(root/release).resolve()
  if work in seen or not (work/'app').is_dir():continue
  seen.add(work);data=work/'data';server=read(data/'server.json');owner=read(data/'worker.lock')
  item=dict(workspace=str(work),release=release,server=server,worker=owner,ui_sha256=hashlib.sha256((work/'app/wave_view.js').read_bytes()).hexdigest(),jobs=[])
  db=data/'queue.sqlite'
  if db.exists():
   try:
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
     conn.row_factory=sqlite3.Row
     for row in conn.execute('SELECT id,status,case_id,folder,controller_pid,controller_birth FROM jobs ORDER BY created DESC LIMIT 4'):
      j=dict(row);folder=Path(j['folder'])
      j.update(process=read(folder/'process.json'),monitor=read(folder/'monitor.json'),progress=read(folder/'progress.json'),controller_error=compact_error(folder/'controller_failure.json'),macro_error=compact_error(folder/'macro_error.json'))
      item['jobs'].append(j)
   except Exception as ex:item['database_error']=str(ex)
  url=server.get('url','');u=urlparse(url)
  if u.scheme=='http' and u.hostname in ('127.0.0.1','localhost'):
   try:
    with urllib.request.urlopen(url+'/api/status',timeout=4) as response:status=json.load(response)
    item['live']={k:status.get(k) for k in ['sampled_at','current_run','current_resume','worker_alive','paused','stops']}
    item['live']['jobs']=[{k:j.get(k) for k in ['id','case_id','status','observed_status','controller_pid','controller_birth']}|{'history':{k:j.get('live',{}).get(k) for k in ['time_s','step','age_s','stale','s_per_step']}} for j in status.get('jobs',[])[:4]]
    with urllib.request.urlopen(url+'/wave_view.js?ui=diagnostic',timeout=4) as response:script=response.read()
    item['served_ui2']=b'20261103-ui2' in script
   except Exception as ex:item['service_error']=str(ex)
  report['workspaces'].append(item)
destination=Path(__file__).resolve().parent/'dashboard_diagnostic.json'
destination.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
print('Read-only report saved: '+str(destination))
