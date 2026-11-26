"""Verified archive + NTFS directory junctions; never operate on a live run.

The original run path remains readable by unchanged dashboard/lineage code.
Only closed completed runs are eligible. Pauses, failures, source checkpoints
and the explicitly protected W04k case are excluded. No solver controls exist
in this module. Identical large backup files share an NTFS hard link.
"""
from common import *
import argparse
import shutil
import stat
import subprocess

REPARSE = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
LARGE_SUFFIXES = ('.sim', '.simh')


def reparse(path):
    return bool(path.lstat().st_file_attributes & REPARSE)


def fingerprint(path):
    s = path.stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]


def within(path, roots):
    path = path.resolve()
    return any(path != root.resolve() and path.is_relative_to(root.resolve()) for root in roots)


def protected_paths(entries, config):
    protected = {SOURCE.resolve(), Path(read(HERE/'wave_profiles.json').get('source', SOURCE)).resolve()}
    by_id = {j['id']: j for j in entries}
    protected_cases = {j['case_id'] for j in entries
                       if j['status'] in ('running','preflight','pausing','queued')
                       and j['case_id'] in config['protected_case_ids']}
    pending = [j for j in entries if j['status'] in ('running', 'preflight', 'pausing', 'queued')
               or j['case_id'] in protected_cases]
    seen = set()
    while pending:
        j = pending.pop()
        if j['id'] in seen:
            continue
        seen.add(j['id'])
        protected.add(Path(j['folder']).resolve())
        source = j.get('spec', {}).get('source')
        if source:
            protected.add(Path(source).resolve())
        parent = j.get('spec', {}).get('parent_id')
        if parent in by_id:
            pending.append(by_id[parent])
    return protected


def overlaps(path, protected):
    path = path.resolve()
    return any(path == p or path.is_relative_to(p) or p.is_relative_to(path) for p in protected)


def eligible(entry, config, protected):
    p = Path(entry['folder'])
    if (entry['status'] != 'completed'
            or not p.is_dir() or reparse(p) or overlaps(p, protected)
            or not within(p, (RUNS, CLEAN, DATA/'glhf_imports'))):
        return False
    pid, expected = entry.get('controller_pid'), entry.get('controller_birth')
    if expected and birth(pid) == expected:
        return False
    current_entries = jobs()
    if any(j['id'] == entry['id'] and j['status'] != 'completed' for j in current_entries):
        return False
    if any(j['id'] != entry['id'] and Path(j['folder']).resolve() == p.resolve()
           and j['status'] not in ('completed',) for j in current_entries):
        return False
    return True


class Archive:
    def __init__(self, root, apply):
        self.root, self.apply = root.resolve(), apply
        self.state = self.root/'housekeeping'
        self.cache_path = self.state/'verified_hash_cache.json'
        self.cache = read(self.cache_path)
        self.index = {}
        self.actions = []

    def progress(self, **values):
        if self.apply:
            write(self.state/'progress.json', dict(at=now(),pid=os.getpid(),**values))

    def digest(self, path):
        before = fingerprint(path)
        key = ':'.join(map(str, before))
        if key in self.cache:
            return self.cache[key]
        value = sha(path)
        if before != fingerprint(path):
            raise ValueError('File changed during checksum verification: '+str(path))
        self.cache[key] = value
        return value

    def index_backup(self):
        self.progress(phase='verifying_existing_backup')
        for base, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = [n for n in dirs if not reparse(Path(base, n)) and not n.startswith('.staging_')]
            for name in files:
                p = Path(base, name)
                if (p.suffix.lower() in LARGE_SUFFIXES and not reparse(p)
                        and 'evaluation' not in p.name.lower()):
                    key = (p.stat().st_size, self.digest(p))
                    self.index.setdefault(key, p)

    def file(self, src, dst):
        if src.stat().st_size > 100_000_000:
            self.progress(phase='verifying_and_archiving',source=str(src),target=str(dst))
        before = fingerprint(src)
        digest = self.digest(src)
        key = (before[2], digest)
        if dst.exists():
            if self.digest(dst) != digest:
                raise ValueError('Archive destination differs: '+str(dst))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            duplicate = self.index.get(key) if src.suffix.lower() in LARGE_SUFFIXES else None
            # Imported native-save receipts also pin mtime_ns. A hard link may
            # only reuse that timestamp; never change another archived inode.
            if duplicate and duplicate.stat().st_mtime_ns != before[3]:
                duplicate = None
            if duplicate:
                if self.digest(duplicate) != digest:
                    raise ValueError('Backup duplicate changed.')
                os.link(duplicate, dst)
            else:
                if shutil.disk_usage(self.root).free - before[2] < self.reserve:
                    raise ValueError('Insufficient backup reserve; working run preserved.')
                temp = dst.with_name(dst.name+'.copying')
                shutil.copy2(src, temp)
                if self.digest(temp) != digest:
                    raise ValueError('Backup copy failed checksum verification.')
                os.replace(temp, dst)
                if src.suffix.lower() in LARGE_SUFFIXES:
                    self.index[key] = dst
        if before != fingerprint(src):
            raise ValueError('Source changed during archival: '+str(src))
        return dict(bytes=before[2], sha256=digest, fingerprint=before)

    def junction(self, source, target):
        if source.exists() or not target.is_relative_to(self.root):
            raise ValueError('Unexpected junction source/target.')
        # Creation only: no cmd deletion/move commands, no command-line secrets.
        p = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(source), str(target)],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode or not source.is_dir() or not reparse(source) or source.resolve() != target.resolve():
            raise ValueError('Cannot create verified archive directory junction.')

    def purge_retired(self, old, origin):
        # Validate the final absolute delete target, not just its parent.
        if (not old.name.startswith('.nwar_cleanup_retired_') or reparse(old)
                or not within(old, (RUNS, CLEAN, DATA/'glhf_imports'))
                or overlaps(origin, protected_paths(jobs(), self.config))):
            raise ValueError('Retired directory is outside the authorized cleanup scope.')
        if any(reparse(Path(base, name)) for base, dirs, files in os.walk(old) for name in dirs+files):
            raise ValueError('Refusing recursive deletion through a reparse point.')
        shutil.rmtree(old)

    def archive(self, entry):
        source = Path(entry['folder']).absolute()
        target = self.root/'run_archive'/entry['case_id']/entry['id']
        old = source.with_name('.nwar_cleanup_retired_'+entry['id'])
        if not self.apply:
            self.actions.append(dict(action='archive_closed_run', source=str(source), target=str(target)))
            return
        snapshots = {}
        for base, dirs, files in os.walk(source, followlinks=False):
            if any(reparse(Path(base, name)) for name in dirs+files):
                raise ValueError('Run contains an unreviewed reparse point.')
            for name in files:
                src = Path(base, name)
                relative = src.relative_to(source).as_posix()
                snapshots[relative] = self.file(src, target/relative)
        # Recheck the whole source and live queue immediately before mutation.
        if not eligible(entry, self.config, protected_paths(jobs(), self.config)):
            raise ValueError('Run became protected before archive commit.')
        actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
        if actual != set(snapshots) or any(fingerprint(source/n) != proof['fingerprint'] for n, proof in snapshots.items()):
            raise ValueError('Source run changed; no working files removed.')
        manifest = dict(at=now(),job_id=entry['id'],case_id=entry['case_id'],original_path=str(source),
                        target=str(target),files=snapshots,verified=True)
        write(target/'storage_archive_manifest.json', manifest)
        journal = self.state/'transactions'/(entry['id']+'.json')
        write(journal, dict(original=str(source),retired=str(old),target=str(target),phase='backup_verified'))
        if old.exists() or not within(source, (RUNS, CLEAN, DATA/'glhf_imports')):
            raise ValueError('Archive rename scope is invalid.')
        source.rename(old)
        try:
            self.junction(source, target)
        except BaseException:
            if not source.exists():
                old.rename(source)
            raise
        write(journal, dict(original=str(source),retired=str(old),target=str(target),phase='junction_verified'))
        self.purge_retired(old, source)
        write(journal, dict(original=str(source),target=str(target),phase='completed',at=now()))
        self.actions.append(dict(action='archived',job_id=entry['id'],source=str(source),target=str(target),files=len(snapshots)))
        self.publish_final(entry, target)

    def publish_final(self, entry, target):
        """Update the convenient flat final-SIM name only for an accepted run."""
        latest=read(HERE/'latest_report.json')
        audit=read(Path(latest.get('directory',HERE))/'audit.json')
        accepted=next((r for r in audit.get('results',[]) if str(r.get('id'))==entry['id']
                       and r.get('project_accepted') is True),None)
        if not accepted:
            return
        final=next((target/n for n in ('wave_pilot_final.sim','wave_pilot_extended_final.sim') if (target/n).is_file()),None)
        if final is None:
            return
        digest=self.digest(final)
        canonical=self.root/(entry['case_id']+'_final.sim')
        temp=canonical.with_name('.'+canonical.name+'.new')
        if canonical.exists() and self.digest(canonical)==digest:
            return
        if temp.exists():
            raise ValueError('Unexpected pending final-SIM publication.')
        os.link(final,temp)
        os.replace(temp,canonical)
        self.actions.append(dict(action='published_final',case=entry['case_id'],file=str(canonical),sha256=digest))

    def old_reports(self):
        latest = read(HERE/'latest_report.json')
        current = Path(latest.get('directory', HERE)).resolve()
        if (not (current/'report.html').is_file() or latest.get('errors')
                or not within(current, (Path(read(HERE/'report_storage.json')['final_directory']),))):
            return
        lock = read(HERE/'report.lock')
        if lock.get('birth') and birth(lock.get('pid')) == lock['birth']:
            return
        root = (HERE/'reports').resolve()
        for p in root.iterdir():
            import re
            complete = (p/'audit.json').is_file() and (p/'report.html').is_file()
            partial = (p.is_dir() and p.stat().st_mtime < time.time()-86400
                       and (p/'C01_forces.png').is_file() and (p/'C01_forces.svg').is_file()
                       and any(p.glob('W*_validation.json'))
                       and all(f.is_file() and f.suffix.lower() in
                               ('.png','.svg','.csv','.json','.html','.pdf','.zip','.mat','.m','.txt')
                               for f in p.iterdir()))
            if (not re.fullmatch(r'\d{8}_\d{6}_[0-9a-f]{6}', p.name) or not p.is_dir()
                    or reparse(p) or p.resolve() == current or p.resolve().parent != root
                    or not (complete or partial)):
                continue
            size = sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
            self.actions.append(dict(action='delete_obsolete_report',path=str(p),bytes=size))
            if self.apply:
                if any(reparse(Path(base, name)) for base, dirs, files in os.walk(p) for name in dirs+files):
                    raise ValueError('Report contains a reparse point.')
                shutil.rmtree(p)

    def recover_transactions(self):
        for journal in (self.state/'transactions').glob('*.json'):
            t = read(journal)
            if t.get('phase') == 'completed':
                continue
            source, target = Path(t['original']), Path(t['target'])
            old = Path(t['retired'])
            lexical_scope = any(source.absolute().is_relative_to(r.absolute())
                                and source.absolute() != r.absolute() for r in (RUNS,CLEAN,DATA/'glhf_imports'))
            if (not lexical_scope or source.parent.resolve() != source.parent.absolute()
                    or old != source.with_name('.nwar_cleanup_retired_'+target.name)
                    or not target.resolve().is_relative_to(self.root)
                    or overlaps(source, protected_paths(jobs(), self.config))):
                continue
            if not old.exists():
                continue
            manifest = read(target/'storage_archive_manifest.json')
            if manifest.get('verified') is not True or manifest.get('original_path') != str(source):
                raise ValueError('Incomplete archive recovery proof.')
            for n, proof in manifest['files'].items():
                dst = (target/n).resolve()
                if not dst.is_relative_to(target.resolve()) or self.digest(dst) != proof['sha256']:
                    raise ValueError('Archive recovery integrity failure.')
            if not source.exists():
                self.junction(source,target)
            if not reparse(source) or source.resolve() != target.resolve():
                raise ValueError('Archive recovery path has an unexpected owner.')
            self.purge_retired(old,source)
            write(journal,dict(original=str(source),target=str(target),phase='completed',at=now()))


def cleanup(apply=False):
    config = read(HERE/'storage_cleanup.json')
    if not config.get('enabled'):
        return dict(status='disabled')
    root = Path(config['backup_root'])
    if not root.is_dir() or str(root.drive).upper() != 'H:':
        raise ValueError('Expected backup drive is unavailable; no files changed.')
    archive = Archive(root, apply)
    archive.config, archive.reserve = config, config['minimum_backup_free_GiB']*2**30
    if apply:
        archive.state.mkdir(exist_ok=True)
    lock = archive.state/'cleanup.lock'
    owner = read(lock)
    if owner and birth(owner.get('pid')) == owner.get('birth'):
        return dict(status='already_running')
    token = uuid.uuid4().hex
    if apply:
        if lock.exists():
            if not owner.get('birth') or birth(owner.get('pid')) is not None:
                raise ValueError('Cannot prove old cleanup lock owner has exited.')
            lock.unlink()
        with lock.open('x',encoding='utf8') as stream:
            json.dump(dict(pid=os.getpid(),birth=birth(os.getpid()),token=token),stream)
    errors=[]
    try:
        if apply:
            archive.recover_transactions()
            archive.index_backup()
        entries = jobs()
        candidates = [j for j in entries if eligible(j, config, protected_paths(entries, config))]
        for case, folder in EXISTING.items():
            done = read(folder/'completed.json').get('status')
            legacy = dict(id='legacy_'+case,case_id=case,folder=str(folder),status='completed')
            if (done in ('target_reached','four_cycles_repeated','five_cycles_repeated','five_cycles_recorded')
                    and eligible(legacy, config, protected_paths(entries, config))):
                candidates.append(legacy)
        latest = read(HERE/'latest_report.json')
        audit = read(Path(latest.get('directory', HERE))/'audit.json')
        seen = {Path(j['folder']).resolve() for j in candidates}
        for r in audit.get('results', []):
            if not r.get('project_accepted') or not r.get('folder'):
                continue
            entry = dict(id=str(r['id']),case_id=r['case'],folder=r['folder'],status='completed')
            import_root = (DATA/'glhf_imports').absolute()
            folder = Path(entry['folder']).absolute()
            if folder.is_relative_to(import_root):
                # path_under() validates every imported segment against the
                # resolved package root. Preserve the whole import boundary.
                entry['folder'] = str(import_root/folder.relative_to(import_root).parts[0])
                entry['id'] += '_import_root'
            if Path(entry['folder']).resolve() not in seen and eligible(entry, config, protected_paths(entries, config)):
                candidates.append(entry);seen.add(Path(entry['folder']).resolve())
        for entry in candidates:
            try:
                archive.archive(entry)
                if apply:write(archive.cache_path,archive.cache)
            except (OSError,ValueError) as ex:
                errors.append(dict(id=entry['id'],error=str(ex)))
        archive.old_reports()
        result=dict(at=now(),applied=apply,actions=archive.actions,errors=errors,protected_cases=config['protected_case_ids'],
                    disk_free_GiB={d:round(shutil.disk_usage(d+':/').free/2**30,2) for d in ('C','E','H')})
        if apply:
            write(archive.cache_path,archive.cache)
            write(archive.state/'latest_cleanup.json',result)
            write(archive.state/('cleanup_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'),result)
            archive.progress(phase='finished',actions=len(archive.actions),errors=len(errors))
        return result
    finally:
        if apply and read(lock).get('token') == token:
            lock.unlink()


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    # Low-priority background disk work; MINI CPUs 22/23 and solver CPU11 untouched.
    k=ctypes.windll.kernel32;k.SetPriorityClass(k.GetCurrentProcess(),0x4000)
    k.SetProcessAffinityMask(k.GetCurrentProcess(),1 << 20)
    try:
        result=cleanup(args.apply)
    except Exception as ex:
        write(DATA/'storage_cleanup_error.json',dict(at=now(),error=str(ex)))
        if sys.stderr is not None:print(str(ex),file=sys.stderr)
        raise SystemExit(1)
    if not result.get('errors'):
        (DATA/'storage_cleanup_error.json').unlink(missing_ok=True)
    if sys.stdout is not None:
        print(json.dumps(dict(applied=result.get('applied'),status=result.get('status'),actions=len(result.get('actions',[])),errors=result.get('errors',[]),disk_free_GiB=result.get('disk_free_GiB')),ensure_ascii=False))
    if result.get('errors'):raise SystemExit(1)
