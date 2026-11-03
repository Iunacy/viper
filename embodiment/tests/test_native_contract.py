"""CPU-only parity checks against the compiled C++ physical action boundary."""
import os
import unittest

from embodiment.benchmark import Action
from embodiment.native_contract import NativeContract


@unittest.skipUnless(os.environ.get('VIPER_ACTION_CONTRACT_LIBRARY'), 'build embodiment/native and set VIPER_ACTION_CONTRACT_LIBRARY')
class NativeActionContract(unittest.TestCase):
    def test_entire_chunk_and_scalar_boundary_match_python(self):
        import numpy as np
        contract = NativeContract(os.environ['VIPER_ACTION_CONTRACT_LIBRARY'])
        rng = np.random.default_rng(1707)
        rows = rng.uniform(-.004, .004, (1000, 4))
        rows[:, 3] = rng.uniform(-.1, 1.1, len(rows))
        rows = np.vstack((rows, [[.003, 0, 0, 0], [0, 0, 0, 1], [float('nan'), 0, 0, 0],
                                [0, 0, 0, float('inf')]]))
        for row in rows:
            try:
                Action(tuple(float(v) for v in row[:3]), float(row[3]))
                expected = True
            except ValueError:
                expected = False
            try:
                contract.validate(row[None])
                actual = True
            except ValueError:
                actual = False
            self.assertEqual(actual, expected)
        chunk = np.zeros((16, 4))
        contract.validate(chunk)
        chunk[-1, 0] = .01
        with self.assertRaises(ValueError):
            contract.validate(chunk)
        for shape in ((0, 4), (17, 4), (1, 3), (1, 4, 1)):
            with self.assertRaises(ValueError):
                contract.validate(np.zeros(shape))

    def test_configured_missing_native_library_never_falls_back(self):
        from unittest.mock import patch
        from embodiment.policy import GrootPolicy
        with patch.dict(os.environ, VIPER_ACTION_CONTRACT_LIBRARY='/missing/contract.so'):
            with self.assertRaises(FileNotFoundError):
                GrootPolicy(None)
