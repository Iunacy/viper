"""VIPER rental execution: python3 -m embodiment.rental STAGE --prefix P --root R

Supported host: Ubuntu 22.04 x86_64; 8 CPU cores; NVIDIA RTX rendering GPU.
Use one RTX A6000/RTX 6000 Ada/L40S-class GPU with 48 GB-class VRAM (>=40 GiB total/38 GiB free), >=48 GiB
available RAM and >=250 GiB persistent free disk for the complete workflow.
Simulation alone requires >=16 GiB total /12 GiB free VRAM and >=32 GiB free
RAM before setup; training requires >=40/38 GiB VRAM. Actual host gates remain
authoritative. An A100/H100 alone cannot render the frozen RGB camera protocol.
NVIDIA host driver >=580.65.06 and Vulkan device access must be supplied by the
rental host. setup installs system packages, uv, separate Python runtimes,
CUDA 12.8 development toolkit when requested, cached robot assets and C++ boundary.
System installation requires root or passwordless sudo.
It never installs/replaces the host driver or provisions/rents a machine.

From a clean checkout on a persistent mount, inspect everything first:
  python3 -m embodiment.rental doctor --prefix /workspace/viper --root /workspace/runs/viper
  python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper
Install the simulation/reader runtimes after reading the Isaac license:
  python3 -m embodiment.rental setup --prefix /workspace/viper --root /workspace/runs/viper --execute --accept-isaac-license
Run startup smoke, 20 frozen trials/arm, then collect 12 successful pilot demos/arm:
  python3 -m embodiment.rental collect --prefix /workspace/viper --root /workspace/runs/viper --execute --allow-gpu --accept-isaac-license --background
Inspect persistent results after reconnecting:
  python3 -m embodiment.rental report --prefix /workspace/viper --root /workspace/runs/viper

Training setup is separate; append --training-runtime to setup. To acquire the
pinned large weights also append --allow-model-downloads --accept-model-license;
Hugging Face gated access must already be granted (credentials are never logged).
Otherwise place existing local snapshots in the model cache or use --pretrained.
Then run g3 with --execute --allow-gpu --allow-training --accept-isaac-license.
m0 uses the same consents, trains the source under the frozen bounded campaign
budget (default 2000 steps, effective batch 12), then evaluates 50 held-out scenes
and nine separate instruction flips. Neither a two-step G3 nor a completed
failing M0 permits a learning/transfer claim. --steps/--save-steps must be frozen
before starting a run. Do not reuse held-out scenes to tune a policy.

All stages default to dry-run; no downloads, subprocesses or CUDA execution.
'full' explicitly sequences setup, qualify, collect, g3, m0 and stops at failure.
It requires all execution consents; setup alone never requires GPU/training
consent or model weights. --background survives a terminal/SSH disconnect,
not machine shutdown. Repeating the exact stage resumes verified work; never
silently reruns a completed evaluation. New source/configuration needs a new root.

Artifacts: prefix/deployment and prefix/setup hold installation logs/receipts;
root/session/{smoke,qualification,pilot} holds raw PhysX evidence and datasets;
root/g3 holds A/B optimizer, conversion and closed-loop attempts; root/campaign
holds source training and m0_evaluate_a attempts. root/pipeline holds commands,
immutable attempts, verified receipts, report.json and detached console logs.
BLOCKED errors name the failed stage; inspect its process.log, process.json and
result.json. Failed/partial trials are retained. 'report' hashes completed
artifacts and reruns their validators; absent receipts are UNVERIFIED. Resource
logs describe sampled GPU usage (system-wide) and process-tree peak host memory.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .collection import atomic_json, execute, hashes, locked
from .dataset import read_json
from .qualify import source_provenance

STAGES = ('doctor', 'setup', 'qualify', 'collect', 'g3', 'm0', 'report', 'full')
DEPENDENCIES = {'qualify': [], 'collect': ['qualify'], 'g3': ['collect'], 'm0': ['g3'], 'full': ['setup', 'm0']}


def paths(prefix):
    prefix = Path(prefix).resolve()
    return {'simulation': prefix/'simulation/bin/python', 'reader': prefix/'reader/bin/python',
        'training': prefix/'sources/GR00T/.venv/bin/python', 'isaac': prefix/'sources/IsaacLab',
        'groot': prefix/'sources/GR00T', 'native': prefix/'native/libviper_action_contract.so'}


def commands(args):
    p, root, prefix = paths(args.prefix), args.root, args.prefix
    session = [str(p['reader']), '-m', 'embodiment.first_session', '--root', str(root/'session'),
        '--simulation-python', str(p['simulation']), '--reader-python', str(p['reader']),
        '--isaac-source', str(p['isaac']), '--groot-source', str(p['groot']),
        '--robot-cache', str(prefix/'robot_cache'), '--panda-assets', str(prefix/'assets'),
        '--reader-library-path', str(prefix/'reader_codec'), '--episodes', str(args.episodes),
        '--timeout', str(args.trial_timeout), '--max-attempts', str(args.max_attempts), '--total-timeout', str(min(args.timeout, 86400)), '--execute']
    datasets = root/'session/pilot/exports'
    common = ['--source', str(p['groot']), '--dataset-a', str(datasets/'openmanipulator_x/train'),
        '--dataset-b', str(datasets/'franka_panda/train'), '--pretrained', str(args.pretrained),
        '--simulation-python', str(p['simulation'])]
    campaign = [str(p['training']), '-m', 'embodiment.training_campaign', *common,
        '--root', str(root/'campaign'), '--smoke-root', str(root/'g3'), '--execute',
        '--steps', str(args.steps), '--save-steps', str(args.save_steps), '--timeout', str(args.timeout)]
    return {'qualify': [*session, '--stop-after', 'qualification'], 'collect': session,
        'g3_preflight': [str(p['training']), '-m', 'embodiment.cloud', '--source', str(p['groot']), '--pretrained', str(args.pretrained), '--volume', str(root)],
        'g3': [str(p['training']), '-m', 'embodiment.cross_smoke', *common, '--output', str(root/'g3'),
            '--native-library', str(p['native']), '--timeout', str(min(args.timeout, 3600)), '--execute'],
        'm0_train': [*campaign, '--stage', 'train_a'],
        'm0': [*campaign, '--stage', 'evaluate_a', '--m0']}


def environment(args, stage):
    prefix = args.prefix
    from .asset_cache import PANDA
    codec = prefix/('codec' if stage in ('g3', 'm0', 'm0_train') else 'reader_codec')
    result = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'VIPER_OFFLINE': '1',
        'WANDB_MODE': 'disabled', 'HF_HOME': str(prefix/'cache/huggingface'), 'HF_HUB_CACHE': str(prefix/'cache/huggingface/hub'),
        'XDG_CACHE_HOME': str(prefix/'cache/xdg'), 'TORCH_HOME': str(prefix/'cache/torch'),
        'TORCH_EXTENSIONS_DIR': str(prefix/'cache/torch_extensions'), 'TRITON_CACHE_DIR': str(prefix/'cache/triton'),
        'CUDA_CACHE_PATH': str(prefix/'cache/cuda'), 'VIPER_ASSET_CACHE': str(prefix/'robot_cache'),
        'VIPER_PANDA_USD': str(prefix/'assets'/PANDA), 'VIPER_ACTION_CONTRACT_LIBRARY': str(paths(prefix)['native']),
        'LD_LIBRARY_PATH': os.pathsep.join(filter(None, (str(codec), os.environ.get('LD_LIBRARY_PATH')))),
        'PATH': '/usr/local/cuda-12.8/bin'+os.pathsep+str(prefix/'bootstrap/bin')+os.pathsep+os.environ['PATH'],
        'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MAX_JOBS': '2'}
    if args.accept_isaac_license: result['OMNI_KIT_ACCEPT_EULA'] = 'YES'
    return result


def no_live_workers(root):
    for path in root.rglob('.running'):
        with path.open('a') as lease:
            try: fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError('prior worker still running: '+str(path.parent)) from None


def verify(stage, args):
    from .first_session import verify_pilot, verify_qualification
    provenance = source_provenance()
    root = args.root
    if stage == 'qualify':
        from .simulation_smoke import verify as verify_smoke
        verify_smoke(root/'session/smoke', provenance)
        return verify_qualification(root/'session/qualification', provenance)
    if stage == 'collect': return verify_pilot(root/'session/pilot', provenance)
    if stage == 'g3':
        from .closed_loop_smoke import verify_report
        from .policy import checkpoint_digest
        report = read_json(root/'g3/result.json')
        from .dataset import file_digest
        from .training import dataset_digest
        configuration = read_json(root/'g3/configuration.json')
        if configuration['source'] != provenance['source_sha256'] or configuration['pretrained'] != str(args.pretrained.resolve()):
            raise ValueError('G3 source or pretrained identity changed')
        if any(file_digest(args.pretrained/name) != digest for name, digest in configuration['pretrained_files'].items()):
            raise ValueError('G3 original pretrained weights changed')
        for robot in ('openmanipulator_x', 'franka_panda'):
            if dataset_digest(root/'session/pilot/exports'/robot/'train') != configuration['datasets'][robot]['sha256']:
                raise ValueError('G3 training dataset changed')
        if report.get('status') != 'OPTIMIZER_AND_INFERENCE_PASS' or report.get('g3_closed_loop_verified') is not True:
            raise ValueError('G3 lacks optimizer/reload and real closed-loop evidence')
        for name in ('robot_a', 'robot_b'):
            saved = report['stages'][name]
            if checkpoint_digest(Path(saved['checkpoint'])) != saved['checkpoint_sha256']:
                raise ValueError('G3 checkpoint integrity changed')
        gate = read_json(root/'g3/closed_loop/result.json')
        if gate.get('status') != 'PASS': raise ValueError('G3 physical gate did not pass')
        return verify_report(gate['report'], gate['request'])
    if stage in ('m0', 'm0_train'):
        from .policy import checkpoint_digest
        location = root/('campaign/m0_evaluate_a/completed.json' if stage == 'm0' else 'campaign/train_a/completed.json')
        report = read_json(location)
        if report.get('status') != 'COMPLETE' or checkpoint_digest(Path(report['checkpoint'])) != report['checkpoint_sha256']:
            raise ValueError('source training/evaluation completion or checkpoint changed')
        if stage == 'm0':
            from .m0 import verify as verify_m0
            return verify_m0(Path(report['report']).parent)
        return {'status': 'COMPLETE', 'checkpoint_sha256': report['checkpoint_sha256']}
    raise ValueError('unknown verification stage')


def artifact_roots(stage, root):
    return {'qualify': [root/'session/smoke', root/'session/qualification'],
        'collect': [root/'session/pilot'], 'g3': [root/'g3'],
        'm0_train': [root/'campaign/models/a', root/'campaign/train_a'],
        'm0': [root/'campaign/m0_evaluate_a']}[stage]


def acquire_models(args):
    command = [str(paths(args.prefix)['training']), '-m', 'embodiment.models', '--prefix', str(args.prefix), '--execute', '--license-accepted']
    directory = args.prefix/'model_acquisition'
    directory.mkdir(parents=True, exist_ok=True)
    job = directory/f'attempt-{len(list(directory.glob("attempt-*"))):04d}'
    job.mkdir()
    env = environment(args, 'models')
    for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'VIPER_OFFLINE'): env.pop(key, None)
    measured = execute(command, job, args.timeout, env)
    if measured['returncode']: raise RuntimeError('model acquisition failed; inspect '+str(job/'process.log'))
    return measured


def pipeline(args):
    planned = commands(args)
    if args.allow_model_downloads:
        planned['models'] = [str(paths(args.prefix)['training']), '-m', 'embodiment.models', '--prefix', str(args.prefix), '--execute', '--license-accepted']
    report = {'schema': 'viper.rental.v1', 'status': 'NOT_EXECUTED', 'stage': args.stage,
        'commands': planned, 'provisions_hardware': False, 'stages': {},
        'physical_qualification_passed': False, 'g3_passed': False, 'm0_passed': False}
    from .deployment import install, system_doctor
    if args.stage == 'doctor':
        report['doctor'] = system_doctor(args.prefix, args.training_runtime)
        p = paths(args.prefix)
        report['runtime_probes'] = {}
        for role in ('simulation', 'reader', *(['training'] if args.training_runtime else [])):
            python = p[role]
            if not python.is_file():
                report['runtime_probes'][role] = {'ready': False, 'blockers': ['runtime missing; run setup: '+str(python)]}
            else:
                try:
                    volume = args.root
                    while not volume.exists(): volume = volume.parent
                    checked = subprocess.run([str(python), '-m', 'embodiment.host', '--stage', role, '--volume', str(volume)],
                        capture_output=True, text=True, timeout=60, env={**environment(args, role), 'CUDA_VISIBLE_DEVICES': ''})
                    report['runtime_probes'][role] = json.loads(checked.stdout)
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    report['runtime_probes'][role] = {'ready': False, 'blockers': [str(error)]}
        report['status'] = 'READY' if report['doctor']['ready'] and all(r['ready'] for r in report['runtime_probes'].values()) else 'BLOCKED'
        return report
    if args.stage == 'setup':
        setup_report = install(args.prefix, args.training_runtime, args.execute, args.accept_isaac_license, args.timeout)
        if args.allow_model_downloads: setup_report['model_operation'] = planned['models']
        return setup_report
    if not args.execute and args.stage != 'report':
        report['setup'] = install(args.prefix, args.training_runtime or args.stage == 'full', False)
        report['dependencies'] = DEPENDENCIES
        return report
    if args.stage == 'report' and (args.root/'pipeline/.lock').is_file():
        with (args.root/'pipeline/.lock').open('r') as lease:
            try: fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                report.update(status='RUNNING', reason='pipeline owns its run lock',
                    console_logs=[str(p) for p in sorted((args.root/'detached').glob('job-*/console.log'))])
                return report
    with locked(args.root/'pipeline'):
        if args.stage == 'report':
            from .deployment import verify_installation
            report['deployment'] = verify_installation(args.prefix)
        started = time.monotonic()
        try:
            provenance = source_provenance()
            frozen = {'source': provenance, 'prefix': str(args.prefix), 'root': str(args.root),
                'pretrained': str(args.pretrained), 'commands': planned, 'max_attempts': args.max_attempts}
            path = args.root/'pipeline/configuration.json'
            if path.exists():
                saved_config = read_json(path)
                if args.stage == 'report':
                    if saved_config['source'] != provenance or saved_config['root'] != str(args.root):
                        raise ValueError('pipeline source or root changed')
                    report['commands'] = saved_config['commands']
                elif saved_config != frozen:
                    raise ValueError('pipeline source or configuration changed; use a new root')
            if args.stage != 'report':
                if provenance['relic_worktree_dirty']: raise ValueError('clean committed source required')
                atomic_json(path, frozen)
            elif not path.exists():
                report.update(status='UNVERIFIED', reason='no executed pipeline configuration')
                return report
            no_live_workers(args.root)
            deadline = started+args.timeout
            def invoke(stage):
                if stage == 'g3' and 'g3_preflight' not in report['stages']:
                    # Check weights/runtime before consuming simulation time on
                    # unmet dependencies. Ordinary qualification needs no weights.
                    preflight_root = args.root/'pipeline/g3_preflight'
                    preflight_root.mkdir(exist_ok=True)
                    job = preflight_root/f'attempt-{len(list(preflight_root.glob("attempt-*"))):04d}'
                    job.mkdir()
                    preflight = subprocess.run(planned['g3_preflight'], capture_output=True, text=True,
                        timeout=max(.1, min(180, deadline-time.monotonic())),
                        env={**environment(args, stage), 'CUDA_VISIBLE_DEVICES': ''})
                    (job/'stdout.log').write_text(preflight.stdout)
                    (job/'stderr.log').write_text(preflight.stderr)
                    checked_host = json.loads(preflight.stdout)
                    report['stages']['g3_preflight'] = checked_host
                    if preflight.returncode or checked_host.get('ready_for_training_preflight') is not True:
                        raise RuntimeError('local training/model preflight failed; inspect '+str(job/'stdout.log'))
                for dependency in DEPENDENCIES.get(stage, []): invoke(dependency)
                if stage == 'full': return
                if stage == 'setup':
                    measured = install(args.prefix, True, True, args.accept_isaac_license, max(1, int(deadline-time.monotonic())))
                    if measured['status'] != 'INSTALLED': raise RuntimeError(str(measured.get('error')))
                    report['stages'][stage] = measured
                    if args.allow_model_downloads: report['stages']['models'] = acquire_models(args)
                    return
                if stage in report['stages']: return
                job = args.root/'pipeline'/stage
                job.mkdir(exist_ok=True)
                receipt = job/'completed.json'
                if receipt.exists():
                    saved = read_json(receipt)
                    if saved['files'] != {str(p): hashes(p) for p in artifact_roots(stage, args.root)}:
                        raise ValueError('completed '+stage+' artifacts changed')
                    saved['verification'] = verify(stage, args)
                    report['stages'][stage] = {**saved, 'reused': True}
                    return
                if stage == 'm0': invoke('m0_train')
                # Recover a crash after the subsystem committed its evidence but
                # before this outer receipt was published. Never rerun valid work.
                markers = {'qualify': args.root/'session/qualification/result.json',
                    'collect': args.root/'session/pilot/execution/result.json',
                    'g3': args.root/'g3/result.json', 'm0_train': args.root/'campaign/train_a/completed.json',
                    'm0': args.root/'campaign/m0_evaluate_a/completed.json'}
                if markers[stage].exists():
                    try: recovered = verify(stage, args)
                    except (ValueError, OSError, KeyError): recovered = None
                    if recovered is not None:
                        saved = {'stage': stage, 'verification': recovered, 'recovered': True,
                            'files': {str(p): hashes(p) for p in artifact_roots(stage, args.root)}}
                        atomic_json(receipt, saved)
                        report['stages'][stage] = saved
                        return
                attempts = sorted(job.glob('attempt-*'))
                if len(attempts) >= args.max_attempts: raise RuntimeError('stage attempt limit reached: '+stage)
                attempt = job/f'attempt-{len(attempts):04d}'
                attempt.mkdir()
                command = planned[stage]
                atomic_json(attempt/'command.json', command)
                if time.monotonic() >= deadline: raise TimeoutError('pipeline invocation deadline exceeded')
                measured = execute(command, attempt, deadline-time.monotonic(), environment(args, stage), resource_monitor=True)
                if measured['returncode'] or measured['timed_out']: raise RuntimeError(stage+' blocked; inspect '+str(attempt/'process.log'))
                checked = verify(stage, args)
                saved = {'stage': stage, 'verification': checked, 'process': measured,
                    'files': {str(p): hashes(p) for p in artifact_roots(stage, args.root)}}
                if source_provenance() != provenance: raise ValueError('source changed during pipeline')
                atomic_json(receipt, saved)
                report['stages'][stage] = saved
            if args.stage == 'report':
                for stage in ('qualify', 'collect', 'g3', 'm0_train', 'm0'):
                    receipt = args.root/'pipeline'/stage/'completed.json'
                    if not receipt.exists(): report['stages'][stage] = {'status': 'UNVERIFIED'}
                    else:
                        saved = read_json(receipt)
                        if saved['files'] != {str(p): hashes(p) for p in artifact_roots(stage, args.root)}:
                            raise ValueError('completed '+stage+' artifacts changed')
                        report['stages'][stage] = {'status': 'VERIFIED', 'verification': verify(stage, args)}
                report['status'] = 'AUDITED'
            else:
                invoke(args.stage)
                report['status'] = 'COMPLETE'
            report['physical_qualification_passed'] = 'verification' in report['stages'].get('qualify', {})
            report['g3_passed'] = 'verification' in report['stages'].get('g3', {})
            report['m0_passed'] = report['stages'].get('m0', {}).get('verification', {}).get('status') == 'PASS'
        except (Exception, KeyboardInterrupt) as error:
            report.update(status='BLOCKED', error=f'{type(error).__name__}: {error}')
        finally:
            report['wall_seconds'] = time.monotonic()-started
            history = args.root/'pipeline/reports'
            history.mkdir(exist_ok=True)
            atomic_json(history/f'run-{len(list(history.glob("run-*"))):04d}.json', report)
            atomic_json(args.root/'pipeline/report.json', report)
    return report


def parser():
    result = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    result.add_argument('stage', choices=STAGES)
    result.add_argument('--prefix', type=Path, default=Path('/workspace/viper'))
    result.add_argument('--root', type=Path, default=Path('/workspace/runs/viper'))
    result.add_argument('--pretrained', type=Path)
    result.add_argument('--episodes', type=int, choices=range(10, 21), default=12)
    result.add_argument('--steps', type=int, default=2000)
    result.add_argument('--save-steps', type=int, default=500)
    result.add_argument('--timeout', type=int, default=28800, help='total seconds per pipeline invocation, including dependencies')
    result.add_argument('--trial-timeout', type=int, default=2400)
    result.add_argument('--max-attempts', type=int, choices=range(1, 4), default=2)
    for name in ('execute', 'allow-gpu', 'allow-training', 'allow-model-downloads', 'accept-isaac-license',
                 'accept-model-license', 'training-runtime', 'background'):
        result.add_argument('--'+name, action='store_true')
    return result


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    cli = parser()
    args = cli.parse_args(arguments)
    args.prefix, args.root = args.prefix.resolve(), args.root.resolve()
    args.pretrained = args.pretrained.resolve() if args.pretrained else args.prefix/'models/groot'
    if not 1 <= args.timeout <= 86400 or not 1 <= args.trial_timeout <= 7200:
        cli.error('timeouts must be positive and bounded (total <=86400, trial <=7200)')
    if not 1 <= args.save_steps <= args.steps <= 10000: cli.error('source training requires 1 <= save-steps <= steps <=10000')
    if args.execute:
        if args.stage in ('qualify', 'collect', 'g3', 'm0', 'full') and not (args.allow_gpu and args.accept_isaac_license):
            cli.error('execution requires --allow-gpu --accept-isaac-license')
        if args.stage in ('g3', 'm0', 'full') and not args.allow_training:
            cli.error('training requires --allow-training')
    if args.allow_model_downloads and not (args.stage in ('setup', 'full') and args.training_runtime and args.accept_model_license):
        cli.error('model acquisition requires setup/full --training-runtime --accept-model-license')
    if args.background:
        if not args.execute or args.stage in ('doctor', 'report'): cli.error('--background requires an executable stage')
        directory = args.root/'detached'
        with locked(directory):
            attempt = directory/f'job-{len(list(directory.glob("job-*"))):04d}'
            attempt.mkdir()
            command = [sys.executable, '-m', 'embodiment.rental', *[a for a in arguments if a != '--background']]
            with (attempt/'console.log').open('xb') as stream:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                    start_new_session=True, cwd=Path(__file__).resolve().parents[1])
            result = {'status': 'LAUNCHED', 'pid': process.pid, 'command': command, 'log': str(attempt/'console.log'),
                'claim': 'launch receipt only; inspect report after reconnecting'}
            atomic_json(attempt/'launch.json', result)
    else:
        try:
            result = pipeline(args)
            if args.execute and args.allow_model_downloads and args.stage == 'setup' and result['status'] == 'INSTALLED':
                result['models'] = acquire_models(args)
        except (Exception, KeyboardInterrupt) as error:
            result = {'status': 'BLOCKED', 'error': f'{type(error).__name__}: {error}'}
    print(json.dumps(result, indent=2, allow_nan=False))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__': raise SystemExit(main())
