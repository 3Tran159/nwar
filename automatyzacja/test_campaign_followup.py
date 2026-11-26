import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from common import read, write, sha, HERE
from pre_lineage import prepared_lineage
from advance_wave_queue import choose_case
import advance_wave_queue as campaign


class CampaignTests(unittest.TestCase):
    def entry(self, case='W04', status='completed', smoke=0):
        return dict(id=case, case_id=case, status=status, created='2026-11-02', spec=dict(smoke=smoke))

    def proof(self, j):
        from cycle_policy import selection
        return dict(project_accepted=True, run_verification='passed'), dict(health=dict(ok=True), cycles=dict(repeatable=True, count=5, **selection([dict(number=i) for i in range(1,6)])))

    def test_start_in_order_and_advance_only_after_validation(self):
        seq=['W04','W05','W06','W07']
        self.assertEqual(choose_case(seq,[],self.proof)['case'],'W04')
        entries=[]
        for i,case in enumerate(seq):
            entries.append(self.entry(case))
            result=choose_case(seq,entries,self.proof)
            self.assertEqual(result['status'],'complete' if i==3 else 'ready')
            if i<3:self.assertEqual(result['case'],seq[i+1])

    def test_topups_run_before_w06_and_four_recorded_cycles_cannot_release_it(self):
        seq=['W04','W02','W03','W06'];entries=[self.entry('W04')]
        self.assertEqual(choose_case(seq,entries,self.proof)['case'],'W02')
        entries.append(self.entry('W02'))
        def incomplete(j):
            v,r=self.proof(j)
            if j['case_id']=='W02':r['cycles']['count']=4;r['cycles']['analyzed_count']=3
            return v,r
        self.assertEqual(choose_case(seq,entries,incomplete)['status'],'blocked')
        self.assertEqual(choose_case(seq,entries,self.proof)['case'],'W03')
        entries.append(self.entry('W03'))
        self.assertEqual(choose_case(seq,entries,self.proof)['case'],'W06')

    def test_unaccepted_or_nonrepeated_waves_block_the_next_case(self):
        for proof in [(dict(project_accepted=False),{}), (dict(project_accepted=True,run_verification='passed'),dict(health=dict(ok=True),cycles=dict(repeatable=True,count=3)))]:
            self.assertEqual(choose_case(['W04','W05'],[self.entry()],lambda j:proof)['status'],'blocked')

    def test_existing_job_is_not_duplicated_and_stop_is_not_retried(self):
        for status,expected in [('queued','queued'),('running','waiting_wave'),('paused','blocked'),('cancelled','blocked'),('needs_review','blocked'),('failed','blocked')]:
            self.assertEqual(choose_case(['W04'],[self.entry(status=status)],self.proof)['status'],expected)
        self.assertEqual(choose_case(['W04'],[self.entry(smoke=10)],self.proof)['status'],'ready')

    def test_live_pre_does_not_enqueue_or_start_worker(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            write(root/'plan.json',dict(enabled=True,sequence=['W04','W05','W06','W07']))
            write(root/'state.json',dict(status='calm_running',pid=42,birth='live'))
            with patch.multiple(campaign,PLAN=root/'plan.json',PRE=root,DATA=root,STOPS=[]),patch.object(campaign,'birth',return_value='live'),patch.object(campaign,'enqueue') as enqueue,patch.object(campaign,'native') as native:
                self.assertEqual(campaign.step(True)['status'],'waiting_pre')
                enqueue.assert_not_called();native.assert_not_called()
                (root/'STOP').touch()
                self.assertEqual(campaign.step(True)['status'],'blocked')
                self.assertTrue((root/'STOP').exists())

    def test_w07_uses_same_profile_and_forty_meter_wave(self):
        from wave_profiles import ALLOWED
        self.assertEqual(ALLOWED['W07'],(1.,40.))
        self.assertEqual(read(HERE/'wave_plan.json')['cases']['W07']['L'],40.)
        text=(HERE/'NwarWave.java').read_text()
        self.assertIn('caseId.equals("W07")&&H==1&&lambda==40',text)
        self.assertNotIn('initializeSolution',text)
        self.assertNotIn('clearSolution',text)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.sim';self.source.write_bytes(b'original scenes and geometry')
        self.folders=[self.root/'fresh',self.root/'resume']
        previous=self.source
        for folder in self.folders:
            folder.mkdir();write(folder/'source_identity.json',dict(path=str(previous),sha256=sha(previous)))
            write(folder/'stage_result.json',dict(source_unchanged=True))
            previous=folder/'final.sim';previous.write_bytes(folder.name.encode())
        write(self.folders[0]/'setup.json',dict(initialization='whole_domain_momentum_ramp',fresh_fields=True,start_time_s=0.))
        write(self.folders[-1]/'global_ramp_completed.json',dict(momentum_source_option='NONE',extra_force_active=False))
        self.receipt=dict(initialization='whole_domain_momentum_ramp',gates=dict(startup_momentum_source_removed=True))

    def test_global_ramp_provenance_without_old_geometry_source_field(self):
        last,valid,links=prepared_lineage(self.receipt,self.folders)
        self.assertTrue(valid);self.assertEqual(last,self.folders[-1]/'final.sim');self.assertEqual(len(links),2)

    def test_changed_source_or_wrong_parent_or_remaining_force_rejected(self):
        self.source.write_bytes(b'changed');self.assertFalse(prepared_lineage(self.receipt,self.folders)[1])
        self.source.write_bytes(b'original scenes and geometry')
        write(self.folders[-1]/'global_ramp_completed.json',dict(momentum_source_option='SPECIFIED',extra_force_active=True))
        self.assertFalse(prepared_lineage(self.receipt,self.folders)[1])
        write(self.folders[-1]/'global_ramp_completed.json',dict(momentum_source_option='NONE',extra_force_active=False))
        write(self.folders[-1]/'source_identity.json',dict(path=str(self.source),sha256=sha(self.source)))
        self.assertFalse(prepared_lineage(self.receipt,self.folders)[1])

    def test_previous_fresh_from_rest_provenance_is_preserved(self):
        receipt=dict(initialization='fresh_from_rest',geometry_source=str(self.source),geometry_source_sha256=sha(self.source))
        self.assertTrue(prepared_lineage(receipt,self.folders)[1])


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'pre';self.folder.mkdir()
        write(self.root/'plan.json',dict(id='authorized-sequence',enabled=True,sequence=['W04','W05','W06','W07']))
        write(self.root/'state.json',dict(status='ready_for_wave',pid=42,birth='old'))
        write(self.root/'calm_receipt.json',dict(passed=True,gates=dict(native=True,independent=True),final_check=dict(wave_allowed=True),checkpoint_time_s=4.))
        write(self.folder/'completed.json',dict(status='calm_gate_passed',time_s=4.))
        write(self.folder/'stage_result.json',dict(exit_code=0,source_unchanged=True))
        (self.folder/'history.csv').write_text('time_s\n4.0\n')
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(campaign,PLAN=self.root/'plan.json',PRE=self.root,DATA=self.root,OWNER=self.root/'worker.lock',STOPS=[],SOLVER_LOCKS=[],OTHER_LOCKS=[]))
        self.stack.enter_context(patch.object(campaign,'calm_folders',return_value=[self.folder]))
        self.stack.enter_context(patch.object(campaign,'birth',return_value=None))
        self.native=self.stack.enter_context(patch.object(campaign,'native',return_value=[]))
        self.jobs=self.stack.enter_context(patch.object(campaign,'jobs',return_value=[]))
        self.profile=self.stack.enter_context(patch.object(campaign,'approved_profile',return_value=dict(source='saved-pre.sim',source_time=4.)))
        self.enqueue=self.stack.enter_context(patch.object(campaign,'enqueue',return_value='wave-job'))
        self.worker=self.stack.enter_context(patch('server.ensure_worker',return_value=100))
        self.reports=self.stack.enter_context(patch('server.enable_report_updates'))

    def test_verified_handoff_dispatches_once_and_recovers_queued_job(self):
        self.assertEqual(campaign.step(False)['status'],'ready');self.enqueue.assert_not_called();self.worker.assert_not_called()
        result=campaign.step(True)
        self.assertEqual(result['status'],'dispatched')
        self.enqueue.assert_called_once_with('W04',request_key='authorized-sequence_W04')
        self.reports.assert_called_once();self.worker.assert_called_once()
        self.jobs.return_value=[dict(id='wave-job',case_id='W04',created='now',status='queued',spec={})]
        self.assertEqual(campaign.step(True)['job_id'],'wave-job')
        self.assertEqual(self.enqueue.call_count,1)

    def test_live_solver_or_lock_defers_handoff(self):
        self.native.return_value=[(99,'star-ccm+.exe')]
        self.assertEqual(campaign.step(True)['status'],'waiting_resources')
        self.native.return_value=[];lock=self.root/'foreign.lock';lock.touch()
        with patch.object(campaign,'OTHER_LOCKS',[lock]):
            self.assertEqual(campaign.step(True)['status'],'waiting_resources')
        self.assertTrue(lock.exists());self.enqueue.assert_not_called();self.worker.assert_not_called()

    def test_pre_evidence_mismatch_or_guard_never_dispatches(self):
        for done in [dict(status='CFL_guard',time_s=4.),dict(status='calm_gate_passed',time_s=3.9)]:
            write(self.folder/'completed.json',done)
            self.assertEqual(campaign.step(True)['status'],'blocked')
        write(self.folder/'completed.json',dict(status='calm_gate_passed',time_s=4.))
        receipt=read(self.root/'calm_receipt.json');receipt['gates']['independent']=False;write(self.root/'calm_receipt.json',receipt)
        self.assertEqual(campaign.step(True)['status'],'blocked')
        self.enqueue.assert_not_called();self.worker.assert_not_called()

    def test_wrong_w07_wavelength_is_rejected_by_worker_contract(self):
        from wave_profiles import verify_spec
        with patch('wave_profiles.approved_profile',return_value={'id':'profile'}):
            spec=dict(mesh_profile={'id':'profile'},H=1.,L=50.,dt=.0004,mode='resume')
            with self.assertRaises(ValueError):verify_spec('W07',spec)
            spec['L']=40.
            self.assertEqual(verify_spec('W07',spec),{'id':'profile'})


if __name__=='__main__':unittest.main()
