from pathlib import Path
from datetime import datetime
import sys,json,hashlib,shutil,subprocess,os,uuid
D=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard')
ROOT=Path(r'E:\ntnu_mesh_optimization_20261030')
P=D/'campaign_hub.py'
original=P.read_bytes();s=original.decode('utf-8')
assert 'campaign_compare.enrich' not in s,'Already installed'
backup=ROOT/'dashboard_compare_backup'/datetime.now().strftime('%Y%m%d_%H%M%S');backup.mkdir(parents=True,exist_ok=False)
shutil.copy2(P,backup/P.name)
for a in ('campaign_hub.js','campaign_hub.css'):shutil.copy2(D/a,backup/a)
def once(old,new):
 global s
 assert s.count(old)==1,old
 s=s.replace(old,new,1)
once('data=collect();payload=publish(data)','data=collect()\n import importlib,campaign_compare\n importlib.reload(campaign_compare)\n campaign_compare.enrich(data)\n payload=publish(data)')
once("css=(HERE/'campaign_hub.css').read_text(encoding='utf-8');js=(HERE/'campaign_hub.js').read_text(encoding='utf-8')","css=(HERE/'campaign_hub.css').read_text(encoding='utf-8')+'\\n'+(HERE/'campaign_compare.css').read_text(encoding='utf-8');js=(HERE/'campaign_hub.js').read_text(encoding='utf-8')+'\\n'+(HERE/'campaign_compare.js').read_text(encoding='utf-8')")
once("r'M1[012]|G10_[MF]|W01a'","r'M1[0-5]|G10_[MF]|W01a'")
once("for mesh in ('M12','M11','M10'):","for mesh in ('M12','M11','M10','M13','M14','M15'):")
compile(s,str(P),'exec')
sys.path.insert(0,str(D));import campaign_hub,campaign_compare
payload=campaign_hub.collect();campaign_compare.enrich(payload)
json.dumps(payload,allow_nan=False)
assert payload['simulation_preview'] and payload['simulation_preview']['url'].startswith('/simulation_assets/')
assert len(payload['comparison']['rows'])>=10
assert {'M10','M11','M12'}<={r['mesh'] for r in payload['comparison']['rows']}
assert any(g['views'].get('streamlines') for g in payload['gallery'])
assert payload['next_candidate']['mesh']=='M13'
node=r'F:\Program Files\nodejs\node.exe'
check=subprocess.run([node,'--check',str(D/'campaign_compare.js')],capture_output=True,text=True,timeout=15)
if check.returncode:raise RuntimeError(check.stderr)
assert P.read_bytes()==original,'Concurrent edit to dashboard'
tmp=P.with_name(P.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(s,encoding='utf8');os.replace(tmp,P)
report={'at':datetime.now().astimezone().isoformat(),'backup':str(backup),'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'comparisons':[{k:r.get(k) for k in ('mesh','accepted','mean_CL','mean_CD')} for r in payload['comparison']['rows']],'preview':{k:payload['simulation_preview'].get(k) for k in ('mesh','time_s','active','url')},'gallery':{g['mesh']:list(g['views']) for g in payload['gallery']},'candidate':payload['next_candidate'],'solver_modified':False}
(ROOT/'dashboard_compare_installation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False))
