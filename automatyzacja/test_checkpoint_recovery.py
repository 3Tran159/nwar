import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import checkpoint_recovery as recovery
from analysis import segment_chain, merge_segments


class RecoveryTests(unittest.TestCase):
    def test_rollback_preserves_raw_tail_and_exact_join(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);old=root/'old';view=root/'view';new=root/'new'
            for p in (old,view,new):p.mkdir()
            raw='time_s,CL_hydrodynamic\n1.0,1\n1.0004,2\n1.0008,3\n'
            (old/'history.csv').write_text(raw)
            recovery.prefix_csv(old/'history.csv',view/'history.csv',1.0004)
            (new/'history.csv').write_text('time_s,CL_hydrodynamic\n1.0004,2\n1.0008,4\n')
            data,_=merge_segments([view,new])
            self.assertEqual(data['CL_hydrodynamic'].tolist(),[1,2,4])
            self.assertEqual((old/'history.csv').read_text(),raw)

    def test_missing_exact_checkpoint_boundary_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);src=root/'raw.csv';src.write_text('time_s,value\n1.0,1\n1.0008,2\n')
            with self.assertRaisesRegex(ValueError,'exact history endpoint'):
                recovery.prefix_csv(src,root/'prefix.csv',1.0004)

    def test_failed_parent_is_only_replaced_in_recovery_chain(self):
        parent=dict(id='parent',spec={},folder='original')
        child=dict(id='child',spec=dict(parent_id='parent',checkpoint_recovery='receipt'),folder='new')
        with patch('analysis.job',return_value=parent), patch('checkpoint_recovery.verify',return_value=dict(original_folder='original',view_folder='prefix')):
            self.assertEqual(segment_chain(child),[Path('prefix'),Path('new')])
            self.assertEqual(segment_chain(parent),[Path('original')])

    def test_wrong_parent_rejected(self):
        with self.assertRaisesRegex(ValueError,'authorization'):
            recovery.check_authorization(dict(id='other',case_id='W04',status='failed'))

    def test_surface_exception_does_not_cover_other_failures(self):
        auth=dict(authorized=True,parent_id=recovery.PARENT,case_id='W04',surface_limit_m=1.5,
                  other_guards_unchanged=True,four_repeatable_cycles_required=True)
        with patch('checkpoint_recovery.read',side_effect=[auth,{},dict(error='CFL limit')]):
            with self.assertRaisesRegex(ValueError,'does not cover this failure'):
                recovery.check_authorization(dict(id=recovery.PARENT,case_id='W04',status='failed',folder='original'))

    def test_io_authorization_is_separate_and_rejects_physics_failure(self):
        self.assertNotEqual(recovery.policy(recovery.PARENT)[0],recovery.policy(recovery.IO_PARENT)[0])
        auth=dict(authorized=True,parent_id=recovery.IO_PARENT,case_id='W04',surface_limit_m=1.5,
                  other_guards_unchanged=True,four_repeatable_cycles_required=True)
        for error in ('CFL limit',recovery.EXPECTED_ERROR):
            with patch('checkpoint_recovery.read',side_effect=[auth,{},dict(error=error)]):
                with self.assertRaisesRegex(ValueError,'does not cover this failure'):
                    recovery.check_authorization(dict(id=recovery.IO_PARENT,case_id='W04',status='failed',folder='original'))


if __name__=='__main__':unittest.main()
