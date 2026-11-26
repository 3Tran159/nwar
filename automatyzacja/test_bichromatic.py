import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
from datetime import datetime,timedelta
import bichromatic as b
from common import write,period
from cycle_policy import selection
from advance_wave_queue import choose_case

class BichromaticTests(unittest.TestCase):
 def test_direct_w06_route_preserves_acceptance_gate(self):
  entries=[dict(id='W04',case_id='W04',status='completed',created='1',spec={})]
  cy=dict(count=5,repeatable=True,**selection([dict(number=i) for i in range(1,6)]))
  proof=lambda j:(dict(project_accepted=True,run_verification='passed'),dict(health=dict(ok=True),cycles=cy))
  self.assertEqual(choose_case(['W04','W06'],entries,proof)['case'],'W06')
  entries[0]['status']='running'
  self.assertEqual(choose_case(['W04','W06'],entries,proof)['status'],'waiting_wave')

 def test_optional_wave_skips_when_no_night_time_and_never_enqueues(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);write(root/'plan.json',dict(night_deadline=(datetime.now().astimezone()-timedelta(seconds=1)).isoformat()))
   with patch.object(b,'PLAN',root/'plan.json'),patch.object(b,'jobs',return_value=[]),patch.object(b,'enqueue') as enqueue:
    self.assertEqual(b.followup(dict(id='test'),True)['optional_w08'],'skipped_night_finished')
    enqueue.assert_not_called()

 def test_duration_uses_difference_frequency_not_single_carrier(self):
  beat=1/abs(1/period(20)-1/period(30))
  self.assertGreater(b.duration(),5*beat)
  self.assertNotAlmostEqual(beat,period(30))

 def test_definition_matches_existing_baselines_and_remains_diagnostic(self):
  c=b.case();self.assertEqual(c['H'],1.)
  self.assertEqual([(x['baseline'],x['H_m'],x['lambda_m'],x['phase_deg']) for x in c['components']],[('W01',.5,20.,0),('W03',.5,30.,0)])
  self.assertTrue(c['diagnostic_only'])
  self.assertIn('existing',c)
  source=Path(__file__).with_name('NwarBichromatic.java').read_text(encoding='utf8')
  self.assertIn('SuperpositionVofWave',source)
  self.assertIn('FirstOrderSuperposingVofWave',source)
  self.assertNotIn('initializeSolution',source)
  self.assertIn('interCFL>2.2||CFL>25',source)

if __name__=='__main__':unittest.main()
