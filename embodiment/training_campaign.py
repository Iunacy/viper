"""Resumable matched training and evaluation; explicit execution only after G3."""
import argparse
from dataclasses import asdict
import json
import os
import shutil
import socket
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from .collection import atomic_json, execute, locked
from .dataset import read_json
from .policy import checkpoint_digest, prepare_training_checkpoint, validate_checkpoint
from .qualify import source_provenance
from .training import Budget, prepare, validate_upstream_arguments
from .training_smoke import validate_resume
from .weights import inspect_weights

CONDITIONS = ('a', 'b_only', 'a_to_b')
STAGES = tuple('train_'+name for name in CONDITIONS)+tuple('evaluate_'+name for name in CONDITIONS)


def restore_final_snapshot(checkpoint, destination):
    checkpoint, destination = Path(checkpoint).resolve(), Path(destination).resolve()
    if checkpoint.parent != destination: raise ValueError('recovery checkpoint must belong to training output')
    prepare_training_checkpoint(checkpoint)
    manifest = validate_checkpoint(checkpoint)
    names = ['config.json', *manifest['weight_paths'], 'processor_config.json', 'statistics.json', 'embodiment_id.json']
    if (checkpoint/'model.safetensors.index.json').exists(): names.append('model.safetensors.index.json')
    from .dataset import file_digest
    for name in names:
        target = destination/name
        if target.exists() and file_digest(target) != file_digest(checkpoint/name):
            raise ValueError('existing final weights disagree with completed recovery checkpoint')
    for name in names:
        if not (destination/name).exists(): os.link(checkpoint/name, destination/name)
    return validate_checkpoint(destination)


def run(source, dataset_a, dataset_b, pretrained, root, simulation_python, smoke_root,
        stage=None, execute_stage=False, budget=Budget(batch_size=1, gradient_accumulation=12), timeout=14400,
        observation_disturbance='baseline', m0=False):
    if m0 and (stage != 'evaluate_a' or observation_disturbance != 'baseline'):
        raise ValueError('M0 requires undisturbed source evaluation')
    from .perception import condition as perception_condition
    perception = perception_condition(observation_disturbance)
    source, dataset_a, dataset_b, pretrained, root, smoke_root = map(lambda p: Path(p).resolve(),
        (source, dataset_a, dataset_b, pretrained, root, smoke_root))
    with locked(root):
        training = prepare(source, dataset_a, dataset_b, root/'models', budget, pretrained)
        configuration = {'source': source_provenance(), 'budget': asdict(budget),
            'dataset_a': training['datasets']['a']['digest'], 'dataset_b': training['datasets']['b']['digest'],
            'pretrained': str(pretrained), 'pretrained_sha256': inspect_weights(pretrained)['sha256'],
            'simulation_python': str(simulation_python), 'source_path': str(source), 'smoke_root': str(smoke_root)}
        path = root/'configuration.json'
        if path.exists() and read_json(path) != configuration: raise ValueError('campaign inputs changed')
        atomic_json(path, configuration)
        atomic_json(root/'plan.json', training)
        result = {'schema': 'viper.training_campaign.v1', 'status': 'NOT_EXECUTED', 'training': training,
                  'training_executed': False, 'evaluation_executed': False}
        weights = validate_checkpoint(pretrained, require_processor=False)['weight_paths']
        weight_bytes = sum((pretrained/name).stat().st_size for name in weights)
        result['storage_estimate'] = {'pretrained_weight_bytes': weight_bytes,
            'conservative_campaign_reserve_bytes': 62*weight_bytes+12*1024**3,
            'scope': 'three runs, three retained checkpoints each, final snapshots and two initializations; conservative float32 and full optimizer upper bound'}
        if not execute_stage: return result
        if stage not in STAGES: raise ValueError('select a campaign stage')
        stored = {}
        for path in (root/'models').rglob('*'):
            if path.is_file() and not path.is_symlink():
                stat = path.stat()
                stored[(stat.st_dev, stat.st_ino)] = stat.st_size
        reserve = (18*weight_bytes+12*1024**3 if stage == 'train_a' else result['storage_estimate']['conservative_campaign_reserve_bytes'])
        remaining = max(12*1024**3, reserve-sum(stored.values())) if stage.startswith('train_') else 12*1024**3
        result['storage_estimate']['remaining_reserve_bytes'] = remaining
        if shutil.disk_usage(root).free < remaining:
            raise RuntimeError('insufficient storage reserve for matched training campaign')
        if configuration['source']['relic_worktree_dirty']: raise ValueError('clean committed source required')
        g3 = read_json(smoke_root/'result.json')
        g3_inputs = read_json(smoke_root/'configuration.json')
        if g3.get('status') != 'OPTIMIZER_AND_INFERENCE_PASS': raise ValueError('real G3 optimizer/reload/inference smoke required')
        if (g3_inputs['source'] != configuration['source']['source_sha256'] or
                g3_inputs['pretrained'] != str(pretrained) or
                g3_inputs['datasets']['openmanipulator_x']['sha256'] != configuration['dataset_a'] or
                g3_inputs['datasets']['franka_panda']['sha256'] != configuration['dataset_b']):
            raise ValueError('G3 source or datasets differ from full training campaign')
        # Optimizer/inference alone cannot admit full training: G3 also requires
        # the same B checkpoint to move the real target articulation in PhysX.
        from .closed_loop_smoke import verify_report
        gate = read_json(smoke_root/'closed_loop/result.json')
        target = g3['stages']['robot_b']
        if (gate.get('status') != 'PASS' or gate.get('simulation_executed') is not True or
                gate['request']['robot'] != 'franka_panda' or
                gate['request']['provenance']['source_sha256'] != configuration['source']['source_sha256'] or
                gate['request']['verified']['checkpoint_sha256'] != target['checkpoint_sha256'] or
                gate['request']['verified']['dataset_sha256'] != configuration['dataset_b'] or
                checkpoint_digest(Path(target['checkpoint'])) != target['checkpoint_sha256']):
            raise ValueError('matching real G3 closed-loop execution gate required')
        from .dataset import file_digest
        if file_digest(Path(gate['request']['native_library'])) != gate['request']['verified']['native_contract_sha256']:
            raise ValueError('G3 native action boundary changed')
        if file_digest(Path(gate['report'])) != gate['report_sha256']:
            raise ValueError('G3 physical report changed')
        verify_report(gate['report'], gate['request'])
        from .dataset import file_digest
        if any(file_digest(pretrained/name) != digest for name, digest in g3_inputs['pretrained_files'].items()):
            raise ValueError('pretrained weights changed after G3 validation')
        from .cloud import preflight
        if not preflight(source, pretrained, root)['ready_for_training_preflight']:
            raise RuntimeError('training host or cached model preflight failed')
        condition = stage.split('_', 1)[1]
        selected = next(item for item in training['runs'] if item['condition'] == condition)
        model = Path(selected['checkpoint'])
        job = root/('m0_evaluate_a' if m0 else stage+('_'+observation_disturbance if observation_disturbance != 'baseline' else ''))
        job.mkdir(exist_ok=True)
        job_config = job/'configuration.json'
        if job_config.exists() and read_json(job_config) != perception: raise ValueError('evaluation disturbance changed')
        atomic_json(job_config, perception)
        completed = job/'completed.json'
        if completed.exists():
            saved = read_json(completed)
            if checkpoint_digest(model) != saved['checkpoint_sha256']: raise ValueError('completed checkpoint changed')
            if saved.get('report_sha256'):
                from .dataset import file_digest
                if file_digest(Path(saved['report'])) != saved['report_sha256']: raise ValueError('evaluation report changed')
            if saved.get('evaluation_files'):
                from .collection import hashes
                if hashes(Path(saved['report']).parent) != saved['evaluation_files']: raise ValueError('evaluation artifacts changed')
                if m0:
                    from .m0 import verify as verify_m0
                    verify_m0(Path(saved['report']).parent)
            return saved
        if stage.startswith('evaluate_') and list(job.glob('attempt-*')):
            # Reconstruct a completed evaluation after a controller crash. An
            # incomplete held-out run requires explicit investigation, not reruns.
            from .paired import verify_evidence
            from .collection import hashes
            prior = sorted(job.glob('attempt-*'))[-1]/'evaluation/report.json'
            if not prior.exists() or read_json(prior).get('status') != 'COMPLETE':
                raise ValueError('prior held-out evaluation is incomplete; preserve it and investigate before a new predeclared run')
            measured = read_json(prior)
            verify_evidence(prior.parent, measured)
            if measured['policy_service']['checkpoint_sha256'] != checkpoint_digest(model):
                raise ValueError('prior evaluation checkpoint differs')
            recovered = {**result, 'status': 'COMPLETE', 'checkpoint': str(model), 'checkpoint_sha256': checkpoint_digest(model),
                'evaluation_executed': True, 'report': str(prior), 'report_sha256': file_digest(prior), 'evaluation_files': hashes(prior.parent), 'recovered': True}
            if m0:
                from .m0 import verify as verify_m0
                recovered['m0'] = verify_m0(prior.parent)
            atomic_json(completed, recovered)
            return recovered
        attempt = job/f'attempt-{len(list(job.glob("attempt-*"))):04d}'
        attempt.mkdir()
        environment = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'WANDB_MODE': 'disabled'}
        result.update(status='BLOCKED', stage=stage)
        try:
            if stage.startswith('train_'):
                if condition != 'a' and not Path(selected['base_model']).exists():
                    from .transfer import prepare as initialize
                    donor = root/'models/a'
                    initialize(donor, pretrained, dataset_b, source, Path(selected['base_model']),
                               condition='E3' if condition == 'a_to_b' else 'E2')
                if condition != 'a':
                    initialization = read_json(Path(selected['base_model'])/'initialization.json')
                    if (initialization['target_dataset_sha256'] != configuration['dataset_b'] or
                            initialization['checkpoint_sha256'] != checkpoint_digest(Path(selected['base_model']))):
                        raise ValueError('target initialization changed')
                arguments = list(selected['arguments'])
                checkpoints = sorted(model.glob('checkpoint-*'), key=lambda p: int(p.name.split('-')[-1]))
                already_complete = False
                if checkpoints:
                    result['resume'] = validate_resume(checkpoints[-1], budget.steps)
                    already_complete = result['resume']['step'] == budget.steps
                    arguments += ['--resume-from-checkpoint']
                validate_upstream_arguments(source, arguments)
                command = [sys.executable, '-m', 'embodiment.training_worker', '--source', str(source),
                           '--metrics', str(attempt/'resources.json'), *arguments]
                if not already_complete:
                    result['process'] = execute(command, attempt, timeout, environment, resource_monitor=True)
                    if result['process']['returncode']: raise RuntimeError('training failed; rerun this stage to resume')
                else:
                    restore_final_snapshot(checkpoints[-1], model)
                prepare_training_checkpoint(model)
                state = read_json(model/f'checkpoint-{budget.steps}/trainer_state.json')
                if state.get('global_step') != budget.steps: raise ValueError('requested optimizer steps not completed')
                result['training_executed'] = True
                result['training_executed_this_attempt'] = not already_complete
            else:
                validate_checkpoint(model)
                from .closed_loop_smoke import stop_process
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                service_log = (attempt/'service.log').open('xb')
                service = subprocess.Popen([sys.executable, '-m', 'embodiment.policy_service', '--source', str(source),
                    '--checkpoint', str(model), '--port', str(port)], stdout=service_log,
                    stderr=subprocess.STDOUT, env=environment, start_new_session=True)
                try:
                    deadline = time.monotonic()+180
                    while True:
                        if service.poll() is not None: raise RuntimeError('policy service failed; inspect service.log')
                        try:
                            with urllib.request.urlopen(f'http://127.0.0.1:{port}/metadata', timeout=2) as response:
                                metadata = json.load(response)
                            if (metadata['checkpoint_sha256'] != checkpoint_digest(model) or
                                    metadata.get('source_sha256') != configuration['source']['source_sha256']):
                                raise ValueError('port serves a different policy or source')
                            if m0:
                                library = Path(environment['VIPER_ACTION_CONTRACT_LIBRARY'])
                                if metadata.get('native_contract_sha256') != file_digest(library):
                                    raise ValueError('policy lacks the selected native action boundary')
                            break
                        except OSError:
                            if time.monotonic() >= deadline: raise RuntimeError('policy service startup timed out')
                            time.sleep(1)
                    command = [str(simulation_python), '-m', 'embodiment.evaluate', '--output', str(attempt/'evaluation'),
                        '--robot', selected['embodiment'], '--condition', condition, '--training-plan', str(root/'plan.json'),
                        '--observation-disturbance', observation_disturbance, '--policy-port', str(port),
                        '--headless', '--device', 'cuda:0', '--enable_cameras']
                    if m0: command += ['--no-fallback', '--counterfactual']
                    result['process'] = execute(command, attempt, timeout, environment, resource_monitor=True)
                    if result['process']['returncode']: raise RuntimeError('policy evaluation failed')
                    report = attempt/'evaluation/report.json'
                    from .paired import verify_evidence
                    measured = read_json(report)
                    verify_evidence(report.parent, measured)
                    if measured['status'] != 'COMPLETE': raise ValueError('incomplete physical policy evaluation')
                    from .dataset import file_digest
                    from .collection import hashes
                    result.update(evaluation_executed=True, report=str(report), report_sha256=file_digest(report), evaluation_files=hashes(report.parent))
                    if m0:
                        from .m0 import verify as verify_m0
                        result['m0'] = verify_m0(report.parent)
                finally:
                    try: stop_process(service)
                    finally: service_log.close()
            if source_provenance() != configuration['source']: raise ValueError('source changed during campaign')
            result.update(status='COMPLETE', checkpoint=str(model), checkpoint_sha256=checkpoint_digest(model))
            atomic_json(completed, result)
        except Exception as error:
            result['error'] = f'{type(error).__name__}: {error}'
        atomic_json(attempt/'result.json', result)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'dataset-a', 'dataset-b', 'pretrained', 'root', 'smoke-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--simulation-python', required=True)
    parser.add_argument('--stage', choices=STAGES)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--m0', action='store_true')
    parser.add_argument('--steps', type=int, default=2000)
    parser.add_argument('--save-steps', type=int, default=500)
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--gradient-accumulation', type=int, default=12)
    parser.add_argument('--timeout', type=int, default=14400)
    from .perception import KINDS as OBSERVATION_KINDS
    parser.add_argument('--observation-disturbance', choices=OBSERVATION_KINDS, default='baseline')
    args = parser.parse_args()
    measured = run(args.source, args.dataset_a, args.dataset_b, args.pretrained, args.root,
        args.simulation_python, args.smoke_root, args.stage, args.execute,
        Budget(args.steps, args.batch_size, gradient_accumulation=args.gradient_accumulation, save_steps=args.save_steps), args.timeout,
        args.observation_disturbance, args.m0)
    print(json.dumps(measured, indent=2))
    raise SystemExit(2 if measured['status'] == 'BLOCKED' else 0)
