"""Explicit RAM-policy recovery after native field recording has started."""
from common import *
import re

def saved_header(path):
    with Path(path).open('rb') as f:
        head=f.read(1024);match=re.search(rb"'StatePosition'\s*:\s*(\d+)",head)
        if not match:raise ValueError('Missing native state offset.')
        f.seek(int(match[1]));state=f.read(32*1024**2)
    view=re.findall(rb"(?m)^\{[^\r\n]*'ClassName'\s*:\s*'star.post.CurrentSolutionView'[^\r\n]*$",state)
    solutions=re.findall(rb"(?m)^\{[^\r\n]*'ClassName'\s*:\s*'star.common.Solution'[^\r\n]*'PhysicalTime'\s*:\s*([-+0-9.eE]+)",state)
    if len(view)!=1 or len(solutions)!=1:raise ValueError('Ambiguous native state header.')
    step=int(re.search(rb"'TimeStep'\s*:\s*(\d+)",view[0])[1]);t=float(re.search(rb"'PhysicalTime'\s*:\s*([-+0-9.eE]+)",view[0])[1])
    scenes=len(re.findall(rb"'ClassName'\s*:\s*'star.vis.Scene'",state))
    if abs(t-float(solutions[0]))>1e-7 or scenes!=30:raise ValueError('Native time or scenes disagree.')
    return step,t,scenes

def verify(parent):
    from native_production import native_health_snapshot
    from resource_limits import minimum_free_ram_gib
    folder=Path(parent['folder']);solve=folder/'native_solve';stage=read(solve/'stage_result.json');plan=read(folder/'native_plan.json')
    authority=folder/'resource_resume_authorization.json';auth=read(authority)
    if (parent['case_id']!='W04k' or parent['status']!='failed' or not parent['spec'].get('native_production')
            or stage.get('phase')!='NWAR_native_solve' or stage.get('ownership')!='windows_job_closed'
            or stage.get('source_unchanged') is not True or stage.get('controller_reason') not in ('RAM_below16GiB','RAM_below8GiB')
            or auth.get('authorized') is not True or auth.get('job_id')!=parent['id']
            or auth.get('action') not in ('resume_after_RAM_reserve_change','resume_after_RAM_guard') or minimum_free_ram_gib()!=8
            or stage.get('controller_reason')!=auth.get('controller_reason','RAM_below16GiB')
            or auth.get('stage_sha256')!=sha(solve/'stage_result.json')
            or any(p.exists() for p in STOPS+[DATA/'PAUSE',DATA/'STOP',folder/'STOP',solve/'STOP'])
            or any(folder.rglob('macro_error.*'))
            or parent.get('controller_birth') and birth(parent.get('controller_pid'))==parent['controller_birth']):
        raise ValueError('Missing explicit RAM-policy recovery proof or a stop is present.')
    checkpoint=Path(auth['checkpoint']);wake=Path(auth['wake_file'])
    if (checkpoint.parent.resolve()!=solve.resolve() or wake.parent.resolve()!=solve.resolve()
            or not checkpoint.is_file() or not wake.is_file()
            or sha(checkpoint)!=auth['checkpoint_sha256'] or sha(wake)!=auth['wake_sha256']):
        raise ValueError('Pinned native checkpoint or field history changed.')
    step,t,scenes=saved_header(checkpoint)
    begin=parent['spec']['native_recovery']['initial_step']
    if (step!=auth['checkpoint_step'] or abs(t-auth['time_s'])>1e-7
            or abs(t-(plan['start_s']+(step-begin)*plan['dt_s']))>1e-7 or not plan['wake_start_s']<t<plan['target_s']):
        raise ValueError('Native continuation time grid differs.')
    compiled=read(HERE/'qa/native_RAM_resume_20261109/compile.json')
    if compiled.get('passed') is not True or compiled.get('macro_sha256')!=sha(HERE/'NwarNativeResume.java'):
        raise ValueError('Native resume preparation is not compiled and pinned.')
    return dict(parent_id=parent['id'],checkpoint=str(checkpoint),sha256=auth['checkpoint_sha256'],
                initial_step=begin,checkpoint_step=step,time_s=t,plan=plan,wake_file=str(folder/'wake.simh'),
                resource_resume=True,previous_wake_file=str(wake),previous_wake_sha256=auth['wake_sha256'],
                health_before_resume=native_health_snapshot(solve/'star.log',plan,step),scene_count=scenes,
                authorization_sha256=sha(authority),compile_receipt_sha256=sha(HERE/'qa/native_RAM_resume_20261109/compile.json'))
