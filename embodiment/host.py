"""Read-only stage-specific host checks; never initializes Kit or model weights."""
import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from .preflight import SIM, LAB_COMMIT

STAGES = {'reader': {'total_gib': 0, 'free_gib': 0, 'ram_gib': 4, 'disk_gib': 2},
          'simulation': {'total_gib': 16, 'free_gib': 12, 'ram_gib': 24, 'disk_gib': 12},
          'training': {'total_gib': 40, 'free_gib': 38, 'ram_gib': 32, 'disk_gib': 32}}


def rtx_capable(name):
    return 'RTX' in name or bool(re.search(r'\b(?:A10G?|A40|L4|L40S?)\b', name))


def inspect_host(stage, volume=None, cuda_check=False):
    if stage not in STAGES: raise ValueError('unknown compute stage')
    limits = STAGES[stage]
    result = {'schema': 'viper.host_preflight.v1', 'stage': stage, 'ready': False, 'blockers': [],
              'requirements': limits, 'python': sys.version, 'platform': platform.platform(),
              'compute_started': False, 'cuda_probe_executed': False, 'packages': {},
              'isaac_requirements_source': 'https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html'}
    packages = {'simulation': ('isaacsim', 'isaaclab', 'torch', 'numpy', 'pillow'),
                'reader': ('numpy', 'pandas', 'scipy', 'transformers', 'torchvision', 'pyarrow', 'av', 'torchcodec', 'torch', 'pillow'),
                'training': ('torch', 'transformers', 'safetensors', 'pyarrow', 'av', 'torchcodec', 'tyro')}[stage]
    for name in packages:
        try: result['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: result['blockers'].append('missing package: '+name)
    try:
        from packaging.version import Version
    except ImportError:
        result['blockers'].append('missing package: packaging')
        return result
    pins = ({'torch': '2.7.0', 'numpy': '1.26.0', 'isaaclab': '0.47.2'} if stage == 'simulation' else
            {'torch': '2.9.0', 'transformers': '4.57.3', 'torchcodec': '0.8.0'})
    if stage == 'reader':
        pins = {'numpy': '1.26.4', 'torch': '2.9.0', 'torchcodec': '0.8.0', 'av': '14.2.0', 'pyarrow': '19.0.1', 'pandas': '2.2.3', 'scipy': '1.15.3', 'transformers': '4.57.3', 'torchvision': '0.24.0'}
        if sys.version_info[:2] != (3, 12): result['blockers'].append('pinned reader requires Python 3.12')
    for name, expected in pins.items():
        installed = result['packages'].get(name)
        if installed and Version(installed).base_version != expected:
            result['blockers'].append(name+' version differs from pinned runtime '+expected)
    if stage == 'simulation':
        if os.environ.get('OMNI_KIT_ACCEPT_EULA', '').lower() not in ('y', 'yes', '1'):
            result['blockers'].append('Isaac runtime license must be accepted through OMNI_KIT_ACCEPT_EULA before unattended Kit startup')
        if sys.version_info[:2] != (3, 11): result['blockers'].append('Isaac Sim stage requires Python 3.11')
        if 'isaacsim' in result['packages'] and Version(result['packages']['isaacsim']) != Version(SIM):
            result['blockers'].append('Isaac Sim version differs from pin')
        try:
            spec = importlib.util.find_spec('isaaclab')
            if spec is None or spec.origin is None: raise ValueError('Isaac Lab source cannot be resolved')
            root = Path(spec.origin).resolve().parents[3]
            commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
            changes = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--', 'source/isaaclab', 'source/isaaclab_assets'], text=True)
            result['isaaclab_commit'] = commit
            if commit != LAB_COMMIT or changes: result['blockers'].append('Isaac Lab source differs from clean pin')
        except (OSError, ValueError, subprocess.SubprocessError) as error: result['blockers'].append(str(error))
    if stage == 'training':
        if sys.version_info[:2] != (3, 12): result['blockers'].append('pinned GR00T training stage requires Python 3.12')
        try:
            import torch
            result['torch_cuda_build'] = torch.version.cuda
            if torch.version.cuda is None: result['blockers'].append('training interpreter contains a CPU-only PyTorch build')
        except ImportError: pass
        compiler = shutil.which('nvcc')
        if compiler is None:
            result['blockers'].append('CUDA 12.8 development compiler required by installed DeepSpeed compatibility checks; use the pinned cloud image')
        else:
            try:
                result['cuda_compiler'] = subprocess.check_output([compiler, '--version'], text=True, timeout=15)
                if 'release 12.8,' not in result['cuda_compiler']: result['blockers'].append('CUDA compiler version differs from 12.8 pin')
            except (OSError, subprocess.SubprocessError) as error: result['blockers'].append('CUDA compiler check: '+str(error))
    if stage != 'reader':
        try:
            process = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.free', '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, check=True, timeout=15)
            gpu = process.stdout.splitlines()[0].split(',')
            result['gpu'] = {'name': gpu[0].strip(), 'driver': gpu[1].strip(), 'total_mib': int(gpu[2]), 'free_mib': int(gpu[3])}
            if int(gpu[2]) < limits['total_gib']*1024 or int(gpu[3]) < limits['free_gib']*1024:
                result['blockers'].append('insufficient total or free GPU memory for '+stage)
            if stage == 'simulation' and not rtx_capable(gpu[0]):
                result['blockers'].append('RTX-capable rendering GPU not verified for Isaac camera stage')
            driver = tuple(int(value) for value in gpu[1].strip().split('.'))
            minimum = (580, 65, 6) if stage == 'simulation' else (570, 0, 0)
            if driver < minimum:
                result['blockers'].append('NVIDIA driver is below the conservative pinned CUDA/runtime requirement')
        except (OSError, ValueError, IndexError, subprocess.SubprocessError) as error: result['blockers'].append('GPU check: '+str(error))
    result['cuda_probe_executed'] = False
    if cuda_check and stage == 'simulation':
        result['cuda_probe_executed'] = True
        try:
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError('CUDA unavailable to simulation interpreter')
            free, total = torch.cuda.mem_get_info(0)
            result['cuda'] = {'build': torch.version.cuda, 'device': torch.cuda.get_device_name(0),
                              'free_bytes': free, 'total_bytes': total}
            if torch.version.cuda != '12.8':
                result['blockers'].append('simulation CUDA build differs from 12.8 pin')
            if free < limits['free_gib']*1024**3 or total < limits['total_gib']*1024**3:
                result['blockers'].append('CUDA-reported device memory is insufficient')
        except (ImportError, RuntimeError, OSError) as error:
            result['blockers'].append('CUDA probe: '+str(error))
    memory = {}
    if Path('/proc/meminfo').exists():
        memory = {line.split(':')[0]: int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))}
    result['memory_bytes'] = memory
    if memory.get('MemAvailable', 0) < limits['ram_gib']*1024**3: result['blockers'].append('insufficient available host RAM')
    if volume is not None:
        volume = Path(volume).resolve()
        result['volume'] = str(volume)
        if not volume.is_dir() or not os.access(volume, os.W_OK): result['blockers'].append('existing writable volume required')
        else:
            result['storage_free_bytes'] = shutil.disk_usage(volume).free
            if result['storage_free_bytes'] < limits['disk_gib']*1024**3: result['blockers'].append('insufficient storage reserve')
    result['ready'] = not result['blockers']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=STAGES, required=True)
    parser.add_argument('--volume', type=Path)
    parser.add_argument('--cuda-check', action='store_true', help='explicit driver/context probe for an approved simulation host; no kernels or Kit')
    args = parser.parse_args()
    result = inspect_host(args.stage, args.volume, args.cuda_check)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ready'] else 2)
