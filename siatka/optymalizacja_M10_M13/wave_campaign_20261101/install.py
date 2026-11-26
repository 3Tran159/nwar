"""Add a sourced C01/Wxx campaign tab; preserve existing dashboards and running CFD."""
from pathlib import Path
from datetime import datetime
import json,hashlib,subprocess,importlib.util,sys,os,uuid
A=Path(__file__).parent;H=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard\campaign_hub.py')
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
original=H.read_bytes();src=original.decode('utf-8');assert "data['wave_campaign']=" not in src,'Already installed, inspect current state'
nl='\r\n' if '\r\n' in src else '\n'
for f in ['campaign.py','campaign.js','campaign.css','campaign.json']:assert (A/f).exists()
compile((A/'campaign.py').read_text(encoding='utf-8'),str(A/'campaign.py'),'exec')
q=subprocess.run([r'F:\Program Files\nodejs\node.exe','--check',str(A/'campaign.js')],capture_output=True,text=True,timeout=25);assert q.returncode==0,q.stderr
foil=load('foil_campaign_install',A.parent/'foil_live_dashboard_20261031'/'foil_live.py').collect()
data=load('wave_campaign_install',A/'campaign.py').enrich({'foil_live':foil})
assert [x['id'] for x in data['cases']]==['C01','W01','W02','W03','W04','W05','W06','W07']
assert data['cases'][0]['status']=='reference' and data['cases'][1]['status']=='saved'
assert data['cases'][1]['cycles']>=4 and len(data['cases'][1]['phase_points'])==121
assert data['cases'][2]['mean_CD'] is None and data['cases'][6]['mean_CD'] is None
assert len(data['controls'])==3 and data['cases'][7]['status']=='domain_review'
json.dumps(data,allow_nan=False)
a=" data['foil_live']=foil_module.collect()"
b=a+nl+" wave_campaign_ui=Path(r'E:\\ntnu_mesh_optimization_20261030\\wave_campaign_20261101')"+nl+" campaign_spec=importlib.util.spec_from_file_location('m13_wave_campaign_current',wave_campaign_ui/'campaign.py')"+nl+" campaign_module=importlib.util.module_from_spec(campaign_spec);campaign_spec.loader.exec_module(campaign_module)"+nl+" data['wave_campaign']=campaign_module.enrich(data)"
assert src.count(a)==1;src=src.replace(a,b,1)
a=" js+='\\n'+(foil_ui/'foil_live.js').read_text(encoding='utf-8')"
b=a+nl+" css+='\\n'+(wave_campaign_ui/'campaign.css').read_text(encoding='utf-8')"+nl+" js+='\\n'+(wave_campaign_ui/'campaign.js').read_text(encoding='utf-8')"
assert src.count(a)==1;src=src.replace(a,b,1);compile(src,str(H),'exec')
backup=A/'backup';backup.mkdir(exist_ok=True);bp=backup/('campaign_hub_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.py');bp.write_bytes(original)
assert H.read_bytes()==original,'Concurrent hub edit; refuse overwrite'
tmp=H.with_name(H.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(src.encode('utf-8'));os.replace(tmp,H)
result={'at':datetime.now().astimezone().isoformat(),'installed':True,'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':hashlib.sha256(H.read_bytes()).hexdigest(),'backup':str(bp),'source_simulations_changed':False,'solver_macros_changed':False,'old_comparison_and_gallery_preserved':True,'alias_C01':'accepted M13 calm','alias_W01':'M13 H0.5 lambda20 lineage R2/R3V/R4V','active_ids':data['active_ids'],'next_wave':'W02'}
(A/'installation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
