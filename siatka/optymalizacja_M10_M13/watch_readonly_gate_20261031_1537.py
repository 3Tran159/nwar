from pathlib import Path
import json,hashlib,datetime,urllib.request
R=Path(r'E:\ntnu_mesh_optimization_20261030')
print('DEVICE_TIME', datetime.datetime.now().astimezone().isoformat())
plan=json.loads((R/'plan.json').read_text(encoding='utf-8-sig'))
runbook=R/'AUTONOMOUS_RECOVERY_PROMPT.md'
print('RUNBOOK_SHA_MATCH',hashlib.sha256(runbook.read_bytes()).hexdigest()==plan['recovery_policy']['runbook_sha256'])
print('RUNBOOK_FINAL_SECTION',runbook.read_text(encoding='utf-8-sig')[-1700:])
print('PLAN_AUTH',json.dumps({'selection':plan.get('selection',{}).get('user_primary_CL_CD_override'),'parallel_execution':plan.get('parallel_execution',{})},ensure_ascii=False)[:2500])
for name in ['decisions.jsonl','attempts.jsonl','watch_status_20261031.jsonl','mesh_queue_state.json','parallel_cpu_20261031/current.json','parallel_cpu_20261031/auxiliary.lock','wave_surface_only/zero_start_12_current.json']:
 p=R/name
 print('FILE',name,'EXISTS',p.exists(),'TAIL',p.read_text(encoding='utf-8-sig')[-3500:] if p.exists() else '')
for name in ['STOP_ALL','parallel_cpu_20261031/auxiliary.lock','wave_surface_only/wave_inlet.lock','wave_surface_only/wave_mesh_comparison.lock']:
 print('MARKER',name,(R/name).exists())
for name in ['F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL','F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/campaign_hold.json']:
 print('MARKER',name,Path(name).exists())
try:
 print('API',urllib.request.urlopen('http://127.0.0.1:8771/api/mesh-study',timeout=3).read().decode()[:800])
except Exception as e:print('API_ERR',type(e).__name__,str(e)[:200])
