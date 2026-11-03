"""Opt-in GR00T/Isaac execution gate. Run --help for the single smoke entry point.

Build the dependency-free C++ boundary first:
  cmake -S embodiment/native -B build-action-contract -DCMAKE_BUILD_TYPE=Release
  cmake --build build-action-contract && ctest --test-dir build-action-contract

Preflight (no model load, training, Kit startup, downloads or GPU execution):
  python -m embodiment.closed_loop_smoke --source /runtime/GR00T \
    --checkpoint /runs/checkpoint --dataset /data/robot/train --robot franka_panda \
    --training-python /runtime/GR00T/.venv/bin/python \
    --simulation-python /runtime/simulation/bin/python \
    --native-library build-action-contract/libviper_action_contract.so --output /runs/smoke

Add --execute on an already approved compatible host to load weights and run PhysX.
Use a new output directory per attempt. Runs three validation scenes by default;
these are development diagnostics, never the frozen held-out evaluation scenes.
Integration PASS requires movement and verified raw physical evidence in every
scene, not task completion. It establishes neither M0 nor experimental transfer.
"""
import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from .collection import atomic_json, execute, hashes
from .contract import ADAPTERS, manifest
from .dataset import file_digest, read_json
from .policy import checkpoint_digest
from .qualify import source_provenance
from .scenarios import plan


def offline_inputs(request):
    """Run in the pinned GR00T interpreter; never instantiate a model."""
    from .checkpoint_compatibility import validate_processor
    from .dataset import validate_export
    from .native_contract import NativeContract
    from .runtime_probe import probe
    from .training import dataset_digest
    from .upstream_validation import validate_with_upstream, verify_source
    source, dataset, checkpoint = (Path(request[key]) for key in ('source', 'dataset', 'checkpoint'))
    verify_source(source)
    validated = validate_export(dataset)
    if validated['embodiment'] != request['robot'] or validated['split'] != 'train':
        raise ValueError('matching physical training dataset required')
    info = read_json(dataset/'meta/info.json')
    if info['features']['observation.images.overhead']['shape'] != [480, 640, 3]:
        raise ValueError('training camera resolution differs from the frozen Isaac camera')
    compatibility = validate_processor(checkpoint, request['robot'])
    trainer = read_json(checkpoint/'trainer_state.json')
    if type(trainer.get('global_step')) is not int or trainer['global_step'] <= 0:
        raise ValueError('checkpoint lacks evidence of completed optimizer steps')
    upstream = validate_with_upstream(source, dataset, decode_video=True)
    # Compare every saved normalizer with statistics recomputed from this robot's
    # training split. A shape-compatible but stale normalizer is insufficient.
    from gr00t.data.dataset.lerobot_episode_loader import LeRobotEpisodeLoader
    from .groot_modalities import RELIC_CONFIG
    from .policy import validate_checkpoint
    processor_root = Path(validate_checkpoint(checkpoint)['processor'])
    ids = read_json(processor_root/'embodiment_id.json')
    if type(ids.get('new_embodiment')) is not int or ids['new_embodiment'] != 10:
        raise ValueError('checkpoint projector index differs from pinned NEW_EMBODIMENT index 10')
    saved = read_json(processor_root/'statistics.json')['new_embodiment']
    expected = LeRobotEpisodeLoader(dataset, RELIC_CONFIG).get_dataset_statistics()
    import numpy as np
    for modality in ('state', 'action'):
        for group, statistics in saved[modality].items():
            for field in ('mean', 'std', 'min', 'max', 'q01', 'q99'):
                if not np.allclose(statistics[field], expected[modality][group][field], rtol=1e-6, atol=1e-8):
                    raise ValueError('checkpoint normalization differs from supplied training dataset')
    NativeContract(request['native_library'])
    imported = probe(source)
    if not imported['ready']:
        raise RuntimeError('; '.join(imported['errors']))
    return {'checkpoint_sha256': checkpoint_digest(checkpoint), 'dataset_sha256': dataset_digest(dataset),
            'native_contract_sha256': file_digest(Path(request['native_library'])),
            'processor': compatibility, 'upstream': upstream, 'imports': imported}


def verify_report(path, request):
    """Verify raw evidence, not just success booleans in a summary receipt."""
    from .dataset import load_episode
    from .benchmark import CONTROL_DT
    from .perception import verify_trace
    path = Path(path)
    report = read_json(path)
    if (report.get('schema') != 'viper.closed_loop_smoke.v1' or report.get('error') or
            report.get('completed') is not True or report.get('request') != request or
            len(report.get('trials', [])) != len(request['cases'])):
        raise ValueError('closed-loop report identity or completion differs')
    service = request['policy_service']
    if (service.get('checkpoint_sha256') != request['verified']['checkpoint_sha256'] or
            service.get('source_sha256') != request['provenance']['source_sha256'] or
            service.get('native_contract_sha256') != request['verified']['native_contract_sha256']):
        raise ValueError('report service identity differs from verified inputs')
    commands = 0
    for case, trial in zip(request['cases'], report['trials'], strict=True):
        folder = path.parent/f"trial_{case['seed']}"
        if (any(trial.get(key) != value for key, value in case.items()) or
                trial.get('simulation_executed') is not True or trial.get('controller') != 'vla_only' or
                trial.get('fallback_triggers') or trial.get('policy_errors') or trial.get('safety_events') or
                trial.get('rejected_policy_actions') or trial.get('evidence_sha256') != hashes(folder)):
            raise ValueError('trial lacks matching unassisted physical policy evidence')
        episode = load_episode(folder, expert_only=False)
        if (episode.outcome != {key: value for key, value in trial.items() if key != 'evidence_sha256'} or
                episode.metadata['source_sha256'] != request['provenance']['source_sha256'] or
                episode.metadata['embodiment'] != request['robot'] or
                episode.metadata['policy_service'] != request['policy_service']):
            raise ValueError('raw episode provenance differs from smoke request')
        verify_trace(folder/'perception.jsonl', episode.metadata, episode.rows)
        traces = [json.loads(line) for line in (folder/'execution.jsonl').read_text().splitlines()]
        if len(traces) != len(episode.rows)-1:
            raise ValueError('execution trace does not cover every commanded tick')
        moved = False
        for index, trace in enumerate(traces):
            row, following = episode.rows[index:index+2]
            if (trace.get('controller') != 'vla_only' or trace.get('applied_action') != row['action'] or
                    trace.get('requested_action') != row['action'] or trace.get('timestamp') != row['timestamp'] or
                    not math.isclose(trace.get('response_timestamp', -1), following['timestamp'], abs_tol=1e-8) or
                    not math.isclose(following['timestamp']-row['timestamp'], CONTROL_DT, abs_tol=1e-8) or
                    trace.get('observed_next_ee') != following['ee_position']):
                raise ValueError('execution cadence or requested/applied action trace differs from raw samples')
            error = math.dist(following['ee_position'], trace['desired_ee'])
            if not math.isclose(error, trace['tracking_error_m'], abs_tol=1e-10):
                raise ValueError('recorded tracking error differs from observed motion')
            moved |= math.dist(row['ee_position'], following['ee_position']) > 1e-5
            commands += 1
        if not traces or not moved:
            raise ValueError('policy never moved the physical robot in an assigned scene')
    return {'physical_policy_actions': commands, 'scenes': len(request['cases']),
            'task_successes': sum(row['success'] for row in report['trials']),
            'scope': 'execution integration only; no M0 learning or A-to-B transfer claim'}


def worker(request, output):
    from .policy_service import RemotePolicy
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError('Isaac worker requires Python 3.11')
    app = backend = None
    report = {'schema': 'viper.closed_loop_smoke.v1', 'request': request,
              'completed': False, 'trials': [], 'error': None}
    try:
        if source_provenance() != request['provenance']:
            raise ValueError('worker source differs from frozen smoke request')
        policy = RemotePolicy(request['port'], timeout=request['policy_timeout'])
        if policy.metadata != request['policy_service']:
            raise ValueError('worker connected to a different policy service')
        from .host import inspect_host
        host = inspect_host('simulation', output)
        if not host['ready']:
            raise RuntimeError('simulation capacity after policy load: '+'; '.join(host['blockers']))
        from isaaclab.app import AppLauncher
        parser = argparse.ArgumentParser()
        AppLauncher.add_app_launcher_args(parser)
        app = AppLauncher(parser.parse_args(['--headless', '--device', 'cuda:0', '--enable_cameras'])).app
        from .isaac_backend import IsaacBackend
        from .evaluate import run_trial
        from .execution import ExecutionConfig
        backend = IsaacBackend('cuda:0', True, request['robot'])
        atomic_json(output/'articulation.json', backend.qualify_articulation())
        cases = plan('validation', len(request['cases']))
        if [asdict(case) for case in cases] != request['cases']:
            raise ValueError('smoke scenes differ from deterministic validation schedule')
        for case in cases:
            report['trials'].append(run_trial(backend, policy, case, output/f'trial_{case.seed}',
                request['provenance'], ExecutionConfig(fallback_enabled=False), app.is_running))
            atomic_json(output/'report.json', report)
        if source_provenance() != request['provenance']:
            raise ValueError('runtime source changed during smoke')
        report['completed'] = True
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        try:
            if backend is not None:
                backend.safe_stop()
        finally:
            try:
                if app is not None:
                    app.close(wait_for_replicator=False)
            finally:
                atomic_json(output/'report.json', report)
    return report


def stop_process(process):
    # Process group cleanup includes any child spawned by model initialization.
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def wait_service(process, port, expected, deadline):
    from .policy_service import RemotePolicy
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('policy service exited before readiness; inspect policy.log')
        try:
            policy = RemotePolicy(port, timeout=1)
        except (RuntimeError, ValueError):
            time.sleep(.1)
            continue
        if any(policy.metadata.get(key) != value for key, value in expected.items()):
            raise ValueError('policy service identity differs from frozen smoke inputs')
        return policy.metadata
    raise TimeoutError('policy service readiness deadline exceeded')


def run(request, output, execute_stage=False, timeout=900):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'viper.closed_loop_gate.v1', 'status': 'BLOCKED', 'errors': [],
              'simulation_executed': False, 'checkpoint_loaded': False, 'training_executed': False,
              'learned_manipulation_demonstrated': False, 'transfer_demonstrated': False,
              'stages': {}}
    service = None
    started = time.monotonic()
    deadline = started+timeout
    environment = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                   'WANDB_MODE': 'disabled', 'VIPER_OFFLINE': '1',
                   'VIPER_ACTION_CONTRACT_LIBRARY': str(request['native_library'])}
    try:
        if type(timeout) is not int or timeout <= 0:
            raise ValueError('positive integer timeout required')
        if request['robot'] not in ADAPTERS or not 1 <= len(request['cases']) <= 3:
            raise ValueError('one to three scenes and a supported embodiment required')
        request = {**request, 'provenance': source_provenance()}
        atomic_json(output/'request.json', request)
        # Collect all runtime failures independently, so missing assets do not hide
        # host/version failures. Probes cannot see or execute on a GPU.
        for name, python, args in (
                ('training_host', request['training_python'], ['-m', 'embodiment.host', '--stage', 'training', '--volume', str(output)]),
                ('simulation_host', request['simulation_python'], ['-m', 'embodiment.host', '--stage', 'simulation', '--volume', str(output)]),
                ('inputs', request['training_python'], ['-m', 'embodiment.closed_loop_smoke', '--probe-request', str(output/'request.json')])):
            try:
                process = subprocess.run([python, *args], capture_output=True, text=True,
                    timeout=max(.1, min(180, deadline-time.monotonic())),
                    cwd=Path(__file__).resolve().parents[1],
                    env={**environment, 'CUDA_VISIBLE_DEVICES': ''})
                (output/(name+'.stdout.log')).write_text(process.stdout)
                (output/(name+'.stderr.log')).write_text(process.stderr)
                try:
                    receipt = json.loads(process.stdout)
                except ValueError as error:
                    raise ValueError('probe did not emit JSON: '+process.stderr[-1500:]) from error
                result['stages'][name] = receipt
                if process.returncode or receipt.get('ready') is False or receipt.get('error'):
                    raise ValueError('; '.join(receipt.get('blockers', [])) or receipt.get('error') or 'runtime probe failed')
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                result['errors'].append(name+': '+str(error))
        if result['errors']:
            return result
        verified = result['stages']['inputs']
        request.update(verified=verified)
        atomic_json(output/'request.json', request)
        result['status'] = 'PREFLIGHT_ONLY'
        if not execute_stage:
            return result
        if request['provenance']['relic_worktree_dirty']:
            raise ValueError('real execution requires a clean committed source revision')
        # Reserve a local port; metadata validation also rejects a pre-existing or
        # racing service, so a port collision cannot silently substitute policies.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with (output/'policy.log').open('xb') as log:
            command = [request['training_python'], '-m', 'embodiment.policy_service', '--source', request['source'],
                       '--checkpoint', request['checkpoint'], '--port', str(port)]
            service = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                cwd=Path(__file__).resolve().parents[1], env=environment, start_new_session=True)
            expected = {'checkpoint_sha256': verified['checkpoint_sha256'], 'embodiment': request['robot'],
                        'source_sha256': request['provenance']['source_sha256'],
                        'native_contract_sha256': verified['native_contract_sha256'],
                        'contract': json.loads(json.dumps(manifest(request['robot'])))}
            request.update(port=port, policy_service=wait_service(service, port, expected, min(deadline, time.monotonic()+180)))
            result['checkpoint_loaded'] = True
            atomic_json(output/'request.json', request)
            job = output/'simulation'
            job.mkdir()
            run_output = job/'run'
            command = [request['simulation_python'], '-m', 'embodiment.closed_loop_smoke',
                       '--worker-request', str(output/'request.json'), '--output', str(run_output)]
            result['process'] = execute(command, job, max(.1, deadline-time.monotonic()), environment)
            result['simulation_executed'] = (run_output/'articulation.json').exists()
            if result['process']['returncode'] or result['process']['timed_out']:
                raise RuntimeError('Isaac worker failed or timed out; inspect simulation/process.log')
            result['verification'] = verify_report(run_output/'report.json', request)
            # Repeat input hashes after execution; files may have changed during
            # service startup even when the simulator's source remained frozen.
            from .training import dataset_digest
            if (checkpoint_digest(Path(request['checkpoint'])) != verified['checkpoint_sha256'] or
                    dataset_digest(Path(request['dataset'])) != verified['dataset_sha256'] or
                    file_digest(Path(request['native_library'])) != verified['native_contract_sha256'] or
                    source_provenance() != request['provenance']):
                raise ValueError('smoke inputs changed during execution')
            result.update(status='PASS', simulation_executed=True, request=request,
                          report=str(run_output/'report.json'), report_sha256=file_digest(run_output/'report.json'))
    except (Exception, KeyboardInterrupt) as error:
        result['status'] = 'BLOCKED'
        result['errors'].append(f'{type(error).__name__}: {error}')
    finally:
        try:
            stop_process(service)
            result['policy_process_reaped'] = True
        except Exception as error:
            result['status'] = 'BLOCKED'
            result['errors'].append('policy cleanup failed: '+str(error))
        finally:
            result['wall_seconds'] = time.monotonic()-started
            atomic_json(output/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    internal = parser.add_mutually_exclusive_group()
    internal.add_argument('--probe-request', type=Path)
    internal.add_argument('--worker-request', type=Path)
    for name in ('source', 'checkpoint', 'dataset', 'native-library', 'training-python', 'simulation-python'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--robot', choices=ADAPTERS)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--scenes', type=int, choices=range(1, 4), default=3)
    parser.add_argument('--policy-timeout', type=float, default=30)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.probe_request:
        from contextlib import redirect_stdout
        try:
            with redirect_stdout(sys.stderr):
                result = offline_inputs(read_json(args.probe_request))
        except Exception as error:
            result = {'error': f'{type(error).__name__}: {error}'}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 2 if result.get('error') else 0
    if args.worker_request:
        if args.output is None:
            parser.error('--output required for worker')
        args.output.mkdir(parents=True, exist_ok=False)
        result = worker(read_json(args.worker_request), args.output)
        return 0 if result['completed'] else 2
    for name in ('source', 'checkpoint', 'dataset', 'native_library', 'training_python', 'simulation_python', 'robot', 'output'):
        if getattr(args, name) is None:
            parser.error('--'+name.replace('_', '-')+' required')
    if not 0 < args.policy_timeout <= 120:
        parser.error('--policy-timeout must be in (0, 120] seconds')
    request = {name: str(getattr(args, name).absolute() if name.endswith('_python') else getattr(args, name).resolve()) for name in
               ('source', 'checkpoint', 'dataset', 'native_library', 'training_python', 'simulation_python')}
    request.update(robot=args.robot, policy_timeout=args.policy_timeout,
                   cases=[asdict(case) for case in plan('validation', args.scenes)])
    result = run(request, args.output, args.execute, args.timeout)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['status'] in ('PASS', 'PREFLIGHT_ONLY') else 2


if __name__ == '__main__':
    raise SystemExit(main())
