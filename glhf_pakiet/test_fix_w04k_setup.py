"""Reproduce the GLHF pre-solver folder failure without launching STAR."""
from pathlib import Path
import importlib.util,json,tempfile,unittest

spec=importlib.util.spec_from_file_location('setup_fix',Path(__file__).parent/'templates/fix_w04k_gpu.py')
fix=importlib.util.module_from_spec(spec);spec.loader.exec_module(fix)

class SetupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  (self.root/'state').mkdir();(self.root/'seed').mkdir();(self.root/'seed/checkpoint.sim').write_bytes(b'original healthy save')
  self.pin={'checkpoint_sha256':fix.sha(self.root/'seed/checkpoint.sim')}
  self.state={'state':'HOLD','time_s':14.064,'source_time_s':14.064,
              'message':"[WinError 3] The system cannot find the path specified: '"+str(self.root/'work/W04k')+"'"}
  self.put('manifest.json',{'time_s':14.064})
  self.put('state/run_state.json',self.state);self.put('state/error.json',self.state)
 def tearDown(self):self.temp.cleanup()
 def put(self,name,data):(self.root/name).write_text(json.dumps(data),encoding='utf8')
 def rejected(self):
  with self.assertRaises(ValueError):fix.recover_missing_work(self.root,self.pin)
  self.assertTrue((self.root/'state/run_state.json').exists())
 def test_exact_startup_failure_is_archived_and_retry_is_idempotent(self):
  self.assertTrue(fix.recover_missing_work(self.root,self.pin))
  self.assertFalse(fix.recover_missing_work(self.root,self.pin))
  self.assertTrue((self.root/'work').is_dir());self.assertFalse((self.root/'work/W04k').exists())
  self.assertEqual((self.root/'seed/checkpoint.sim').read_bytes(),b'original healthy save')
  self.assertEqual(len(list((self.root/'hotfix_backups').glob('*/run_state.json'))),1)
 def test_existing_solver_work_is_preserved(self):
  (self.root/'work/W04k').mkdir(parents=True);self.rejected()
 def test_manual_pause_is_preserved(self):
  (self.root/'state/PAUSE').write_text('user');self.rejected()
 def test_changed_checkpoint_is_preserved_and_blocked(self):
  (self.root/'seed/checkpoint.sim').write_bytes(b'changed');self.rejected()
 def test_advanced_physical_time_is_not_recovered(self):
  self.put('state/run_state.json',dict(self.state,time_s=14.065));self.rejected()
 def test_solver_error_is_not_recovered(self):
  self.put('state/error.json',dict(self.state,message='Solver disconnected'));self.rejected()
 def test_fresh_package_can_create_nested_work_folder(self):
  (self.root/'work/W04k').mkdir(parents=True,exist_ok=False)
  self.assertTrue((self.root/'work/W04k').is_dir())
 def test_actual_windows_missing_directory_exception_is_recovered(self):
  try:(self.root/'work/W04k').mkdir(exist_ok=False)
  except FileNotFoundError as e:message=str(e)
  else:self.fail('Expected a real missing-parent Windows error')
  self.assertIn('[WinError 3]',message)
  self.put('state/error.json',dict(self.state,message=message))
  self.assertTrue(fix.recover_missing_work(self.root,self.pin))

if __name__=='__main__':unittest.main()
