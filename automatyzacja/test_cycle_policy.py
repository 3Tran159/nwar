import unittest
import numpy as np
import analysis
from common import period
from cycle_policy import POLICY_ID, accepted_cycles, selection
from project_results import q_result


class FiveCyclePolicyTests(unittest.TestCase):
    def signal(self, end=9.3):
        T=period(20);t=np.arange(0,end*T,.0004);angle=2*np.pi*t/T
        data=dict(time_s=t,CL_hydrodynamic=.3+.04*np.sin(angle),CD_total=.007+.002*np.sin(angle))
        gauge=np.column_stack((t[::10],.25*np.sin(angle[::10])))
        return data,gauge

    def analyze(self,data,gauge):
        return analysis.cycles(data,gauge,.5,20,origin=0,probe_distance=0)

    def test_fixed_first_cycle_excluded_and_inputs_preserved(self):
        data,gauge=self.signal();baseline=self.analyze(data,gauge)
        first=baseline['cycles'][0];mask=(data['time_s']>first['start']+.01)&(data['time_s']<first['end']-.01)
        data['CL_hydrodynamic'][mask]+=10;data['CD_total'][mask]+=1
        original={k:v.copy() for k,v in data.items()}
        result=self.analyze(data,gauge)
        self.assertTrue(accepted_cycles(result))
        self.assertEqual(result['analyzed_cycle_numbers'],[2,3,4,5])
        self.assertEqual(result['discarded_cycle_numbers'],[1])
        self.assertAlmostEqual(result['CL_mean'],.3,places=5)
        self.assertAlmostEqual(result['CD_mean'],.007,places=6)
        for k in data:np.testing.assert_array_equal(data[k],original[k])

    def test_second_cycle_outlier_is_not_discarded(self):
        data,gauge=self.signal();baseline=self.analyze(data,gauge)
        second=baseline['cycles'][1];mask=(data['time_s']>second['start']+.01)&(data['time_s']<second['end']-.01)
        data['CL_hydrodynamic'][mask]+=1
        result=self.analyze(data,gauge)
        self.assertFalse(result['repeatable'])
        self.assertEqual(result['analyzed_cycle_numbers'],[2,3,4,5])

    def test_four_recorded_leave_three_and_cannot_pass(self):
        data,gauge=self.signal();baseline=self.analyze(data,gauge)
        end=baseline['cycles'][3]['end']+.02
        result=self.analyze({k:v[data['time_s']<=end] for k,v in data.items()},gauge[gauge[:,0]<=end])
        self.assertEqual(result['count'],4)
        self.assertEqual(result['analyzed_count'],3)
        self.assertFalse(result['repeatable'])
        self.assertNotIn('CD_mean',result)

    def test_no_late_best_window_selection(self):
        complete=[dict(number=i) for i in range(1,12)]
        result=selection(complete)
        self.assertEqual(result['analyzed_cycle_numbers'],[2,3,4,5])
        self.assertEqual(len(complete),11)

    def test_dashboard_finishes_at_five_without_drawing_six(self):
        from wave_view import next_cycle_progress,partial_force_cycle
        data,gauge=self.signal();phase=self.analyze(data,gauge)
        progress=next_cycle_progress(data,gauge,phase,20,0,0,active=True)
        self.assertTrue(progress['complete'])
        self.assertEqual(progress['cycle_number'],5)
        self.assertIsNone(partial_force_cycle(data,gauge,progress))

    def test_legacy_four_cycle_proof_cannot_release_or_publish_q(self):
        self.assertFalse(accepted_cycles(dict(count=4,repeatable=True)))
        from advance_wave_queue import choose_case
        j=dict(id='old',case_id='W04',status='completed',created='1',spec={})
        proof=lambda j:(dict(project_accepted=True,run_verification='passed'),dict(health=dict(ok=True),cycles=dict(count=4,repeatable=True)))
        self.assertEqual(choose_case(['W04'],[j],proof)['status'],'blocked')
        self.assertIsNone(q_result(dict(cycles=dict(CD_mean=.007,window=[1,2])),dict(project_accepted=True),dict(project_primary_settled=True)))


if __name__=='__main__':unittest.main()
