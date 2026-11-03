"""Synthetic startup orchestration; verifier doubles never create qualification evidence."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from embodiment.simulation_smoke import run, verify_robot


class StartupSmoke(unittest.TestCase):
    provenance = {'relic_commit': 'synthetic', 'source_sha256': {'fixture': 'synthetic'}, 'relic_worktree_dirty': False}

    def test_smoke_is_bounded_and_revalidates_raw_files_before_reuse(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.simulation_smoke.source_provenance', return_value=self.provenance), \
             patch('embodiment.simulation_smoke.verify_robot', return_value={'status': 'SYNTHETIC'}):
            root, calls = Path(temp), []
            def execute(command, job, timeout, **kwargs):
                calls.append(command)
                self.assertEqual(timeout, 600)
                self.assertIn('--enable_cameras', command)
                self.assertTrue(kwargs['resource_monitor'])
                (job/'run').mkdir()
                (job/'run/fixture').write_text('synthetic')
                return {'returncode': 0, 'timed_out': False}
            with patch('embodiment.simulation_smoke.execute', side_effect=execute):
                self.assertEqual(run(root, '/sim/python', True)['status'], 'PASS')
            self.assertEqual(len(calls), 2)
            with patch('embodiment.simulation_smoke.execute', side_effect=AssertionError('no repeat')):
                self.assertEqual(run(root, '/sim/python', True)['status'], 'PASS')
                (root/'franka_panda/attempt-0000/run/fixture').write_text('corrupt')
                self.assertEqual(run(root, '/sim/python', True)['status'], 'BLOCKED')

    def test_failed_startup_blocks_second_robot_and_preserves_attempt(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.simulation_smoke.source_provenance', return_value=self.provenance), \
             patch('embodiment.simulation_smoke.execute', return_value={'returncode': 2, 'timed_out': True}) as execute:
            root = Path(temp)
            for _ in range(3): self.assertEqual(run(root, '/sim/python', True)['status'], 'BLOCKED')
            self.assertEqual(execute.call_count, 2)
            self.assertFalse((root/'franka_panda').exists())

    def test_invocation_deadline_caps_worker_and_keeps_resume_configuration_fixed(self):
        from embodiment.dataset import read_json
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.simulation_smoke.source_provenance', return_value=self.provenance), \
             patch('embodiment.simulation_smoke.verify_robot', return_value={'status': 'SYNTHETIC'}):
            root, budgets = Path(temp), []
            def execute(command, job, timeout, **kwargs):
                budgets.append(timeout)
                (job/'run').mkdir()
                (job/'run/fixture').write_text('synthetic')
                return {'returncode': 0, 'timed_out': False}
            with patch('embodiment.simulation_smoke.execute', side_effect=execute), \
                 patch('time.monotonic', side_effect=[10., 100.]):
                result = run(root, '/sim/python', True, deadline=100.)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertIn('deadline exceeded', result['error'])
            self.assertEqual(budgets, [90.])
            self.assertFalse(list((root/'franka_panda').glob('attempt-*')))
            self.assertEqual(read_json(root/'configuration.json')['timeout'], 600)
            with patch('embodiment.simulation_smoke.execute', side_effect=execute), \
                 patch('time.monotonic', return_value=110.):
                result = run(root, '/sim/python', True, deadline=230.)
            self.assertEqual(result['status'], 'PASS', result)
            self.assertEqual(budgets, [90., 120.])

    def test_summary_only_cannot_earn_physical_smoke_pass(self):
        from embodiment.collection import atomic_json
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            atomic_json(root/'report.json', {'status': 'COMPLETE', 'mode': 'smoke', 'simulation_executed': False})
            atomic_json(root/'articulation.json', {})
            with self.assertRaisesRegex(ValueError, 'real completed'): verify_robot(root, 'openmanipulator_x', self.provenance)
