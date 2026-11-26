"""Read the native STAR save state and review a transferred GLHF result offline."""
import math
import re

from common import Path, SOURCE, SOURCE_SHA, catalog, now, read, sha, write
from glhf_bundle import load_manifest, path_under


def sim_state(path):
    with Path(path).open('rb') as stream:
        header = stream.read(1024)
        offset = int(re.search(rb"'StatePosition'\s*:\s*(\d+)", header)[1])
        stream.seek(offset)
        state = stream.read(32 * 1024 * 1024)
    number = rb'([-+0-9.eE]+)'
    solution = re.findall(rb"(?m)^\{[^\r\n]*'ClassName'\s*:\s*'star.common.Solution'[^\r\n]*'PhysicalTime'\s*:\s*"+number, state)
    views = re.findall(rb"(?m)^\{[^\r\n]*'ClassName'\s*:\s*'star.post.CurrentSolutionView'[^\r\n]*$", state)
    if len(solution) != 1 or len(views) != 1:
        raise ValueError('Expected exactly one saved solution and current solution view.')
    view = views[0]
    physical_time = float(solution[0])
    view_time = float(re.search(rb"'PhysicalTime'\s*:\s*"+number, view)[1])
    if not math.isfinite(physical_time) or physical_time != view_time:
        raise ValueError('The two native saved physical times disagree.')
    return dict(
        time_s=physical_time, step=int(re.search(rb"'TimeStep'\s*:\s*(\d+)", view)[1]),
        iteration=int(re.search(rb"'Iteration'\s*:\s*(\d+)", view)[1]),
        release=re.search(rb"'ReleaseNumber'\s*:\s*'([^']+)'", header)[1].decode('ascii'),
        mpi=re.search(rb"'MachineConfig'\s*:\s*'([^']+)'", header)[1].decode('ascii'),
        wave_numbers=[float(v) for v in re.findall(rb"'WaveNumber'\s*:\s*"+number, state)],
        time_steps=[float(v) for v in re.findall(rb"'TimeStepValue'\s*:\s*"+number, state)],
        scene_count=len(re.findall(rb"'ClassName'\s*:\s*'star.vis.Scene'", state)),
        state_offset=offset,
    )


def review(folder, sim):
    from analysis import analyze, numeric_rows
    from cycle_policy import accepted_cycles
    from project_results import policy
    import numpy as np

    folder, sim = Path(folder).resolve(), Path(sim).resolve()
    manifest = load_manifest(folder)
    checkpoint = manifest['checkpoint']
    if not (manifest.get('history_only_after_checkpoint') and checkpoint.get('final_save_verified')
            and manifest['case_id'] == 'W05' and manifest['release'] == '2606'):
        raise ValueError('Expected the independently anchored W05 continuation export.')
    segments = [path_under(folder, segment) for segment in manifest['segments']]
    case = next(c for c in catalog() if c['id'] == manifest['case_id'])
    result, data, _ = analyze(case, segments)
    samples = numeric_rows(segments[-1]/'history.csv')
    anchor = sim_state(path_under(folder, checkpoint['path']))
    saved = sim_state(sim)
    dt = manifest['dt_s']
    end = float(samples['time_s'][-1])
    expected_steps = np.arange(len(samples['step']))
    if (not np.array_equal(samples['step'], expected_steps) or abs(anchor['time_s']-checkpoint['time_s'])>1e-7
            or abs(samples['time_s'][0]-anchor['time_s'])>1e-7 or abs(saved['time_s']-end)>1e-7
            or abs(end-manifest['history_end_s'])>1e-7 or saved['step']-anchor['step'] != expected_steps[-1]
            or not np.allclose(np.diff(data['time_s']), dt, atol=1e-7, rtol=0)):
        raise ValueError('The native SIM time or step does not match the joined CSV history.')
    if (saved['release']!=anchor['release'] or not saved['release'].startswith('21.04.')
            or saved['mpi']!='Np=1' or saved['scene_count']!=anchor['scene_count'] or saved['scene_count']!=30
            or saved['wave_numbers']!=anchor['wave_numbers'] or len(saved['wave_numbers'])!=1
            or abs(saved['wave_numbers'][0]-math.tau/case['L'])>1e-8 or dt not in saved['time_steps']):
        raise ValueError('The native saved configuration or scene inventory differs from the prior W05 save.')
    if (not manifest['continuation_export']['prior_history_matches'] or not manifest['continuation_export']['prior_gauges_match']
            or sha(SOURCE)!=SOURCE_SHA or not result['health']['ok'] or not accepted_cycles(result['cycles'])
            or np.max(np.abs(data['target_H_m'][-len(samples['step']):]-case['H']))>1e-8):
        raise ValueError('W05 reference, wave height, numerical health or cycle repeatability check failed.')
    for coefficient, force, offset in (('CD_total','Fx_N',0),('CL_hydrodynamic','Fz_N',22.718189111947265)):
        if np.max(np.abs(data[coefficient]-(data[force]-offset)/3855.6))>=1e-10:
            raise ValueError('The force coefficient convention differs from C01.')
    digest = sha(sim)
    checks = [
        dict(id='checkpoint',title='Native checkpoint and CSV endpoint',values=dict(actual_sha256=digest, native=saved, previous=anchor)),
        dict(id='configuration',title='Saved configuration and original C01',values=dict(height_m=case['H'],wavelength_m=case['L'],C01_sha256=SOURCE_SHA)),
        dict(id='health',title='Joined numerical history',values=result['health']),
        dict(id='repeatability',title='Repeatability of measured cycles 2–5',values=dict(metrics=result['cycles']['metrics'],count=result['cycles']['count'])),
    ]
    receipt=dict(id=folder.name,case_id='W05',generated_at=now(),project_accepted=True,
        run_verification='passed',verification_kind='glhf_saved_state',
        scope='User-authorized qualitative acceptance of a transferred saved state',
        native_controller_exit_verified=False,policy_id=policy()['id'],
        manifest_sha256=sha(folder/'manifest.json'),checkpoint=str(sim),checkpoint_sha256=digest,
        checkpoint_bytes=sim.stat().st_size,checkpoint_mtime_ns=sim.stat().st_mtime_ns,
        time_s=saved['time_s'],checks=[dict(c,status='passed',group='run',criterion=c['title'],
            evidence_files=[str(sim),str(folder/'manifest.json')]) for c in checks],
        counts=dict(passed=4,failed=0,pending=0,future=0))
    write(folder/'saved_result_review.json',receipt)
    return receipt
