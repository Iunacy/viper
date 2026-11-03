import importlib.metadata
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from embodiment.codec_runtime import prepare


def available():
    try: return importlib.metadata.version('av') == '14.2.0' and all(importlib.util.find_spec(name) for name in ('torchcodec', 'torch'))
    except importlib.metadata.PackageNotFoundError: return False


@unittest.skipUnless(available(), 'pinned PyAV/TorchCodec libraries required')
class NativeCodecBridge(unittest.TestCase):
    def test_private_bridge_loads_real_decoder_without_gpu_or_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(prepare(temporary))
            self.assertTrue((root/'libavcodec.so.61').is_file())
            self.assertTrue(list(root.glob('libdrm-*.so.*')))
            result = subprocess.run([sys.executable, '-c', 'import torch; from torchcodec.decoders import VideoDecoder; print(VideoDecoder.__name__)'],
                env={**os.environ, 'LD_LIBRARY_PATH': str(root), 'CUDA_VISIBLE_DEVICES': '', 'OPENBLAS_NUM_THREADS': '1'},
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('VideoDecoder', result.stdout)


class SystemCodecIsolation(unittest.TestCase):
    def test_exporter_removes_private_codec_bridge_but_preserves_driver_paths(self):
        from embodiment.codec_runtime import system_codec_environment
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bridge = root/'codec'
            bridge.mkdir()
            (bridge/'libavcodec-wheelhash.so.61.1.0').touch()
            environment = {'LD_LIBRARY_PATH': str(bridge)+os.pathsep+'/driver/lib', 'OTHER': 'retained'}
            cleaned = system_codec_environment(environment)
            self.assertEqual(cleaned['LD_LIBRARY_PATH'], '/driver/lib')
            self.assertEqual(cleaned['OTHER'], 'retained')
            self.assertEqual(environment['LD_LIBRARY_PATH'], str(bridge)+os.pathsep+'/driver/lib')
