"""Apply the locally compiled CUSTOM001 free-surface patch to its GLHF workspace."""
import argparse
from contextlib import closing
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile


EXPECTED_ERROR = 'Unphysical free surface at gauge x=-6.0: eta=1.0014672823102977'
MARKER = '// GLHF CUSTOM001 H1.50 L20.0 only'
OVERRIDE = ('   boolean glhfDisableSurfaceLimit=expanded&&caseId.equals("CUSTOM001")&&H==1.5&&lambda==20.0; '
            + MARKER)
OLD_OVERRIDE = ('   if(expanded&&caseId.equals("CUSTOM001")&&H==1.5&&lambda==20.0)'
                'surfaceLimit=2.0; '+MARKER)


def patched_macro(source):
    source = source.replace(OLD_OVERRIDE+'\r\n','').replace(OLD_OVERRIDE+'\n','')
    line = re.search(r'(?m)^   surfaceLimit=expanded[^\r\n]+', source)
    guard = 'Math.abs(eta)>surfaceLimit'
    audit = 'stopPolicy.put("surface_elevation_limit_m",surfaceLimit);'
    if not line or MARKER in source or source.count(guard)!=1 or source.count(audit)!=1:
        raise ValueError('Unexpected free-surface guard in NwarWave.java.')
    newline = '\r\n' if source[line.end():].startswith('\r\n') else '\n'
    source = source[:line.end()]+newline+OVERRIDE+source[line.end():]
    return (source.replace(guard,'(!glhfDisableSurfaceLimit&&'+guard+')')
            .replace(audit,'stopPolicy.put("surface_elevation_limit_m",glhfDisableSurfaceLimit?null:surfaceLimit);'
                           'stopPolicy.put("surface_elevation_limit_disabled",glhfDisableSurfaceLimit);')
            .replace('stopPolicy.put("safety_guards_unchanged",surfaceLimit==1.0)',
                     'stopPolicy.put("safety_guards_unchanged",surfaceLimit==1.0&&!glhfDisableSurfaceLimit)'))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, payload):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as staged:
        staged.write(payload)
        temp = Path(staged.name)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def target_run(data):
    with closing(sqlite3.connect((data/'queue.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        if db.execute("SELECT 1 FROM jobs WHERE status IN ('running','preflight','pausing','queued','deferred')").fetchone():
            raise ValueError('Save and stop any active or pending workspace job before patching.')
        entry = db.execute("SELECT * FROM jobs WHERE case_id='CUSTOM001' ORDER BY created DESC LIMIT 1").fetchone()
    if entry is None or entry['status'] not in ('failed','needs_review','needs_attention'):
        raise ValueError('The latest CUSTOM001 is not the stopped run from the screenshot.')
    spec = json.loads(entry['spec'])
    folder = Path(entry['folder']).resolve()
    if (spec.get('H'),spec.get('L'))!=(1.5,20.) or not folder.is_relative_to((data/'runs').resolve()):
        raise ValueError('CUSTOM001 dimensions or workspace do not match the screenshot.')
    if EXPECTED_ERROR not in read(folder/'macro_error.json').get('error',''):
        raise ValueError('CUSTOM001 has a different error from the screenshot.')
    checkpoint = read(folder/'latest_checkpoint.json')
    checkpoint_path = (folder/checkpoint['file']).resolve()
    if (checkpoint_path.parent!=folder or checkpoint.get('healthy') is not True
            or abs(float(checkpoint['time_s'])-9.4)>1e-7 or checkpoint_path.stat().st_size<400_000_000):
        raise ValueError('The recorded 9.4000 s checkpoint is missing or differs.')
    with (folder/'history.csv').open(encoding='utf-8-sig',newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows or abs(float(rows[-1]['time_s'])-9.824)>1e-7:
        raise ValueError('Saved history does not end at the screenshot time.')
    return entry['id']


def apply(root, manifest, check=False):
    launcher = read(root/'launcher.json')
    release = launcher['release']
    if release not in ('2602','2606'):
        raise ValueError('Select the GLHF STAR workspace in its launcher.')
    work = (Path(launcher['workspace_root'])/release).resolve()
    app, data = work/'app', work/'data'
    macro, receipt = app/'NwarWave.java', app/'compile_receipt.json'
    original = macro.read_bytes()
    receipt_bytes = receipt.read_bytes()
    compile_info = json.loads(receipt_bytes.decode('utf-8-sig'))
    original_sha = digest(original)
    if compile_info.get('macro_sha256')!=original_sha or compile_info.get('ok') is not True:
        raise ValueError('Installed macro differs from its compilation receipt.')
    entry_id = target_run(data)
    applied = compile_info.get('glhf_custom001_surface_limit')
    if applied and applied.get('run_id')==entry_id and applied.get('magnitude_limit_disabled') is True and MARKER.encode() in original:
        return 'Already applied to this GLHF workspace.'
    revised = patched_macro(original.decode('utf-8')).encode('utf-8')
    compiled = manifest['compiled'].get(original_sha, {})
    if compiled.get('patched_sha256')!=digest(revised) or release not in compiled.get('releases', []):
        raise ValueError('This installed macro revision was not compiled for the patch. Send its SHA256 for a matching patch.')
    if check:
        return 'Verified target and compiled macro. Workspace files unchanged.'
    if (data/'worker.lock').exists() or any((data/name).exists() for name in ('STOP','STOP_ALL')):
        raise ValueError('The workspace controller or a STOP marker is still present.')
    process_list = subprocess.run(['tasklist','/fo','csv','/nh'],capture_output=True, text=True,check=True)
    if re.search(r'(?im)^"(?:star-?ccm\+|mpiexec)\.exe"',process_list.stdout):
        raise ValueError('Wait for STAR and MPI processes to close before patching.')
    with tempfile.TemporaryDirectory(prefix='nwar-limit-stage-',dir=work) as staging:
        backup = work/('backup-custom001-no-surface-cap-'+entry_id)
        if backup.exists():
            raise ValueError('A backup for this run exists. Review it before applying again.')
        for path in (macro,receipt):
            shutil.copy2(path,Path(staging)/path.name)
        Path(staging).rename(backup)
        if macro.read_bytes()!=original or receipt.read_bytes()!=receipt_bytes or (data/'worker.lock').exists():
            raise ValueError('The workspace changed during validation.')
        compile_info.update(macro_sha256=digest(revised),glhf_custom001_surface_limit=dict(
            run_id=entry_id,case='CUSTOM001',H_m=1.5,lambda_m=20.0,limit_m=None,magnitude_limit_disabled=True,
            original_macro_sha256=original_sha))
        try:
            atomic_write(macro,revised)
            atomic_write(receipt,json.dumps(compile_info,indent=2).encode('utf-8'))
        except Exception:
            atomic_write(macro,original)
            atomic_write(receipt,receipt_bytes)
            raise
    return f'Disabled the magnitude limit for GLHF CUSTOM001 only. Backup: {backup}'


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        manifest = read(Path(__file__).with_name('custom001_no_surface_cap_manifest.json'))
        print(apply(args.root.resolve(),manifest,args.check))
    except (OSError,ValueError,KeyError,sqlite3.Error,subprocess.CalledProcessError) as exc:
        print('HOLD: '+str(exc))
        raise SystemExit(1)
