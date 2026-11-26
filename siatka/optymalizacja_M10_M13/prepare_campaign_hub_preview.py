from pathlib import Path
import sys,json,hashlib,subprocess,os
D=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard')
p=D/'campaign_hub.py';s=p.read_text(encoding='utf-8')
def one(a,b):
 global s
 assert s.count(a)==1,a[:100]
 s=s.replace(a,b,1)
one("mesh=re.search(r'M\\d\\d',p.name)","mesh=re.search(r'M\\d\\d',p.name) or re.search(r'M\\d\\d',p.parent.name)")
one("discover(E,2,True)","discover(E,3,True)")
one("if W in p.parents or 'parallel_cpu_20261031' in p.parts:continue", "if W in p.parents:continue")
one("if not re.search(r'M1[012]|G10_[MF]|W01a',p.name):continue", "if not re.search(r'M1[012]|G10_[MF]|W01a',str(p.relative_to(E)) if p.is_relative_to(E) else p.name):continue")
compile(s,str(p),'exec');p.write_text(s,encoding='utf-8')
j=D/'campaign_hub.js';t=j.read_text(encoding='utf-8')
for expr in ('a.dt_s*1000','r.dt_s*1000'):
 t=t.replace(expr,'(finite('+expr.split('*')[0]+')?'+expr+':null)')
j.write_text(t,encoding='utf-8')
node=r'F:\Program Files\nodejs\node.exe'
z=subprocess.run([node,'--check',str(j)],capture_output=True,text=True,timeout=15)
assert z.returncode==0,z.stderr
sys.path.insert(0,str(D));import campaign_hub as hub
# Generate a new read-only preview page before activating the bridge.
old=hub.PUBLIC/'dashboard.html'
page=hub.render_page(old.read_text(encoding='utf-8'))
preview=hub.PUBLIC/'archive_runs'/'campaign_preview.html';hub.atomic(preview,page)
d=hub.collect()
assert d['counts']['wave_planned']==12
assert any(r['mesh']=='M01' for r in d['records'])
assert all(any(r['mesh']==m for r in d['records']) for m in ('M02','M03','M04','M05','M06','M07','M08','M09','M10','M11','M12'))
assert d['current_foil'] and d['current_foil']['mesh']=='M10'
assert len({r['id'] for r in d['records']})==len(d['records'])
print(json.dumps({'preview':str(preview),'bytes':len(page.encode()),'counts':d['counts'],'foil':d['current_foil']['mesh'],'collection_s':d['collection_s'],'sources_unchanged':True}))
