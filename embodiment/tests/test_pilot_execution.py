from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from embodiment.pilot import prepare, run


class ExecutablePilot(unittest.TestCase):
    def test_dry_run_has_separate_runtime_commands_and_no_compute(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('embodiment.pilot.run_process', side_effect=AssertionError('compute forbidden')):
                result = run(root, python='/simulation/python', data_python='/data/python')
            self.assertEqual(result['status'], 'NOT_EXECUTED')
            self.assertFalse(result['training_ready'])
            command = result['commands']['franka_panda']['train']
            self.assertEqual(command[0], '/data/python')
            self.assertEqual(command[command.index('--python')+1], '/simulation/python')
            self.assertEqual(command[command.index('--target')+1], '12')
            self.assertEqual(len(result['commands']['franka_panda']), 3)

    def test_underpowered_host_is_blocked_before_collection(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('embodiment.pilot.subprocess.run', return_value=SimpleNamespace(stdout='{"ready": false, "blockers": ["VRAM"]}', stderr='')), \
                 patch('embodiment.pilot.run_process', side_effect=AssertionError('compute forbidden')):
                result = run(Path(temporary), execute=True, groot_source=Path('/source'))
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertFalse(result['simulation_executed'])

    def test_twenty_episode_option_has_a_sufficient_frozen_retry_schedule(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare(Path(temporary), count=20)
            self.assertEqual(len(result['attempt_schedule']['train']), 60)
            for commands in result['split_commands'].values():
                for command in commands.values():
                    self.assertEqual(command[command.index('--attempt-limit')+1], '60')
                    self.assertEqual(command[command.index('--max-jobs')+1], '60')

    def test_first_failed_collection_stops_dependent_splits(self):
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = {'relic_commit': 'synthetic', 'source_sha256': {'fixture': 'synthetic'}, 'relic_worktree_dirty': False}
            with patch('embodiment.pilot.source_provenance', return_value=source), \
                 patch('embodiment.pilot.subprocess.run', return_value=SimpleNamespace(stdout='{"ready":true}', stderr='')), \
                 patch('embodiment.pilot.run_process', return_value={'returncode': 2}) as worker:
                result = run(root, groot_source=Path('/groot'), execute=True)
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertFalse(result['training_ready'])
            self.assertEqual(worker.call_count, 1)
            self.assertEqual(len(result['errors']), 1)
            self.assertEqual(json.loads((root/'execution/result.json').read_text())['status'], 'INCOMPLETE')
