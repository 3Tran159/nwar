from pathlib import Path
import json,datetime
O=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
request=read(O/'gpu_transition_request.json');check=read(O/'gpu_equivalence_check.json');sources=read(O/'gpu_campaign_sources.json')
assert check['pass_check']
policy=request['selection_policy']
policy.update(status='pending_mesh_campaign_results',selected_mesh=None,selected_case_name='C01',wave_execution='after_mesh_selection',current_legacy_C01_cases_preserved=True,scope='Use the selected calm-water mesh as the basis for future C01 wave calculations; do not treat calm-water GCI as wave-response GCI.')
(O/'mesh_selection_policy.json').write_text(json.dumps(policy,indent=2))
request.update(status='GPU_continuation_active',CPU_checkpoint_time_s=sources['start_times']['G10_F'],hardware_equivalence_passed=True,measured_speedup=check['speedup'],updated_at=datetime.datetime.now().astimezone().isoformat())
(O/'gpu_transition_request.json').write_text(json.dumps(request,indent=2))
print(json.dumps({'GPU_transition':request['status'],'saved_CPU_time_s':request['CPU_checkpoint_time_s'],'selected_wave_case_after_campaign':'C01'}))
