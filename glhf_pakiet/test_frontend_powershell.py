import unittest,subprocess,json,os
from pathlib import Path
from test_frontend_patch import FrontendPatchTests,ui,ROOT,QA
PS=Path('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
SCRIPT=Path(os.environ.get('NWAR_UI_PS_SCRIPT',str(ROOT/'Update-NWAR-Dashboard-UI2.ps1')))
SPEC=ui.read(Path(os.environ.get('NWAR_UI_PS_MANIFEST',str(ROOT/'NWAR_GLHF_UI_hotfix_v2/frontend_manifest.json'))))
class PowerShellTests(FrontendPatchTests):
 def invoke(self,base):
  p=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(SCRIPT),'-PackageRoot',str(base)],capture_output=True,text=True,errors='replace',timeout=50)
  self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)
  return p
 def test_powershell_while_queue_active_and_controller_marker_present(self):
  for version in ['base','v2','v3','ui1']:
   with self.subTest(version=version):
    base,works=self.fixture('base' if version=='ui1' else version)
    if version=='ui1':ui.apply(base,ROOT/'NWAR_GLHF_UI_hotfix')
    if 'UI3' in SCRIPT.name:
     for app in [base/'app',*[work/'app' for work in works]]:
      p=app/'app.js';p.write_text('// GLHF customized status handling\n'+p.read_text(encoding='utf8'),encoding='utf8')
    before=self.fingerprint(base);self.invoke(base);after=self.fingerprint(base)
    names={item['name'] for item in SPEC['files']}
    allowed={'package_manifest.json'}|{'app/'+name for name in names}|{str((work/'app'/name).relative_to(base)).replace('\\','/') for work in works for name in names}
    changed={name for name in before if before[name]!=after[name]}
    self.assertTrue(changed<=allowed,changed-allowed)
    for item in SPEC['files']:
     self.assertEqual(ui.digest(base/'app'/item['name']),item['sha256'])
     for work in works:self.assertEqual(ui.digest(work/'app'/item['name']),item['sha256'])
    self.invoke(base);self.assertEqual(after,self.fingerprint(base))
 def test_powershell_preserves_unknown_local_ui(self):
  base,_=self.fixture();(base/'app'/('wave_view.js' if 'UI3' in SCRIPT.name else 'app.js')).write_text('local revision');before=self.fingerprint(base)
  p=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(SCRIPT),'-PackageRoot',str(base)],capture_output=True,text=True,errors='replace',timeout=30)
  self.assertNotEqual(p.returncode,0);self.assertEqual(before,self.fingerprint(base))
if __name__=='__main__':
 tests=unittest.TestSuite([PowerShellTests('test_powershell_while_queue_active_and_controller_marker_present'),PowerShellTests('test_powershell_preserves_unknown_local_ui')])
 result=unittest.TextTestRunner(verbosity=2).run(tests)
 (QA/('powershell_ui3_tests.json' if 'UI3' in SCRIPT.name else 'powershell_tests.json')).write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors))),encoding='utf8')
 raise SystemExit(0 if result.wasSuccessful() else 1)
