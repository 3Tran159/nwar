from pathlib import Path
from datetime import datetime
import sys,json,hashlib,shutil,subprocess,os,uuid
D=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard')
R=Path(r'E:\ntnu_mesh_optimization_20261030');P=D/'campaign_hub.py'
original=P.read_bytes();source=original.decode('utf-8')
assert 'campaign_visuals.enrich' not in source,'Already installed'
# Reuse the new read-only media functions, but do not override concurrently installed comparisons.
js=(D/'campaign_compare.js').read_text(encoding='utf-8')
start=js.index('function previewCard()');end=js.index('function comparisonRows()')
media=js[start:end]
start2=js.index('function imageViewer(');end2=js.index('const baseSetTab=setTab;')
media+='\nlet galleryMesh="M10",galleryView="mesh";\n'+js[start2:end2]
media+='''
const visualsBaseTab=setTab;
setTab=function(t){
 if(t==='gallery'){
  tab=t;for(const name of ['live','archive','compare'])$('view-'+name).hidden=true;
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('selected',b.dataset.tab===t));
  $('view-gallery').hidden=false;renderGallery();
 }else{visualsBaseTab(t);$('view-gallery').hidden=true}
};
const visualsBaseLive=renderLive;
renderLive=function(force=false){visualsBaseLive(force);if(tab==='gallery')renderGallery()};
const visualsBaseShow=showRecord;
showRecord=function(id,scroll=true){
 visualsBaseShow(id,scroll);const r=data.records.find(r=>r.id===id),host=$('record-detail').querySelector('article');
 if(r&&host&&data.gallery?.some(g=>g.mesh===r.mesh)&&!host.querySelector('.record-views'))host.insertAdjacentHTML('beforeend','<div class="record-views"><h3>Configuration visualizations</h3><p class="note">Images have their own source and physical timestamp; they are not automatically the result of this attempt.</p><button data-gallery-mesh="'+esc(r.mesh)+'">Mesh / streamlines / saved fields</button></div>');
};
(function(){
 const nav=document.querySelector('main>nav'),button=document.createElement('button');button.dataset.tab='gallery';button.textContent='Mesh & flow views';
 nav.insertBefore(button,nav.querySelector('[data-tab="archive"]'));
 const section=document.createElement('section');section.id='view-gallery';section.hidden=true;$('view-archive').before(section);
 document.addEventListener('click',e=>{const g=e.target.closest('[data-gallery-mesh]');if(g){galleryMesh=g.dataset.galleryMesh;const selected=data.gallery?.find(x=>x.mesh===galleryMesh);galleryView=selected?.views.velocity?'velocity':'mesh';setTab('gallery')}});
 renderPulse();
})();
'''
asset=D/'campaign_visuals.js';asset.write_text(media,encoding='utf8')
node=r'F:\Program Files\nodejs\node.exe';check=subprocess.run([node,'--check',str(asset)],capture_output=True,text=True,timeout=15)
assert check.returncode==0,check.stderr
before='data=collect();payload=publish(data)'
after='data=collect()\n import importlib,campaign_visuals\n importlib.reload(campaign_visuals)\n campaign_visuals.enrich(data)\n payload=publish(data)'
assert source.count(before)==1;source=source.replace(before,after,1)
anchor="css=(HERE/'campaign_hub.css').read_text(encoding='utf-8');js=(HERE/'mesh_comparison.js').read_text(encoding='utf-8')+'\\n'+(HERE/'campaign_hub.js').read_text(encoding='utf-8')"
assert source.count(anchor)==1,'Concurrent builder layout changed; do not replace'
replacement=anchor+"\n css+='\\n'+(HERE/'campaign_compare.css').read_text(encoding='utf-8')\n js+='\\n'+(HERE/'campaign_visuals.js').read_text(encoding='utf-8')"
source=source.replace(anchor,replacement,1)
compile(source,str(P),'exec')
sys.path.insert(0,str(D));import campaign_hub,campaign_visuals
payload=campaign_hub.collect();campaign_visuals.enrich(payload);json.dumps(payload,allow_nan=False)
assert payload['simulation_preview'] and payload['comparison'].get('runs')
assert len(payload['comparison']['runs'])>=10
assert any(g['views'].get('streamlines') for g in payload['gallery'])
backup=R/'dashboard_visuals_backup'/datetime.now().strftime('%Y%m%d_%H%M%S');backup.mkdir(parents=True,exist_ok=False);shutil.copy2(P,backup/P.name)
assert P.read_bytes()==original,'Concurrent edit detected'
tmp=P.with_name(P.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(source,encoding='utf8');os.replace(tmp,P)
result={'installed_at':datetime.now().astimezone().isoformat(),'backup':str(backup),'hub_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'preview':{k:payload['simulation_preview'].get(k) for k in ('mesh','time_s','active','url')},'comparison_runs_preserved':len(payload['comparison']['runs']),'gallery':{g['mesh']:list(g['views']) for g in payload['gallery']},'no_solver_changes':True}
(R/'dashboard_visuals_installation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
