"""Install the W08bi transfer in an already configured GLHF workspace."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

PATCH = Path(__file__).resolve().parent
SEED_ID = '28cb7c64d2f04420'
REQUEST = 'glhf_w08bi_resume_3b28035594c92910'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def manifest():
    value = json.loads((PATCH/'manifest.json').read_text(encoding='utf8'))
    for name, expected in value['files'].items():
        path = (PATCH/name).resolve()
        if not path.is_relative_to(PATCH) or digest(path) != expected:
            raise ValueError('Transfer checksum mismatch: '+name)
    return value


def install(app, receipt):
    changes = []
    for key, expected in receipt['files'].items():
        if not key.startswith('app/'):
            continue
        source = PATCH/key
        target = app/source.name
        if target.is_file():
            current = digest(target)
            if current == expected:
                continue
            if current not in receipt['originals'].get(source.name, []):
                raise ValueError('Different version of '+source.name+' in this GLHF workspace.')
        changes.append((source, target))
    data = app.parent/'data'
    seed = data/'glhf_seed'/SEED_ID
    seed.parent.mkdir(parents=True, exist_ok=True)
    if not seed.exists():
        with tempfile.TemporaryDirectory(dir=seed.parent) as staging:
            staged = Path(staging)/'seed'
            shutil.copytree(PATCH/'seed', staged)
            if digest(staged/'checkpoint.sim') != receipt['files']['seed/checkpoint.sim']:
                raise ValueError('Checkpoint copy failed verification.')
            staged.rename(seed)
    for key, expected in receipt['files'].items():
        if key.startswith('seed/') and digest(seed/key[5:]) != expected:
            raise ValueError('Existing GLHF seed differs from the transfer: '+key)
    if changes:
        backup = Path(tempfile.mkdtemp(prefix='w08bi-backup-', dir=app.parent))
        for source, target in changes:
            if target.is_file():
                shutil.copy2(target, backup/target.name)
            with tempfile.NamedTemporaryFile(dir=app, delete=False) as staged:
                path = Path(staged.name)
                with source.open('rb') as stream:
                    shutil.copyfileobj(stream, staged)
            path.replace(target)
        print('Previous dashboard files: '+str(backup), flush=True)


def inspect_workspace():
    from common import DATA, SOLVER_LOCKS, OTHER_LOCKS, birth, jobs, read
    from worker import native, rt

    records = jobs()
    existing = next((record for record in records if record['request_key']==REQUEST), None)
    if existing and existing['status'] != 'queued':
        return dict(existing=existing['id'], status=existing['status'])
    for record in records:
        if record['request_key'] != REQUEST and record['status'] in ('queued', 'deferred', 'preflight', 'running', 'pausing'):
            raise ValueError('Save the active GLHF run and clear waiting requests in the dashboard first.')
    owner = read(DATA/'worker.lock')
    if (native() or owner.get('birth') and owner['birth']==birth(owner.get('pid'))
            or any(path.exists() for path in SOLVER_LOCKS+OTHER_LOCKS)):
        raise ValueError('GLHF STAR, the queue controller, or a resource lock is still active.')
    problem = rt.resource_problem()
    if problem:
        raise ValueError(problem)
    owner = read(DATA/'server.json')
    return dict(server=bool(owner.get('birth') and owner['birth']==birth(owner.get('pid'))))


def dispatch(queue_only=False):
    from common import DATA, HERE, PYTHON, enqueue, job
    from w08_portable import REQUEST, TIME, verify_job
    from worker import rt

    status = inspect_workspace() if not queue_only else {}
    if status.get('existing'):
        print(f'W08bi {status["existing"]} already exists ({status["status"]}). See the dashboard.')
        return status['existing']
    if not queue_only:
        rt.launch_arguments(DATA/'glhf_seed'/SEED_ID/'checkpoint.sim', HERE/'NwarBichromatic.java')
    ident = enqueue('W08', 'resume', request_key=REQUEST, w08_seed=True, mpi_processes=1)
    verify_job(job(ident))
    if not queue_only:
        with (DATA/'glhf_worker.log').open('a', encoding='utf8') as log:
            subprocess.Popen([str(PYTHON), str(HERE/'worker.py'), '--only', ident], cwd=HERE,
                             stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        print(f'W08bi queued as {ident} from t={TIME:.4f} s. Check physical time on the dashboard.', flush=True)
    return ident


def start(base):
    sys.path.insert(0, str(base))
    import start_nwar as launcher

    config = launcher.read(base/'launcher.json')
    if config.get('release') != '2606':
        raise ValueError('Open the configured GLHF dashboard in STAR-CCM+ 2606 first.')
    env = launcher.environment(config)
    app = Path(env['NWAR_WORKSPACE'])/'app'
    if not (app/'server.py').is_file() or not (app.parent/'settings.json').is_file():
        raise ValueError('The existing GLHF workspace could not be found.')
    receipt = manifest()
    python = base/'runtime/python.exe'

    def run(mode, capture=False):
        return subprocess.run([str(python), __file__, mode], cwd=app, env=env,
                              text=True, capture_output=capture, check=True)

    def state():
        result = run('--inspect', capture=True)
        status = json.loads(result.stdout)
        if status.get('error'):
            raise ValueError(status['error'])
        return status

    current = state()
    if current.get('existing'):
        panel = launcher.launch(config)
        print(f'W08bi {current["existing"]} already exists ({current["status"]}). Dashboard: {panel["url"]}')
        return
    if config.get('license_mode')=='pod' and not os.environ.get('NWAR_POD_KEY'):
        key = getpass.getpass('Power-on-Demand key for this session: ')
        if not key:
            raise ValueError('A Power-on-Demand key is required.')
        os.environ['NWAR_POD_KEY'] = env['NWAR_POD_KEY'] = key
    if current['server']:
        subprocess.run([str(python), str(base/'start_nwar.py'), '--stop-dashboard', '--headless'],
                       cwd=base, env=env, check=True)
        for _ in range(40):
            if not state().get('server'):
                break
            time.sleep(.25)
        else:
            raise ValueError('The previous dashboard is still closing.')
    install(app, receipt)
    panel = launcher.launch(config)
    print('Dashboard: '+panel['url'], flush=True)
    run('--dispatch')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=PATCH.parent)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--inspect', action='store_true')
    mode.add_argument('--dispatch', action='store_true')
    args = parser.parse_args()
    if args.inspect or args.dispatch:
        sys.path.insert(0, str(Path.cwd()))
    if args.inspect:
        try:
            print(json.dumps(inspect_workspace()))
        except (OSError, ValueError, RuntimeError) as error:
            print(json.dumps(dict(error=str(error))))
    elif args.dispatch:
        dispatch()
    else:
        start(args.base.resolve())


if __name__ == '__main__':
    try:
        main()
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        message = str(error)
        key = os.environ.get('NWAR_POD_KEY')
        print('HOLD: '+(message.replace(key, '[REDACTED]') if key else message), file=sys.stderr)
        sys.exit(1)
