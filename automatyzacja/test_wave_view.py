import csv, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from common import period, sha
from wave_view import build_view, probe_points, select_source, first_cycle_progress, next_cycle_progress, partial_force_cycle
from analysis import cycles


class WaveViewTests(unittest.TestCase):
    def cycle_fixture(self, end_cycles):
        T=period(20)
        t=np.arange(2.8*T,end_cycles*T,.0004)
        data=dict(time_s=t,CL_hydrodynamic=.3+.02*np.sin(2*np.pi*t/T+.4),CD_total=.007+.001*np.cos(2*np.pi*t/T))
        gauge=np.column_stack((t[::5],.25*np.sin(2*np.pi*t[::5]/T)))
        phase=cycles(data,gauge,.5,20,origin=0,probe_distance=0)
        return data,gauge,phase

    def test_rolling_countdown_and_partial_draw_advance_after_measured_crossing(self):
        timing=dict(available=True,wall_s_per_physical_s=4000,rate_range=[3800,4200])
        for end,count in [(4.3,1),(4.7,1),(5.2,2),(7.4,4)]:
            data,gauge,phase=self.cycle_fixture(end)
            before=json.dumps(phase);raw=data['CL_hydrodynamic'].copy()
            self.assertEqual(phase['count'],count)
            progress=next_cycle_progress(data,gauge,phase,20,0,0,timing)
            partial=partial_force_cycle(data,gauge,progress)
            self.assertEqual(progress['cycle_number'],count+1)
            self.assertFalse(progress['complete']);self.assertGreater(progress['eta_wall_s'],0)
            self.assertAlmostEqual(progress['percent'],(end%1)*100,delta=2)
            self.assertEqual(partial['number'],count+1);self.assertTrue(partial['provisional'])
            self.assertAlmostEqual(partial['phase'][-1],end%1,delta=.02)
            self.assertLessEqual(partial['end'],data['time_s'][-1]);self.assertLessEqual(partial['end'],gauge[-1,0])
            np.testing.assert_allclose(partial['CL'],np.interp(partial['time_s'],data['time_s'],data['CL_hydrodynamic']))
            self.assertEqual(before,json.dumps(phase));np.testing.assert_array_equal(raw,data['CL_hydrodynamic'])
            saved=next_cycle_progress(data,gauge,phase,20,0,0,active=False)
            self.assertTrue(saved['complete']);self.assertIsNone(partial_force_cycle(data,gauge,saved))

    def test_open_cycle_never_draws_across_missing_force_samples(self):
        data,gauge,phase=self.cycle_fixture(4.6)
        p=next_cycle_progress(data,gauge,phase,20,0,0)
        keep=(data['time_s']<4.2*period(20))|(data['time_s']>4.3*period(20))
        broken={key:value[keep] for key,value in data.items()}
        self.assertIsNone(partial_force_cycle(broken,gauge,p))
        errored=dict(phase,error='Phase-probe history is not continuous')
        unavailable=next_cycle_progress(data,gauge,errored,20,0,0)
        self.assertEqual(unavailable['state'],'unavailable')
        self.assertIsNone(partial_force_cycle(data,gauge,unavailable))

    def test_estimated_end_cannot_complete_an_open_cycle(self):
        data,gauge,phase=self.cycle_fixture(5.2)
        # Preserve just the first measured cycle, with no subsequent upward crossing.
        phase.update(count=1,cycles=phase['cycles'][:1],phase_level=0,period_measured_s=period(20))
        gauge[gauge[:,0]>4.1*period(20),1]=.2
        p=next_cycle_progress(data,gauge,phase,20,0,0,dict(available=True,wall_s_per_physical_s=4000,rate_range=[3800,4200]))
        self.assertEqual(p['cycle_number'],2);self.assertEqual(p['state'],'awaiting_crossing')
        self.assertLess(p['percent'],100);self.assertFalse(p['complete']);self.assertIsNone(p['eta_wall_s'])
        partial=partial_force_cycle(data,gauge,p)
        self.assertGreater(partial['phase'][-1],1);self.assertFalse(partial['complete'])

    def test_partial_cycle_eta_and_only_measured_completion(self):
        T=period(20);start=3*T
        gauge=np.array([[start-.01,-.1],[start+.01,.1],[start+.5*T,.8]])
        phase=dict(count=0,phase_level=0)
        timing=dict(available=True,wall_s_per_physical_s=4000,rate_range=[3800,4200])
        p=first_cycle_progress({'time_s':np.array([start+.5*T])},gauge,phase,20,0,0,timing)
        self.assertAlmostEqual(p['percent'],50)
        self.assertAlmostEqual(p['eta_wall_s'],.5*T*4000)
        self.assertFalse(p['complete'])
        overdue=first_cycle_progress({'time_s':np.array([start+1.1*T])},gauge,phase,20,0,0,timing)
        self.assertEqual(overdue['state'],'awaiting_crossing')
        self.assertLess(overdue['percent'],100)
        self.assertIsNone(overdue['eta_wall_s'])
        stopped=first_cycle_progress({'time_s':np.array([start+.5*T])},gauge,phase,20,0,0,{'available':False})
        self.assertIsNone(stopped['eta_wall_s'])
        phase.update(count=1,cycles=[{'start':start,'end':start+T}])
        done=first_cycle_progress({'time_s':np.array([start+T])},gauge,phase,20,0,0)
        self.assertTrue(done['complete']);self.assertEqual(done['percent'],100)

    def test_probe_display_keeps_extrema_and_breaks_missing_intervals(self):
        t = np.arange(0, 1, .002)
        a = np.column_stack((t, np.sin(20*t)))
        a[88, 1] = 9
        a = a[(t < .3) | (t > .5)]
        points = probe_points(a, budget=80)
        self.assertIn(None, points)
        self.assertEqual(max(p[1] for p in points if p), 9)
        self.assertFalse(any(.3 <= p[0] <= .5 for p in points if p))

    def test_running_continuation_takes_precedence_over_saved_failure_tail(self):
        current = dict(id='current', case_id='W04', status='running', folder='current', spec={'parent_id':'old'})
        old = dict(id='old', case_id='W04', status='failed', folder='old', spec={})
        with patch('wave_view.run_chain', return_value=[Path('prefix'), Path('current')]), patch('wave_view.read', return_value={}):
            entry, chain, accepted = select_source('W04', [current, old], [dict(case='W04', id='old', time_s=99, source_segments=[{'path':'old/history.csv'}])])
        self.assertEqual(entry['id'], 'current')
        self.assertEqual(chain, [Path('prefix'), Path('current')])
        self.assertFalse(accepted)

    def test_probe_added_on_resume_keeps_prior_cycles_and_draws_cycle_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders=[Path(tmp)/name for name in ('original','resume')]
            T=period(20);dt=.0004;split=round(7.2*T/dt)
            t=np.arange(round(7.55*T/dt))*dt
            for folder,tt in zip(folders,(t[:split+1],t[split:])):
                folder.mkdir()
                with (folder/'history.csv').open('w',newline='') as f:
                    writer=csv.writer(f);writer.writerow(['time_s','CL_hydrodynamic','CD_total'])
                    for ti in tt:writer.writerow([ti,.3+.02*np.sin(2*np.pi*ti/T),.007+.001*np.cos(2*np.pi*ti/T)])
                with (folder/'gauges.csv').open('w',newline='') as f:
                    writer=csv.writer(f);writer.writerow(['time_s','x_m','eta_actual_m'])
                    for ti in tt[::5]:
                        writer.writerow([ti,-.5,.25*np.sin(2*np.pi*ti/T)])
                        if folder==folders[-1]:writer.writerow([ti,0,.25*np.sin(2*np.pi*(ti-.5*T/20)/T)])
            (folders[0]/'wave_setup_audit.json').write_text(json.dumps({'t0':0,'probe_distance_m':0}))
            before=[sha(folder/name) for folder in folders for name in ('history.csv','gauges.csv')]
            ref=dict(CL=.3,CD=.007,coefficient_denominator_N=3855.6)
            with patch('wave_view.force_reference_for',return_value=ref):
                view=build_view(dict(id='W02',H=.5,L=20),dict(id='resume',status='running',spec={}),folders,False)
            self.assertEqual(view['cycle_count'],4)
            self.assertEqual([c['number'] for c in view['cycles']],[2,3,4])
            self.assertEqual(view['in_progress_cycle']['number'],5)
            self.assertGreater(view['in_progress_cycle']['phase'][-1],.4)
            self.assertTrue(view['alignment']['partial_direct_history'])
            self.assertTrue(view['alignment']['estimated'])
            self.assertEqual(view['alignment']['force_shift_s'],0.)
            self.assertFalse(view['project_accepted'])
            self.assertEqual(before,[sha(folder/name) for folder in folders for name in ('history.csv','gauges.csv')])

    def test_measured_phase_preserves_force_lag_and_two_probe_delay(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); T = period(20); omega = 2*np.pi/T
            t = np.arange(0, 9*T, .0004)
            fields = ['step','time_s','CL_hydrodynamic','CD_total','Fx_N','Fz_N','max_CFL','interface_CFL','max_speed_m_s','alpha_min','alpha_max','p_min_Pa','p_max_Pa','water_volume_m3']
            with (folder/'history.csv').open('w', newline='') as f:
                writer = csv.writer(f); writer.writerow(fields)
                for i, ti in enumerate(t):
                    writer.writerow([i,ti,.3+.02*np.sin(omega*ti+np.pi/4),.007+.001*np.cos(omega*ti),1,1,1,1,18,0,1,-1000,1000,100])
            with (folder/'gauges.csv').open('w', newline='') as f:
                writer = csv.writer(f); writer.writerow(['time_s','x_m','eta_actual_m'])
                for ti in t[::5]:
                    for x, delay in [(-.5, 0),(0, 0),(1, .1)]:
                        writer.writerow([ti,x,.25*np.sin(omega*(ti-delay))])
            (folder/'wave_setup_audit.json').write_text(json.dumps({'t0':0,'probe_distance_m':0}))
            before = [sha(folder/name) for name in ('history.csv','gauges.csv')]
            ref = dict(CL=.3,CD=.007,coefficient_denominator_N=3855.6)
            with patch('wave_view.force_reference_for', return_value=ref):
                view = build_view(dict(id='W04',H=.5,L=20), dict(id='fixture',status='running',spec={}), [folder], False)
            self.assertGreaterEqual(view['cycle_count'], 4)
            self.assertAlmostEqual(view['cycles'][-1]['CL'][0], .3+.02/np.sqrt(2), delta=.0003)
            self.assertEqual(view['alignment']['force_shift_s'], 0)
            probes = {p['x_m']:p['points'] for p in view['probes']}
            peaks = [max((p for p in probes[x] if p and 3*T < p[0] < 4*T), key=lambda p:p[1])[0] for x in (0,1)]
            self.assertAlmostEqual(peaks[1]-peaks[0], .1, delta=.005)
            self.assertEqual(before, [sha(folder/name) for name in ('history.csv','gauges.csv')])
            json.dumps(view, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
