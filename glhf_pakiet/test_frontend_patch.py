from pathlib import Path
import importlib.util,json,os,shutil,sqlite3,tempfile,unittest,zipfile
from unittest.mock import patch
ROOT=Path('E:/NWAR_portable_20261103');PATCH=ROOT/'NWAR_GLHF_UI_hotfix';QA=ROOT/'QA_frontend'
spec=importlib.util.spec_from_file_location('ui_updater',PATCH/'apply_frontend_patch.py');ui=importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)
class FrontendPatchTests(unittest.TestCase):
 def fixture(self,version='base'):
  temp=tempfile.TemporaryDirectory(prefix='QA_frontend_',dir=QA);self.addCleanup(temp.cleanup);base=Path(temp.name)
  (base/'runtime').mkdir();(base/'runtime/python.exe').write_bytes(b'not executed')
  with zipfile.ZipFile(ROOT/'NWAR_Windows_2602_2606.zip') as z:
   (base/'package_manifest.json').write_bytes(z.read('NWAR_Windows_2602_2606/package_manifest.json'))
   for name in ui.STATIC:
    p=base/'app'/name;p.parent.mkdir(exist_ok=True);p.write_bytes(z.read('NWAR_Windows_2602_2606/app/'+name))
  if version!='base':
   candidate=ROOT/('QA_v2/patch_candidate' if version=='v2' else 'QA_v3/candidate')
   shutil.copy2(candidate/'package_manifest.json',base/'package_manifest.json')
   for name in ui.STATIC:
    p=candidate/'app'/name
    if p.exists():shutil.copy2(p,base/'app'/name)
  works=[]
  for release in ['2602','2606']:
   work=base/'results'/release;shutil.copytree(base/'app',work/'app');(work/'data/runs/active').mkdir(parents=True)
   (work/'settings.json').write_text(json.dumps(dict(release=release,license_server='preserve-local-license',executable='unchanged/starccm+.exe')))
   (work/'app/worker.py').write_bytes(b'preserved backend')
   (work/'app/NwarWave.java').write_bytes(b'preserved solver macro')
   for path in ['data/worker.lock','data/server.json','data/runs/active/process.json']:(work/path).write_text(json.dumps(dict(pid=os.getpid(),birth='live-test-process',controller_pid=os.getpid())))
   for name in ['history.csv','final.sim','STOP','PAUSE']:(work/'data'/name).write_bytes(b'preserved '+name.encode())
   with sqlite3.connect(work/'data/queue.sqlite') as con:
    con.execute('CREATE TABLE jobs(status TEXT)');con.execute("INSERT INTO jobs VALUES ('running')")
   con.close()
   works.append(work)
  (base/'launcher.json').write_text(json.dumps(dict(workspace_root=str(base/'results'))))
  return base,works
 def fingerprint(self,base):
  return {p.relative_to(base).as_posix():ui.digest(p) for p in base.rglob('*') if p.is_file() and '.nwar_frontend_backups' not in p.parts}
 def test_apply_while_active_preserves_backend_queues_and_results_for_all_versions(self):
  for version in ['base','v2','v3']:
   with self.subTest(version=version):
    base,works=self.fixture(version);before=self.fingerprint(base)
    result=ui.apply(base,PATCH);self.assertTrue(result['passed']);self.assertEqual(result['processes_stopped'],0)
    after=self.fingerprint(base)
    changed={p for p in before if before[p]!=after[p]}
    allowed={str(Path(app).relative_to(base)/name).replace('\\','/') for app in result['apps'] for name in ui.STATIC}|{'package_manifest.json'}
    self.assertTrue(changed<=allowed,changed-allowed)
    self.assertTrue(ui.apply(base,PATCH)['already_applied'])
    self.assertEqual(after,self.fingerprint(base))
 def test_check_is_read_only_even_for_active_queue(self):
  base,_=self.fixture();before=self.fingerprint(base);ui.apply(base,PATCH,dry_run=True);self.assertEqual(before,self.fingerprint(base))
 def test_backend_in_payload_is_rejected(self):
  base,_=self.fixture();bad=base/'bad';shutil.copytree(PATCH,bad)
  data=ui.read(bad/'frontend_manifest.json');data['files'][0]['name']='worker.py';(bad/'frontend_manifest.json').write_text(json.dumps(data))
  before=self.fingerprint(base)
  with self.assertRaisesRegex(ValueError,'six static'):ui.apply(base,bad)
  self.assertEqual(before,self.fingerprint(base))
 def test_unknown_local_ui_is_preserved(self):
  base,_=self.fixture();(base/'app/app.js').write_text('user custom UI');before=self.fingerprint(base)
  with self.assertRaisesRegex(ValueError,'Unknown local UI'):ui.apply(base,PATCH)
  self.assertEqual(before,self.fingerprint(base))
 def test_failed_write_rolls_back_all_ui_and_inventory(self):
  base,_=self.fixture();before=self.fingerprint(base);real=ui.os.replace;count=0
  def fail(source,target):
   nonlocal count
   count+=1
   if count==4:raise OSError('simulated disk failure')
   return real(source,target)
  with patch.object(ui.os,'replace',side_effect=fail):
   with self.assertRaisesRegex(OSError,'simulated'):ui.apply(base,PATCH)
  self.assertEqual(before,self.fingerprint(base))
 def test_payload_checksum_is_checked_before_any_write(self):
  base,_=self.fixture();bad=base/'bad';shutil.copytree(PATCH,bad);(bad/'payload/app.js').write_text('tampered');before=self.fingerprint(base)
  with self.assertRaisesRegex(ValueError,'checksum'):ui.apply(base,bad)
  self.assertEqual(before,self.fingerprint(base))
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FrontendPatchTests))
 (QA/'installer_tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors))),encoding='utf8')
 raise SystemExit(0 if result.wasSuccessful() else 1)
