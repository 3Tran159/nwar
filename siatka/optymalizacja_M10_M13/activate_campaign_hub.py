"""Activate the tested current-campaign view. No solver or queue changes."""
from pathlib import Path
from datetime import datetime
import sys,json,hashlib,shutil,os,uuid,importlib.util,subprocess
D=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard');E=Path(r'E:\ntnu_mesh_optimization_20261030')
H=D/'campaign_hub.py';s=H.read_text(encoding='utf-8')
a="css=(HERE/'campaign_hub.css').read_text(encoding='utf-8');js=(HERE/'campaign_hub.js').read_text(encoding='utf-8')"
b=a+"\n # Preserve the existing generation-checked queue controls unchanged and folded away.\n import importlib.util\n spec=importlib.util.spec_from_file_location('hub_existing_queue_panel',F/'mesh_study_control_panel.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)\n controls=module.panel()"
assert s.count(a)==1;s=s.replace(a,b,1)
a=" return body\n\nif __name__=='__main__':"
b=" body=body.replace('<div id=\"campaign-notes\"></div>','<div id=\"campaign-notes\"></div><details class=\"details\" id=\"queue-controls\"><summary>Calculation controls · pause / save / resume the existing queue</summary>'+controls+'</details>',1)\n return body\n\nif __name__=='__main__':"
assert s.count(a)==1;s=s.replace(a,b,1)
# Preserve previously indexed history if a source later becomes temporarily unavailable.
a="dedup={r['id']:r for r in records};records=list(dedup.values());records.sort(key=lambda r:r.get('updated_at') or '',reverse=True)"
b="dedup={r['id']:r for r in records}\n for old in read(CATALOG/'results.json').get('records',[]):\n  if old.get('id') not in dedup:\n   old=dict(old,active=False,source_unavailable=True,status='source_unavailable',notes='Retained catalog record; original source not present in this scan. Last known values only.');dedup[old['id']]=old\n records=list(dedup.values());records.sort(key=lambda r:r.get('updated_at') or '',reverse=True)"
assert s.count(a)==1;s=s.replace(a,b,1)
compile(s,str(H),'exec');H.write_bytes(s.encode('utf-8'))
sys.path.insert(0,str(D));import campaign_hub as hub
qa=json.loads((E/'campaign_hub_qa'/'qa_report.json').read_text(encoding='utf-8'));assert qa['passed'] and not qa['errors'] and not qa['writes']
bridge=D/'local_mesh_dashboard.py';before=bridge.read_bytes();oldsha=hashlib.sha256(before).hexdigest()
assert oldsha=='1f210c93be69bf2b0f8c12fb97d2968f89f622456b6082cec2b8071b50560ab7','Bridge changed concurrently'
t=before.decode('utf-8')
anchor='    return preserve_reload_position(page)'
assert t.count(anchor)==1
patch='''    # Campaign Hub replaces only the presentation; original controls and simulations stay intact.
    previous_path=list(sys.path)
    try:
        sys.path.insert(0,str(HERE))
        import campaign_hub
        importlib.reload(campaign_hub)
        return campaign_hub.render_page(preserve_reload_position(page))
    finally:
        sys.path[:]=previous_path'''
t=t.replace(anchor,patch,1);compile(t,str(bridge),'exec')
# Build a candidate before changing the long-lived server's next render.
preview=hub.render_page((hub.PUBLIC/'dashboard.html').read_text(encoding='utf-8'))
assert 'window.CAMPAIGN_INITIAL=' in preview and 'data-mesh-action="pause"' in preview
backup=E/'campaign_hub_backup'/datetime.now().strftime('%Y%m%d_%H%M%S');backup.mkdir(parents=True)
shutil.copy2(bridge,backup/bridge.name)
for name in ('campaign_hub.py','campaign_hub.js','campaign_hub.css'):shutil.copy2(D/name,backup/name)
assert bridge.read_bytes()==before
f=bridge.with_name(bridge.name+'.'+uuid.uuid4().hex+'.tmp');f.write_bytes(t.encode('utf-8'));os.replace(f,bridge)
manifest={'activated_at':datetime.now().astimezone().isoformat(),'backup':str(backup),'before_sha256':oldsha,'installed_sha256':hashlib.sha256(bridge.read_bytes()).hexdigest(),'catalog':str(hub.CATALOG),'solver_files_changed':False,'queue_controls_preserved':True,'legacy_view':'/archive_runs/legacy_dashboard.html'}
(E/'campaign_hub_installation.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
# Publish exactly the tested generated page atomically, then server refresh retains it through the bridge hook.
hub.atomic(hub.PUBLIC/'dashboard.html',preview)
hub.atomic(hub.F.parent/'dashboard.html',preview)
print(json.dumps(manifest))
