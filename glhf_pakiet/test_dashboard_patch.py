"""Installer tests use small disposable replicas, never a real campaign."""
from pathlib import Path
from unittest.mock import patch
import importlib.util, json, shutil, sqlite3, unittest, uuid, zipfile, os

ROOT=Path('E:/NWAR_portable_20261103')
PATCH=Path(os.environ.get('NWAR_PATCH_TEST_PATH',str(ROOT/'NWAR_patch_v2')))
QA=Path(os.environ.get('NWAR_PATCH_TEST_QA',str(ROOT/'QA_v2')))
spec=importlib.util.spec_from_file_location('updater',PATCH/'apply_dashboard_patch.py')
updater=importlib.util.module_from_spec(spec);spec.loader.exec_module(updater)
MANIFEST=updater.read(PATCH/'patch_manifest.json')


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.base=QA/'installer_tests'/uuid.uuid4().hex
        self.base.mkdir(parents=True)
        (self.base/'runtime').mkdir();(self.base/'runtime/python.exe').write_bytes(b'test placeholder; never executed')
        with zipfile.ZipFile(ROOT/'NWAR_Windows_2602_2606.zip') as z:
            for entry in MANIFEST['files']:
                if entry['before_sha256'] is None:continue
                path=self.base/entry['path'];path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(z.read('NWAR_Windows_2602_2606/'+entry['path']))
        self.works=[]
        for release in ('2602','2606'):
            work=self.base/'workspaces'/release;work.mkdir(parents=True)
            (work/'settings.json').write_text(json.dumps(dict(release=release)),encoding='utf8')
            for entry in MANIFEST['files']:
                if entry['path'].startswith('app/'):
                    target=work/entry['path'];target.parent.mkdir(parents=True,exist_ok=True)
                    if (self.base/entry['path']).exists():shutil.copy2(self.base/entry['path'],target)
            data=work/'data';data.mkdir()
            with sqlite3.connect(data/'queue.sqlite') as con:
                con.execute('CREATE TABLE jobs(status TEXT)');con.execute("INSERT INTO jobs VALUES ('cancelled')")
            (data/'preserved-results.sim').write_bytes(b'Untouched simulation results')
            self.works.append(work)
        self.initial=self.fingerprint()

    def fingerprint(self):
        return {p.relative_to(self.base).as_posix():updater.digest(p) for p in self.base.rglob('*') if p.is_file() and '.nwar_patch_backups' not in p.parts}

    def test_apply_both_versions_preserves_data_and_is_idempotent(self):
        result=updater.apply(self.base,PATCH)
        self.assertTrue(result['passed']);self.assertEqual(len(result['workspaces']),2)
        for entry in MANIFEST['files']:
            self.assertEqual(updater.digest(self.base/entry['path']),entry['sha256'])
            if entry['path'].startswith('app/'):
                for work in self.works:self.assertEqual(updater.digest(work/entry['path']),entry['sha256'])
        for name,digest in self.initial.items():
            if '/data/' in name:self.assertEqual(updater.digest(self.base/name),digest)
        after=self.fingerprint();again=updater.apply(self.base,PATCH)
        self.assertTrue(again['already_applied']);self.assertEqual(self.fingerprint(),after)
        for entry in MANIFEST['files']:
            if entry['before_sha256']:
                backup=self.base/'.nwar_patch_backups'/result['backup_folder']/entry['path']
                self.assertEqual(updater.digest(backup),entry['before_sha256'])

    def test_check_is_read_only(self):
        result=updater.apply(self.base,PATCH,dry_run=True)
        self.assertGreater(result['files_to_update'],0);self.assertEqual(self.fingerprint(),self.initial)
        self.assertFalse((self.base/'.nwar_patch_backups').exists())

    def test_active_owner_blocks_before_changes(self):
        owner=self.works[0]/'data/worker.lock'
        owner.write_text(json.dumps(dict(pid=123,birth='verified-birth')),encoding='utf8')
        before=self.fingerprint()
        with patch.object(updater,'process_birth',side_effect=lambda pid:'verified-birth' if pid==123 else None):
            with self.assertRaisesRegex(ValueError,'active'):updater.apply(self.base,PATCH)
        self.assertEqual(self.fingerprint(),before)
        self.assertFalse((self.base/'.nwar_patch_backups').exists())

    def test_active_queue_blocks_without_changing_it(self):
        with sqlite3.connect(self.works[0]/'data/queue.sqlite') as con:con.execute("INSERT INTO jobs VALUES ('running')")
        before=self.fingerprint()
        with self.assertRaisesRegex(ValueError,'active or pending'):updater.apply(self.base,PATCH)
        self.assertEqual(self.fingerprint(),before)

    def test_local_edit_is_not_overwritten(self):
        (self.base/'app/portable_runtime.py').write_text('local customized runtime',encoding='utf8')
        before=self.fingerprint()
        with self.assertRaisesRegex(ValueError,'differs'):updater.apply(self.base,PATCH)
        self.assertEqual(self.fingerprint(),before)

    def test_tampered_payload_blocks_before_changes(self):
        bad=QA/'installer_tests'/('bad_patch_'+uuid.uuid4().hex);shutil.copytree(PATCH,bad)
        (bad/'payload/app/portable_runtime.py').write_text('corrupt',encoding='utf8')
        with self.assertRaisesRegex(ValueError,'checksum'):updater.apply(self.base,bad)
        self.assertEqual(self.fingerprint(),self.initial)

    def test_write_failure_rolls_back_both_distribution_and_workspace(self):
        real=updater.os.replace;count=0
        def fail_on_workspace(source,target):
            nonlocal count
            count+=1
            if count==11:raise OSError('simulated write failure')
            return real(source,target)
        with patch.object(updater.os,'replace',side_effect=fail_on_workspace):
            with self.assertRaisesRegex(OSError,'simulated'):updater.apply(self.base,PATCH)
        self.assertEqual(self.fingerprint(),self.initial)

    def test_already_updated_package_can_update_an_old_workspace(self):
        updater.apply(self.base,PATCH)
        old=ROOT/'QA_v2/before_update/app/portable_runtime.py'
        shutil.copy2(old,self.works[1]/'app/portable_runtime.py')
        result=updater.apply(self.base,PATCH)
        self.assertEqual(result['files_updated'],1)

    def test_unknown_package_and_unsafe_paths_are_rejected(self):
        with self.assertRaises(ValueError):updater.contained(self.base,'../outside')
        with self.assertRaises(ValueError):updater.contained(self.base,'C:/outside')
        (self.base/'package_manifest.json').write_text('{}',encoding='utf8')
        before=self.fingerprint()
        with self.assertRaisesRegex(ValueError,'requires the original'):updater.apply(self.base,PATCH)
        self.assertEqual(self.fingerprint(),before)

    def test_upgrade_from_v2_preserves_data(self):
        if 'allowed_before_sha256' not in MANIFEST['files'][0]:self.skipTest('v3-only input variant')
        previous=ROOT/'NWAR_patch_v2'
        for entry in updater.read(previous/'patch_manifest.json')['files']:
            source=previous/'payload'/entry['path'];target=self.base/entry['path']
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            if entry['path'].startswith('app/'):
                for work in self.works:
                    target=work/entry['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        old_data=[updater.digest(work/'data/preserved-results.sim') for work in self.works]
        result=updater.apply(self.base,PATCH)
        self.assertTrue(result['passed'])
        self.assertEqual(old_data,[updater.digest(work/'data/preserved-results.sim') for work in self.works])
        self.assertTrue(updater.apply(self.base,PATCH)['already_applied'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PatchTests))
    (QA/'patch_installer_checks.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),real_solver_started=False,disposable_replicas_only=True),indent=2),encoding='utf8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
