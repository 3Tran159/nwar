from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'nwar_portable/templates'))
import patch_glhf_15m as installer
PACKAGE=Path('E:/NWAR_portable_20261103/NWAR_GLHF_15m_Waves_v2')
OLD=PACKAGE.parent/'NWAR_GLHF_Transfer_v4/engine'


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.work=self.root/'workspaces/2606'
        self.work.mkdir(parents=True)
        (self.root/'launcher.json').write_text(json.dumps(dict(release='2606',workspace_root=str(self.root/'workspaces'))))
        (self.work/'settings.json').write_text(json.dumps(dict(release='2606')))
        (self.work/'data').mkdir()
        with closing(sqlite3.connect(self.work/'data/queue.sqlite')) as db:
            db.execute('CREATE TABLE jobs(status TEXT)')
            db.commit()
        for app in (self.root/'app',self.work/'app'):
            app.mkdir()
            for name in ('NwarWave.java','custom_waves.py','index.html'):
                shutil.copy2(OLD/name,app/name)
            info=dict(ok=True,macro_sha256=installer.sha((app/'NwarWave.java').read_bytes()))
            (app/'compile_receipt.json').write_bytes(installer.encode(info))
        (self.root/'package_manifest.json').write_bytes(installer.encode(dict(files=[
            dict(path='app/'+p.name,sha256=installer.sha(p.read_bytes()),bytes=p.stat().st_size)
            for p in (self.root/'app').iterdir()])))

    def fingerprint(self):
        return {str(p.relative_to(self.root)):installer.sha(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}

    def test_apply_twice_and_validation(self):
        self.assertIn('APPLIED',installer.apply(self.root,PACKAGE))
        before=self.fingerprint()
        self.assertIn('Already applied',installer.apply(self.root,PACKAGE))
        self.assertEqual(before,self.fingerprint())
        app=self.work/'app'
        source=(app/'custom_waves.py').read_text(encoding='utf8')
        import ast
        tree=ast.parse(source)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='dimensions')
        scope=dict(number=lambda x:float(x) if x is not None else None)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'dimensions','exec'),scope)
        for h,l in [(1.,15.),(.25,40.),(1.5,15.)]:
            self.assertEqual(scope['dimensions'](h,l),(h,l))
        for h,l in [(1,14.999),(1,40.001),(.249,15),(1.501,15),(True,15),(1,float('nan'))]:
            with self.assertRaises(ValueError):scope['dimensions'](h,l)
        html=(app/'index.html').read_text(encoding='utf8')
        self.assertIn('id="custom-length" type="number" min="15"',html)
        self.assertIn('five complete measured cycles',html)
        self.assertIn('surface-amplitude stop is disabled',html)
        self.assertNotIn('custom waves retain ±1.0 m',html)
        inventory=installer.read(self.root/'package_manifest.json')
        for record in inventory['files']:
            self.assertEqual(record['sha256'],installer.sha((self.root/record['path']).read_bytes()))

    def test_active_job_no_mutations(self):
        with closing(sqlite3.connect(self.work/'data/queue.sqlite')) as db:
            db.execute("INSERT INTO jobs VALUES ('running')")
            db.commit()
        before=self.fingerprint()
        with self.assertRaisesRegex(ValueError,'active or pending'):
            installer.apply(self.root,PACKAGE)
        self.assertEqual(before,self.fingerprint())

    def test_historical_protected_pid_ignored(self):
        folder=self.work/'data/runs/old'
        folder.mkdir(parents=True)
        (folder/'process.json').write_text(json.dumps(dict(pid=4,birth='123')))
        with patch.object(installer,'process_identity',side_effect=AssertionError('Historical PID queried')):
            self.assertIn('APPLIED',installer.apply(self.root,PACKAGE))

    def test_reused_owner_pid_ignored(self):
        (self.work/'data/server.json').write_text(json.dumps(dict(pid=4,birth='123')))
        with patch.object(installer,'process_identity',return_value=dict(birth='456',name='System')):
            self.assertIn('APPLIED',installer.apply(self.root,PACKAGE))

    def test_live_dashboard_no_mutations(self):
        (self.work/'data/server.json').write_text(json.dumps(dict(pid=777,birth='123')))
        before=self.fingerprint()
        with patch.object(installer,'process_identity',return_value=dict(birth='123',name='python.exe')):
            with self.assertRaisesRegex(ValueError,'still active'):
                installer.apply(self.root,PACKAGE)
        self.assertEqual(before,self.fingerprint())

    def test_live_dashboard_cim_rounding_no_mutations(self):
        (self.work/'data/server.json').write_text(json.dumps(dict(pid=777,birth='134386391331751421')))
        before=self.fingerprint()
        with patch.object(installer,'process_identity',return_value=dict(birth='134386391331751420',name='python.exe')):
            with self.assertRaisesRegex(ValueError,'still active'):
                installer.apply(self.root,PACKAGE)
        self.assertEqual(before,self.fingerprint())

    def test_unknown_macro_no_mutations(self):
        path=self.work/'app/NwarWave.java'
        path.write_bytes(path.read_bytes()+b'\n// local change\n')
        before=self.fingerprint()
        with self.assertRaisesRegex(ValueError,'Unknown macro'):
            installer.apply(self.root,PACKAGE)
        self.assertEqual(before,self.fingerprint())

    def test_rollback(self):
        originals={p:p.read_bytes() for p in [*self.root.glob('app/*'),*self.work.glob('app/*'),self.root/'package_manifest.json']}
        real=installer.atomic
        calls=0
        def fail_once(path,data):
            nonlocal calls
            calls+=1
            if calls==3:raise OSError('test failure')
            real(path,data)
        with patch.object(installer,'atomic',fail_once):
            with self.assertRaisesRegex(OSError,'test failure'):
                installer.apply(self.root,PACKAGE)
        self.assertTrue(all(p.read_bytes()==old for p,old in originals.items()))


if __name__=='__main__':unittest.main()
