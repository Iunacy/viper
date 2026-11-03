"""Installation doubles only: no apt, package downloads or model execution."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from embodiment.bootstrap import plan, setup
from embodiment.deployment import operations, install, system_doctor, KEYRING_SHA256


class Deployment(unittest.TestCase):
    def test_entire_clean_install_plan_includes_system_dependencies_and_native_checks(self):
        with tempfile.TemporaryDirectory() as temp, patch('embodiment.deployment.execute', side_effect=AssertionError('no installation')):
            report = install(Path(temp), training=True)
            self.assertEqual(report['status'], 'NOT_EXECUTED')
            self.assertEqual(set(report['runtimes']), {'simulation', 'reader', 'training'})
            self.assertIn('cuda-toolkit-12-8=12.8.1-1', str(report))
            self.assertIn('cmake', str(report['system_operations']))
            self.assertIn('ctest', str(report['native_operations']))
            self.assertFalse(report['downloads_models'])
            self.assertEqual(len(KEYRING_SHA256), 64)
            with self.assertRaisesRegex(ValueError, 'accept-isaac-license'): install(Path(temp), execute_stage=True)

    def test_interrupted_runtime_resumes_only_failed_commands_and_verifies_completed_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp)
            source = prefix/'source'
            source.mkdir()
            config = plan(prefix, 'reader')
            config.update(source=str(source), commands=[['fixture', 'first'], ['fixture', 'second']])
            state = {'packages': [['synthetic', '1']], 'prefix': str(prefix), 'python': 'fixture'}
            failures = [False, True, False]
            calls = []
            def run(command, *arguments, **kwargs):
                calls.append(command)
                return {'returncode': 2 if failures.pop(0) else 0}
            with patch('embodiment.bootstrap.plan', return_value=config), \
                 patch('embodiment.bootstrap.shutil.which', return_value='/uv'), \
                 patch('embodiment.bootstrap.shutil.disk_usage', return_value=type('Usage', (), {'free': 100*1024**3})()), \
                 patch('embodiment.bootstrap.runtime_fingerprint', return_value=state), \
                 patch('embodiment.bootstrap.run_process', side_effect=run), \
                 patch('embodiment.bootstrap.subprocess.check_output', side_effect=lambda command, **kw: 'uv 0.13.4 (fixture)' if command[-1] == '--version' else config['commit'] if 'rev-parse' in command else ''):
                with self.assertRaisesRegex(RuntimeError, 'setup failed'): setup(prefix, 'reader', True)
                receipt = json.loads((prefix/'setup/reader.receipt.json').read_text())
                self.assertEqual(receipt['completed_commands'], [0])
                self.assertEqual(setup(prefix, 'reader', True)['status'], 'INSTALLED')
                self.assertTrue(setup(prefix, 'reader', True)['reused'])
                self.assertEqual(calls, [config['commands'][0], config['commands'][1], config['commands'][1]])
                with patch('embodiment.bootstrap.runtime_fingerprint', return_value={'packages': 'changed'}):
                    with self.assertRaisesRegex(ValueError, 'runtime changed'): setup(prefix, 'reader', True)

    def test_missing_tools_and_wrong_os_are_actionable_without_gpu_initialization(self):
        with patch('embodiment.deployment.shutil.which', return_value=None):
            result = system_doctor('/tmp')
        self.assertFalse(result['ready'])
        self.assertFalse(result['compute_started'])
        self.assertIn('missing executable: cmake', str(result['blockers']))

    def test_system_install_resumes_and_reuses_verified_native_build(self):
        import os
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ), \
             patch('embodiment.deployment.system_doctor', return_value={'blockers': []}), \
             patch('embodiment.deployment.setup', return_value={'status': 'INSTALLED'}), \
             patch('embodiment.first_session.assets', return_value={'status': 'SYNTHETIC_ASSET_VALIDATOR'}), \
             patch('embodiment.native_contract.NativeContract'), \
             patch('embodiment.deployment.subprocess.check_output', return_value='fixture=1\n'):
            root = Path(temp)
            calls = []
            fail = [True]
            def execute(command, job, timeout, environment):
                calls.append(command)
                if fail and command[-1] != 'update':
                    fail.pop()
                    return {'returncode': 2}
                if command[:2] == ['cmake', '--build']:
                    (root/'native').mkdir(exist_ok=True)
                    (root/'native/libviper_action_contract.so').write_text('synthetic native library; not loaded')
                return {'returncode': 0}
            with patch('embodiment.deployment.execute', side_effect=execute):
                first = install(root, execute_stage=True, accept_isaac=True)
                self.assertEqual(first['status'], 'BLOCKED')
                second = install(root, execute_stage=True, accept_isaac=True)
                self.assertEqual(second['status'], 'INSTALLED', second.get('error'))
                count = len(calls)
                self.assertEqual(install(root, execute_stage=True, accept_isaac=True)['status'], 'INSTALLED')
                self.assertEqual(len(calls), count)
                self.assertEqual(sum(command[-1] == 'update' for command in calls), 1)
                (root/'native/libviper_action_contract.so').write_text('corrupt')
                self.assertEqual(install(root, execute_stage=True, accept_isaac=True)['status'], 'BLOCKED')

    def test_report_verifies_runtime_inventory_and_native_hash_without_gpu(self):
        from embodiment.collection import atomic_json
        from embodiment.dataset import file_digest
        from embodiment.deployment import verify_installation
        with tempfile.TemporaryDirectory() as temp, \
             patch('embodiment.bootstrap.runtime_fingerprint', return_value={'fixture': 'synthetic'}), \
             patch('embodiment.first_session.assets', return_value={'files': {'fixture': 'synthetic'}}):
            root = Path(temp)
            for name in ('deployment', 'setup', 'native'): (root/name).mkdir()
            library = root/'native/libviper_action_contract.so'
            library.write_text('synthetic library not loaded')
            native = Path(__file__).resolve().parents[1]/'native'
            sources = {p.name: file_digest(p) for p in sorted(native.glob('*')) if p.suffix in ('.cpp', '.h') or p.name == 'CMakeLists.txt'}
            atomic_json(root/'deployment/result.json', {'status': 'INSTALLED', 'runtimes': {'reader': {}}})
            atomic_json(root/'setup/reader.receipt.json', {'status': 'INSTALLED', 'configuration': plan(root, 'reader'), 'runtime_fingerprint': {'fixture': 'synthetic'}})
            atomic_json(root/'deployment/native.json', {'sources': sources, 'library_sha256': file_digest(library)})
            self.assertEqual(verify_installation(root)['status'], 'VERIFIED')
            library.write_text('corrupted')
            self.assertEqual(verify_installation(root)['status'], 'BLOCKED')

    def test_interrupted_clone_never_publishes_unpinned_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = plan(root, 'reader')
            config['commands'] = [['fixture', 'install']]
            source = Path(config['source'])
            failure = [True]
            calls = []
            def execute(command, job, timeout, environment):
                calls.append(command)
                if command[:2] == ['git', 'clone']:
                    Path(command[-1]).mkdir()
                    if failure:
                        failure.pop()
                        return {'returncode': 2}
                return {'returncode': 0}
            with patch('embodiment.bootstrap.plan', return_value=config), \
                 patch('embodiment.bootstrap.shutil.which', return_value='/uv'), \
                 patch('embodiment.bootstrap.shutil.disk_usage', return_value=type('Usage', (), {'free': 100*1024**3})()), \
                 patch('embodiment.bootstrap.runtime_fingerprint', return_value={'fixture': 'synthetic'}), \
                 patch('embodiment.bootstrap.run_process', side_effect=execute), \
                 patch('embodiment.bootstrap.subprocess.check_output', side_effect=lambda command, **kw: 'uv 0.13.4 (fixture)' if command[-1] == '--version' else config['commit'] if 'rev-parse' in command else ''):
                with self.assertRaisesRegex(RuntimeError, 'source installation failed'): setup(root, 'reader', True)
                self.assertFalse(source.exists())
                self.assertTrue(source.with_name(source.name+'.installing').is_dir())
                self.assertEqual(setup(root, 'reader', True)['status'], 'INSTALLED')
                self.assertTrue(source.is_dir())
                self.assertFalse(source.with_name(source.name+'.installing').exists())
                self.assertEqual(sum(command[:2] == ['git', 'clone'] for command in calls), 2)

    def test_container_build_leaves_runtime_setup_to_explicit_host_execution(self):
        dockerfile = (Path(__file__).resolve().parents[1]/'cloud.Dockerfile').read_text()
        self.assertIn('sha256:6617a625f4090c76c545a0e7d63f2e441718ef9af7f4efe7dd1242a29e289fd7', dockerfile)
        self.assertIn('embodiment.rental', dockerfile)
        self.assertNotIn('INSTALL_RUNTIME', dockerfile)
        self.assertNotIn('ACCEPT_ISAAC_LICENSE', dockerfile)
        self.assertNotIn('-m embodiment.rental setup', dockerfile)
