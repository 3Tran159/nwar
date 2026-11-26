import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pre_w04 import convergence,REFERENCE,T0,DT
from common import catalog

class CalmGateTests(unittest.TestCase):
 def values(self,n=2000,cd=1,cl=1):
  return np.column_stack((T0+DT*np.arange(1,n+1),np.full(n,REFERENCE['CD']*cd),np.full(n,REFERENCE['CL']*cl)))
 def test_short_partial_windows_do_not_qualify(self):
  self.assertEqual(convergence(self.values(999),T0),[])
  self.assertFalse(convergence(self.values(1999),T0)[-1]['wave_allowed'])
 def test_two_eligible_checks_at_original_reference(self):
  checks=convergence(self.values(),T0)
  self.assertEqual(len(checks),3)
  self.assertFalse(checks[-2]['wave_allowed']);self.assertTrue(checks[-1]['wave_allowed'])
 def test_stable_wrong_reference_blocks_wave(self):
  r=convergence(self.values(cd=1.01),T0)[-1]
  self.assertTrue(r['stable']);self.assertFalse(r['compatible']);self.assertFalse(r['wave_allowed'])
  self.assertTrue(r['stable_reference_mismatch']);self.assertAlmostEqual(r['CD_C01_pct'],1)
 def test_rms_rejects_stationary_oscillation(self):
  values=self.values();values[:,2]*=1+.02*np.sin(np.arange(len(values))*2*np.pi/100)
  r=convergence(values,T0)[-1]
  self.assertFalse(r['stable']);self.assertFalse(r['wave_allowed'])
 def test_missing_sample_cannot_qualify(self):
  values=self.values(2001);values=np.delete(values,1250,axis=0)
  r=convergence(values,T0)[-1];self.assertFalse(r['complete']);self.assertFalse(r['wave_allowed'])
 def test_updated_plan_keeps_ids_and_exact_wavelengths(self):
  with patch('wave_profiles.approved_profile',return_value=None):cases={c['id']:c for c in catalog()}
  for id,L in [('W05',20),('W06',30),('W07',40)]:
   self.assertEqual(cases[id]['H'],1);self.assertEqual(cases[id]['L'],L)
   self.assertFalse(cases[id]['ready'])
 def test_profile_without_calm_gate_cannot_start(self):
  from wave_profiles import verify_spec
  with patch('wave_profiles.approved_profile',return_value=None):
   with self.assertRaises(ValueError):verify_spec('W04',{'mesh_profile':{'id':'M13_W04_20261102'}})
 def test_fresh_start_excludes_ramp_before_acceptance(self):
  values=self.values(4500);values[:,0]=DT*np.arange(1,len(values)+1)
  checks=convergence(values,0,ramp_s=1)
  self.assertFalse(any(r['wave_allowed'] for r in checks[:-1]))
  self.assertTrue(checks[-1]['wave_allowed']);self.assertAlmostEqual(checks[-1]['time_s'],1.8)
 def test_expanded_domain_uses_later_wave_arrival(self):
  from analysis import cycles
  from common import period
  L=38.99857691441418;origin=T0+.8;T=period(L)
  t=origin+np.arange(0,20,.0004);phase=2*np.pi*(t-origin)/T
  data=dict(time_s=t,CD_total=.007+.001*np.sin(phase),CL_hydrodynamic=.3+.02*np.sin(phase))
  gauge=np.column_stack((t[::10],.75*np.sin(phase[::10])))
  result=cycles(data,gauge,1.5,L,origin=origin,probe_distance=69.5)
  self.assertAlmostEqual(result['analysis_not_before_s'],origin+2*T+69.5*T/L)
  self.assertGreaterEqual(result['count'],4)

class FreshAttemptHistoryTests(unittest.TestCase):
 def test_new_global_attempt_excludes_previous_startup_history(self):
  from pre_w04 import calm_folders,calm_values
  from common import write
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);old=root/'calm';new=root/'calm_global';old.mkdir();new.mkdir()
   header='time_s,CD_total,CL_hydrodynamic\n'
   (old/'history.csv').write_text(header+'0.0004,9,9\n0.0008,8,8\n')
   (new/'history.csv').write_text(header+'0.0004,0.001,0.01\n0.0008,0.002,0.02\n')
   write(root/'continuation.json',dict(root_folder=str(new),folders=[str(new)]))
   with patch('pre_w04.PRE',root),patch('pre_w04.CALM_RUN',old):
    self.assertEqual(calm_folders(),[new.resolve()])
    np.testing.assert_allclose(calm_values(),[[.0004,.001,.01],[.0008,.002,.02]])
   self.assertIn('9,9',(old/'history.csv').read_text())
 def test_legacy_continuation_still_includes_original_calm(self):
  from pre_w04 import calm_folders
  from common import write
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);old=root/'calm';resume=root/'resume'
   write(root/'continuation.json',dict(folders=[str(old),str(resume)]))
   with patch('pre_w04.PRE',root),patch('pre_w04.CALM_RUN',old):
    self.assertEqual(calm_folders(),[old.resolve(),resume.resolve()])
 def test_external_root_cannot_replace_pre_history(self):
  from pre_w04 import calm_folders
  from common import write
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'pre';root.mkdir()
   write(root/'continuation.json',dict(root_folder=str(Path(td)/'elsewhere')))
   with patch('pre_w04.PRE',root),patch('pre_w04.CALM_RUN',root/'calm'):
    with self.assertRaises(ValueError):calm_folders()

class FoilProbeTests(unittest.TestCase):
 def test_common_reference_uses_measured_zero_when_available(self):
  from phase_alignment import align_to_position
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td)
   (folder/'gauges.csv').write_text('time_s,x_m,eta_actual_m\n0,-0.5,0.1\n0,0,0.2\n0.004,-0.5,0.15\n0.004,0,0.25\n')
   g,evidence=align_to_position([folder],-.5,{})
   np.testing.assert_allclose(g,[[0,.2],[.004,.25]])
   self.assertEqual(evidence['target_x_m'],0.);self.assertFalse(evidence['estimated'])
 def test_missing_common_probe_is_translated_without_changing_recorded_wave(self):
  from phase_alignment import align_to_position
  T=.85;speed=24.;t=np.arange(0,8,.004)
  upstream=np.column_stack((t,.25*np.sin(2*np.pi*t/T)))
  source=np.column_stack((t,.25*np.sin(2*np.pi*(t-4/speed)/T)))
  original=source.copy()
  def gauge(folders,x):return {-10.:upstream,-6.:source}.get(x,np.empty((0,2)))
  result={'L':20,'cycles':{'period_measured_s':T,'analysis_not_before_s':2.}}
  with patch('phase_alignment.gauge_series',side_effect=gauge):aligned,evidence=align_to_position([], -6.,result)
  self.assertEqual(evidence['target_x_m'],0.);self.assertEqual(evidence['source_probe_x_m'],-6.)
  self.assertAlmostEqual(evidence['time_shift_s'],6/speed,places=6)
  self.assertEqual(evidence['force_shift_s'],0.)
  np.testing.assert_array_equal(source,original)
  np.testing.assert_allclose(aligned[:,0]-source[:,0],6/speed,atol=1e-6)
  np.testing.assert_array_equal(aligned[:,1],source[:,1])
 def test_wave_delay_sign_and_independence_from_forces(self):
  from phase_alignment import pair_delay
  T=.85;lag=.17;t=np.arange(0,6,.004)
  up=np.column_stack((t,.25*np.sin(2*np.pi*t/T)))
  down=np.column_stack((t,.25*np.sin(2*np.pi*(t-lag)/T)))
  result=pair_delay(up,down,T,.17,1.)
  self.assertIsNotNone(result);self.assertAlmostEqual(result['measured_delay_s'],lag,places=5)
 def test_force_lag_is_preserved_after_wave_transport(self):
  from phase_alignment import pair_delay
  from response_plots import response_profile
  T=.8478873476270993;lag=.17;travel=.28;phi=.6;t=T0+np.arange(0,15,.004)
  up=np.column_stack((t,.25*np.sin(2*np.pi*(t-T0)/T)))
  ref=np.column_stack((t,.25*np.sin(2*np.pi*(t-T0-lag)/T)))
  delay=pair_delay(up,ref,T,lag,T0+3)['measured_delay_s']
  shifted=ref.copy();shifted[:,0]+=delay*(travel-lag)/lag
  phase=2*np.pi*(t-T0-travel)/T
  data=dict(time_s=t,CL_hydrodynamic=.3+.03*np.sin(phase+phi),CD_total=.007+.001*np.sin(phase-.4))
  # The normal response reader requires the full force sampling rate.
  tf=np.arange(t[0],t[-1],.0004);data={k:np.interp(tf,t,v) for k,v in data.items()};data['time_s']=tf
  profile=response_profile(data,shifted,.5,20,x=0.,probe_distance=35.)
  p=np.array(profile['phase_deg']);wave=p[np.argmax(profile['eta_prime_mean_m'])];lift=p[np.argmax(profile['lift_minus_C01_mean_N'])]
  self.assertAlmostEqual(lift-wave,-phi*180/np.pi,delta=4)
 def test_local_probe_preferred_without_phase_shift(self):
  from response_plots import response_gauge
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td)
   (folder/'gauges.csv').write_text('time_s,x_m,eta_actual_m\n0,-0.5,0.1\n0,0,0.2\n0.004,-0.5,0.15\n0.004,0,0.25\n')
   x,g,local=response_gauge([folder],-.5)
   self.assertTrue(local);self.assertEqual(x,0.);np.testing.assert_allclose(g,[[0,.2],[.004,.25]])
 def test_missing_local_history_is_not_invented(self):
  from response_plots import response_gauge
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);(folder/'gauges.csv').write_text('time_s,x_m,eta_actual_m\n0,-6,0.1\n0.004,-6,0.15\n')
   x,g,local=response_gauge([folder],-6)
   self.assertFalse(local);self.assertEqual(x,-6)

class OpenDomainBalanceTests(unittest.TestCase):
 def test_recovery_uses_saved_prefix_and_preserves_uncheckpointed_tail(self):
  from history_view import _history,history_view
  from pre_balance import balance_seed
  from common import write
  with tempfile.TemporaryDirectory() as td:
   first=Path(td)/'failed';scene=Path(td)/'scenes';resume=Path(td)/'resume'
   for folder in [first,scene,resume]:folder.mkdir()
   raw='time_s,CD_total,CL_hydrodynamic\n0.0004,0.007,0.30\n0.0008,0.008,0.31\n0.0012,9,9\n'
   (first/'history.csv').write_text(raw);self.assertEqual(len(_history(first)),3)
   write(first/'history_cutoff.json',dict(time_s=.0008))
   (scene/'history.csv').write_text('time_s,CD_total,CL_hydrodynamic\n0.0008,0.008,0.31\n')
   write(scene/'completed.json',dict(status='scene_prepared'))
   (resume/'history.csv').write_text('time_s,CD_total,CL_hydrodynamic\n0.0008,0.008,0.31\n0.0012,0.009,0.32\n')
   display=history_view([first,scene,resume]);self.assertEqual(display['history_samples'],3)
   self.assertEqual(len(display['resume_markers']),1);self.assertTrue(display['resume_markers'][0]['contiguous'])
   self.assertEqual((first/'history.csv').read_text(),raw);self.assertEqual(len(_history(first)),2)
   header='time_s,mass_kg,water_volume_m3,net_outward_mass_kg_s\n'
   (first/'conservation.csv').write_text(header+'0.0004,1000,1,0\n0.0008,1000,1,0\n0.0012,9999,9,0\n')
   (scene/'conservation.csv').write_text(header+'0.0008,1000,1,0\n')
   (resume/'conservation.csv').write_text(header+'0.0008,1000,1,0\n0.0012,1000,1,0\n')
   balance=balance_seed([first,scene,resume]);self.assertAlmostEqual(balance['water_closure_error_m3'],0)
   self.assertAlmostEqual(balance['last_time_s'],.0012)
 def test_water_readiness_is_post_ramp_and_requires_settled_inventory(self):
  from pre_balance import water_readiness
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td)
   def readiness(t,water,eta):
    (folder/'gauges.csv').write_text('time_s,x_m,eta_actual_m\n'+''.join(f'{t},{x},{eta}\n' for x in range(8)))
    return water_readiness([folder],dict(last_time_s=t,last_water_m3=water,initial_water_m3=76.8))
   self.assertFalse(readiness(.7,76.8,.01)['ready'])
   self.assertFalse(readiness(1.8,78.,.9)['ready'])
   self.assertFalse(readiness(1.8,76.8,.9)['ready'])
   self.assertTrue(readiness(1.8,76.81,.01)['ready'])
 def test_real_inflow_is_allowed_and_unexplained_water_is_detected(self):
  from pre_balance import balance_seed
  t=np.arange(0,.4001,.0004);water=76.8+2*t;mass=76800+(1000-1.2)*(water-76.8)
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);path=folder/'conservation.csv'
   def write_data(v,m):
    np.savetxt(path,np.column_stack((t,m,v,np.full(len(t),-2*(1000-1.2)))),delimiter=',',header='time_s,mass_kg,water_volume_m3,net_outward_mass_kg_s',comments='')
   write_data(water,mass);result=balance_seed([folder])
   self.assertGreater(water[-1]-water[0],.25)
   self.assertAlmostEqual(result['water_closure_error_m3'],0.,places=8)
   self.assertAlmostEqual(result['mass_closure_error_kg'],0.,places=8)
   water[-1]+=.3;mass[-1]+=.3*(1000-1.2);write_data(water,mass)
   self.assertGreater(balance_seed([folder])['water_closure_error_m3'],.25)
 def test_resume_history_retains_start_and_joins_duplicate_boundary(self):
  from pre_w04 import calm_values
  a=np.array([[.0004,.1,.2],[.0008,.11,.21]])
  b=np.array([[.0008,.11,.21],[.0012,.12,.22]])
  with patch('pre_w04.calm_folders',return_value=['first','resume']),patch('pre_w04._history',side_effect=[a,b]):
   np.testing.assert_allclose(calm_values(),[[.0004,.1,.2],[.0008,.11,.21],[.0012,.12,.22]])

if __name__=='__main__':unittest.main()
