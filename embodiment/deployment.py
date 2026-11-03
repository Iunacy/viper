"""Ubuntu 22.04 x86_64 deployment; no host driver changes or implicit model acquisition."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from .bootstrap import UV_VERSION, plan, setup
from .collection import atomic_json, execute, locked
from .dataset import read_json

SYSTEM_PACKAGES = ['ca-certificates', 'git', 'build-essential', 'cmake', 'python3', 'python3-venv', 'ffmpeg',
    'libgl1', 'libegl1', 'libglib2.0-0', 'libgomp1', 'libx11-6', 'libxext6', 'libxrender1', 'libxi6',
    'libxrandr2', 'libvulkan1', 'libsm6', 'libxt6', 'libxkbcommon0', 'libnss3']
KEYRING_URL = 'https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb'
# Populated from NVIDIA's small public keyring artifact, never a model download.
KEYRING_SHA256 = 'd93190d50b98ad4699ff40f4f7af50f16a76dac3bb8da1eaaf366d47898ff8df'


def operations(prefix, training=False):
    prefix = Path(prefix).resolve()
    admin = [] if os.geteuid() == 0 else ['sudo', '-n']
    system = [[*admin, 'apt-get', 'update'], [*admin, 'apt-get', 'install', '-y', '--no-install-recommends', *SYSTEM_PACKAGES]]
    if training:
        system += [['download-sha256', KEYRING_URL, KEYRING_SHA256, str(prefix/'setup/cuda-keyring.deb')],
            [*admin, 'dpkg', '-i', str(prefix/'setup/cuda-keyring.deb')], [*admin, 'apt-get', 'update'],
            [*admin, 'apt-get', 'install', '-y', 'cuda-toolkit-12-8=12.8.1-1']]
    bootstrap = [[sys.executable, '-m', 'venv', str(prefix/'bootstrap')],
        [str(prefix/'bootstrap/bin/python'), '-m', 'pip', 'install', 'uv=='+UV_VERSION]]
    return {'schema': 'viper.deployment.v1', 'supported_os': 'Ubuntu 22.04 x86_64',
        'system_operations': system, 'bootstrap_operations': bootstrap,
        'runtimes': {role: plan(prefix, role) for role in ('simulation', 'reader', *(['training'] if training else []))},
        'native_operations': [['cmake', '-S', str(Path(__file__).parent/'native'), '-B', str(prefix/'native'), '-DCMAKE_BUILD_TYPE=Release'],
            ['cmake', '--build', str(prefix/'native'), '--parallel', '2'], ['ctest', '--test-dir', str(prefix/'native'), '--output-on-failure']],
        'downloads_models': False, 'provisions_hardware': False,
        'licenses': {'isaac': 'https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_python.html',
                     'models': 'separate model acquisition consent and gated Hugging Face license acceptance'},
        'persistent_paths': [str(prefix/name) for name in ('sources', 'cache', 'robot_cache', 'assets', 'models')]}


def system_doctor(prefix, training=False):
    blockers = []
    release = {}
    if Path('/etc/os-release').is_file():
        release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') != 'ubuntu' or release.get('VERSION_ID', '').strip('"') != '22.04' or platform.machine() != 'x86_64':
        blockers.append('supported deployment requires Ubuntu 22.04 x86_64')
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 0
    if cpus < 8: blockers.append('at least 8 available CPU cores required')
    for name in ('git', 'cmake', 'c++', 'ffmpeg', 'nvidia-smi'):
        if not shutil.which(name): blockers.append('missing executable: '+name+'; run setup or prepare the NVIDIA host driver')
    gpu = None
    if shutil.which('nvidia-smi'):
        try:
            raw = subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.free', '--format=csv,noheader,nounits'], text=True, timeout=15)
            name, driver, total, free_gpu = [value.strip() for value in raw.splitlines()[0].split(',')]
            gpu = {'name': name, 'driver': driver, 'total_mib': int(total), 'free_mib': int(free_gpu)}
            from .host import rtx_capable
            if not rtx_capable(name): blockers.append('RTX rendering GPU required for the frozen camera protocol')
            if tuple(map(int, driver.split('.'))) < (580, 65, 6): blockers.append('host NVIDIA driver >=580.65.06 required')
            if int(total) < (40 if training else 16)*1024 or int(free_gpu) < (38 if training else 12)*1024:
                blockers.append('insufficient GPU memory for requested deployment role')
        except (OSError, ValueError, IndexError, subprocess.SubprocessError) as error:
            blockers.append('NVIDIA host inspection failed: '+str(error))
    if training and not shutil.which('nvcc'): blockers.append('CUDA 12.8 toolkit missing; run setup --training-runtime')
    ancestor = Path(prefix).resolve()
    while not ancestor.exists(): ancestor = ancestor.parent
    if not os.access(ancestor, os.W_OK): blockers.append('persistent runtime parent is not writable: '+str(ancestor))
    free = shutil.disk_usage(ancestor).free
    if free < (250 if training else 100)*1024**3:
        blockers.append('persistent storage requires at least '+('250' if training else '100')+' GiB free before setup')
    memory = {line.split(':')[0]: int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:', 'MemAvailable:'))}
    if memory.get('MemAvailable', 0) < (48 if training else 32)*1024**3:
        blockers.append('insufficient available RAM; require '+('48' if training else '32')+' GiB before setup')
    return {'ready': not blockers, 'blockers': blockers, 'os': release, 'available_cpu_cores': cpus,
        'storage_free_bytes': free, 'memory_bytes': memory, 'gpu': gpu,
        'compute_started': False, 'operations': operations(prefix, training)}


def install(prefix, training=False, execute_stage=False, accept_isaac=False, timeout=14400):
    if not 1 <= timeout <= 86400: raise ValueError('deployment deadline must be in 1..86400 seconds')
    deadline = time.monotonic()+timeout
    prefix = Path(prefix).resolve()
    config = operations(prefix, training)
    if not execute_stage: return {**config, 'status': 'NOT_EXECUTED'}
    if not accept_isaac: raise ValueError('setup requires --accept-isaac-license')
    # OS checks precede privileged commands. Missing tools are installed below.
    doctor = system_doctor(prefix, training)
    fatal = [b for b in doctor['blockers'] if b.startswith('missing executable: nvidia-smi') or not b.startswith(('missing executable:', 'CUDA 12.8 toolkit missing'))]
    if fatal: raise RuntimeError('; '.join(fatal))
    with locked(prefix/'deployment'):
        from .rental import no_live_workers
        no_live_workers(prefix)
        result = {'schema': 'viper.deployment_result.v1', 'status': 'BLOCKED', 'runtimes': {}, 'operations': config}
        try:
            environment = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'OMNI_KIT_ACCEPT_EULA': 'YES'}
            from .dataset import file_digest
            native_receipt = prefix/'deployment/native.json'
            native_sources = {str(p.name): file_digest(p) for p in sorted((Path(__file__).parent/'native').glob('*')) if p.suffix in ('.cpp', '.h') or p.name == 'CMakeLists.txt'}
            if native_receipt.exists():
                previous = read_json(native_receipt)
                if previous['sources'] != native_sources or file_digest(prefix/'native/libviper_action_contract.so') != previous['library_sha256']:
                    raise ValueError('verified native build changed; use a new runtime prefix')
            def command_step(command, name):
                job = prefix/'deployment'/name
                job.mkdir(exist_ok=True)
                # System/uv commands are idempotent, and isolated runtime setup
                # verifies its own receipt instead of repeating installations.
                done = job/'completed.json'
                if done.exists():
                    if read_json(done)['command'] != command: raise ValueError('installation operation changed')
                    missing_tools = any(not shutil.which(name) for name in ('git', 'cmake', 'c++', 'ffmpeg'))
                    if not (name.startswith('system-') and 'install' in command and missing_tools): return
                attempt = job/f'attempt-{len(list(job.glob("attempt-*"))):04d}'
                attempt.mkdir()
                remaining = deadline-time.monotonic()
                if remaining <= 0: raise TimeoutError('deployment deadline exceeded')
                measured = execute(command, attempt, remaining, environment)
                if measured['returncode']: raise RuntimeError('installation failed; inspect '+str(attempt/'process.log'))
                atomic_json(done, {'command': command, 'process': measured})
            for index, command in enumerate(config['system_operations']):
                if command[0] == 'download-sha256':
                    destination = Path(command[-1])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    data = urllib.request.urlopen(KEYRING_URL, timeout=60).read(1024*1024)
                    if hashlib.sha256(data).hexdigest() != KEYRING_SHA256: raise ValueError('CUDA repository keyring integrity failed')
                    destination.write_bytes(data)
                else: command_step(command, 'system-'+str(index))
            for index, command in enumerate(config['bootstrap_operations']):
                command_step(command, 'bootstrap-'+str(index))
            os.environ['PATH'] = str(prefix/'bootstrap/bin')+os.pathsep+os.environ['PATH']
            os.environ['PATH'] = '/usr/local/cuda-12.8/bin'+os.pathsep+os.environ['PATH']
            os.environ['OMNI_KIT_ACCEPT_EULA'] = 'YES'
            for role in config['runtimes']:
                remaining = deadline-time.monotonic()
                if remaining < 1: raise TimeoutError('deployment deadline exceeded')
                result['runtimes'][role] = setup(prefix, role, True, timeout=int(remaining))
            for index, command in enumerate(config['native_operations']):
                command_step(command, 'native-'+str(index))
            from .first_session import assets
            result['assets'] = assets(prefix/'robot_cache', prefix/'assets')
            from .native_contract import NativeContract
            NativeContract(prefix/'native/libviper_action_contract.so')
            atomic_json(native_receipt, {'sources': native_sources, 'library_sha256': file_digest(prefix/'native/libviper_action_contract.so')})
            result['system_package_versions'] = subprocess.check_output(['dpkg-query', '-W', '-f=${Package}=${Version}\n', *SYSTEM_PACKAGES], text=True, timeout=30).splitlines()
            result['status'] = 'INSTALLED'
        except (Exception, KeyboardInterrupt) as error:
            result['error'] = f'{type(error).__name__}: {error}'
        atomic_json(prefix/'deployment/result.json', result)
        return result


def verify_installation(prefix):
    """Revalidate installed software receipts and asset hashes; never load models or Kit."""
    from .bootstrap import runtime_fingerprint
    from .dataset import file_digest
    prefix = Path(prefix).resolve()
    receipt = prefix/'deployment/result.json'
    if not receipt.exists(): return {'status': 'UNVERIFIED', 'reason': 'no completed deployment receipt'}
    saved = read_json(receipt)
    if saved.get('status') != 'INSTALLED': return {'status': 'UNVERIFIED', 'reason': saved.get('error', 'installation incomplete')}
    try:
        roles = {}
        for role in saved['runtimes']:
            runtime = read_json(prefix/'setup'/(role+'.receipt.json'))
            if runtime.get('status') != 'INSTALLED' or runtime.get('configuration') != plan(prefix, role):
                raise ValueError('runtime receipt configuration differs: '+role)
            if runtime.get('runtime_fingerprint') != runtime_fingerprint(runtime['configuration']):
                raise ValueError('runtime inventory differs: '+role)
            roles[role] = 'VERIFIED'
        native = read_json(prefix/'deployment/native.json')
        sources = {str(p.name): file_digest(p) for p in sorted((Path(__file__).parent/'native').glob('*')) if p.suffix in ('.cpp', '.h') or p.name == 'CMakeLists.txt'}
        if native['sources'] != sources or file_digest(prefix/'native/libviper_action_contract.so') != native['library_sha256']:
            raise ValueError('native library or sources differ')
        from .first_session import assets
        checked = assets(prefix/'robot_cache', prefix/'assets')
        return {'status': 'VERIFIED', 'runtimes': roles, 'asset_files': len(checked['files']),
                'scope': 'software inventory and asset integrity; no GPU/PhysX/training execution claim'}
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        return {'status': 'BLOCKED', 'error': f'{type(error).__name__}: {error}'}
