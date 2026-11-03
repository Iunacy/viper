"""Temporary orchestration doubles only; no physical or learned evidence generated."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from embodiment import rental


class RentalPipeline(unittest.TestCase):
    provenance = {'relic_commit': 'synthetic-test', 'source_sha256': {'fixture': 'synthetic'}, 'relic_worktree_dirty': False}

    def args(self, directory, stage='m0'):
        root = Path(directory)
        args = rental.parser().parse_args([stage, '--prefix', str(root/'runtime'), '--root', str(root/'run'),
            '--execute', '--allow-gpu', '--allow-training', '--accept-isaac-license'])
        args.pretrained = args.prefix/'models/groot'
        return args

    def mocks(self):
        stack = ExitStack()
        stack.enter_context(patch('embodiment.rental.source_provenance', return_value=self.provenance))
        stack.enter_context(patch('embodiment.rental.subprocess.run', return_value=type('Probe', (), {'returncode': 0, 'stdout': '{"ready_for_training_preflight":true}', 'stderr': ''})()))
        stack.enter_context(patch('embodiment.rental.verify', return_value={'status': 'SYNTHETIC_VALIDATOR_DOUBLE'}))
        return stack

    def worker(self, args, order, failure=None):
        planned = rental.commands(args)
        def execute(command, job, timeout, environment, **kwargs):
            stage = next(name for name, value in planned.items() if value == command)
            order.append(stage)
            self.assertTrue(kwargs['resource_monitor'])
            self.assertEqual(environment['HF_HUB_OFFLINE'], '1')
            self.assertGreater(timeout, 0)
            for path in rental.artifact_roots(stage, args.root):
                path.mkdir(parents=True, exist_ok=True)
                (path/'fixture').write_text('synthetic fixture; not PhysX or GR00T')
            return {'returncode': 2 if stage == failure else 0, 'timed_out': False}
        return execute

    def test_full_dependencies_resume_and_corruption_never_reruns(self):
        with tempfile.TemporaryDirectory() as temp, self.mocks():
            args = self.args(temp)
            order = []
            with patch('embodiment.rental.execute', side_effect=self.worker(args, order)):
                result = rental.pipeline(args)
            self.assertEqual(result['status'], 'COMPLETE', result.get('error'))
            self.assertEqual(order, ['qualify', 'collect', 'g3', 'm0_train', 'm0'])
            self.assertFalse(result['m0_passed'])  # a validator double cannot claim M0 PASS
            with patch('embodiment.rental.execute', side_effect=AssertionError('no repeated compute')):
                self.assertEqual(rental.pipeline(args)['status'], 'COMPLETE')
                args.stage = 'report'
                report = rental.pipeline(args)
                self.assertEqual(report['status'], 'AUDITED')
                (args.root/'session/pilot/fixture').write_text('corrupted')
                self.assertEqual(rental.pipeline(args)['status'], 'BLOCKED')

    def test_failed_dependency_stops_all_later_stages_and_limits_attempts(self):
        with tempfile.TemporaryDirectory() as temp, self.mocks():
            args, order = self.args(temp), []
            with patch('embodiment.rental.execute', side_effect=self.worker(args, order, 'qualify')):
                for _ in range(3):
                    self.assertEqual(rental.pipeline(args)['status'], 'BLOCKED')
            self.assertEqual(order, ['qualify', 'qualify'])

    def test_clean_machine_dry_run_has_no_subprocess_or_model_requirement(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.rental.subprocess.run', side_effect=AssertionError('no process')), \
             patch('embodiment.rental.execute', side_effect=AssertionError('no execution')):
            args = self.args(temp, 'full')
            args.execute = False
            report = rental.pipeline(args)
            self.assertEqual(report['status'], 'NOT_EXECUTED')
            self.assertIn('training', report['setup']['runtimes'])
            self.assertIn('download-sha256', str(report['setup']))
            self.assertFalse(args.root.exists())
            for command in report['commands'].values():
                self.assertNotIn('/home/iris', str(command))

    def test_consent_rejected_before_launch(self):
        with redirect_stderr(io.StringIO()), patch('embodiment.rental.pipeline', side_effect=AssertionError('no execution')):
            for arguments in (['collect', '--execute'], ['g3', '--execute', '--allow-gpu', '--accept-isaac-license'],
                              ['setup', '--allow-model-downloads'], ['collect', '--background']):
                with self.assertRaises(SystemExit): rental.main(arguments)

    def test_detached_launcher_closes_terminal_and_preserves_consent(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), \
             patch('embodiment.rental.subprocess.Popen') as spawn:
            spawn.return_value.pid = 123
            self.assertEqual(rental.main(['collect', '--root', temp, '--execute', '--allow-gpu',
                '--accept-isaac-license', '--background']), 0)
            self.assertTrue(spawn.call_args.kwargs['start_new_session'])
            self.assertEqual(spawn.call_args.kwargs['stdin'], -3)
            command = spawn.call_args.args[0]
            self.assertNotIn('--background', command)
            self.assertIn('--allow-gpu', command)
            launch = json.loads((Path(temp)/'detached/job-0000/launch.json').read_text())
            self.assertEqual(launch['status'], 'LAUNCHED')

    def test_acquisition_removes_offline_flags_and_preserves_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args(temp, 'setup')
            def acquire(command, job, timeout, environment):
                self.assertNotIn('HF_HUB_OFFLINE', environment)
                self.assertNotIn('TRANSFORMERS_OFFLINE', environment)
                self.assertIn('--license-accepted', command)
                return {'returncode': 0}
            with patch('embodiment.rental.execute', side_effect=acquire):
                rental.acquire_models(args)
                rental.acquire_models(args)
            self.assertEqual(len(list((args.prefix/'model_acquisition').glob('attempt-*'))), 2)

    def test_live_orphan_prevents_new_pipeline(self):
        import fcntl
        with tempfile.TemporaryDirectory() as temp, self.mocks():
            args = self.args(temp)
            lease_path = args.root/'orphan/.running'
            lease_path.parent.mkdir(parents=True)
            with lease_path.open('a') as lease:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch('embodiment.rental.execute', side_effect=AssertionError('no duplicate')):
                    report = rental.pipeline(args)
                self.assertEqual(report['status'], 'BLOCKED')
                self.assertIn('still running', report['error'])

    def test_explicit_full_workflow_installs_and_acquires_before_gpu_stages(self):
        with tempfile.TemporaryDirectory() as temp, self.mocks():
            args = self.args(temp, 'full')
            args.allow_model_downloads = args.accept_model_license = args.training_runtime = True
            order = []
            with patch('embodiment.deployment.install', side_effect=lambda *a, **kw: order.append('setup') or {'status': 'INSTALLED'}), \
                 patch('embodiment.rental.acquire_models', side_effect=lambda *a: order.append('models') or {'returncode': 0}), \
                 patch('embodiment.rental.execute', side_effect=self.worker(args, order)):
                result = rental.pipeline(args)
            self.assertEqual(result['status'], 'COMPLETE', result.get('error'))
            self.assertEqual(order, ['setup', 'models', 'qualify', 'collect', 'g3', 'm0_train', 'm0'])

    def test_report_reads_saved_custom_budget_and_reports_an_active_detached_run(self):
        import fcntl
        with tempfile.TemporaryDirectory() as temp, self.mocks():
            args = self.args(temp, 'collect')
            args.episodes = 20
            with patch('embodiment.rental.execute', side_effect=self.worker(args, [])):
                self.assertEqual(rental.pipeline(args)['status'], 'COMPLETE')
            args.stage, args.episodes = 'report', 12
            self.assertEqual(rental.pipeline(args)['status'], 'AUDITED')
            with (args.root/'pipeline/.lock').open('r') as lease:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(rental.pipeline(args)['status'], 'RUNNING')

    def test_missing_pretrained_weights_block_before_simulation_dependencies(self):
        with tempfile.TemporaryDirectory() as temp, self.mocks(), \
             patch('embodiment.rental.subprocess.run', return_value=type('Probe', (), {'returncode': 2, 'stdout': '{"ready_for_training_preflight":false,"blockers":["missing local weights"]}', 'stderr': ''})()), \
             patch('embodiment.rental.execute', side_effect=AssertionError('no paid simulation without G3 prerequisites')):
            result = rental.pipeline(self.args(temp, 'g3'))
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertIn('preflight failed', result['error'])
