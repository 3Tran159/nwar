import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import native_resource_resume as recovery
from common import write

class ResourceAuthorizationTests(unittest.TestCase):
    def review(self,reason,authorized_reason):
        with tempfile.TemporaryDirectory(prefix='nwar_resource_authorization_') as work:
            folder=Path(work);(folder/'native_solve').mkdir()
            write(folder/'native_solve/stage_result.json',dict(controller_reason=reason,
                  phase='NWAR_native_solve',ownership='windows_job_closed',source_unchanged=True))
            write(folder/'resource_resume_authorization.json',dict(authorized=True,job_id='parent',
                  action='resume_after_RAM_guard',controller_reason=authorized_reason))
            parent=dict(id='parent',case_id='W04k',status='failed',folder=str(folder),spec=dict(native_production=True))
            with patch('resource_limits.minimum_free_ram_gib',return_value=8):
                recovery.verify(parent)

    def test_numerical_failure_cannot_use_ram_authorization(self):
        with self.assertRaisesRegex(ValueError,'Missing explicit RAM-policy'):
            self.review('field_health','field_health')

    def test_ram_authorization_must_match_exact_stop_reason(self):
        with self.assertRaisesRegex(ValueError,'Missing explicit RAM-policy'):
            self.review('RAM_below8GiB','RAM_below16GiB')

if __name__=='__main__':unittest.main()
