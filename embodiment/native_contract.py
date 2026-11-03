"""Explicit, fail-closed C++ physical action boundary, shared across runtimes."""
import ctypes
from pathlib import Path


class NativeContract:
    def __init__(self, library):
        self.path = Path(library).resolve(strict=True)
        self.library = ctypes.CDLL(str(self.path))
        self.library.viper_action_contract_abi.argtypes = []
        self.library.viper_action_contract_abi.restype = ctypes.c_uint
        if self.library.viper_action_contract_abi() != 1:
            raise ValueError('unsupported native action contract ABI')
        self.library.viper_validate_actions.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t]
        self.library.viper_validate_actions.restype = ctypes.c_int

    def validate(self, rows):
        import numpy as np
        values = np.asarray(rows)
        if values.ndim != 2 or values.shape[1] != 4 or not 1 <= len(values) <= 16 or values.dtype.kind not in 'fi':
            raise ValueError('invalid native action chunk shape or numeric type')
        values = np.ascontiguousarray(values, dtype=np.float64)
        code = self.library.viper_validate_actions(values.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), len(values), 4)
        if code:
            raise ValueError('native action contract rejected chunk: '+str(code))


if __name__ == '__main__':
    import argparse
    import subprocess
    parser = argparse.ArgumentParser(description='Explicit CPU build and test of the shared C++ action boundary')
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().with_name('native')
    subprocess.run(['cmake', '-S', str(source), '-B', str(args.build.resolve()), '-DCMAKE_BUILD_TYPE=Release'], check=True)
    subprocess.run(['cmake', '--build', str(args.build.resolve())], check=True)
    subprocess.run(['ctest', '--test-dir', str(args.build.resolve()), '--output-on-failure'], check=True)
