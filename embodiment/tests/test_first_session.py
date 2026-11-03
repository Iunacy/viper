"""Synthetic orchestration only: no Kit, CUDA kernels or physical trials."""
from contextlib import ExitStack
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from embodiment.first_session import run


class FirstSession(unittest.TestCase):
    provenance = {'relic_commit': 'synthetic', 'source_sha256': {'fixture': 'synthetic'}, 'relic_worktree_dirty': False}
    def arguments(self, root):
        return (root, '/sim/python', '/reader/python', '/isaac', '/groot', '/robots', '/usd')

    def mocks(self):
        stack = ExitStack()
        stack.enter_context(patch('embodiment.first_session.source_provenance', return_value=self.provenance))
        stack.enter_context(patch('embodiment.first_session.assets', return_value={'files': {'fixture': 'synthetic'}}))
        stack.enter_context(patch('embodiment.isaac_interfaces.verify', return_value={'source_interfaces_present': True}))
        stack.enter_context(patch('embodiment.upstream_validation.verify_source'))
        return stack

    def probe(self, command, **kwargs):
        self.assertNotIn('training', command)
        if 'embodiment.first_session' in command:
            self.assertEqual(kwargs['env']['CUDA_VISIBLE_DEVICES'], '')
        return SimpleNamespace(returncode=0, stdout='{"ready":true}', stderr='')

    def test_dry_run_creates_frozen_dual_robot_plan_without_processes(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks(), \
             patch('embodiment.first_session.subprocess.run', side_effect=AssertionError('no processes')), \
             patch('embodiment.first_session.execute', side_effect=AssertionError('no simulation')):
            root = Path(temporary)
            result = run(*self.arguments(root), episodes=20)
            self.assertEqual(result['status'], 'NOT_EXECUTED')
            config = json.loads((root/'session.json').read_text())
            self.assertEqual(config['contracts']['openmanipulator_x']['joint_count'], 6)
            self.assertEqual(config['contracts']['franka_panda']['joint_count'], 9)
            self.assertEqual(len(config['qualification_cases']), 20)
            self.assertEqual(len(config['pilot_cases']['train']), 60)
            self.assertFalse(result['model_weights_required'])
            self.assertEqual(run(*self.arguments(root), episodes=12)['status'], 'BLOCKED')
            self.assertEqual(len(list((root/'reports').glob('run-*.json'))), 2)

    def test_preflight_failure_reports_all_prerequisites_without_physics(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks(), \
             patch('embodiment.first_session.subprocess.run', return_value=SimpleNamespace(returncode=2,
                 stdout='{"ready":false,"blockers":["missing runtime"]}', stderr='')), \
             patch('embodiment.first_session.execute', side_effect=AssertionError('must not start')):
            result = run(*self.arguments(Path(temporary)), execute_stage=True)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertEqual(len(result['blockers']), 2)
            self.assertFalse(result['simulation_executed'])

    def test_successful_stages_resume_only_after_integrity_and_provenance_validation(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks(), \
             patch('embodiment.first_session.subprocess.run', side_effect=self.probe), \
             patch('embodiment.first_session.verify_qualification', return_value={'status': 'PASS'}), \
             patch('embodiment.first_session.verify_pilot', return_value={'status': 'VALIDATED'}):
            root = Path(temporary)
            order = []
            def worker(command, job, timeout, environment):
                stage = 'qualification' if 'embodiment.qualification_pair' in command else 'pilot'
                order.append(stage)
                path = root/stage
                path.mkdir()
                (path/'raw').write_text('synthetic temporary fixture')
                self.assertEqual(environment['VIPER_OFFLINE'], '1')
                self.assertGreater(timeout, 0)
                return {'returncode': 0, 'timed_out': False}
            with patch('embodiment.first_session.execute', side_effect=worker):
                first = run(*self.arguments(root), execute_stage=True)
            self.assertEqual(first['status'], 'QUALIFIED_AND_COLLECTED', first['blockers'])
            self.assertEqual(order, ['qualification', 'pilot'])
            self.assertFalse(first['training_executed'])
            with patch('embodiment.first_session.execute', side_effect=AssertionError('no rerun')):
                resumed = run(*self.arguments(root), execute_stage=True)
                self.assertEqual(resumed['status'], 'QUALIFIED_AND_COLLECTED')
                self.assertTrue(resumed['stages']['pilot']['reused'])
                (root/'qualification/raw').write_text('corrupted')
                rejected = run(*self.arguments(root), execute_stage=True)
                self.assertEqual(rejected['status'], 'BLOCKED')
                self.assertIn('artifacts changed', str(rejected['blockers']))

    def test_failed_qualification_stops_collection_and_caps_retry(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks(), \
             patch('embodiment.first_session.subprocess.run', side_effect=self.probe):
            root = Path(temporary)
            calls = []
            def failed(command, job, timeout, environment):
                calls.append(command)
                self.assertIn('embodiment.qualification_pair', command)
                return {'returncode': 2, 'timed_out': False}
            with patch('embodiment.first_session.execute', side_effect=failed):
                for _ in range(3):
                    self.assertEqual(run(*self.arguments(root), execute_stage=True)['status'], 'BLOCKED')
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(list((root/'processes/qualification').glob('attempt-*'))), 2)

    def test_cached_assets_can_be_relocated_but_not_corrupted_or_escaped(self):
        from embodiment.first_session import assets
        from embodiment.asset_cache import ORIGIN, PANDA
        from embodiment.dataset import file_digest
        from embodiment.assets import ROOT
        from embodiment.collection import atomic_json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, usd = root/'cache', root/'usd'
            cache.mkdir(); usd.mkdir()
            (cache/'robot').write_text('synthetic robot asset')
            (cache/'panda_replay').mkdir()
            (cache/'panda_replay/description').write_text('synthetic description')
            (usd/PANDA).parent.mkdir(parents=True)
            (usd/PANDA).write_text('synthetic USD asset')
            receipt = {'status': 'CACHED', 'origin': ORIGIN, 'entry': PANDA,
                'usd': '/previous/machine/'+PANDA, 'files': {PANDA: {'sha256': file_digest(usd/PANDA)}}}
            atomic_json(usd/'assets.json', receipt)
            catalog = {'robot': file_digest(cache/'robot')}
            panda_catalog = {'description': file_digest(cache/'panda_replay/description')}
            real_read = __import__('embodiment.first_session', fromlist=['read_json']).read_json
            def read(path):
                if path == ROOT/'assets/panda_replay_manifest.json':
                    return {'files': panda_catalog}
                return real_read(path)
            with patch('embodiment.first_session.MANIFEST', {'files': catalog}), \
                 patch('embodiment.first_session.read_json', side_effect=read), \
                 patch('embodiment.first_session.validate_urdf'):
                self.assertEqual(assets(cache, usd)['panda_usd'], str(usd/PANDA))
                (usd/PANDA).write_text('corrupt')
                with self.assertRaisesRegex(ValueError, 'asset missing or changed'):
                    assets(cache, usd)

    def test_live_prior_process_lease_prevents_another_stage_launch(self):
        import fcntl
        with tempfile.TemporaryDirectory() as temporary, self.mocks(), \
             patch('embodiment.first_session.execute', side_effect=AssertionError('no second launch')):
            root = Path(temporary)
            path = root/'processes/qualification/attempt-0000/.running'
            path.parent.mkdir(parents=True)
            with path.open('a') as lease:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = run(*self.arguments(root), execute_stage=True)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertIn('still running', str(result['blockers']))

    def test_total_deadline_stops_physics_and_preserves_the_report(self):
        with tempfile.TemporaryDirectory() as temporary, self.mocks(), \
             patch('embodiment.first_session.subprocess.run', side_effect=self.probe), \
             patch('embodiment.first_session.time.monotonic', side_effect=[0., 10., 20., 30., 40.]), \
             patch('embodiment.first_session.execute', side_effect=AssertionError('deadline must prevent physics')):
            result = run(*self.arguments(Path(temporary)), execute_stage=True, total_timeout=1)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertIn('deadline exceeded', str(result['blockers']))
