"""Extend the installed, idle GLHF custom-wave form and solver gate to 15 m."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from contextlib import closing
import sqlite3
import subprocess


def process_identity(pid):
    """Query creation time without opening a protected/reused process handle."""
    if type(pid) is not int or pid<=0:
        return None
    command=(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' -ErrorAction Stop; "
             "if($p){[pscustomobject]@{birth=[string]$p.CreationDate.ToUniversalTime().ToFileTimeUtc();"
             "name=$p.Name}|ConvertTo-Json -Compress}")
    result=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,
                          text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Cannot query the dashboard identity. Close it with Close dashboard.cmd or restart Windows before installing.')
    return json.loads(result.stdout) if result.stdout.strip() else None


def idle(work):
    # Terminal runs retain old PIDs. Inspect the current queue and service owners,
    # never every historical process.json (those PIDs can now belong to Windows).
    database=work/'data/queue.sqlite'
    if database.exists():
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as db:
            if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','deferred','preflight','running','pausing')").fetchone():
                raise ValueError('Workspace has active or pending jobs. Save the run before installing.')
    for path in (work/'data/server.json',work/'data/worker.lock',work/'app/report.lock'):
        if not path.is_file():
            continue
        owner=read(path)
        actual=process_identity(owner.get('pid'))
        if not actual:
            continue
        expected=owner.get('birth')
        # CIM timestamps can lose the last sub-microsecond digit compared with
        # GetProcessTimes. Treat that rounding as the same live owner.
        same=expected is not None and abs(int(actual['birth'])-int(expected))<=10
        if expected and not same:
            continue  # A reused PID belongs to another process, which is untouched.
        if not expected or same:
            raise ValueError('Dashboard or queue service is still active. Run Close dashboard.cmd before installing. No process was stopped.')

POLICY = ('Runs use one GPU solver process and record five complete measured cycles. '
          'Cycle 1 is excluded; cycles 2–5 must pass repeatability and health checks. '
          'The surface-amplitude stop is disabled for all GLHF waves; non-finite values '
          'and the other numerical health checks still stop the run.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False).encode('utf8')


def atomic(path, data):
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def backend(source):
    old = '.25 <= H <= 1.5 and 20 <= L <= 40'
    new = '.25 <= H <= 1.5 and 15 <= L <= 40'
    if source.count(old)+source.count(new) != 1:
        raise ValueError('Unknown custom-wave validation; no files changed.')
    return source.replace(old,new).replace('wavelength 20–40 m.','wavelength 15–40 m.')


def frontend(source):
    match = re.search(r'<form\b[^>]*id="custom-wave-form"[^>]*>.*?</form>',source,re.S)
    if not match:
        raise ValueError('Custom-wave form is missing.')
    form = match.group()
    if len(re.findall(r'id="custom-length"',form)) != 1:
        raise ValueError('Unknown wavelength input.')
    updated, count = re.subn(r'(<input\b[^>]*id="custom-length"[^>]*\bmin=")(?:20|15)(")',r'\g<1>15\2',form)
    if count != 1:
        raise ValueError('Unknown wavelength lower bound.')
    updated = updated.replace('<small>20–40 m</small>','<small>15–40 m</small>')
    notes=list(re.finditer(r'<p class="note">.*?</p>',updated,re.S))
    if not notes or not any(word in notes[-1].group().lower() for word in ('cycles','surface')):
        raise ValueError('Unknown custom-wave policy paragraph.')
    policy=notes[-1]
    updated=updated[:policy.start()]+'<p class="note">'+POLICY+'</p>'+updated[policy.end():]
    return source[:match.start()]+updated+source[match.end():]


def apply(root, patch):
    root, patch = root.resolve(), patch.resolve()
    config = read(root/'launcher.json')
    selected = config.get('release')
    if selected not in ('2602','2606'):
        raise ValueError('Configure the GLHF STAR workspace first.')
    works = []
    for base in (root/'workspaces',Path(config['workspace_root'])):
        for release in ('2602','2606'):
            work = (base/release).resolve()
            if (work/'app').is_dir() and work not in works:
                if read(work/'settings.json').get('release') != release:
                    raise ValueError('Workspace identity differs: '+str(work))
                works.append(work)
    if not any(w.name==selected for w in works):
        raise ValueError('Configured workspace is missing.')
    for work in works:
        idle(work)
    manifest = read(patch/'manifest.json')
    changes = []
    apps = [root/'app']+[w/'app' for w in works]
    for app in apps:
        if not app.is_dir():
            raise ValueError('Package application folder is missing.')
        for name, compiled, receipt in [('NwarWave.java','ok','compile_receipt.json'),
                                        ('NwarBichromatic.java','compiled','bichromatic_w08.json')]:
            target = app/name
            if name=='NwarBichromatic.java' and not target.exists():
                continue
            original = target.read_bytes()
            before_sha = sha(original)
            entry = manifest['variants'].get(before_sha)
            if not entry or entry['macro']!=name or not all(w.name in entry['releases'] for w in works):
                raise ValueError('Unknown macro revision preserved: '+name+' SHA-256 '+before_sha)
            payload = (patch/'payload'/name).read_bytes()
            if sha(payload)!=entry['patched_sha256']:
                raise ValueError('Patch payload checksum failed.')
            receipt_path = app/receipt
            before_receipt = receipt_path.read_bytes()
            info = json.loads(before_receipt.decode('utf-8-sig'))
            if info.get(compiled) is not True or info.get('macro_sha256')!=before_sha:
                raise ValueError('Compilation receipt differs: '+str(target))
            if payload!=original:
                info.update(macro_sha256=sha(payload),glhf_surface_magnitude_limit_disabled=True,
                            custom_wavelength_range_m=[15,40],range_patch=manifest['id'])
                changes += [(target,original,payload),(receipt_path,before_receipt,encode(info))]
        for name, transform in [('index.html',frontend),('custom_waves.py',backend)]:
            target = app/name
            original = target.read_bytes()
            updated = transform(original.decode('utf-8-sig')).encode('utf8')
            if updated!=original:
                changes.append((target,original,updated))
    inventory_path = root/'package_manifest.json'
    original_inventory = inventory_path.read_bytes()
    inventory = json.loads(original_inventory.decode('utf-8-sig'))
    records = {x['path']:x for x in inventory['files']}
    for target,_,payload in changes:
        if target.parent == root/'app':
            key='app/'+target.name
            records[key]=dict(path=key,sha256=sha(payload),bytes=len(payload))
    if not changes:
        return 'Already applied: wavelength 15–40 m; five measured cycles; magnitude cap disabled.'
    inventory.update(files=list(records.values()),total_bytes=sum(x['bytes'] for x in records.values()))
    changes.append((inventory_path,original_inventory,encode(inventory)))
    if any(p.is_symlink() or not p.resolve().is_relative_to(root) and not any(p.resolve().is_relative_to(w) for w in works) for p,_,_ in changes):
        raise ValueError('Linked or out-of-scope target preserved.')
    backup=root/('backup-glhf-15m-'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    backup.mkdir()
    for i,(target,original,_) in enumerate(changes):
        (backup/(str(i)+'_'+target.name)).write_bytes(original)
    (backup/'targets.json').write_bytes(encode([str(p) for p,_,_ in changes]))
    for work in works:
        idle(work)
    if any(p.read_bytes()!=old for p,old,_ in changes):
        raise ValueError('Workspace changed during validation; no application files changed.')
    try:
        for path,_,payload in changes:
            atomic(path,payload)
        if any(p.read_bytes()!=new for p,_,new in changes):
            raise ValueError('Installed checksum differs.')
    except Exception:
        for path,original,_ in reversed(changes):
            atomic(path,original)
        raise
    return 'APPLIED: wavelength 15–40 m. Reopen the dashboard and press Ctrl+F5. Backup: '+str(backup)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    args=parser.parse_args()
    try:
        print(apply(args.root,Path(__file__).parent))
    except Exception as error:
        print('HOLD: '+str(error))
        raise SystemExit(1)
