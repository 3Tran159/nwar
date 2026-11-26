"""Apply a verified delta to the portable distribution and its idle workspaces."""
from pathlib import Path, PurePosixPath
from contextlib import closing
import argparse, ctypes, datetime, hashlib, json, os, shutil, sqlite3, uuid

PATCH = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def expected_before(entry, current):
    return current in entry.get('allowed_before_sha256', [entry['before_sha256']])


def contained(root, relative):
    part = PurePosixPath(relative)
    if part.is_absolute() or '..' in part.parts or '\\' in relative or ':' in relative:
        raise ValueError('Unsafe patch path.')
    path = root.joinpath(*part.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Patch path leaves its target directory.')
    return path


def process_birth(pid):
    if type(pid) is not int or pid <= 0:
        return None
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    k.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        # Invalid PID means exited; access denied cannot prove that it is idle.
        if k.GetLastError() == 5:
            raise ValueError('Cannot verify process ownership. No files changed.')
        return None
    try:
        code = ctypes.c_ulong()
        if not k.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ValueError('Cannot inspect workspace process.')
        if code.value != 259:
            return None
        times = [ctypes.c_ulonglong() for _ in range(4)]
        if not k.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            raise ValueError('Cannot inspect workspace process identity.')
        return str(times[0].value)
    finally:
        k.CloseHandle(handle)


def idle(work):
    owners = [work/'data/server.json', work/'data/worker.lock', work/'app/report.lock']
    owners += list((work/'data/runs').glob('*/process.json'))
    for path in owners:
        if not path.exists():
            continue
        owner = read(path)
        for field, stamp in [('pid', 'birth'), ('controller_pid', 'controller_birth')]:
            actual = process_birth(owner.get(field))
            if actual and (not owner.get(stamp) or actual == str(owner[stamp])):
                raise ValueError(f'Workspace is active: {work}. Save any run and close its dashboard before applying the patch. Nothing is stopped by this installer.')
    database = work/'data/queue.sqlite'
    if database.exists():
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
            active = connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','preflight','running','pausing','deferred')").fetchone()[0]
        if active:
            raise ValueError(f'Workspace has active or pending jobs: {work}. Save the run and cancel pending requests before applying the patch.')


def workspaces(base, extra_roots=()):
    roots = [base/'workspaces', *map(Path, extra_roots)]
    config = base/'launcher.json'
    if config.exists():
        selected = read(config).get('workspace_root')
        if selected:
            roots.append(Path(selected))
    result = []
    for root in roots:
        for release in ('2602', '2606'):
            work = (root/release).resolve()
            if not (work/'app').is_dir():
                continue
            if read(work/'settings.json').get('release') != release:
                raise ValueError('Workspace release could not be verified: ' + str(work))
            if work not in result:
                result.append(work)
    return result


def apply(base, patch=PATCH, extra_roots=(), dry_run=False):
    base, patch = Path(base).resolve(), Path(patch).resolve()
    spec = read(patch/'patch_manifest.json')
    if not (base/'runtime/python.exe').is_file():
        raise ValueError('Extract this patch folder inside the original NWAR portable folder containing runtime, app and assets.')
    if digest(base/'package_manifest.json') not in spec['allowed_package_manifest_sha256']:
        raise ValueError('This patch requires the original NWAR Windows 2602/2606 package or this same updated version.')
    for entry in spec['files']:
        payload = contained(patch/'payload', entry['path'])
        if digest(payload) != entry['sha256']:
            raise ValueError('Patch file checksum failed: ' + entry['path'])
    works = workspaces(base, extra_roots)
    for work in works:
        idle(work)
    targets = [(base, entry) for entry in spec['files']]
    targets += [(work, entry) for work in works for entry in spec['files'] if entry['path'].startswith('app/')]
    pending = []
    for root, entry in targets:
        target = contained(root, entry['path'])
        current = digest(target) if target.exists() else None
        if current == entry['sha256']:
            continue
        if not expected_before(entry,current):
            raise ValueError('An existing file differs from the supported version: ' + str(target))
        pending.append((root, entry, target))
    # Update the distribution inventory only after all application files.
    pending.sort(key=lambda item: item[1]['path'] == 'package_manifest.json')
    result = dict(patch_id=spec['id'],package=str(base),workspaces=list(map(str, works)),files_to_update=len(pending),dry_run=dry_run,solver_started=False,solver_stopped=False)
    if dry_run or not pending:
        result['already_applied'] = not pending
        return result
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    backups, applied = {}, []
    for root, entry, target in pending:
        backup = contained(root, '.nwar_patch_backups/' + stamp + '/' + entry['path'])
        if target.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
            if digest(backup) != digest(target):
                raise ValueError('Backup verification failed; application files unchanged.')
        backups[str(target)] = backup if target.exists() else None
    for work in works:
        idle(work)
    try:
        for root, entry, target in pending:
            current = digest(target) if target.exists() else None
            if not expected_before(entry,current):
                raise ValueError('A target file changed during patch preparation.')
            temp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(contained(patch/'payload', entry['path']), temp)
                if digest(temp) != entry['sha256']:
                    raise ValueError('Staged patch checksum failed.')
                os.replace(temp, target)
                applied.append(target)
            finally:
                temp.unlink(missing_ok=True)
        for root, entry, target in pending:
            if digest(target) != entry['sha256']:
                raise ValueError('Installed patch verification failed.')
    except Exception:
        for target in reversed(applied):
            backup = backups[str(target)]
            if backup is None:
                target.unlink()
            else:
                shutil.copy2(backup, target)
        raise
    result.update(passed=True,backup_folder=stamp,files_updated=len(applied))
    receipt = contained(base, '.nwar_patch_backups/' + stamp + '/receipt.json')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2), encoding='utf8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, default=PATCH.parent)
    parser.add_argument('--workspace-root', type=Path, action='append', default=[])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(apply(args.package, extra_roots=args.workspace_root, dry_run=args.check), indent=2))
        print('Patch verified. Start NWAR.cmd opens the updated dashboard.')
    except Exception as error:
        print('Patch not applied: ' + str(error))
        raise SystemExit(1)
