from pathlib import Path
import json,datetime
O=Path(__file__).resolve().parent
state=json.loads((O/'gpu_study_state.json').read_text())
out=Path(state['directory'])
assert state['pid']==10064 and state['star_pid']==33476 and out.name=='calm_settle_G10_F_GPU_r1'
assert out.parent==O/'force_stabilization_20261029'
request=dict(source_case=str(out),controller_pid=state['pid'],launcher_pid=state['star_pid'],requested_at=datetime.datetime.now().astimezone().isoformat(),purpose='Save and continue same fields; add live velocity preview and hydrodynamic CL settling',physics_unchanged=True)
(O/'gpu_live_transition.json').write_text(json.dumps(request,indent=2))
(out/'STOP').touch()
print('Requested save of owned M12 GPU continuation only.')
