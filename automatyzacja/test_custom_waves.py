import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import common, custom_waves as custom


class CustomWaveTests(unittest.TestCase):
    def test_range_and_nonfinite_rejected(self):
        for pair in [(0,20),(.24,30),(1.50001,40),(1,19.9),(1,40.1),(float('nan'),30),(1,float('inf')),(True,20)]:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                custom.dimensions(*pair)
        self.assertEqual(custom.dimensions(1.5,40),(1.5,40))

    def test_real_queue_is_deferred_idempotent_and_uses_pre(self):
        profile=dict(source='verified/PRE/final.sim',source_sha='pinned-pre-sha',source_time=5.8)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root=Path(tmp)
            stack.enter_context(patch.object(common,'DATA',root))
            stack.enter_context(patch.object(common,'RUNS',root/'runs'))
            stack.enter_context(patch.object(custom,'REGISTRY',root/'custom.json'))
            stack.enter_context(patch('wave_profiles.approved_profile',return_value=profile))
            id=custom.submit(1.5,40,'test-custom-request')
            self.assertEqual(custom.submit(1.5,40,'test-custom-request'),id)
            self.assertEqual(len(common.jobs()),1)
            j=common.job(id)
            self.assertEqual(j['status'],'deferred')
            self.assertEqual(j['spec']['mpi_processes'],1)
            self.assertEqual(j['spec']['source'],profile['source'])
            self.assertEqual(j['spec']['stop_kind'],'five_cycles')
            self.assertEqual(j['spec']['wait_for_campaign_id'],'nwar-night-20261102_original')
            self.assertEqual(j['spec']['campaign_id'],'custom-waves-original')
            self.assertIsNone(j['spec'].get('reference_id'))
            self.assertFalse(Path(j['folder']).exists())
            with self.assertRaises(ValueError):custom.submit(1,30,'test-custom-request')
            with self.assertRaises(ValueError):custom.submit(1.5,40,'another-request')
            with self.assertRaises(ValueError):common.enqueue(j['case_id'],mpi_processes=2)

    def test_all_four_wave_proofs_required_and_latest_failure_blocks(self):
        entries=[dict(id=c,case_id=c,created='1',status='completed',spec=dict(campaign_id='campaign')) for c in custom.SEQUENCE]
        from cycle_policy import selection
        def valid(j):
            cycles=dict(repeatable=True,count=5,**selection([dict(number=i) for i in range(1,6)]))
            return dict(project_accepted=True,run_verification='passed'),dict(health=dict(ok=True),cycles=cycles)
        self.assertTrue(custom.campaign_complete('campaign',entries,valid))
        self.assertFalse(custom.campaign_complete('campaign',entries[:-1],valid))
        self.assertFalse(custom.campaign_complete('different',entries,valid))
        self.assertFalse(custom.campaign_complete('campaign',entries,lambda j:(valid(j)[0],dict(health=dict(ok=True),cycles=dict(repeatable=True,count=3)))))
        entries.append(dict(entries[-1],id='new',created='2',status='failed'))
        self.assertFalse(custom.campaign_complete('campaign',entries,valid))

    def test_local_route_does_not_require_glhf_waves(self):
        sequence=['W04','W02','W03','W06']
        entries=[dict(id=c,case_id=c,created='1',status='completed',spec=dict(campaign_id='local')) for c in sequence]
        from cycle_policy import selection
        cycles=dict(repeatable=True,count=5,**selection([dict(number=i) for i in range(1,6)]))
        def proof(entry):
            return dict(project_accepted=True,run_verification='passed'),dict(health=dict(ok=True),cycles=cycles)
        self.assertTrue(custom.campaign_complete('local',entries,proof,sequence))
        self.assertFalse(custom.campaign_complete('local',entries[:-1],proof,sequence))

    def test_release_promotes_once_only_when_worker_is_free(self):
        profile=dict(source='verified/PRE/final.sim',source_sha='pinned-pre-sha',source_time=5.8)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root=Path(tmp)
            for module,attribute,value in [(common,'DATA',root),(common,'RUNS',root/'runs'),(custom,'DATA',root),(custom,'REGISTRY',root/'custom.json'),(custom,'STOPS',[]),(custom,'SOLVER_LOCKS',[]),(custom,'OTHER_LOCKS',[])]:
                stack.enter_context(patch.object(module,attribute,value))
            stack.enter_context(patch('pre_w04.PRE',root/'pre'))
            stack.enter_context(patch('wave_profiles.approved_profile',return_value=profile))
            stack.enter_context(patch('cpu_coexistence.check',return_value=None))
            stack.enter_context(patch.object(custom,'campaign_complete',return_value=True))
            id=custom.submit(1,25,'release-request')
            common.write(root/'worker.lock',dict(pid=1,birth='live'))
            with patch.object(custom,'birth',return_value='live'):
                self.assertIsNone(custom.release_next())
                self.assertEqual(common.job(id)['status'],'deferred')
            with patch.object(custom,'birth',return_value=None):
                self.assertEqual(custom.release_next(),id)
                self.assertEqual(common.job(id)['status'],'queued')
                self.assertIsNone(custom.release_next())

    def test_pause_is_preserved_and_no_promotion_before_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root=Path(tmp);(root/'PAUSE').write_text('user pause')
            pending=dict(id='custom',status='deferred',case_id='CUSTOM001',created='1',spec=dict(custom=True,wait_for_campaign_id='campaign'))
            stack.enter_context(patch.object(custom,'DATA',root))
            stack.enter_context(patch.object(custom,'STOPS',[]))
            stack.enter_context(patch.object(custom,'SOLVER_LOCKS',[]))
            stack.enter_context(patch.object(custom,'OTHER_LOCKS',[]))
            stack.enter_context(patch.object(custom,'jobs',return_value=[pending]))
            with patch.object(custom,'connection') as connection:
                self.assertIsNone(custom.release_next())
                self.assertEqual((root/'PAUSE').read_text(),'user pause')
                (root/'PAUSE').unlink()
                self.assertIsNone(custom.release_next())
                connection.assert_not_called()


if __name__=='__main__':unittest.main()
