import unittest
from unittest.mock import patch
from types import SimpleNamespace
import resource_limits as limits

class ResourcePolicyTests(unittest.TestCase):
    def test_eight_gib_boundary_and_recovery_from_old_guard(self):
        with patch.object(limits,'minimum_free_ram_gib',return_value=8),patch.object(limits.shutil,'disk_usage',return_value=SimpleNamespace(free=100*2**30)):
            self.assertIsNone(limits.memory_reason(lambda:8*2**30))
            self.assertEqual(limits.memory_reason(lambda:8*2**30-1),'RAM_below8GiB')
            self.assertIsNone(limits.owned_resource_problem(lambda:'RAM_below16GiB',lambda:12*2**30))

    def test_disk_and_stop_guards_remain_effective(self):
        with patch.object(limits,'minimum_free_ram_gib',return_value=8),patch.object(limits.shutil,'disk_usage',return_value=SimpleNamespace(free=5*2**30)):
            self.assertEqual(limits.owned_resource_problem(lambda:'RAM_below16GiB',lambda:12*2**30),'disk_guard')
            self.assertEqual(limits.owned_resource_problem(lambda:'STOP_ALL',lambda:12*2**30),'STOP_ALL')

if __name__=='__main__':unittest.main()
