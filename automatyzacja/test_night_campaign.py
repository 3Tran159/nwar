import unittest,tempfile
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pre_w04 import endpoint_convergence,REFERENCE,DT
from night_campaign_step import decision
from common import read,write,sha


class NightDecisionTests(unittest.TestCase):
 def setUp(self):
  self.midnight=datetime.fromisoformat('2026-11-03T00:00:00+01:00')
 def values(self,n=1500,cd=1.,cl=1.):
  return np.column_stack((3.7832+DT*np.arange(1,n+1),np.full(n,REFERENCE['CD']*cd),np.full(n,REFERENCE['CL']*cl)))
 def test_non_aligned_resume_has_two_complete_eligible_checks(self):
  values=self.values();checks=endpoint_convergence(values)
  self.assertEqual(len(checks),2);self.assertEqual(checks[-1]['consecutive_compatible'],2)
  self.assertTrue(checks[-1]['wave_allowed']);self.assertAlmostEqual(checks[-1]['time_s'],values[-1,0])
 def test_partial_missing_or_oscillating_history_does_not_pass(self):
  self.assertEqual(endpoint_convergence(self.values(1499)),[])
  values=self.values(1501);values=np.delete(values,750,axis=0)
  self.assertFalse(endpoint_convergence(values)[-1]['wave_allowed'])
  values=self.values();values[:,1]*=1+.02*np.sin(np.arange(1500)*2*np.pi/100)
  self.assertFalse(endpoint_convergence(values)[-1]['stable'])
 def test_early_match_retains_original_reference(self):
  final=endpoint_convergence(self.values())[-1]
  self.assertEqual(decision(self.midnight-timedelta(hours=1),self.midnight,'calm_gate_passed',final),'original')
 def test_mismatch_cannot_become_reference_before_midnight(self):
  final=endpoint_convergence(self.values(cd=1.04,cl=.98))[-1]
  self.assertEqual(final['consecutive_stable'],2);self.assertFalse(final['wave_allowed'])
  self.assertEqual(decision(self.midnight-timedelta(seconds=1),self.midnight,'stable_reference_mismatch',final),'review')
  self.assertEqual(decision(self.midnight,self.midnight,'stable_reference_mismatch',final),'prepared')
 def test_unstable_and_wall_budget_continue_without_false_acceptance(self):
  final=endpoint_convergence(self.values(cd=1.04,cl=.98))[-1]
  self.assertEqual(decision(self.midnight,self.midnight,'wall_budget',final),'continue')
  final['stable']=False;final['consecutive_stable']=0
  self.assertNotEqual(decision(self.midnight,self.midnight,'stable_reference_mismatch',final),'prepared')
 def test_manual_stop_and_guards_never_auto_resume(self):
  final=endpoint_convergence(self.values())[-1]
  for status in ('stopped_by_marker','CFL_guard','stability_guard','field_health_guard','error'):
   self.assertEqual(decision(self.midnight,self.midnight,status,final),'review')


class ReferenceIsolationTests(unittest.TestCase):
 def test_archived_run_keeps_original_reference_after_switch(self):
  from calm_reference import reference_for,REFERENCE_ID
  old=dict(project_primary_settled=True,normalized_CD_total=.007,normalized_CL_hydro=.31)
  new=dict(project_primary_settled=True,reference_id=REFERENCE_ID,normalized_CD_total=.0073,normalized_CL_hydro=.309)
  with patch('calm_reference.read',return_value=old),patch('calm_reference.prepared_reference',return_value=new):
   self.assertEqual(reference_for(dict(spec={}))['normalized_CD_total'],.007)
   self.assertEqual(reference_for(dict(spec=dict(reference_id=REFERENCE_ID)))['normalized_CD_total'],.0073)
 def test_new_series_hides_old_results_without_changing_entries(self):
  from report_selection import active_entries
  from calm_reference import REFERENCE_ID
  entries=[dict(id='old',spec={}),dict(id='new',spec=dict(reference_id=REFERENCE_ID))]
  with patch('calm_reference.local_reference_enabled',return_value=True):
   self.assertEqual([e['id'] for e in active_entries(entries)],['new'])
  self.assertEqual(len(entries),2)
 def test_q_uses_the_recorded_reference(self):
  from project_results import q_result
  from cycle_policy import selection
  result=dict(cycles=dict(CD_mean=.0074,window=[10,14],count=5,repeatable=True,**selection([dict(number=i) for i in range(1,6)])));validation=dict(project_accepted=True)
  base=dict(project_primary_settled=True,physical_time_s=4.,checkpoint_sha256='old',normalized_CD_total=.007)
  new=dict(base,checkpoint_sha256='new',normalized_CD_total=.0073)
  with patch('project_results.policy',return_value=dict(scope='test',Q_definition='wave minus calm')):
   self.assertAlmostEqual(q_result(result,validation,base)['Q_CD'],.0004)
   self.assertAlmostEqual(q_result(result,validation,new)['Q_CD'],.0001)
 def test_all_seven_waves_have_exact_expanded_mesh_conditions(self):
  from wave_profiles import ALLOWED,RERUN_ALLOWED,verify_spec
  for case,(h,l) in (ALLOWED|RERUN_ALLOWED).items():
   with patch('wave_profiles.approved_profile',return_value=dict(id='profile')):
    spec=dict(mesh_profile=dict(id='profile'),H=h,L=l,dt=.0004,mode='resume')
    verify_spec(case,spec)
    spec['H']=h+.01
    with self.assertRaises(ValueError):verify_spec(case,spec)
 def test_automatic_pause_does_not_take_ownership_of_manual_pause(self):
  from worker import pause_after_limit
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);folder=root/'run';folder.mkdir();marker=root/'PAUSE';marker.write_text('manual stop')
   with patch('worker.DATA',root):pause_after_limit(dict(id='job',folder=str(folder)))
   self.assertEqual(marker.read_text(),'manual stop');self.assertFalse((folder/'automatic_pause.json').exists())
   marker.unlink()
   with patch('worker.DATA',root):pause_after_limit(dict(id='job',folder=str(folder)))
   proof=read(folder/'automatic_pause.json')
   self.assertEqual(proof['mtime_ns'],marker.stat().st_mtime_ns);self.assertEqual(proof['sha256'],sha(marker))

if __name__=='__main__':unittest.main()
