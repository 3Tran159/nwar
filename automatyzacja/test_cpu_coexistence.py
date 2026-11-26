import copy
import unittest
from cpu_coexistence import classify


class CPUCoexistenceTest(unittest.TestCase):
    def setUp(self):
        self.procs = {
            10: dict(pid=10, parent=1, name='starccm+.exe', birth='100', has_command=True,
                     gpu_flag=False, command_sha256='cpu', exe='STAR21.04'),
            11: dict(pid=11, parent=10, name='python.exe', birth='101', has_command=True,
                     gpu_flag=False, command_sha256='child', exe='Python'),
            12: dict(pid=12, parent=11, name='mpiexec.exe', birth='102', has_command=True,
                     gpu_flag=False, command_sha256='mpi', exe='MPI'),
            13: dict(pid=13, parent=12, name='star-ccm+.exe', birth='103', has_command=True,
                     gpu_flag=False, command_sha256='node', exe='STAR21.04')}
        self.approval = dict(authorized=True, scope='PRE_W04_observation_CPU_coexistence',
                            cpu_roots=[copy.deepcopy(self.procs[10])])

    def blocked(self):
        return classify(self.procs, self.approval)['blockers']

    def test_known_cpu_tree_allowed(self):
        self.assertFalse(self.blocked())

    def test_gpu_child_rejected(self):
        self.procs[13]['gpu_flag'] = True
        self.assertEqual([p['pid'] for p in self.blocked()], [13])

    def test_gpu_root_rejected(self):
        self.procs[10]['gpu_flag'] = True
        self.assertEqual(len(self.blocked()), 3)

    def test_unknown_root_rejected(self):
        self.procs[20] = dict(self.procs[10], pid=20, birth='200')
        self.assertEqual([p['pid'] for p in self.blocked()], [20])

    def test_reused_root_pid_rejected(self):
        self.procs[10]['birth'] = '99'
        self.assertEqual(len(self.blocked()), 3)

    def test_changed_root_command_rejected(self):
        self.procs[10]['command_sha256'] = 'changed'
        self.assertEqual(len(self.blocked()), 3)

    def test_missing_parent_or_command_rejected(self):
        self.procs.pop(11)
        self.assertEqual(len(self.blocked()), 2)
        self.procs[10]['has_command'] = False
        self.assertEqual(len(self.blocked()), 3)

    def test_reused_intermediate_parent_rejected(self):
        self.procs[11]['birth'] = '110'
        self.assertEqual(len(self.blocked()), 2)

    def test_missing_authorization_rejected(self):
        self.approval['authorized'] = False
        with self.assertRaises(ValueError):
            self.blocked()

    def test_completed_foreign_tree_no_longer_blocks(self):
        self.procs.clear()
        self.assertFalse(self.blocked())


if __name__ == '__main__':
    unittest.main()
