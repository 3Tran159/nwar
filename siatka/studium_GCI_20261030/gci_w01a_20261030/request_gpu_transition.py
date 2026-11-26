from pathlib import Path
import json,datetime
O=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030')
s=json.loads((O/'cpu_study_state.json').read_text())
p=Path(s['directory']).resolve()
assert s['pid']==40380 and s['star_pid']==34872 and s['job']=='calm_settle_G10_F' and p.parent==O/'force_stabilization_20261029'
request={'status':'saving_CPU_checkpoint_for_GPU_transition','requested_at':datetime.datetime.now().astimezone().isoformat(),'authorized_gpu':True,'previous_cpu_only_requirement_superseded':True,'source_case':str(p),'CPU_controller_pid':s['pid'],'CPU_launcher_pid':s['star_pid'],'keep_wave_cases_untouched':True,'same_dt_and_inner_iterations':True,'selection_policy':{'target_cells':300000,'choose_lightest_acceptable_mesh_after_campaign':True,'selected_wave_case_name':'C01','rename_only_after_selection':True,'preserve_existing_C01_results':True}}
(O/'gpu_transition_request.json').write_text(json.dumps(request,indent=2))
with (p/'STOP').open('x') as f:f.write('User requested GPU acceleration; preserve final fields before switching backend.\n')
print(json.dumps({'stop_requested_for':p.name,'checkpoint_preservation':True,'future_selected_case':'C01'}))
