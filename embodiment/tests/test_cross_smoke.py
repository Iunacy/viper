from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from embodiment.cross_smoke import workflow


class CrossSmoke(unittest.TestCase):
    def test_dry_run_records_missing_inputs_without_compute(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('embodiment.cross_smoke.verify_source'), patch('embodiment.cross_smoke.smoke', side_effect=AssertionError('compute forbidden')):
                result = workflow(root, root/'a', root/'b', root/'base', root/'run')
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertFalse(result['training_executed'])
            self.assertFalse(result['closed_loop_executed'])
            self.assertTrue((root/'run/result.json').is_file())

    def test_completed_preflight_is_idempotent_and_change_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('embodiment.cross_smoke.verify_source'), \
                 patch('embodiment.cross_smoke.validate_export', side_effect=lambda p: {'embodiment': 'openmanipulator_x' if p.name == 'a' else 'franka_panda', 'split': 'train'}), \
                 patch('embodiment.cross_smoke.validate_with_upstream', return_value={'reader': 'unit_fixture'}), \
                 patch('embodiment.cross_smoke.dataset_digest', return_value='fixture'), \
                 patch('embodiment.cross_smoke.validate_checkpoint', return_value={'weight_paths': []}), \
                 patch('embodiment.cross_smoke.file_digest', return_value='fixture'), \
                 patch('embodiment.cross_smoke.smoke', side_effect=AssertionError('compute forbidden')):
                for _ in range(2):
                    result = workflow(root, root/'a', root/'b', root/'base', root/'run')
                    self.assertEqual(result['status'], 'PREFLIGHT_ONLY')
                changed = workflow(root, root/'a', root/'b', root/'different', root/'run')
                self.assertEqual(changed['status'], 'BLOCKED')
                self.assertIn('changed', changed['errors'][0])

    def test_physical_retries_preserve_previous_attempts(self):
        from embodiment.cross_smoke import physical_gate
        from embodiment.dataset import read_json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'closed_loop'
            def fixture(request, attempt, execute, timeout):
                attempt.mkdir()
                (attempt/'preserved.log').write_text('synthetic fixture')
                return {'status': 'BLOCKED', 'attempt': str(attempt)}
            with patch('embodiment.closed_loop_smoke.run', side_effect=fixture):
                for index in range(2):
                    result = physical_gate({}, root, 10)
                    self.assertEqual(result['attempt'], str(root/f'attempt-{index:04d}'))
                    self.assertEqual(read_json(root/'result.json'), result)
            self.assertTrue((root/'attempt-0000/preserved.log').exists())
            self.assertTrue((root/'attempt-0001/preserved.log').exists())

    def test_incomplete_physical_options_fail_before_training(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('embodiment.cross_smoke.verify_source', side_effect=AssertionError('no training or upstream load')):
                result = workflow(root, root/'a', root/'b', root/'base', root/'run',
                                  execute=True, simulation_python='/sim/python')
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertIn('both simulation interpreter', result['errors'][0])
