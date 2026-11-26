import unittest,copy
from comparison_plots import comparison_records,STYLES

def record(case='W01',time=10,accepted=True):
 return dict(case=case,id=case+'_'+str(time),time_s=time,project_accepted=accepted,
             force_wave_response=dict(cycle_count=4,reference_x_m=0.,force_reference='C01',phase_deg=[0,180,360],
               eta_prime_mean_m=[0,0,0],lift_minus_C01_mean_N=[180,-160,180],drag_minus_C01_mean_N=[-10,8,-10]))

class ComparisonSelectionTests(unittest.TestCase):
 def test_latest_accepted_run_only_with_same_reference_and_four_cycles(self):
  earlier=record(time=10);extended=record(time=12);pending=record(time=13,accepted=False)
  incomplete=record('W02');incomplete['force_wave_response']['cycle_count']=3
  wrong_origin=record('W03');wrong_origin['force_wave_response']['reference_x_m']=-.5
  selected,excluded=comparison_records([earlier,extended,pending,incomplete,wrong_origin])
  self.assertEqual([r['id'] for r in selected],['W01_12']);self.assertEqual(len(excluded),3)
 def test_new_wave_is_added_with_independent_style_and_data_unchanged(self):
  results=[record('W01'),record('W02'),record('W03'),record('W04')];original=copy.deepcopy(results)
  selected,_=comparison_records(results)
  self.assertEqual([r['case'] for r in selected],['W01','W02','W03','W04'])
  self.assertEqual(results,original);self.assertEqual(len({STYLES[r['case']][0] for r in selected}),4)
 def test_nonfinite_or_partial_phase_is_excluded(self):
  bad=record();bad['force_wave_response']['lift_minus_C01_mean_N'][0]=float('nan')
  partial=record('W02');partial['force_wave_response']['phase_deg']=[0,90,180]
  selected,excluded=comparison_records([bad,partial]);self.assertFalse(selected);self.assertEqual(len(excluded),2)
 def test_old_cycle_centered_response_is_excluded(self):
  old=record();old['force_wave_response'].pop('force_reference')
  selected,excluded=comparison_records([old]);self.assertFalse(selected)
  self.assertEqual(excluded[0]['reason'],'Accepted C01 force reference required')

if __name__=='__main__':unittest.main()
