import unittest,tempfile,threading,json,urllib.request,urllib.error
from unittest.mock import patch
from pathlib import Path
import common as c
import analysis as a
import numpy as np
class AnalysisTests(unittest.TestCase):
 def test_trapezoid_exact_linear_boundaries(self):
  t=np.array([0.,.3,.8,1.1,1.7,2.]);y=2*t+3
  self.assertAlmostEqual(a.mean_segment(t,y,.2,1.8,.7),5.,places=12)
 def test_gap_not_interpolated(self):
  self.assertIsNone(a.exact_segment(np.array([0.,.1,1.]),np.array([1.,1.,1.]),0.,1.,.2))
 def test_phase_cycles_known_sine(self):
  L=20;T=c.period(L);t=np.arange(c.T0,c.T0+12*T,.0004);ph=2*np.pi*(t-c.T0)/T
  d=dict(time_s=t,CL_hydrodynamic=.3+.04*np.sin(ph+.6),CD_total=.007+.002*np.sin(ph-.2))
  g=np.column_stack((t[::10],.25*np.sin(ph[::10])))
  r=a.cycles(d,g,.5,L)
  self.assertGreaterEqual(r['count'],4);self.assertTrue(r['repeatable'])
  self.assertAlmostEqual(r['CL_mean'],.3,places=5);self.assertAlmostEqual(r['CD_mean'],.007,places=6)
  self.assertAlmostEqual(r['period_measured_s'],T,places=5)
 def test_less_than_four_not_accepted(self):
  L=20;T=c.period(L);t=np.arange(c.T0,c.T0+6*T,.0004);ph=2*np.pi*(t-c.T0)/T
  d=dict(time_s=t,CL_hydrodynamic=.3+.04*np.sin(ph),CD_total=.007+.002*np.sin(ph))
  r=a.cycles(d,np.column_stack((t[::10],.25*np.sin(ph[::10]))),.5,L)
  self.assertFalse(r['repeatable'])
 def test_nan_health_not_accepted(self):
  self.assertFalse(a.health(dict(max_CFL=np.array([np.nan])))['ok'])
 def test_continuation_boundary_and_gap(self):
  with tempfile.TemporaryDirectory() as td:
   dirs=[Path(td)/str(i) for i in range(3)]
   for p in dirs:p.mkdir()
   (dirs[0]/'history.csv').write_text('time_s,CD_total\n0,1\n0.0004,2\n')
   (dirs[1]/'history.csv').write_text('time_s,CD_total\n0.0004,2\n0.0008,3\n')
   (dirs[2]/'history.csv').write_text('time_s,CD_total\n0.002,2\n0.0024,3\n')
   data,_=a.merge_segments(dirs[:2]);self.assertEqual(list(data['time_s']),[0,.0004,.0008])
   with self.assertRaises(ValueError):a.merge_segments([dirs[0],dirs[2]])
class ProjectResultsTests(unittest.TestCase):
 def test_future_studies_do_not_block_qualitative_acceptance(self):
  from project_results import acceptance
  checks=[dict(group='run',status='passed'),dict(group='future',status='future')]
  self.assertEqual(acceptance(checks),('passed',True))
  self.assertEqual(acceptance(checks,smoke=10),('passed',False))
  checks[0]['status']='failed';self.assertEqual(acceptance(checks),('failed',False))
 def test_q_sign_units_and_acceptance_gate(self):
  from project_results import q_result
  from cycle_policy import selection
  result=dict(cycles=dict(CD_mean=.0065,window=[10.,14.],count=5,repeatable=True,**selection([dict(number=i) for i in range(1,6)])))
  ref=dict(project_primary_settled=True,normalized_CD_total=.007,physical_time_s=4.6992,checkpoint_sha256='reference')
  q=q_result(result,dict(project_accepted=True),ref)
  self.assertAlmostEqual(q['Q_CD'],-.0005);self.assertAlmostEqual(q['delta_D_N'],-1.9278)
  self.assertEqual(q['sign'],'reduction');self.assertIsNone(q_result(result,dict(project_accepted=False),ref))
 def test_force_wave_plot_preserves_known_phase_offset(self):
  from response_plots import response_profile
  L=20;T=c.period(L);t=np.arange(c.T0,c.T0+12*T,.0004);ph=2*np.pi*(t-c.T0)/T
  data=dict(time_s=t,CL_hydrodynamic=.3+.04*np.sin(ph+.6),CD_total=.007+.002*np.sin(ph-.2))
  profile=response_profile(data,np.column_stack((t[::10],.25*np.sin(ph[::10]))),.5,L)
  self.assertIsNotNone(profile);self.assertEqual(profile['cycle_count'],4)
  phase=np.array(profile['phase_deg']);wave_peak=phase[np.argmax(profile['eta_prime_mean_m'])];lift_peak=phase[np.argmax(profile['lift_minus_C01_mean_N'])]
  self.assertAlmostEqual(lift_peak-wave_peak,-.6*180/np.pi,delta=4)
  self.assertFalse(profile['force_phase_shift_applied'])
 def test_c01_response_preserves_mean_force_change_and_raw_history(self):
  from response_plots import response_profile
  from project_results import COEFFICIENT_DENOMINATOR as scale
  reference=dict(CL=.315,CD=.007)
  L=20;T=c.period(L);t=np.arange(c.T0,c.T0+12*T,.0004);ph=2*np.pi*(t-c.T0)/T
  data=dict(time_s=t,CL_hydrodynamic=reference['CL']+(12+100*np.sin(ph+.6))/scale,
            CD_total=reference['CD']+(-2+8*np.sin(ph-.2))/scale)
  original={k:v.copy() for k,v in data.items()}
  profile=response_profile(data,np.column_stack((t[::10],.25*np.sin(ph[::10]))),.5,L,force_reference=reference)
  phase=np.array(profile['phase_deg'])/360
  self.assertEqual(profile['force_reference'],'C01')
  for name,expected in [('lift',12.),('drag',-2.)]:
   for curve in profile[name+'_minus_C01_cycles_N']:
    self.assertAlmostEqual(float(np.trapezoid(curve,phase)),expected,delta=.02)
   np.testing.assert_allclose(profile['cycle_mean_'+name+'_minus_C01_N'],expected,atol=.02)
  for k in data:np.testing.assert_array_equal(data[k],original[k])
class HistoryDisplayTests(unittest.TestCase):
 def test_full_chain_includes_parent_and_two_resumes(self):
  from history_view import history_view,run_chain
  with tempfile.TemporaryDirectory() as td:
   folders=[Path(td)/str(i) for i in range(3)]
   for i,folder in enumerate(folders):
    folder.mkdir();start=i*.0008
    (folder/'history.csv').write_text('time_s,CD_total,CL_hydrodynamic\n'+''.join(f'{start+j*.0004:.7f},0.007,0.3\n' for j in range(3)))
   entry=dict(id='child',folder=str(folders[2]),spec=dict(parent_segments=[str(p) for p in folders[:2]]))
   result=history_view(run_chain(entry))
   self.assertEqual(result['history_samples'],7)
   self.assertEqual(result['history_start_s'],0)
   self.assertAlmostEqual(result['history_end_s'],.0024)
   self.assertEqual([m['time_s'] for m in result['resume_markers']],[.0008,.0016])
   self.assertTrue(all(m['contiguous'] for m in result['resume_markers']))
 def test_display_preserves_narrow_extrema(self):
  from history_view import envelope_indices
  data=np.column_stack((np.arange(10000),np.zeros((10000,2))))
  data[1234,1]=9;data[5432,2]=-8
  indices=envelope_indices(data,200)
  self.assertIn(1234,indices);self.assertIn(5432,indices)
  self.assertIn(0,indices);self.assertIn(9999,indices)
  self.assertLessEqual(len(indices),200)
 def test_history_gap_is_flagged_not_connected(self):
  from history_view import history_view
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'history.csv').write_text('time_s,CD_total,CL_hydrodynamic\n0,.007,.3\n.0004,.007,.3\n.004,.007,.3\n')
   result=history_view([p])
   self.assertEqual(len(result['history_segments']),2)
   self.assertTrue(result['history_warnings'])
 def test_report_uses_extended_w03_and_excludes_tests(self):
  from report_selection import report_entries,display_id
  with tempfile.TemporaryDirectory() as td:
   entries=[]
   for name,end,smoke in [('W03',13.,0),('extended',14.,0),('test',15.,20)]:
    folder=Path(td)/name;folder.mkdir();(folder/'history.csv').write_text(f'time_s,CD_total,CL_hydrodynamic\n{end},.007,.3\n')
    entries.append(dict(id=name,case_id='W03',folder=str(folder),status='completed',legacy=name=='W03',spec=dict(smoke=smoke,parent_folder=str(Path(td)/'W03'))))
   selected=report_entries(entries)
   self.assertEqual([j['id'] for j in selected],['extended'])
   self.assertEqual(display_id(selected[0]),'W03')
   self.assertTrue((Path(td)/'W03'/'history.csv').exists())
 def test_partial_force_wave_response_does_not_claim_four_cycles(self):
  from response_plots import response_profile
  L=20;T=c.period(L);t=np.arange(c.T0,c.T0+7*T,.0004);ph=2*np.pi*(t-c.T0)/T
  data=dict(time_s=t,CL_hydrodynamic=.3+.04*np.sin(ph),CD_total=.007+.002*np.sin(ph))
  profile=response_profile(data,np.column_stack((t[::10],.25*np.sin(ph[::10]))),.5,L)
  self.assertIsNotNone(profile)
  self.assertGreater(profile['cycle_count'],0);self.assertLess(profile['cycle_count'],4)
class QueueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.patches=[patch.object(c,'DATA',self.root),patch.object(c,'RUNS',self.root/'runs'),patch.object(c,'catalog',return_value=[dict(id=id,H=.5,L=20,T=c.period(20),ready=id!='W04',dt=.0004) for id in ('W01','W02','W04')])]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in self.patches[::-1]:p.stop()
  self.tmp.cleanup()
 def test_double_click_idempotent(self):
  x=c.enqueue('W01',request_key='request123');y=c.enqueue('W01',request_key='request123')
  self.assertEqual(x,y);self.assertEqual(len(c.jobs()),1)
 def test_duplicate_different_request_blocked(self):
  c.enqueue('W01')
  with self.assertRaises(ValueError):c.enqueue('W01')
 def test_out_of_envelope_blocked(self):
  with self.assertRaises(ValueError):c.enqueue('W04')
  self.assertEqual(c.jobs(),[])
 def test_atomic_batch_rollback(self):
  with self.assertRaises(ValueError):
   with c.connection() as conn:
    conn.execute('BEGIN IMMEDIATE')
    c.enqueue('W01',conn=conn)
    c.enqueue('W04',conn=conn)
  self.assertEqual(c.jobs(),[])
 def test_concurrent_enqueue_single_job(self):
  result=[]
  def add():
   try:result.append(c.enqueue('W01',request_key='same_request'))
   except Exception as ex:result.append(str(ex))
  threads=[threading.Thread(target=add) for _ in range(4)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(len(c.jobs()),1);self.assertEqual(len(set(result)),1)
 def test_resume_requires_confirmed_source(self):
  with self.assertRaises(ValueError):c.enqueue('W01','resume')
 def test_resume_remaining_steps_and_no_duplicate_branch(self):
  parent=c.enqueue('W01',smoke=10);p=c.job(parent);folder=Path(p['folder']);folder.mkdir(parents=True)
  final=folder/'wave_pilot_final.sim';final.write_bytes(b'verified-pause')
  c.write(folder/'latest_checkpoint.json',dict(healthy=True,file=final.name,time_s=c.T0+8*.0004))
  c.write(folder/'final_integrity.json',dict(sha256=c.sha(final)))
  c.write(folder/'completed.json',dict(steps=8,time_s=c.T0+8*.0004))
  c.update(parent,status='paused')
  resumed=c.enqueue('W01','resume',parent_id=parent,request_key='resume_request')
  self.assertEqual(c.job(resumed)['spec']['extra_steps'],2)
  c.update(resumed,status='completed')
  self.assertEqual(c.enqueue('W01','resume',parent_id=parent,request_key='resume_request'),resumed)
  with self.assertRaises(ValueError):c.enqueue('W01','resume',parent_id=parent,request_key='another_resume')
 def test_float_cycle_count_rejected(self):
  with self.assertRaises(ValueError):c.enqueue('W01',extra_cycles=1.5)
 def test_external_checkpoint_keeps_complete_source_chain(self):
  original=self.root/'original';extended=self.root/'extended';original.mkdir();extended.mkdir()
  (original/'wave_pilot_final.sim').write_bytes(b'original-save')
  (extended/'wave_pilot_extended_final.sim').write_bytes(b'extended-save')
  digest=c.sha(original/'wave_pilot_final.sim')
  c.write(original/'four_cycle_independent_review.json',dict(final_sim_SHA256=digest))
  ext=dict(folder=extended,source=extended/'wave_pilot_extended_final.sim',time_s=14.0,segments=[original,extended],pre=dict(source_sha256=digest),setup=dict(height_m=.5,lambda_m=20,step_dt_s=.0004))
  with patch.object(c,'EXISTING',{'W02':original}),patch.object(c,'external_checkpoint',return_value=ext),patch.object(a,'analyze',return_value=({'health':{'ok':True},'time_s':14.0},None,None)):
   j=c.job(c.enqueue('W02','extend'))
  self.assertEqual(j['spec']['source_time'],14.0)
  self.assertEqual(j['spec']['parent_segments'],[str(original),str(extended)])
  self.assertEqual(a.segment_chain(j),[original,extended,Path(j['folder'])])
 def test_external_checkpoint_rejects_unhealthy_history(self):
  original=self.root/'original';extended=self.root/'extended';original.mkdir();extended.mkdir()
  (original/'wave_pilot_final.sim').write_bytes(b'original-save');digest=c.sha(original/'wave_pilot_final.sim')
  c.write(original/'four_cycle_independent_review.json',dict(final_sim_SHA256=digest))
  ext=dict(folder=extended,source=extended/'wave_pilot_extended_final.sim',time_s=14.0,segments=[original,extended],pre=dict(source_sha256=digest),setup=dict(height_m=.5,lambda_m=20,step_dt_s=.0004))
  with patch.object(c,'EXISTING',{'W02':original}),patch.object(c,'external_checkpoint',return_value=ext),patch.object(a,'analyze',return_value=({'health':{'ok':False},'time_s':14.0},None,None)):
   with self.assertRaises(ValueError):c.enqueue('W02','extend')
  self.assertEqual(c.jobs(),[])
class HttpTests(unittest.TestCase):
 def test_readonly_and_mutation_security(self):
  import server
  h=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);port=h.server_address[1]
  with patch.object(server,'PORT',port),patch.object(server,'snapshot',return_value={'ok':True}):
   thread=threading.Thread(target=h.serve_forever,daemon=True);thread.start()
   base='http://127.0.0.1:'+str(port)
   self.assertTrue(json.load(urllib.request.urlopen(base+'/api/status'))['ok'])
   for headers in ({'Content-Type':'application/json'},{'Content-Type':'application/json','X-NWAR-Token':server.TOKEN,'Origin':'https://untrusted.invalid'}):
    req=urllib.request.Request(base+'/api/enqueue',data=b'{}',headers=headers)
    with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
    self.assertEqual(err.exception.code,403)
   with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(base+'/reports/../../common.py')
   self.assertEqual(err.exception.code,403)
   h.shutdown()
  h.server_close()
if __name__=='__main__':unittest.main(verbosity=2)
