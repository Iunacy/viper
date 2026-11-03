import unittest
import importlib.util
from embodiment.host import rtx_capable, inspect_host


class HostRequirements(unittest.TestCase):
    def test_compute_only_a100_is_not_mistaken_for_a10_rendering(self):
        for name in ('NVIDIA A100-SXM4-40GB', 'NVIDIA H100 80GB HBM3'):
            self.assertFalse(rtx_capable(name))
        for name in ('NVIDIA A10', 'NVIDIA A10G', 'NVIDIA L40S', 'NVIDIA L4', 'NVIDIA RTX 6000 Ada Generation'):
            self.assertTrue(rtx_capable(name))
        with self.assertRaises(ValueError): inspect_host('unrecognized')

    @unittest.skipUnless(importlib.util.find_spec('packaging'), 'runtime version parser required')
    def test_cuda_probe_requires_explicit_opt_in_and_unavailable_cuda_is_reported(self):
        from unittest.mock import Mock, patch
        from types import SimpleNamespace
        cuda = Mock()
        cuda.is_available.return_value = False
        fake = SimpleNamespace(cuda=cuda)
        with patch.dict('sys.modules', {'torch': fake}):
            result = inspect_host('simulation')
            self.assertFalse(result['cuda_probe_executed'])
            cuda.is_available.assert_not_called()
            result = inspect_host('simulation', cuda_check=True)
            self.assertTrue(result['cuda_probe_executed'])
            self.assertIn('CUDA unavailable', str(result['blockers']))

    def test_reader_preflight_does_not_require_gpu_or_training_libraries(self):
        from unittest.mock import patch
        with patch('embodiment.host.platform.platform', return_value='synthetic'), patch('embodiment.host.subprocess.run', side_effect=AssertionError('reader must not query GPU')):
            report = inspect_host('reader')
        self.assertFalse(report['cuda_probe_executed'])
        self.assertNotIn('deepspeed', report['packages'])
        self.assertNotIn('flash_attn', report['packages'])
        self.assertNotIn('GPU', str(report['blockers']))
