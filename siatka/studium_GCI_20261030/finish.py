from pathlib import Path
import json,math,csv,hashlib
HERE=Path(__file__).resolve().parent
p=HERE/'make_report.py';s=p.read_text(encoding='utf-8')
s=s.replace("data=[[p(str(c),'SmallPL' if small else 'BodyPL') for c in row] for row in rows]", "header_style=ParagraphStyle('HeaderPL',parent=ss['SmallPL'],textColor=colors.white,fontName='DVB')\n data=[[Paragraph(clean(str(c)),header_style if i==0 else ss['SmallPL' if small else 'BodyPL']) for c in row] for i,row in enumerate(rows)]")
s=s.replace(" for item in data[0]:item.style=ParagraphStyle('th',parent=ss['SmallPL'],textColor=colors.white,fontName='DVB')\n",'')
p.write_text(s,encoding='utf-8')
D=json.loads((HERE/'evidence.json').read_text(encoding='utf-8'));ROOT=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
checks={}
for m in D['matched']['results']:
 for f in m['history_sources']:
  p=Path(f).parent/'setup.json';a=json.loads(p.read_text(encoding='utf-8-sig'))
  assert a['order']=='SECOND_ORDER' and a['dt_s']==.001 and a['inner_iterations']==10
  checks[str(p)]={k:a[k] for k in ['order','dt_s','inner_iterations','cells']}
  D['manifest'].append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 c=D['cases'][m['mesh']]['curve'];assert len(c)==400
 assert all(abs(c[i]['physical_time_s']-c[i-1]['physical_time_s']-.001)<1e-8 for i in range(1,len(c)))
 assert all(math.isfinite(v) for r in c for v in r.values())
 v=D['cases'][m['mesh']]['mean'];assert abs(v['CD']-(v['pressure_drag_N']+v['viscous_drag_N'])/(.5*1000*18**2*.0238))<1e-12
for f in D['manifest']:assert hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()==f['sha256']
D['independent_settings_checks']=checks
(HERE/'evidence.json').write_text(json.dumps(D,ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified matched settings, sample continuity, finite values, CD normalization and all source hashes.')
