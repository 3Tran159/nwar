"""Start W05 from the recovered GLHF save in a new portable workspace."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SEED_ID = 'fadb7f1cf0684cd0'
CHECKPOINT_SHA = '3996e984d29a04c4a5dad38565cde7d36c016c88ac4396ddee00c222116dd47a'
REQUEST = 'glhf_clean_w05_' + CHECKPOINT_SHA[:16]


def dispatch(check_only):
    from common import DATA, HERE, PYTHON, enqueue, jobs, read, sha, write
    from glhf_bundle import PRE, load_manifest
    from glhf_transfer import checkpoint_for, prepare_resume, read_case, verify_resume
    from portable_config import BASE, RELEASE
    from wave_profiles import approved_profile
    from worker import native, rt

    if RELEASE != '2606':
        raise ValueError('The recovered W05 save requires STAR-CCM+ 2606.')
    bundle = BASE/'recovery/W05'
    manifest = load_manifest(bundle)
    if (manifest['case_id'] != 'W05' or manifest['release'] != RELEASE
            or manifest['run_id'] != SEED_ID or manifest['segments'] != ['segments/000']
            or manifest['checkpoint']['sha256'] != CHECKPOINT_SHA
            or not manifest['checkpoint']['final_save_verified']):
        raise ValueError('The recovery bundle is not the expected W05 save.')
    profile = approved_profile('W05', verify=True)
    if not profile or profile['source_sha'] != PRE:
        raise ValueError('The approved PRE is missing.')
    DATA.mkdir(parents=True, exist_ok=True)
    folder = DATA/'glhf_seed'/SEED_ID
    if not folder.exists():
        folder.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder.parent) as staging:
            seed = Path(staging)/'seed'
            shutil.copytree(bundle/'segments/000', seed)
            shutil.copy2(bundle/'checkpoint/latest.sim', seed/'wave_pilot_final.sim')
            original = read(seed/'source_identity.json')
            if original['sha256'] != PRE or original.get('original_preserved') is not True:
                raise ValueError('The recovered W05 does not descend from the approved PRE.')
            write(seed/'source_identity.json', {**original, 'path': profile['source'],
                                                  'original_glhf_path': original['path']})
            seed.rename(folder)
    entry = dict(id=SEED_ID, case_id='W05', status='needs_review', folder=str(folder),
                 spec=dict(id='W05', H=1., L=20., dt=.0004, mesh_profile=profile,
                           mode='fresh', source=profile['source'], source_sha=PRE,
                           source_time=profile['source_time']))
    chain, result = read_case(entry)
    sim, checkpoint = checkpoint_for(entry)
    if (checkpoint['sha256'] != CHECKPOINT_SHA or checkpoint['final_save_verified'] is not True
            or checkpoint['step'] != manifest['checkpoint']['step']
            or abs(checkpoint['time_s']-manifest['checkpoint']['time_s']) > 1e-7
            or result['cycles']['count'] != 3 or not result['health']['ok']):
        raise ValueError('W05 checkpoint and measured history do not match the verified export.')
    receipt = prepare_resume(entry, chain, checkpoint, sim)
    verify_resume(receipt)
    if check_only:
        print(json.dumps(dict(verified=True, checkpoint_s=checkpoint['time_s'], cycles=3)))
        return

    queued = jobs()
    existing = next((job for job in queued if job['request_key'] == REQUEST), None)
    if existing and existing['status'] != 'queued':
        print(f'W05 job {existing["id"]} already exists ({existing["status"]}). See the dashboard.')
        return
    if native() or any(job['id'] != (existing or {}).get('id')
                       and job['status'] in ('queued', 'deferred', 'preflight', 'running', 'pausing')
                       for job in queued):
        raise ValueError('Another STAR process or queue job is active.')
    problem = rt.resource_problem()
    if problem:
        raise ValueError(problem)
    rt.launch_arguments(sim, HERE/'NwarWave.java')
    ident = enqueue('W05', 'resume', glhf_recovery=receipt, request_key=REQUEST, mpi_processes=1)
    with (DATA/'glhf_worker.log').open('a', encoding='utf8') as log:
        subprocess.Popen([str(PYTHON), str(HERE/'worker.py'), '--only', ident], cwd=HERE,
                         stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    print(f'W05 queued as {ident} from t={checkpoint["time_s"]:.4f} s. Target: five measured cycles.')


def start():
    import start_nwar as launcher
    config = launcher.read(launcher.BASE/'launcher.json')
    if (config.get('release') != '2606'
            or config.get('license_mode') == 'pod' and not os.environ.get('NWAR_POD_KEY')):
        config = launcher.configure(config)
    if not config:
        return 1
    if config['release'] != '2606':
        raise ValueError('Select STAR-CCM+ 2606 for the recovered W05 save.')
    config['workspace_root'] = str(launcher.BASE/'workspaces')
    launcher.write(launcher.BASE/'launcher.json', config)
    panel = launcher.launch(config)
    print('Dashboard: ' + panel['url'], flush=True)
    app, env = launcher.prepare(config)
    return subprocess.run([str(launcher.BASE/'runtime/python.exe'), str(app/'glhf_clean_start.py'),
                           '--dispatch'], cwd=app, env=env).returncode


if __name__ == '__main__':
    try:
        if '--dispatch' in sys.argv:
            dispatch('--check-only' in sys.argv)
        else:
            sys.exit(start())
    except Exception as error:
        from_key = os.environ.get('NWAR_POD_KEY')
        message = str(error).replace(from_key, '[REDACTED]') if from_key else str(error)
        print('HOLD: '+message, file=sys.stderr)
        sys.exit(1)
