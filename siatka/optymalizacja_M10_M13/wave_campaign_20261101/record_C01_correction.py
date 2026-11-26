from pathlib import Path
from datetime import datetime
import json,os,uuid
A=Path(__file__).parent;R=A.parent;D=R/'approved_wave_plan_20261101'
now=datetime.now().astimezone().isoformat();pointer=str(A/'C01_REFERENCE_POLICY_20261101.md')
notice='\n## NADRZĘDNA KOREKTA C01, '+now+'\nPrzeczytaj '+pointer+'. Historyczny M13 calm z badań siatki NIE jest teraz referencją C01 do W01. C01=pending_compatibility; Q/ΔCD/ΔCL/procenty i linie baseline wyłączone do jawnej weryfikacji zgodności gęstości, normalizacji i BC. T01 jest kandydatem/kontrolą, nie automatycznym C01. Własne wyniki W01 zachowane. To zastępuje wcześniejsze, sprzeczne opisy C01 poniżej.\n\n'
files=[A/'HANDOFF.md',D/'HANDOFF.md',R/'plan.json',D/'stage_state.json'];before={p:p.read_bytes() for p in files};after={}
for p in files[:2]:after[p]=(notice+before[p].decode('utf-8')).encode('utf-8')
plan=json.loads(before[R/'plan.json'].decode('utf-8-sig'));plan.setdefault('approved_wave_followup_20261101',{})['campaign_reference_policy']={'at':now,'reference_C01_status':'pending_compatibility','historical_mesh_calm_not_a_wave_reference':True,'wave_comparison_allowed':False,'policy':pointer,'current_control_does_not_auto_approve_reference':True}
after[R/'plan.json']=(json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
state=json.loads(before[D/'stage_state.json'].decode('utf-8-sig'));state.update(C01_reference_status='pending_compatibility',C01_policy=pointer,wave_relative_metrics_enabled=False,C01_policy_updated_at=now)
after[D/'stage_state.json']=(json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
backup=A/('reference_metadata_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir(exist_ok=False)
assert all(p.read_bytes()==b for p,b in before.items()),'Concurrent metadata update; retry only after re-read'
for i,(p,b) in enumerate(before.items()):(backup/(str(i)+'_'+p.name)).write_bytes(b)
for p,b in after.items():
 t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');t.write_bytes(b);os.replace(t,p)
print(json.dumps({'at':now,'C01_pending_recorded':True,'old_sources_unchanged':True,'active_solver_untouched':True,'policy':pointer}))
