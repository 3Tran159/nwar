import json, tempfile, unittest, threading, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch, Mock
from contextlib import ExitStack
from common import write, read
import pre_resume as p
import server

class PreResumeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.folder=self.root/'calm_global';self.folder.mkdir()
  self.checkpoint=self.folder/'final.sim'
  with self.checkpoint.open('wb') as f:f.truncate(400_000_001)
  (self.folder/'history.csv').write_text('time_s,CD_total,CL_hydrodynamic\n0.75,0.008,0.15\n')
  write(self.folder/'setup.json',dict(initialization='whole_domain_momentum_ramp'))
  write(self.folder/'completed.json',dict(status='stopped_by_marker',time_s=.75))
  write(self.folder/'stage_result.json',dict(exit_code=0,source_unchanged=True))
  write(self.folder/'latest_checkpoint.json',dict(path=str(self.checkpoint),time_s=.75))
  write(self.root/'calm_receipt.json',dict(checkpoint=str(self.checkpoint),checkpoint_time_s=.75,checkpoint_sha256='good'))
  self.stack=ExitStack();self.addCleanup(self.stack.close)
  for name,value in dict(PRE=self.root,DATA=self.root,REQUEST=self.root/'request.json',STOPS=[],SOLVER_LOCKS=[],OTHER_LOCKS=[],SOURCE=self.root/'C01.sim',SOURCE_SHA='good').items():self.stack.enter_context(patch.object(p,name,value))
  self.stack.enter_context(patch.object(p,'calm_folders',return_value=[self.folder]))
  self.stack.enter_context(patch.object(p,'birth',return_value=None))
  self.native=self.stack.enter_context(patch.object(p,'native',return_value=[]))
  self.stack.enter_context(patch.object(p,'jobs',return_value=[]))
  self.digest=self.stack.enter_context(patch.object(p,'sha',return_value='good'))
  self.spawn=Mock(return_value=123)
 def launch(self):return p.resume(str(self.folder),'request-12345',self.spawn)
 def test_clean_pause_resumes_without_initialization_and_deduplicates(self):
  (self.folder/'STOP').write_text('User pause; preserve this marker')
  self.assertTrue(p.checkpoint_info()['available']);self.launch();self.launch()
  self.spawn.assert_called_once_with('run_pre_w04_global_ramp.py','--resume')
  self.assertTrue((self.folder/'STOP').exists())
 def test_guard_stops_cannot_be_resumed_by_button(self):
  for reason in ('CFL_guard','stability_guard','field_health_guard'):
   write(self.folder/'completed.json',dict(status=reason,time_s=.75))
   with self.assertRaises(ValueError):self.launch()
  self.spawn.assert_not_called()
 def test_time_mismatch_blocks_start(self):
  write(self.folder/'latest_checkpoint.json',dict(path=str(self.checkpoint),time_s=.74))
  with self.assertRaises(ValueError):self.launch()
  self.spawn.assert_not_called()
 def test_changed_checkpoint_blocks_start(self):
  self.digest.return_value='changed'
  with self.assertRaises(ValueError):self.launch()
  self.spawn.assert_not_called()
 def test_existing_native_solver_blocks_start(self):
  self.native.return_value=[{'pid':99}]
  with self.assertRaises(ValueError):self.launch()
  self.spawn.assert_not_called()
 def test_external_stop_is_preserved(self):
  (self.root/'STOP').write_text('external owner')
  with self.assertRaises(ValueError):self.launch()
  self.assertEqual((self.root/'STOP').read_text(),'external owner');self.spawn.assert_not_called()
 def test_own_pause_is_consumed_and_failure_restores_it(self):
  marker=dict(kind='pre_dashboard_pause',folder=str(self.folder))
  for name in ('STOP','PAUSE'):write(self.root/name,marker)
  self.spawn.side_effect=OSError('spawn failed')
  with self.assertRaises(OSError):self.launch()
  for name in ('STOP','PAUSE'):self.assertEqual(read(self.root/name),marker)
  self.spawn.side_effect=None;self.launch()
  for name in ('STOP','PAUSE'):self.assertFalse((self.root/name).exists())

class UniversalResumeTests(unittest.TestCase):
 def test_failed_wave_remains_visible_after_accepted_preparation(self):
  pre=dict(active=False,phase='ready_for_wave',updated_at='2026-11-03T00:12:00+01:00',live=dict(history_samples=14500))
  wave=dict(id='W04_run',case_id='W04',spec={},created='2026-11-03T00:14:00+01:00',updated='2026-11-03T07:25:00+01:00',status='failed')
  self.assertEqual(server.current_run([wave],pre,[]),dict(kind='wave',id='W04_run'))
  self.assertIsNone(server.current_resume([wave],pre,[]))
 def test_newer_preparation_and_active_run_take_display_priority(self):
  pre=dict(active=False,phase='paused',updated_at='2026-11-03T00:12:00+01:00',live=dict(history_samples=14500))
  wave=dict(id='older_wave',spec={},updated='2026-11-02T22:00:00+01:00',status='completed')
  self.assertEqual(server.current_run([wave],pre,[])['kind'],'preparation')
  wave['status']='running'
  self.assertEqual(server.current_run([wave],pre,[])['id'],'older_wave')
  wave['observed_status']='interrupted'
  self.assertEqual(server.current_run([wave],pre,[])['kind'],'preparation')
 def test_queued_cancelled_and_smoke_runs_do_not_hide_wave_history(self):
  wave=dict(id='saved_wave',spec={},updated='2026-11-03T07:25:00+01:00',status='failed')
  for status in ('queued','cancelled','preflight_blocked','completed'):
   newer=dict(id='newer',spec={'smoke':10} if status=='completed' else {},updated='2026-11-03T08:00:00+01:00',status=status)
   self.assertEqual(server.current_run([newer,wave],None,[])['id'],'saved_wave')
 def test_latest_external_run_can_be_displayed(self):
  own=dict(id='own',spec={},updated='2026-11-02T07:00:00+01:00',status='completed')
  external=dict(id='external',updated='2026-11-02T08:00:00+01:00',status='interrupted')
  self.assertEqual(server.current_run([own],None,[external])['id'],'external')
 def test_current_run_selection_includes_waves_and_excludes_old_pauses(self):
  pre=dict(active=False,phase='paused',updated_at='2026-11-02T15:00',folder='pre',resume_info=dict(available=True,time_s=.75,reason=None))
  wave=dict(id='W06_run',case_id='W06',folder='wave',spec={},updated='2026-11-02T16:00',status='paused',can_resume=True,live=dict(time_s=10))
  self.assertEqual(server.current_resume([wave],pre,[])['kind'],'wave')
  wave['updated']='2026-11-02T14:00'
  self.assertEqual(server.current_resume([wave],pre,[])['kind'],'preparation')
  wave.update(updated='2026-11-02T16:00',status='completed')
  self.assertIsNone(server.current_resume([wave],pre,[]))
  wave['status']='running';self.assertIsNone(server.current_resume([wave],pre,[]))
 def test_authenticated_resume_routes_to_saved_pre_without_starting_solver(self):
  target=dict(kind='preparation',id='PRE_W04',folder='test',available=True)
  h=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);port=h.server_address[1]
  with patch.object(server,'PORT',port),patch.object(server,'snapshot',return_value={'current_resume':target}),patch.object(p,'resume',return_value={'message':'accepted'}) as start,patch.object(server,'enable_report_updates') as reports:
   thread=threading.Thread(target=h.serve_forever,daemon=True);thread.start()
   try:
    def request(body,token=server.TOKEN):
     return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(port)+'/api/resume-current',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-NWAR-Token':token}))
    with self.assertRaises(urllib.error.HTTPError):request(target,token='wrong')
    with self.assertRaises(urllib.error.HTTPError):request(dict(target,folder='stale'))
    start.assert_not_called()
    with request(dict(target,request_key='test-request')) as r:self.assertEqual(r.status,202)
    start.assert_called_once_with('test','test-request',server.spawn);reports.assert_called_once()
   finally:h.shutdown()
  h.server_close()
 def test_report_refresh_does_not_run_while_paused(self):
  with patch.object(server,'read',side_effect=lambda path: {'enabled':True} if Path(path).name=='live_report_refresh.json' else {}),patch.object(server,'jobs',return_value=[]),patch.object(server,'spawn') as spawn:
   server.refresh_live_report();spawn.assert_not_called()
 def test_live_report_follows_progress_and_is_throttled(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);pre=root/'pre';folder=pre/'run';folder.mkdir(parents=True)
   write(pre/'state.json',dict(status='calm_running',pid=77,birth='owner'))
   write(root/'live_report_refresh.json',dict(enabled=True,last_requested_epoch=0))
   history=folder/'history.csv';history.write_text('time_s\n0.75\n')
   with patch.object(server,'DATA',root),patch.object(server,'HERE',root),patch.object(server,'final_report_root',return_value=None),patch('pre_w04.PRE',pre),patch('pre_w04.calm_folders',return_value=[folder]),patch.object(server,'jobs',return_value=[]),patch.object(server,'birth',side_effect=lambda pid:'owner' if pid==77 else None),patch.object(server,'spawn') as spawn:
    server.refresh_live_report();server.refresh_live_report();spawn.assert_called_once_with('report.py')
    config=read(root/'live_report_refresh.json');config['last_requested_epoch']=0;write(root/'live_report_refresh.json',config)
    server.refresh_live_report();self.assertEqual(spawn.call_count,1)
    history.write_text('time_s\n0.75\n0.8\n');server.refresh_live_report();self.assertEqual(spawn.call_count,2)

 def test_final_archive_disables_periodic_exports(self):
  with patch.object(server,'final_report_root',return_value=Path('H:/archive')),patch.object(server,'read') as read_state,patch.object(server,'spawn') as spawn:
   server.refresh_live_report()
   read_state.assert_not_called()
   spawn.assert_not_called()

if __name__=='__main__':unittest.main()
