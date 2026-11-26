"""User correction: mesh-study calm is archival, not yet valid C01 for the wave campaign."""
from pathlib import Path
from datetime import datetime
import json,hashlib,os,uuid,subprocess,importlib.util
A=Path(__file__).parent;R=A.parent;F=R/'foil_live_dashboard_20261031';H=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard\campaign_hub.py')
files=[A/'campaign.py',A/'campaign.js',A/'campaign.json',F/'foil_live.js',H]
original={p:p.read_bytes() for p in files};text={p:b.decode('utf-8') for p,b in original.items()}
assert not (A/'C01_reference_review.json').exists(),'Reference review already exists: inspect, do not overwrite'
def replace(p,old,new):
 assert text[p].count(old)==1,(str(p),old[:110],text[p].count(old))
 text[p]=text[p].replace(old,new,1)
p=A/'campaign.py'
replace(p,"exact_ref=analysis.get('calm_reference_exact',{});ref=exact_ref or foil.get('calm_reference',{})","ref=foil.get('calm_reference',{}) # Only explicit matched-reference policy may supply C01.")
replace(p,"  if item['kind']=='calm':\n   p=Path(paths[0]);state=run_status(p);row.update(state);evidence=read(p/'project_primary_evidence.json')","  if item['kind']=='calm':\n   if not ref.get('verified_for_wave_comparison'):\n    row.update(status='reference_pending',mean_CL=None,mean_CD=None,series=[],source_path=None,time_s=None,step=None,calm_primary_pass=False,reference_status='pending_compatibility',scientifically_accepted=False)\n    entries.append(row);continue\n   p=Path(ref['source']);state=run_status(p);row.update(state);evidence=foil.get('calm_certification',{})")
old="   good=bool(evidence.get('raw_independently_recomputed') and len(evidence.get('checks_s',[]))==2 and all(n(evidence.get(k)) is not None and evidence[k]<.5 for k in ('CL_shift_pct','CD_shift_pct','CL_rms_pct','CD_rms_pct')))"
replace(p,old,"   good=ref.get('verified_for_wave_comparison') is True")
replace(p,"series=[[n(r.get('physical_time_s')),n(r.get('CL')),n(r.get('CD'))] for r in raw]","series=[[n(r.get('physical_time_s',r.get('time_s'))),n(r.get('CL',r.get('CL_hydrodynamic'))),n(r.get('CD',r.get('CD_total')))] for r in raw]")
replace(p,"    matched_ref=r.get('calm_reference') or (ref if abs((r.get('dt') or 0)-.0004)<1e-12 else {})","    matched_ref=r.get('calm_reference',{}) if r.get('reference_comparison_allowed') is True else {}")
p=A/'campaign.js'
replace(p,"const labels={reference:'Referencja zaliczona',","const labels={reference_pending:'C01 · weryfikacja w toku',reference:'Referencja zgodna z falami',")
replace(p,"C01: spokojna woda. W01–W07: warunki falowe. Kontrole numeryczne osobno.","C01: zgodna referencja w weryfikacji. W01–W07: warunki falowe. Kontrole osobno.")
replace(p,"trwa sprawdzenie równoważności calm–wave; wynik W01 pozostaje eksploracyjny.","C01 czeka na weryfikację gęstości, normalizacji i BC. Wyników W01 nie odnosimy do dawnego testu siatki; ΔCD, Q i procenty są wstrzymane.")
replace(p,"row.kind==='calm'?'Projektowa stabilizacja':'Eksploracyjny / planowany'","row.kind==='calm'?(row.calm_primary_pass?'Zgodna referencja':'Weryfikacja w toku'):'Własny wynik / bez porównania'")
replace(p," }else h+='<div class=\"wc-empty\">Ten warunek jest w planie."," }else if(row.kind==='calm')h+='<div class=\"wc-empty\" id=\"wc-reference-pending\"><b>C01: weryfikacja w toku.</b> Stary wynik M13 z testów siatki pozostaje w archiwum, ale nie jest referencją dla W01. Czekamy na zakończenie kontroli T01 i potwierdzenie zgodności gęstości materiałów oraz funkcji falowych, normalizacji sił i warunków brzegowych. Samo zakończenie T01 nie zatwierdza automatycznie C01.</div>';\n else h+='<div class=\"wc-empty\">Ten warunek jest w planie.")
p=F/'foil_live.js'
replace(p," const verifiedCalm=Array.isArray(cert.checks_s)"," const verifiedCalm=r.reference_comparison_allowed===true&&Array.isArray(cert.checks_s)")
card=next(line for line in text[p].splitlines() if "html+='<article" in line and '<h3>Referencja spokojnej wody i dotarcie fali</h3>' in line)
pending=" if(!r.reference_comparison_allowed)html+='<article class=\"m13-card\" id=\"m13-reference-pending\"><h3>C01: weryfikacja zgodnej referencji</h3><p>Wynik calm z testów siatki nie jest obecnie referencją dla tej próby falowej. Czekamy na kontrolę gęstości materiałów i definicji fali, normalizacji, ciśnienia oraz warunków brzegowych. Pokazujemy własne CL/CD i cykle tego przebiegu, bez starej linii odniesienia i bez ΔCD/procentów.</p></article>';\n else "+card.strip()
replace(p,card,pending)
replace(p,"  if(Number.isFinite(ref[key])&&series.length)lines.push","  if(r.reference_comparison_allowed===true&&Number.isFinite(ref[key])&&series.length)lines.push")
p=H;nl='\r\n' if '\r\n' in text[p] else '\n'
a=" data['wave_campaign']=campaign_module.enrich(data)"
b=" reference_spec=importlib.util.spec_from_file_location('m13_C01_reference_policy',wave_campaign_ui/'reference_policy.py')"+nl+" reference_module=importlib.util.module_from_spec(reference_spec);reference_spec.loader.exec_module(reference_module)"+nl+" reference_module.enforce(data)"+nl+a
replace(p,a,b)
manifest=json.loads(text[A/'campaign.json']);c01=manifest['cases'][0];assert c01['id']=='C01'
c01['historical_mesh_source_runs']=c01.get('source_runs',[]);c01['source_runs']=[];c01['candidate_source_runs']=[str(R/'M13_wave_direct_20261031'/'M13_GPU_Hnear0_matched_control_20261101')]
c01.update(title='Spokojna woda · zgodna z kampanią falową',scientific_status='pending_compatibility',reference_status='pending_compatibility',comparison_allowed=False,note='Oczekuje na weryfikację. Historyczny calm z testów mesha nie jest referencją do W01; nie wolno porównywać bez zgodnych gęstości, normalizacji i BC.')
manifest['C01_reference_review']=str(A/'C01_reference_review.json');manifest['historical_mesh_calm_not_a_wave_reference']=True
text[A/'campaign.json']=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
review={'at':datetime.now().astimezone().isoformat(),'status':'pending_compatibility','comparison_allowed':False,'source_run':None,'candidate_source_run':c01['candidate_source_runs'][0],'historical_mesh_sources':c01['historical_mesh_source_runs'],'reference':{},'compatible_run_ids':[],'compatibility_proofs':{},'user_instruction':'C01 must wait for current verification; W01 must not be compared with mesh-study calm under different density/setup.','automatic_acceptance_on_T01_completion':False,'old_results_preserved':True}
for p,s in text.items():
 if p.suffix=='.py':compile(s,str(p),'exec')
rev=A/('reference_fix_'+datetime.now().strftime('%Y%m%d_%H%M%S'));rev.mkdir(exist_ok=False)
for p,s in text.items():
 target=rev/p.name;target.write_bytes(s.encode('utf-8'))
 if p.suffix=='.js':
  q=subprocess.run([r'F:\Program Files\nodejs\node.exe','--check',str(target)],capture_output=True,text=True,timeout=20);assert q.returncode==0,q.stderr
# Compare-and-swap every source file before installing this derived-only correction.
assert all(p.read_bytes()==b for p,b in original.items()),'Concurrent dashboard edit detected'
backup=rev/'backup';backup.mkdir()
for p,b in original.items():(backup/p.name).write_bytes(b)
(A/'C01_reference_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p,s in text.items():
 temp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');temp.write_bytes(s.encode('utf-8'));os.replace(temp,p)
event={'at':datetime.now().astimezone().isoformat(),'event':'user_corrected_C01_pending_matched_reference','comparison_disabled':True,'W01_absolute_results_preserved':True,'raw_and_active_solver_unchanged':True,'backup':str(backup)}
(rev/'installation.json').write_text(json.dumps(event,indent=2),encoding='utf-8')
with (R/'decisions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
print(json.dumps(event,ensure_ascii=False))
