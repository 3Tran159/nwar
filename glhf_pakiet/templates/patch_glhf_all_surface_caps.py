"""Disable just the surface magnitude limit in installed GLHF wave macros."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess

from patch_glhf_custom001_surface import atomic_write, digest, read


FILES = (('NwarWave.java','compile_receipt.json','ok'),
         ('NwarBichromatic.java','bichromatic_w08.json','compiled'))


def transform(source):
    source=re.sub(r'^   .*// GLHF CUSTOM001 H1\.50 L20\.0 only\r?\n','',source,flags=re.M)
    guards=('!Double.isFinite(eta)||Math.abs(eta)>surfaceLimit',
            '!Double.isFinite(eta)||(!glhfDisableSurfaceLimit&&Math.abs(eta)>surfaceLimit)')
    guard=next((s for s in guards if source.count(s)==1),None)
    audits=('stopPolicy.put("surface_elevation_limit_m",surfaceLimit);',
            'stopPolicy.put("surface_elevation_limit_m",glhfDisableSurfaceLimit?null:surfaceLimit);')
    audit=next((s for s in audits if source.count(s)==1),None)
    if not guard or not audit:
        raise ValueError('Unexpected free-surface guard or audit.')
    return (source.replace(guard,'!Double.isFinite(eta)')
            .replace('stopPolicy.put("surface_elevation_limit_disabled",glhfDisableSurfaceLimit);','')
            .replace(audit,'stopPolicy.put("surface_elevation_limit_m",null);'
                     'stopPolicy.put("surface_elevation_limit_disabled",true);')
            .replace('surfaceLimit==1.0&&!glhfDisableSurfaceLimit','surfaceLimit==1.0')
            .replace('stopPolicy.put("safety_guards_unchanged",surfaceLimit==1.0)',
                     'stopPolicy.put("safety_guards_unchanged",false)'))


def idle(data):
    if (data/'worker.lock').exists():
        raise ValueError('Wait for the existing queue controller to exit.')
    with closing(sqlite3.connect((data/'queue.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute("SELECT 1 FROM jobs WHERE status IN ('running','preflight','pausing','queued','deferred')").fetchone():
            raise ValueError('Save the active run and clear pending jobs before installing.')
    result=subprocess.run(['tasklist','/fo','csv','/nh'],capture_output=True,text=True,check=True)
    if re.search(r'(?im)^"(?:star-?ccm\+|mpiexec)\.exe"',result.stdout):
        raise ValueError('Wait for STAR and MPI processes to exit.')


def apply(root,manifest):
    config=read(root/'launcher.json')
    release=config['release']
    if release not in ('2602','2606'):
        raise ValueError('Select the configured GLHF STAR workspace.')
    work=(Path(config['workspace_root'])/release).resolve()
    app,data=work/'app',work/'data'
    idle(data)
    changes=[]
    configured=[]
    for macro_name,receipt_name,compiled in FILES:
        macro,receipt=app/macro_name,app/receipt_name
        if macro_name=='NwarBichromatic.java' and not (macro.exists() or receipt.exists()):
            continue
        configured.append(macro_name)
        original=macro.read_bytes()
        receipt_bytes=receipt.read_bytes()
        info=json.loads(receipt_bytes.decode('utf-8-sig'))
        original_sha=digest(original)
        if info.get(compiled) is not True or info.get('macro_sha256')!=original_sha:
            raise ValueError('Installed compilation receipt differs for '+macro_name)
        if info.get('glhf_surface_magnitude_limit_disabled') is True:
            continue
        expected=manifest['variants'].get(original_sha,{})
        revised=transform(original.decode('utf-8')).encode('utf-8')
        if (expected.get('macro')!=macro_name or release not in expected.get('releases',[])
                or expected.get('patched_sha256')!=digest(revised)):
            raise ValueError('No compiled patch for '+macro_name+' SHA-256 '+original_sha)
        info.update(macro_sha256=digest(revised),glhf_surface_magnitude_limit_disabled=True)
        changes.extend(((macro,original,revised),(receipt,receipt_bytes,json.dumps(info,indent=2).encode('utf-8'))))
    if not changes:
        return 'Already applied to '+', '.join(configured)
    backup=work/'backup-glhf-all-surface-caps'
    if backup.exists():
        raise ValueError('Existing backup requires review before applying again.')
    backup.mkdir()
    for path,_,_ in changes:
        shutil.copy2(path,backup/path.name)
    idle(data)
    if any(path.read_bytes()!=old for path,old,_ in changes):
        raise ValueError('Workspace files changed during validation.')
    try:
        for path,_,new in changes:
            atomic_write(path,new)
    except Exception:
        for path,old,_ in changes:
            atomic_write(path,old)
        raise
    return 'Applied to '+', '.join(configured)+'. Backup: '+str(backup)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    args=parser.parse_args()
    try:
        manifest=read(Path(__file__).with_name('glhf_all_surface_caps_manifest.json'))
        print(apply(args.root.resolve(),manifest))
    except (OSError,ValueError,KeyError,sqlite3.Error,subprocess.CalledProcessError) as exc:
        print('HOLD: '+str(exc))
        raise SystemExit(1)
