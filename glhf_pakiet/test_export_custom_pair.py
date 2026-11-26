from pathlib import Path
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
import zipfile

sys.path.insert(0,str(Path(__file__).parent/'templates'))
import export_custom_pair as exporter


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.data=self.base/'workspaces/2606/data'
        self.data.mkdir(parents=True)
        (self.base/'launcher.json').write_text(json.dumps(dict(release='2606',workspace_root=str(self.base/'workspaces'))))
        self.entries=[]
        for case,length in [('CUSTOM001',20.),('CUSTOM002',30.)]:
            folder=self.data/'runs'/case
            folder.mkdir(parents=True)
            (folder/'latest.sim').write_bytes((case+' mock simulation').encode())
            h=hashlib.sha256((folder/'latest.sim').read_bytes()).hexdigest()
            for name,data in [('latest_checkpoint.json',dict(file='latest.sim',time_s=1.0004,step=1,healthy=True)),
                              ('final_integrity.json',dict(time_s=1.0004,bytes=(folder/'latest.sim').stat().st_size,sha256=h)),
                              ('completed.json',dict(status='target_reached',time_s=1.0004)),
                              ('wave_setup_audit.json',dict(H_m=1.5,lambda_m=length))]:
                (folder/name).write_text(json.dumps(data))
            (folder/'history.csv').write_text('time_s,step,CL_hydrodynamic,CD_total\n1.0000,0,0.1,0.01\n1.0004,1,0.2,0.02\n')
            (folder/'gauges.csv').write_text('time_s,x_m,eta_actual_m\n1.0000,0,0.1\n1.0004,0,0.2\n')
            (folder/'wake.simh').write_bytes(b'mock field history')
            self.entries.append(dict(id=case,status='completed',case_id=case,folder=str(folder),created='2026-11-08',spec=dict(H=1.5,L=length,dt=.0004)))
        with closing(sqlite3.connect(self.data/'queue.sqlite')) as db:
            db.execute('CREATE TABLE jobs(id TEXT,status TEXT,case_id TEXT,folder TEXT,created TEXT,spec TEXT)')
            for item in self.entries:
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',tuple(json.dumps(item[k]) if k=='spec' else item[k] for k in ('id','status','case_id','folder','created','spec')))
            db.commit()

    def test_export_preserves_data_and_both_sims(self):
        before={p:p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        archive=exporter.export_pair(self.base,self.base/'GLHF_exports')
        self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))
        with zipfile.ZipFile(archive) as z:
            m=json.loads(z.read('manifest.json'))
            for case in exporter.CASES:
                self.assertTrue(m['cases'][case]['saved_final_verified'])
                for member,record in m['cases'][case]['files'].items():
                    raw=z.read(case+'/'+member)
                    self.assertEqual(record,dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                self.assertIn(case+'/segments/000/wake.simh',z.namelist())
                self.assertIn(case+'/checkpoint/'+case+'_final.sim',z.namelist())

    def test_active_rejected(self):
        with closing(sqlite3.connect(self.data/'queue.sqlite')) as db:
            db.execute("UPDATE jobs SET status='running' WHERE case_id='CUSTOM001'");db.commit()
        with self.assertRaisesRegex(ValueError,'still active'):
            exporter.export_pair(self.base,self.base/'GLHF_exports')

    def test_wrong_hash_rejected_without_published_zip(self):
        p=self.data/'runs/CUSTOM002/final_integrity.json'
        r=exporter.read(p);r['sha256']='0'*64;p.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError,'checksum differs'):
            exporter.export_pair(self.base,self.base/'GLHF_exports')
        self.assertEqual(list((self.base/'GLHF_exports').glob('*.zip')),[])


if __name__=='__main__':unittest.main()
