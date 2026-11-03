from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from embodiment.collection import atomic_json, hashes
from embodiment.qualification_pair import qualify


class QualificationRestart(unittest.TestCase):
    provenance = {'relic_commit': 'synthetic', 'source_sha256': {'fixture': 'synthetic'}, 'relic_worktree_dirty': False}
    def verify(self, folder, robot, config):
        if not (folder/'valid').is_file():
            raise ValueError('synthetic incomplete evidence')
        saved = {'report': {}, 'run_path': str(folder), 'evidence_sha256': hashes(folder)}
        return saved, [SimpleNamespace(outcome={'success': True}) for _ in range(20)]

    def worker(self, command, job, timeout, **kwargs):
        self.assertIn('--enable_cameras', command)
        self.assertTrue(kwargs['resource_monitor'])
        folder = job/'run'
        folder.mkdir()
        (folder/'valid').write_text('synthetic fixture; no physics')
        return {'returncode': 0, 'timed_out': False}

    def mocks(self):
        stack = ExitStack()
        stack.enter_context(patch('embodiment.qualification_pair.source_provenance', return_value=self.provenance))
        stack.enter_context(patch('embodiment.qualification_pair.verify_robot', side_effect=self.verify))
        stack.enter_context(patch('embodiment.qualification_pair.validate_pair'))
        return stack

    def test_both_completed_arms_are_reused_only_with_identical_raw_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks():
            root = Path(temporary)
            with patch('embodiment.qualification_pair.execute', side_effect=self.worker) as execute:
                result = qualify(root, run=True)
                self.assertEqual(result['status'], 'PASS', result['errors'])
                self.assertEqual(execute.call_count, 2)
            with patch('embodiment.qualification_pair.execute', side_effect=AssertionError('no rerun')):
                self.assertEqual(qualify(root, run=True)['status'], 'PASS')
                (root/'openmanipulator_x/attempt-0000/run/valid').write_text('corrupted')
                result = qualify(root, run=True)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertIn('artifacts changed', result['errors'][0])

    def test_failed_attempt_stops_other_arm_and_retry_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks():
            root = Path(temporary)
            def failed(command, job, timeout, **kwargs):
                (job/'run').mkdir()
                atomic_json(job/'run/report.json', {'simulation_executed': True, 'completed': False})
                return {'returncode': 2, 'timed_out': True}
            with patch('embodiment.qualification_pair.execute', side_effect=failed) as execute:
                result = qualify(root, run=True)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertTrue(result['simulation_executed'])
                self.assertEqual(execute.call_count, 1)
            with patch('embodiment.qualification_pair.execute', side_effect=self.worker):
                self.assertEqual(qualify(root, run=True)['status'], 'PASS')
            self.assertTrue((root/'openmanipulator_x/attempt-0000/run/report.json').exists())
            self.assertTrue((root/'openmanipulator_x/attempt-0001/run/valid').exists())

    def test_failed_attempts_are_bounded_across_restarts(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks(), \
             patch('embodiment.qualification_pair.execute', return_value={'returncode': 2, 'timed_out': False}) as execute:
            root = Path(temporary)
            for _ in range(3):
                self.assertEqual(qualify(root, run=True)['status'], 'BLOCKED')
            self.assertEqual(execute.call_count, 2)
