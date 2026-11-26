from pathlib import Path
from contextlib import closing
import json
import sqlite3
import sys
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).parent/'templates'))
import export_w04i as exporter
from test_export_custom_pair import ExportTests


class W04iTests(ExportTests):
    def setUp(self):
        super().setUp()
        with closing(sqlite3.connect(self.data/'queue.sqlite')) as db:
            old=json.loads(db.execute("SELECT spec FROM jobs WHERE case_id='CUSTOM001'").fetchone()[0])
            old.update(H=1.,L=15.,mesh_profile=dict(original_C01_sha256=exporter.C01))
            db.execute("UPDATE jobs SET spec=? WHERE case_id='CUSTOM001'",(json.dumps(old),));db.commit()
        folder=self.data/'runs/CUSTOM001'
        (folder/'wave_setup_audit.json').write_text(json.dumps(dict(H_m=1.,lambda_m=15.)))
        done=json.loads((folder/'completed.json').read_text());done.update(complete_cycles=5,status='five_cycles_recorded')
        (folder/'completed.json').write_text(json.dumps(done))
        (self.base/'workspaces/2606/app').mkdir()
        (self.base/'workspaces/2606/app/NwarWave.java').write_text('// exact macro provenance')
        self.small=patch.object(exporter,'MIN_SIM_BYTES',1);self.small.start();self.addCleanup(self.small.stop)

    # The inherited tests target the older two-case exporter; this class adds only
    # the pinned-wave export tests below and runs those explicitly.
    def test_W04i_export_and_source_unchanged(self):
        before={p:p.read_bytes() for p in self.data.rglob('*') if p.is_file()}
        archive=exporter.export_w04i(self.base,self.base/'GLHF_exports')
        self.assertTrue(all(p.read_bytes()==value for p,value in before.items()))
        with zipfile.ZipFile(archive) as z:
            m=json.loads(z.read('manifest.json'))['cases']['W04i']
            self.assertEqual(m['original_case_id'],'CUSTOM001')
            self.assertTrue(m['run_completed'])
            self.assertIn('W04i/checkpoint/W04i_final.sim',z.namelist())
            self.assertIn('W04i/application/NwarWave.java',z.namelist())
            self.assertTrue(all(not name.startswith('CUSTOM') for name in z.namelist()))

    def test_W04i_active_newest_not_replaced_by_old_save(self):
        with closing(sqlite3.connect(self.data/'queue.sqlite')) as db:
            row=list(db.execute("SELECT * FROM jobs WHERE case_id='CUSTOM001'").fetchone())
            row[0]='newer';row[1]='running';row[4]='2026-11-09'
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',row);db.commit()
        with self.assertRaisesRegex(ValueError,'still active'):
            exporter.export_w04i(self.base,self.base/'GLHF_exports')

    def test_W04i_wrong_dimensions_rejected(self):
        with closing(sqlite3.connect(self.data/'queue.sqlite')) as db:
            db.execute("DELETE FROM jobs WHERE case_id='CUSTOM001'");db.commit()
        with self.assertRaisesRegex(ValueError,'No W04i save'):
            exporter.export_w04i(self.base,self.base/'GLHF_exports')

    def test_W04i_paused_export_remains_saved(self):
        with closing(sqlite3.connect(self.data/'queue.sqlite')) as db:
            db.execute("UPDATE jobs SET status='paused' WHERE case_id='CUSTOM001'");db.commit()
        archive=exporter.export_w04i(self.base,self.base/'GLHF_exports')
        with zipfile.ZipFile(archive) as z:
            m=json.loads(z.read('manifest.json'))['cases']['W04i']
            self.assertFalse(m['run_completed'])
            self.assertIn('W04i/checkpoint/W04i_saved.sim',z.namelist())


if __name__=='__main__':
    suite=unittest.TestSuite(W04iTests(name) for name in unittest.defaultTestLoader.getTestCaseNames(W04iTests) if name.startswith('test_W04i_'))
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(not result.wasSuccessful())
