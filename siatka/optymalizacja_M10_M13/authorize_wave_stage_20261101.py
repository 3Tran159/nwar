"""Record explicit user authorization, preserve prior plan/runbook and all solver evidence."""
from pathlib import Path
from datetime import datetime
import json,hashlib,os
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'approved_wave_plan_20261101'
P=R/'plan.json';old=P.read_bytes();plan=json.loads(old.decode('utf-8-sig'))
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((R/'AUTONOMOUS_RECOVERY_PROMPT.md').read_bytes())==plan['recovery_policy']['runbook_sha256']
assert not D.exists(),'New stage already recorded; read existing state instead of duplicating'
D.mkdir();(D/'backup').mkdir();(D/'backup'/'plan_before.json').write_bytes(old)
now=datetime.now().astimezone().isoformat();deadline='2026-11-02T09:00:00+01:00'
auth={'authorized_at':now,'user_instruction':'przedluzam do jutra do 9, ztwierdzam wdrozenie planu, potem przejdz do innyhc kombinacji fal','until_local':deadline,'timezone':'Europe/Oslo','approved_source':'Pasted markdown.md, 154 lines, user approved plan on 1 Nov 2026','base_mesh':'M13,309441 cells','ordered_stages':['A_correct_cycle_analysis_and_dashboard','B_audit_forcing_and_calm_wave_equivalence','C_paired_dt0p2ms_sensitivity_against_dt0p4ms','D_H0p25_lambda20','E_H0p5_lambda30'],'phase_gauge_x_m':-.5,'number_of_overlaid_cycles':4,'twenty_cycles':'diagnostic ceiling for persistent non-repeatability, not compulsory minimum','sensitivity_quantity':'Q=mean_CD_wave-CD_calm','working_Q_change_absolute_max':4e-5,'Q_tolerance_is_project_proposal':True,'dt_sensitivity_test_is_new_explicitly_authorized_experiment':True,'retry_budget_not_reset':True,'blanket_rebuild':False,'F_legacy_hold_preserved':True,'one_GPU_only':True,'originals_immutable':True,'source_runbook_sha256':plan['recovery_policy']['runbook_sha256']}
(D/'authorization.json').write_text(json.dumps(auth,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
plan.setdefault('historical_deadlines',[]).append({'recorded_at':now,'deadline_local':plan.get('deadline_local'),'scope':'former mesh/night optimization horizon'})
plan['deadline_local']=deadline
plan['deadline_meaning']='Explicit 1 Nov authorization: M13 wave validation then selected H/lambda cases until 2 Nov 09:00 Oslo. Not a new blanket mesh-search or recovery budget. No automatic killing of healthy existing runs at expiry.'
plan['approved_wave_followup_20261101']=auth;plan['updated_at']=now
plan['status']='M13_wave_followup_authorized_analysis_then_audit'
assert P.read_bytes()==old,'Concurrent plan changed; refuse overwrite'
tmp=R/'plan.wave_stage.tmp';tmp.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(tmp,P)
assert sha((R/'AUTONOMOUS_RECOVERY_PROMPT.md').read_bytes())==json.loads(P.read_text(encoding='utf8'))['recovery_policy']['runbook_sha256']
state={'at':now,'stage':'A_analysis_and_B_audit_preparation','implementation_in_progress':True,'implementation_lease_until':'2026-11-01T11:00:00+01:00','solver_started':False,'next_numerical_start_requires':'audit reviewed; prepared isolated paired time-step workflow, healthy sources and all process/resource guards','deadline':deadline}
(D/'stage_state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
with (R/'decisions.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps({'at':now,'event':'explicit_user_extended_and_approved_M13_followup','authorization':str(D/'authorization.json'),'until':deadline,'runbook_unchanged':True,'no_solver_started':True},ensure_ascii=False)+'\n')
print(json.dumps({'authorization_recorded':True,'deadline_local':deadline,'runbook_hash_matches':True,'plan_backup':str(D/'backup'/'plan_before.json'),'solver_started':False}))
