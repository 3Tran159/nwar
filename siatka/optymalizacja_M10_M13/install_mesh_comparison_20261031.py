"""Integrate measured mesh overlays into the existing read-only dashboard."""
from pathlib import Path
from datetime import datetime
import sys,json,hashlib,shutil,os,uuid,subprocess
D=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard');E=Path(r'E:\ntnu_mesh_optimization_20261030')
P=D/'campaign_hub.py';J=D/'campaign_hub.js';C=D/'campaign_hub.css'
backup=E/('mesh_comparison_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir(exist_ok=False)
original={p:p.read_bytes() for p in (P,J,C)}
for p in original:shutil.copy2(p,backup/p.name)
def once(s,a,b):
 assert s.count(a)==1,'Expected single anchor: '+a[:120]
 return s.replace(a,b,1)
p=original[P].decode('utf-8');j=original[J].decode('utf-8');css=original[C].decode('utf-8')
assert 'mesh_comparison.collect' not in p,'Already installed'
p=once(p,"if not re.search(r'M1[012]|G10_[MF]|W01a'","if not re.search(r'M1[0-5]|G10_[MF]|W01a'")
p=once(p,"for mesh in ('M12','M11','M10'):","for mesh in ('M12','M11','M10','M13','M14','M15'):")
p=once(p,"catalog_only=[{k:v for k,v in r.items() if k not in ('series','drift')} for r in records]","catalog_only=[{k:v for k,v in r.items() if k not in ('series','drift')} for r in records]\n import mesh_comparison\n comparison=mesh_comparison.collect(records)")
p=once(p,"'records':catalog_only,'wave_cases':wave_cases,'geometries':geom,","'records':catalog_only,'wave_cases':wave_cases,'geometries':geom,'comparison':comparison,")
p=once(p,"js=(HERE/'campaign_hub.js').read_text(encoding='utf-8')","js=(HERE/'mesh_comparison.js').read_text(encoding='utf-8')+'\\n'+(HERE/'campaign_hub.js').read_text(encoding='utf-8')")
p=once(p,'<button data-tab="archive">Results archive <span id="archive-count"></span></button>','<button data-tab="compare">Mesh comparison</button><button data-tab="archive">Results archive <span id="archive-count"></span></button>')
p=once(p,'<section id="view-archive" hidden>','<section id="view-compare" hidden><div id="mesh-comparison"></div></section><section id="view-archive" hidden>')
p=once(p,"atomic(CATALOG/'results.csv',output.getvalue())","atomic(CATALOG/'results.csv',output.getvalue())\n atomic(CATALOG/'mesh_comparison.json',json.dumps(data.get('comparison',{}),ensure_ascii=False,allow_nan=False,indent=2))")
j=once(j,"$('view-archive').hidden=t!=='archive';try", "$('view-archive').hidden=t!=='archive';$('view-compare').hidden=t!=='compare';try")
j=once(j,"if(t==='archive')renderArchive();else renderLive(true)","if(t==='archive')renderArchive();else if(t==='compare')renderMeshComparison(true);else renderLive(true)")
j=once(j,"renderLive();if(tab==='archive')renderArchive();tick()","renderLive();if(tab==='archive')renderArchive();if(tab==='compare')renderMeshComparison();tick()")
j=once(j,"tab=localStorage.getItem('ntnu-hub-tab')==='archive'?'archive':'live'","tab=['archive','compare'].includes(localStorage.getItem('ntnu-hub-tab'))?localStorage.getItem('ntnu-hub-tab'):'live'")
j=once(j,"resizeTimer=setTimeout(()=>renderLive(true),160)","resizeTimer=setTimeout(()=>{renderLive(true);if(tab==='compare')renderMeshComparison(true)},160)")
css+='\n.comparison-controls{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin:18px 0}.comparison-controls label{display:flex;flex-direction:column;gap:6px;font-size:12px;color:#59767b}.comparison-controls select{padding:10px;border:1px solid #c5d8cf;border-radius:8px;background:white;max-width:100%}.comparison-legend{display:flex;flex-wrap:wrap;gap:8px;margin:15px 0}.comparison-legend button{padding:8px 11px;text-align:left;border:1px solid #d6e4dc;border-radius:8px;background:white;font-size:12px}.comparison-legend i{display:inline-block;width:10px;height:10px;margin-right:6px;border-radius:50%}.comparison-legend small{display:block;color:#647d80;font-size:10px;margin-top:3px}.comparison-legend button[aria-pressed=false]{opacity:.4}.empty-chart{padding:40px 15px;color:#637c81;background:#f5f8f6}#comparison-means-table{min-width:1000px}#view-compare .chart svg{display:block;width:100%;height:auto}#view-compare .chart{min-width:0}@media(max-width:700px){.comparison-controls{display:block}.comparison-controls button{margin-top:10px}.comparison-controls select{width:100%}.comparison-legend button{font-size:11px}.comparison-legend{gap:6px}}\n'
compile(p,str(P),'exec');sys.path.insert(0,str(D));import campaign_hub as h,mesh_comparison as comp
s=h.collect();comparison=comp.collect(s['records'])
current=[r for r in comparison['runs'] if r['group']=='current']
assert {r['mesh'] for r in current}>={'M10','M11','M12'}
assert all(r['accepted'] and r['settled'] for r in current if r['mesh'] in ('M10','M11','M12'))
assert all(len(r['series'])>50 for r in current)
node=r'F:\Program Files\nodejs\node.exe'
combo=backup/'combined.cjs';combo.write_text((D/'mesh_comparison.js').read_text(encoding='utf-8')+'\n'+j,encoding='utf-8')
check=subprocess.run([node,'--check',str(combo)],capture_output=True,text=True,timeout=20)
assert check.returncode==0,check.stderr
for path,text in ((P,p),(J,j),(C,css)):
 assert path.read_bytes()==original[path],'Concurrent edit: stop'
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(text,encoding='utf-8');os.replace(tmp,path)
info={'at':datetime.now().astimezone().isoformat(),'backup':str(backup),'means':[{k:r.get(k) for k in ('mesh','cells','dt_s','settled','delta_CL_pct','delta_CD_pct')} for r in current], 'sources_untouched':True,'solver_untouched':True}
(backup/'installation.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'installed':True,'current_meshes':[r['mesh'] for r in current],'groups':len(comparison['groups']),'overlay_traces':len(comparison['runs']),'backup':str(backup)},ensure_ascii=False))
