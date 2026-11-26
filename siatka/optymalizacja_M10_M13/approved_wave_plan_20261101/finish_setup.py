"""Finish derived dashboard wiring and persist stage readiness without launching a solver."""
from pathlib import Path
from datetime import datetime
import json,hashlib,os,subprocess
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=R/'approved_wave_plan_20261101';UI=R/'foil_live_dashboard_20261031'
py=UI/'foil_live.py';js=UI/'foil_live.js';pb=py.read_bytes();jb=js.read_bytes();ps=pb.decode('utf8');ss=jb.decode('utf8')
anchor=" audits=sorted(P.glob('WAVE_PROPAGATION_AUDIT_*.json'),key=stamp,reverse=True)"
insert=""" # A changed dt may only be compared against its own verified calm reference.
 matched=read(ROOT/'approved_wave_plan_20261101'/'calm_dt02_result.json')
 for item in runs:
  if abs(float(item.get('dt') or 0)-.0002)<1e-12:
   item['calm_reference']={};item['calm_certification']={}
   if matched.get('project_primary_pass') is True and matched.get('raw_recomputed') is True:
    item['calm_reference']={'CL':matched.get('CL'),'CD':matched.get('CD'),'source':'Separate matched M13 calm dt0.2ms','dt_s':.0002}
    checks=matched.get('checks',[])
    if len(checks)==2:
     m=checks[-1]['metrics'];item['calm_certification']={'checks_s':[c['time_s'] for c in checks],'CL_shift_pct':m['CL']['mean_shift_pct'],'CD_shift_pct':m['CD']['mean_shift_pct'],'CL_rms_pct':max(m['CL']['RMS_previous_pct'],m['CL']['RMS_latest_pct']),'CD_rms_pct':max(m['CD']['RMS_previous_pct'],m['CD']['RMS_latest_pct']),'same_dt_reference':True}
  else:item['calm_reference']=ref
"""
assert ps.count(anchor)==1 and 'matched=read(ROOT/' not in ps
ps=ps.replace(anchor,insert+anchor,1)
a='ref=d.calm_reference||{},cert=d.calm_certification||{}';b='ref=r.calm_reference||d.calm_reference||{},cert=r.calm_certification||d.calm_certification||{}'
assert ss.count(a)==1;ss=ss.replace(a,b,1)
compile(ps,str(py),'exec');(D/'foil_live_candidate.js').write_text(ss,encoding='utf8')
q=subprocess.run([r'F:\Program Files\nodejs\node.exe','--check',str(D/'foil_live_candidate.js')],capture_output=True,text=True,timeout=30);assert q.returncode==0,q.stderr
assert py.read_bytes()==pb and js.read_bytes()==jb,'Concurrent UI change'
(D/'backup'/'foil_live_before_matched_ref.py').write_bytes(pb);(D/'backup'/'foil_live_before_matched_ref.js').write_bytes(jb)
for path,text in ((py,ps),(js,ss)):
 tmp=path.with_suffix(path.suffix+'.ready.tmp');tmp.write_text(text,encoding='utf8');os.replace(tmp,path)
plan=json.loads((R/'plan.json').read_text(encoding='utf8'));assert hashlib.sha256((R/'AUTONOMOUS_RECOVERY_PROMPT.md').read_bytes()).hexdigest()==plan['recovery_policy']['runbook_sha256']
state={'at':datetime.now().astimezone().isoformat(),'implementation_in_progress':False,'stage':'B_forcing_audit_pending','analysis_installed':True,'analysis_Q_CD':json.loads((D/'analysis_corrected.json').read_text(encoding='utf8'))['Q_CD'],'browser_qa_passed':True,'sensitivity_macros_compiled':True,'sensitivity_runner':str(D/'run_sensitivity.py'),'sensitivity_started':False,'case_sequence':['calm_dt02','wave_dt02','H0.25_lambda20','H0.5_lambda30'],'variant_queue':str(D/'wave_variant_queue.json'),'forcing_review_missing':not (D/'forcing_review.json').exists(),'known_audit_warning':'Inherited Hydrostatic Pressure of Heavy Fluid of Calm evaluation warning; must review before declaring audit passed','deadline_local':plan['deadline_local']}
(D/'stage_state.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
with (R/'decisions.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps({'at':state['at'],'event':'approved_M13_analysis_deployed_audit_in_progress_sensitivity_prepared','handoff':str(D/'HANDOFF.md'),'deadline':state['deadline_local'],'Q':state['analysis_Q_CD'],'raw_unchanged':True,'new_physical_CFD_runs_started':False},ensure_ascii=False)+'\n')
print(json.dumps(state,ensure_ascii=False))
