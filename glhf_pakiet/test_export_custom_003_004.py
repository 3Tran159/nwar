from pathlib import Path
from contextlib import closing
from unittest.mock import patch
import csv,hashlib,json,math,sqlite3,sys,tempfile,unittest,zipfile
sys.path.insert(0,str(Path(__file__).parent/'templates'))
import export_custom_003_004 as exporter

class ExportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.data=self.root/'workspaces/2606/data';self.data.mkdir(parents=True)
  (self.root/'launcher.json').write_text(json.dumps(dict(release='2606',workspace_root=str(self.root/'workspaces'))))
  self.entries=[]
  for i,(case,(label,h,l))in enumerate(exporter.WAVES.items()):
   folder=self.data/'runs'/case;folder.mkdir(parents=True)
   sim=folder/'wave_pilot_final.sim';sim.write_bytes((case+' final SIM').encode())
   digest=hashlib.sha256(sim.read_bytes()).hexdigest()
   docs={'latest_checkpoint.json':dict(file=sim.name,time_s=5.8008,step=2,healthy=True),
         'final_integrity.json':dict(sha256=digest,bytes=sim.stat().st_size,time_s=5.8008),
         'wave_setup_audit.json':dict(H_m=h,lambda_m=l,begin_time_s=5.8),
         'completed.json':dict(status='five_cycles_recorded',complete_cycles=5),
         'stage_result.json':dict(exit_code=0,source_unchanged=True)}
   for name,v in docs.items():(folder/name).write_text(json.dumps(v))
   for name,header,rows in [('history.csv',['time_s','step'],[(5.8,0),(5.8004,1),(5.8008,2)]),
                            ('gauges.csv',['time_s','x_m','eta_actual_m'],[(5.8,-.5,0),(5.8004,-.5,.01),(5.8008,-.5,.02)])]:
    with(folder/name).open('w',newline='')as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
   (folder/'wake.simh').write_bytes(b'preserved field history')
   self.entries.append(dict(id=str(i),case_id=case,status='completed',created=str(i),folder=str(folder),
    spec=dict(H=h,L=l,dt=.0004,mesh_profile=dict(original_C01_sha256=exporter.C01))))
  with closing(sqlite3.connect(self.data/'queue.sqlite'))as db:
   db.execute('CREATE TABLE jobs(id TEXT,case_id TEXT,status TEXT,created TEXT,folder TEXT,spec TEXT)')
   for e in self.entries:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',tuple(json.dumps(e[k])if k=='spec'else e[k]for k in('id','case_id','status','created','folder','spec')))
   db.commit()

 def test_exports_both_cases_without_queue_changes(self):
  database=self.data/'queue.sqlite';before=hashlib.sha256(database.read_bytes()).hexdigest()
  with patch.object(exporter,'MIN_SIM_BYTES',0),patch.object(exporter,'saved_state',return_value=dict(time_s=5.8008,step=14502,scenes=30,wave_numbers=[math.tau/15],dt_values=[.0004])):
   archive=exporter.export_pair(self.root,self.root/'GLHF_exports')
  self.assertEqual(before,hashlib.sha256(database.read_bytes()).hexdigest())
  with zipfile.ZipFile(archive)as z:
   m=json.loads(z.read('manifest.json'))
   self.assertEqual(set(m['cases']),{'CUSTOM003','CUSTOM004'});self.assertFalse(m['queue_changed']);self.assertFalse(m['solver_started'])
   for case,(label,h,l)in exporter.WAVES.items():
    self.assertEqual(m['cases'][case]['display_id'],label)
    self.assertIn(case+'/segments/000/wake.simh',z.namelist())
    sim=m['cases'][case]['checkpoint']['path'];record=m['cases'][case]['files'][sim]
    self.assertEqual(hashlib.sha256(z.read(case+'/'+sim)).hexdigest(),record['sha256'])

 def test_newest_active_attempt_is_not_replaced_by_older_save(self):
  new=dict(self.entries[0],id='new',status='running',folder=str(self.data/'runs/new'))
  selected=exporter.select([new,*self.entries],'CUSTOM003');self.assertEqual(selected['id'],'new')
  with self.assertRaisesRegex(ValueError,'still active'):exporter.inspect_case(selected,{j['id']:j for j in self.entries},self.data)

 def test_wrong_dimensions_are_rejected(self):
  e=dict(self.entries[0],spec=dict(H=1.5,L=30.,dt=.0004))
  with self.assertRaisesRegex(ValueError,'dimensions'):exporter.select([e],'CUSTOM003')

 def test_native_sim_time_mismatch_is_rejected(self):
  with patch.object(exporter,'MIN_SIM_BYTES',0),patch.object(exporter,'saved_state',return_value=dict(time_s=5.81,step=14502,scenes=30,wave_numbers=[math.tau/15],dt_values=[.0004])):
   with self.assertRaisesRegex(ValueError,'Native SIM'):exporter.export_pair(self.root,self.root/'GLHF_exports')
  self.assertFalse((self.root/'GLHF_exports').exists())

if __name__=='__main__':unittest.main(verbosity=2)
