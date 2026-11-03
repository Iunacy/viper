"""Synthetic orchestration tests; no model, Kit, GPU or physical evidence produced."""
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from embodiment.closed_loop_smoke import run, stop_process, verify_report, wait_service
from embodiment.scenarios import plan


class SmokeOrchestration(unittest.TestCase):
    def request(self):
        return {'source': '/missing/source', 'checkpoint': '/missing/checkpoint', 'dataset': '/missing/data',
                'native_library': '/missing/kernel.so', 'robot': 'franka_panda',
                'training_python': '/training/python', 'simulation_python': '/simulation/python',
                'policy_timeout': 1, 'cases': [asdict(case) for case in plan('validation', 1)]}

    def probe(self, command, **kwargs):
        self.assertEqual(kwargs['env']['CUDA_VISIBLE_DEVICES'], '')
        self.assertEqual(kwargs['env']['HF_HUB_OFFLINE'], '1')
        receipt = {'ready': True} if 'embodiment.host' in command else {
            'checkpoint_sha256': 'synthetic', 'dataset_sha256': 'synthetic', 'native_contract_sha256': 'synthetic'}
        return subprocess.CompletedProcess(command, 0, json.dumps(receipt), '')

    def test_preflight_never_starts_policy_or_simulator_and_preserves_logs(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.closed_loop_smoke.source_provenance', return_value={'source_sha256': {}, 'relic_worktree_dirty': False}), \
             patch('embodiment.closed_loop_smoke.subprocess.run', side_effect=self.probe), \
             patch('embodiment.closed_loop_smoke.subprocess.Popen', side_effect=AssertionError('execution forbidden')):
            output = Path(temp)/'run'
            result = run(self.request(), output)
            self.assertEqual(result['status'], 'PREFLIGHT_ONLY')
            self.assertFalse(result['simulation_executed'])
            self.assertFalse(result['checkpoint_loaded'])
            self.assertEqual(len(result['stages']), 3)
            self.assertTrue((output/'inputs.stdout.log').exists())
            self.assertEqual(json.loads((output/'result.json').read_text()), result)
            with self.assertRaises(FileExistsError):
                run(self.request(), output)

    def test_all_missing_runtime_failures_are_reported_without_launching(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.closed_loop_smoke.source_provenance', return_value={'source_sha256': {}, 'relic_worktree_dirty': False}), \
             patch('embodiment.closed_loop_smoke.subprocess.run', side_effect=FileNotFoundError('missing interpreter')), \
             patch('embodiment.closed_loop_smoke.subprocess.Popen', side_effect=AssertionError('execution forbidden')):
            result = run(self.request(), Path(temp)/'run', True)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertEqual(len(result['errors']), 3)
            self.assertFalse(result['checkpoint_loaded'])

    def test_failed_service_readiness_cleans_up_and_records_failure(self):
        process = Mock()
        provenance = {'source_sha256': {'synthetic': 'fixture'}, 'relic_worktree_dirty': False}
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.closed_loop_smoke.source_provenance', return_value=provenance), \
             patch('embodiment.closed_loop_smoke.subprocess.run', side_effect=self.probe), \
             patch('embodiment.closed_loop_smoke.subprocess.Popen', return_value=process), \
             patch('embodiment.closed_loop_smoke.wait_service', side_effect=TimeoutError('synthetic readiness timeout')), \
             patch('embodiment.closed_loop_smoke.stop_process') as cleanup:
            result = run(self.request(), Path(temp)/'run', True)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertIn('readiness timeout', result['errors'][0])
            cleanup.assert_called_once_with(process)

    def test_service_exit_wrong_identity_and_readiness_deadline(self):
        process = Mock()
        process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'exited'):
            wait_service(process, 1234, {}, time.monotonic()+1)
        process.poll.return_value = None
        with patch('embodiment.policy_service.RemotePolicy', return_value=Mock(metadata={'checkpoint': 'wrong'})):
            with self.assertRaisesRegex(ValueError, 'identity'):
                wait_service(process, 1234, {'checkpoint': 'expected'}, time.monotonic()+1)
        with self.assertRaises(TimeoutError):
            wait_service(process, 1234, {}, time.monotonic()-1)

    def test_actual_service_process_group_is_reaped(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
        try:
            stop_process(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_summary_without_raw_evidence_and_incomplete_report_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'report.json'
            request = self.request()
            for report in ({'status': 'PASS', 'simulation_executed': True},
                           {'schema': 'viper.closed_loop_smoke.v1', 'request': request,
                            'completed': True, 'trials': [], 'error': None}):
                path.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    verify_report(path, request)

    def test_virtual_environment_executable_symlinks_are_preserved(self):
        from embodiment.closed_loop_smoke import main
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp)/'venv/bin/python'
            executable.parent.mkdir(parents=True)
            executable.symlink_to(sys.executable)
            args = ['smoke', '--source', temp, '--checkpoint', temp, '--dataset', temp,
                    '--native-library', temp, '--training-python', str(executable),
                    '--simulation-python', str(executable), '--robot', 'franka_panda', '--output', temp]
            with patch.object(sys, 'argv', args), patch('embodiment.closed_loop_smoke.run', return_value={'status': 'PREFLIGHT_ONLY'}) as runner:
                self.assertEqual(main(), 0)
                request = runner.call_args.args[0]
                self.assertEqual(request['training_python'], str(executable))
                self.assertEqual(request['simulation_python'], str(executable))

    def test_raw_trace_validation_detects_tampering_and_assisted_evidence(self):
        # A fabricated PhysX envelope exercises the verifier only. Every artifact
        # is temporary and all provenance explicitly says synthetic fixture.
        from dataclasses import replace
        import numpy as np
        from embodiment.assets import ARM, FINGERS
        from embodiment.benchmark import Action, COLORS, CONTROL_DT, Observation, layout
        from embodiment.collection import hashes
        from embodiment.evaluate import run_trial
        from embodiment.execution import ExecutionConfig
        from embodiment.safety import SafetyConfig

        case = plan('validation', 1)[0]
        class FixtureBackend:
            embodiment = 'openmanipulator_x'
            evidence_source = 'isaac_lab_physx'
            arm_names, finger_names = ARM, FINGERS
            safety_config = SafetyConfig(((-3., 3.),)*4+((-.011, .02),)*2, 4)
            def reset(self, seed):
                self.obs = Observation(0., (.17, 0., .085), (0.,)*4+(.004, .004), (0.,)*6,
                    {c: (*p, 1., 0., 0., 0.) for c, p in layout(seed).items()},
                    {c: 0. for c in COLORS}, contacts={c: False for c in COLORS},
                    contact_forces={c: (0., 0.) for c in COLORS}, gripper_open=1., ee_quaternion=(1., 0., 0., 0.))
                return self.obs
            def step(self, action):
                self.obs = replace(self.obs, time=self.obs.time+CONTROL_DT,
                    ee=tuple(a+b for a, b in zip(self.obs.ee, action.delta)))
                return self.obs
            def frame(self):
                return np.zeros((8, 8, 3), dtype=np.uint8)
            def safe_stop(self):
                pass
        class FixturePolicy:
            metadata = {'checkpoint_sha256': 'synthetic-fixture-no-real-checkpoint',
                        'source_sha256': {'fixture': 'synthetic'}, 'native_contract_sha256': 'synthetic'}
            def reset(self):
                pass
            def actions(self, observation):
                return (Action((.001, 0., 0.), 1.),)
        provenance = {'source_sha256': {'fixture': 'synthetic'}, 'relic_commit': 'synthetic'}
        request = {'robot': 'openmanipulator_x', 'cases': [asdict(case)], 'provenance': provenance,
                   'policy_service': FixturePolicy.metadata,
                   'verified': {'checkpoint_sha256': FixturePolicy.metadata['checkpoint_sha256'],
                                'native_contract_sha256': 'synthetic'}}
        with tempfile.TemporaryDirectory() as temp, patch('embodiment.execution.TIMEOUT', 2*CONTROL_DT):
            root = Path(temp)
            folder = root/f'trial_{case.seed}'
            trial = run_trial(FixtureBackend(), FixturePolicy(), case, folder, provenance,
                              ExecutionConfig(fallback_enabled=False), lambda: True)
            report = {'schema': 'viper.closed_loop_smoke.v1', 'request': request,
                      'completed': True, 'trials': [trial], 'error': None}
            path = root/'report.json'
            path.write_text(json.dumps(report))
            self.assertEqual(verify_report(path, request)['physical_policy_actions'], 2)
            trace_path = folder/'execution.jsonl'
            original = trace_path.read_text()
            for defect in ('cadence', 'applied', 'tracking', 'missing', 'stationary'):
                trace = [json.loads(line) for line in original.splitlines()]
                if defect == 'cadence': trace[0]['response_timestamp'] += .01
                if defect == 'applied': trace[0]['applied_action'][0] = 0.
                if defect == 'tracking': trace[0]['tracking_error_m'] += .1
                if defect == 'missing': trace.pop()
                if defect == 'stationary': trace[0]['observed_next_ee'] = [0., 0., 0.]
                trace_path.write_text(''.join(json.dumps(row)+'\n' for row in trace))
                report['trials'][0]['evidence_sha256'] = hashes(folder)
                path.write_text(json.dumps(report))
                with self.subTest(defect=defect), self.assertRaises(ValueError):
                    verify_report(path, request)
            trace_path.write_text(original)
            report['trials'][0]['evidence_sha256'] = hashes(folder)
            report['trials'][0]['controller'] = 'fallback_assisted'
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'unassisted'):
                verify_report(path, request)

    def test_successful_orchestration_keeps_learning_claims_false_and_reaps_service(self):
        # Probe/service/worker receipts are injected. This is not physical evidence.
        provenance = {'source_sha256': {'synthetic': 'fixture'}, 'relic_worktree_dirty': False}
        metadata = {'checkpoint_sha256': 'synthetic', 'source_sha256': provenance['source_sha256'],
                    'native_contract_sha256': 'synthetic'}
        process = Mock()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'smoke'
            def simulate(command, job, timeout, environment):
                self.assertEqual(command[0], '/simulation/python')
                self.assertIn('--worker-request', command)
                self.assertEqual(environment['HF_HUB_OFFLINE'], '1')
                self.assertGreater(timeout, 0)
                result = job/'run'
                result.mkdir()
                (result/'articulation.json').write_text('{}')
                (result/'report.json').write_text('{"synthetic_fixture":true}')
                return {'returncode': 0, 'timed_out': False}
            with patch('embodiment.closed_loop_smoke.source_provenance', return_value=provenance), \
                 patch('embodiment.closed_loop_smoke.subprocess.run', side_effect=self.probe), \
                 patch('embodiment.closed_loop_smoke.subprocess.Popen', return_value=process), \
                 patch('embodiment.closed_loop_smoke.wait_service', return_value=metadata), \
                 patch('embodiment.closed_loop_smoke.execute', side_effect=simulate), \
                 patch('embodiment.closed_loop_smoke.verify_report', return_value={'physical_policy_actions': 3}) as verify, \
                 patch('embodiment.closed_loop_smoke.checkpoint_digest', return_value='synthetic'), \
                 patch('embodiment.training.dataset_digest', return_value='synthetic'), \
                 patch('embodiment.closed_loop_smoke.file_digest', return_value='synthetic'), \
                 patch('embodiment.closed_loop_smoke.stop_process') as cleanup:
                result = run(self.request(), output, True)
                self.assertEqual(result['status'], 'PASS', result['errors'])
                self.assertTrue(result['checkpoint_loaded'])
                self.assertTrue(result['simulation_executed'])
                self.assertTrue(result['policy_process_reaped'])
                self.assertFalse(result['learned_manipulation_demonstrated'])
                self.assertFalse(result['transfer_demonstrated'])
                self.assertFalse(result['training_executed'])
                self.assertEqual(verify.call_args.args[1]['policy_service'], metadata)
                cleanup.assert_called_once_with(process)
