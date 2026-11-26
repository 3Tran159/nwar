"""Record the explicitly requested density-corrected W01 as a new pending revision.
Derived campaign metadata only: no solver, active macro, reference gate or raw file changes.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,uuid
A=Path(__file__).parent;R=A.parent;D=R/'approved_wave_plan_20261101'
registry=A/'campaign.json';collector=A/'campaign.py';handoff=A/'HANDOFF.md'
files=(registry,collector,handoff);old={p:p.read_bytes() for p in files}
plan=json.loads((R/'plan.json').read_text(encoding='utf-8-sig'))
assert hashlib.sha256((R/'AUTONOMOUS_RECOVERY_PROMPT.md').read_bytes()).hexdigest().lower()==plan['recovery_policy']['runbook_sha256'].lower()
authority=D/'USER_DENSITY_CORRECTED_W01_20261101_1136.json'
auth=json.loads(authority.read_text(encoding='utf-8-sig'))
assert auth['kind']=='explicit_user_authorization_addendum_not_a_solver_start'
assert auth['until_local']=='2026-11-02T09:00:00+01:00'
manifest=json.loads(old[registry].decode('utf-8-sig'))
assert not manifest.get('density_correction_revision'),'Revision already registered; inspect before modifying'
now=datetime.now().astimezone().isoformat()
revision={'id':'W01-rho1000-air1p2','status':'pending_preparation','target_water_kg_m3':1000.0,'target_air_kg_m3':1.2,'mesh':'M13','cells':309441,'H_m':0.5,'lambda_m':20.0,'dt_s':0.0004,'inner_iterations':10,'time_discretization':'second_order','GPU':1,'source_run':None,'solver_started':False,'verified_configuration':False,'requires_native_material_and_wave_density_readback':True,'requires_matched_C01':True,'source_authorization':str(authority),'do_not_change_active_T01':True,'no_density_rescaling_of_old_results':True}
manifest['density_correction_revision']=revision
manifest['required_density_contract']={'water_kg_m3':1000.0,'air_kg_m3':1.2,'applies_to':['C01','W01-rho1000-air1p2','all subsequent Wxx'], 'check_points':['native phase materials','Calm wave definition','FifthOrder wave definition','inlet/top/outlet hydrostatic bindings','CL/CD normalization','hydrostatic lift correction once'],'fail_closed_on_mismatch':True,'setting_declared_is_not_a_readback':True}
manifest['next_case']='W01 · korekta ρ 1000/1,2'
manifest['next_case_id']='W01-rho1000-air1p2'
manifest['queue_order']=['W01-rho1000-air1p2']+[x for x in manifest['queue_order'] if x!='W01-rho1000-air1p2']
w01=next(x for x in manifest['cases'] if x['id']=='W01')
assert w01['source_runs'],'Keep original W01 lineage available'
w01['displayed_revision']='historical_density_mismatch'
w01['title']='Pierwsza fala · dotychczasowa konfiguracja gęstości'
w01['note']='Wyświetlone wyniki to stary W01: w definicji fali odczytano 997,561 / 1,18415 kg/m³, a w Calm 1000 / 1,2. Nie utożsamiamy tych odczytów z właściwościami materiałów solvera. Osobny W01-rho1000-air1p2 jest następny po obecnej kontroli i zgodnym C01. Nie przeskalowujemy ani nie nadpisujemy starych sił.'
w01['observed_wave_object_density']={'water_kg_m3':997.561,'air_kg_m3':1.18415,'source':str(D/'forcing_review.json'),'native_material_density_confirmed':False}
w01['requested_revision']=revision['id'];w01['comparison_allowed']=False
for case in manifest['cases']:
 case['target_water_density_kg_m3']=1000.0;case['target_air_density_kg_m3']=1.2
 if case['id']!='W01':case['density_contract_verified']=False
text=old[collector].decode('utf-8')
a="'next_case':'W02'";b="'next_case':manifest.get('next_case','W02')"
assert text.count(a)==1,'Collector changed; re-read before patch'
text=text.replace(a,b,1);compile(text,str(collector),'exec')
notice='\n## Priorytet: powtórzenie W01 na 1000 / 1,2 kg/m³, '+now+'\nNajnowsze polecenie użytkownika: trzeba policzyć W01 na rho_water1000 i rho_air1.2, ponieważ nie przypilnowano zgodności gęstości. Pełne upoważnienie: '+str(authority)+'. Aktywny T01 pozostaje nietknięty. Kolejny warunek to W01-rho1000-air1p2, nie W02 ani jednoczesna zmiana dt. Rejestr zawiera JEDYNIE plan nowej wersji, nie kompilację lub start solvera. Trzeba jawnie odczytać/ustawić/ponownie odczytać właściwości MATERIAŁÓW water/air i Calm/FifthOrder, hydrostatykę, normalizację i jednorazowy wypór. Jeśli C01 nie jest zgodny, najpierw policzyć osobny zgodny calm. Nowa fala tylko od wlotu, z poprawnego calm, bez przerabiania starego pola falowego. Wyniki starego W01 zachować w historii i nie mieszać z nową wersją. Referencje i procenty pozostają zablokowane do accepted_matched_reference. Dalsze Wxx odziedziczą ten sam jawny kontrakt1000/1.2.\n\n'
new={registry:(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8'),collector:text.encode('utf-8'),handoff:(notice+old[handoff].decode('utf-8')).encode('utf-8')}
backup=A/('density_revision_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir(exist_ok=False)
assert all(p.read_bytes()==v for p,v in old.items()),'Concurrent derived metadata change; nothing overwritten'
for p,v in old.items():(backup/p.name).write_bytes(v)
for p,v in new.items():
 tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(v);os.replace(tmp,p)
event={'at':now,'event':'W01_density1000_air1p2_pending_revision_registered','revision':revision['id'],'target_water_kg_m3':1000.0,'target_air_kg_m3':1.2,'solver_started':False,'active_T01_unchanged':True,'old_W01_source_runs_preserved':w01['source_runs'],'reference_gate_unchanged':True,'backup':str(backup),'authorization':str(authority)}
with (R/'decisions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
(A/'density_revision_registration.json').write_text(json.dumps(event,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(event,ensure_ascii=False))
