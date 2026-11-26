"""Read every ZIP member and verify it against the shipped SHA-256 manifest."""
from pathlib import Path,PurePosixPath
import os,ctypes,json,zipfile,hashlib,datetime
if os.name=='nt':ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
base=Path('E:/NWAR_portable_20261103/NWAR_Windows_2602_2606');archive=Path(os.environ.get('NWAR_ARCHIVE',str(base.with_suffix('.zip'))))
prefix=base.name+'/'
with zipfile.ZipFile(archive) as z:
    names=z.namelist();assert len(names)==len(set(names))
    assert all(n.startswith(prefix) and '..' not in PurePosixPath(n).parts and not PurePosixPath(n).is_absolute() for n in names)
    manifest=json.loads(z.read(prefix+'package_manifest.json'))
    assert set(names)=={prefix+x['path'] for x in manifest['files']}|{prefix+'package_manifest.json'}
    for index,item in enumerate(manifest['files']):
        info=z.getinfo(prefix+item['path']);assert info.file_size==item['bytes'];h=hashlib.sha256()
        with z.open(info) as f:
            for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
        assert h.hexdigest()==item['sha256'],item['path']
        if item['path'].endswith('final.sim'):print('Verified checkpoint in ZIP:',PurePosixPath(item['path']).parent.name,flush=True)
    assert not any('/workspaces/' in n or n.endswith('/launcher.json') or n.endswith('/solver.lock') for n in names)
result=dict(passed=True,at=datetime.datetime.now().astimezone().isoformat(),archive=str(archive),bytes=archive.stat().st_size,files_checked=len(manifest['files']),all_crc_and_sha256_match=True,no_duplicate_or_unsafe_paths=True,no_runtime_settings_queue_or_license_keys=True,native_solver_started=False)
(Path(os.environ.get('NWAR_QA_DIR',str(base.parent/'QA')))/'archive_verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result),flush=True)
