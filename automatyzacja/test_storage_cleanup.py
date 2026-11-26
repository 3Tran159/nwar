import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import storage_cleanup as clean


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='nwar_retention_test_')
        self.base=Path(self.temp.name)
        self.runs=self.base/'runs';self.runs.mkdir()
        self.backup=self.base/'backup';self.backup.mkdir()
        self.config=dict(protected_case_ids=['W04k'])
        self.patches=[patch.object(clean,'RUNS',self.runs),patch.object(clean,'jobs',return_value=[])]
        for p in self.patches:p.start()

    def tearDown(self):
        # Remove only test-owned junctions with rmdir, never recurse through them.
        for p in self.runs.iterdir():
            if clean.reparse(p):p.rmdir()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def archive(self):
        a=clean.Archive(self.backup,True);a.config=self.config;a.reserve=0
        return a

    def entry(self,name='finished'):
        p=self.runs/name;p.mkdir()
        (p/'final.sim').write_bytes(b'saved simulation')
        (p/'wake.simh').write_bytes(b'field history')
        return dict(id=name,case_id='W04h',status='completed',folder=str(p))

    def test_archive_verifies_then_preserves_original_path(self):
        j=self.entry();a=self.archive();a.archive(j)
        original=Path(j['folder']);target=self.backup/'run_archive/W04h/finished'
        self.assertTrue(clean.reparse(original));self.assertEqual(original.resolve(),target)
        self.assertEqual((original/'wake.simh').read_bytes(),b'field history')
        self.assertFalse(any(p.name.startswith('.nwar_cleanup_retired_') for p in self.runs.iterdir()))
        self.assertFalse(clean.eligible(j,self.config,set()))

    def test_checksum_failure_preserves_original(self):
        j=self.entry();a=self.archive()
        target=self.backup/'run_archive/W04h/finished';target.mkdir(parents=True)
        (target/'final.sim').write_bytes(b'wrong archive')
        with self.assertRaises(ValueError):a.archive(j)
        self.assertFalse(clean.reparse(Path(j['folder'])))
        self.assertEqual((Path(j['folder'])/'final.sim').read_bytes(),b'saved simulation')

    def test_active_source_and_parent_are_protected(self):
        j=self.entry();active=dict(id='active',case_id='W04k',status='running',folder=str(self.runs/'live'),spec=dict(parent_id=j['id'],source=str(Path(j['folder'])/'final.sim')))
        protected=clean.protected_paths([j,active],self.config)
        self.assertFalse(clean.eligible(j,self.config,protected))
        self.assertFalse(clean.eligible(active,self.config,protected))

    def test_identical_histories_share_only_backup_storage(self):
        import os
        a=self.archive();j=self.entry('one');timestamp=(Path(j['folder'])/'wake.simh').stat().st_mtime_ns;a.archive(j);j2=self.entry('two')
        os.utime(Path(j2['folder'])/'wake.simh',ns=(timestamp,timestamp));a.archive(j2)
        one=self.backup/'run_archive/W04h/one/wake.simh';two=self.backup/'run_archive/W04h/two/wake.simh'
        self.assertEqual(one.stat().st_ino,two.stat().st_ino)
        self.assertEqual(one.read_bytes(),b'field history')

    def test_junction_failure_rolls_back_working_directory(self):
        j=self.entry();a=self.archive()
        with patch.object(a,'junction',side_effect=ValueError('test: unavailable junction')):
            with self.assertRaises(ValueError):a.archive(j)
        self.assertFalse(clean.reparse(Path(j['folder'])))
        self.assertEqual((Path(j['folder'])/'wake.simh').read_bytes(),b'field history')

    def test_interrupted_purge_is_recovered_without_losing_archive(self):
        j=self.entry();a=self.archive()
        with patch.object(a,'purge_retired',side_effect=OSError('test: interrupted purge')):
            with self.assertRaises(OSError):a.archive(j)
        old=self.runs/'.nwar_cleanup_retired_finished'
        self.assertTrue(old.exists());self.assertTrue(clean.reparse(Path(j['folder'])))
        a.recover_transactions()
        self.assertFalse(old.exists());self.assertEqual((Path(j['folder'])/'final.sim').read_bytes(),b'saved simulation')

    def test_only_old_marked_reports_are_deleted(self):
        import os,time
        a=self.archive();reports=self.base/'reports';reports.mkdir()
        old=reports/'20261104_072353_632994';old.mkdir()
        (old/'report.html').write_text('old');(old/'audit.json').write_text('{}')
        unrelated=reports/'personal';unrelated.mkdir();(unrelated/'report.html').write_text('keep')
        partial=reports/'20261104_082158_212575';partial.mkdir()
        for n in ('C01_forces.png','C01_forces.svg','W01_validation.json'):(partial/n).write_text('generated')
        os.utime(partial,(time.time()-172800,time.time()-172800))
        finalroot=self.backup/'final_reports';current=finalroot/'final_current';current.mkdir(parents=True)
        (current/'report.html').write_text('current')
        clean.write(self.base/'latest_report.json',dict(directory=str(current),errors=[]))
        clean.write(self.base/'report_storage.json',dict(final_directory=str(finalroot)))
        with patch.object(clean,'HERE',self.base):a.old_reports()
        self.assertFalse(old.exists());self.assertFalse(partial.exists());self.assertTrue(unrelated.exists());self.assertTrue(current.exists())

    def test_complete_import_keeps_containment_checks_valid(self):
        from glhf_bundle import path_under
        j=self.entry();source=Path(j['folder']);segment=source/'segments/001';segment.mkdir(parents=True)
        (segment/'history.csv').write_text('time_s,Fx_N\n1,2\n')
        self.archive().archive(j)
        resolved=path_under(source,'segments/001/history.csv')
        self.assertEqual(resolved.read_text(),'time_s,Fx_N\n1,2\n')
        self.assertTrue(resolved.resolve().is_relative_to(source.resolve()))

    def test_native_save_timestamp_is_preserved(self):
        import os
        a=self.archive();one=self.entry('one');a.archive(one)
        two=self.entry('two');source=Path(two['folder'])/'wake.simh'
        os.utime(source,ns=(1700000000000000000,1700000000000000000));a.archive(two)
        result=Path(two['folder'])/'wake.simh'
        self.assertEqual(result.stat().st_mtime_ns,1700000000000000000)
        self.assertNotEqual(result.stat().st_ino,(Path(one['folder'])/'wake.simh').stat().st_ino)


if __name__=='__main__':unittest.main()
