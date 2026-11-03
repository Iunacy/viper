"""First approved-host qualification and physical pilot, separated from training.

Runtime preparation is separate and explicit: inspect plans with
  python -m embodiment.bootstrap --prefix /opt/viper-runtime --role simulation
  python -m embodiment.bootstrap --prefix /opt/viper-runtime --role reader
Only add --execute to those setup commands when package/asset installation is
authorized. They do not acquire GR00T model weights.

Dry-run plan (no subprocesses, downloads, CUDA or Kit):
  python -m embodiment.first_session --root /workspace/runs/first \
    --simulation-python /opt/viper-runtime/simulation/bin/python \
    --reader-python /opt/viper-runtime/reader/bin/python \
    --isaac-source /opt/viper-runtime/sources/IsaacLab \
    --groot-source /opt/viper-runtime/sources/GR00T \
    --robot-cache /opt/viper-runtime/robot_cache --panda-assets /opt/viper-runtime/assets \
    --reader-library-path /opt/viper-runtime/reader_codec --episodes 12

Add --preflight for read-only host, cached-asset and reader checks. Add --execute
on a compatible, already approved host to check CUDA, run 20 frozen expert trials
per robot, and collect/export the bounded pilot. No training or model weights are
required. Accept the Isaac license separately before unattended execution.

Repeat the identical command to resume. Successful stages are hash-checked and
revalidated; failed attempts remain immutable and retries are capped. Configuration
changes require a new root. report.json contains precise failures and resources.
"""
import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
import importlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .assets import MANIFEST, ROOT, validate_urdf
from .asset_cache import ORIGIN, PANDA
from .collection import atomic_json, execute, hashes, locked
from .contract import manifest
from .dataset import DOF, file_digest, read_json
from .qualify import source_provenance
from .scenarios import plan


def assets(robot_cache, panda_assets):
    robot_cache, panda_assets = Path(robot_cache), Path(panda_assets)
    checked = {}
    catalogs = [(robot_cache, MANIFEST['files']),
                (robot_cache/'panda_replay', read_json(ROOT/'assets/panda_replay_manifest.json')['files'])]
    receipt = read_json(panda_assets/'assets.json')
    if (receipt.get('status') != 'CACHED' or receipt.get('origin') != ORIGIN or receipt.get('entry') != PANDA
            or PANDA not in receipt.get('files', {})):
        raise ValueError('Panda USD cache lacks a matching versioned dependency receipt')
    catalogs.append((panda_assets, {name: value['sha256'] for name, value in receipt['files'].items()}))
    for base, catalog in catalogs:
        for name, expected in catalog.items():
            path = base/name
            if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(base.resolve()):
                raise ValueError('asset dependency escapes its cache')
            if not path.is_file() or file_digest(path) != expected:
                raise ValueError('required cached robot asset missing or changed: '+str(path))
            checked[str(path)] = expected
    validate_urdf(robot_cache/'open_manipulator_description/urdf/open_manipulator_x/open_manipulator_x.urdf')
    checked[str(panda_assets/'assets.json')] = file_digest(panda_assets/'assets.json')
    return {'files': checked, 'panda_usd': str(panda_assets/PANDA), 'model_weights_required': False,
            'license_scope': 'cached upstream notices retained; Isaac runtime license accepted independently'}


def reader_probe(source, volume):
    from .host import inspect_host
    from .upstream_validation import verify_source
    report = inspect_host('reader', volume)
    verify_source(source)
    sys.path.insert(0, str(source))
    report['reader_requirements_sha256'] = file_digest(ROOT/'reader_requirements.txt')
    report['imports'] = {}
    for name in ('gr00t.data.dataset.lerobot_episode_loader', 'gr00t.data.state_action.state_action_processor', 'gr00t.data.dataset.sharded_single_step_dataset', 'embodiment.groot_modalities', 'torchcodec.decoders', 'av'):
        try:
            importlib.import_module(name)
            report['imports'][name] = 'IMPORTED'
        except Exception as error:
            report['blockers'].append(f'{name}: {type(error).__name__}: {error}')
    from .codec_runtime import system_codec_environment
    try:
        ffmpeg = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=15,
                                env=system_codec_environment(), check=True)
        report['ffmpeg'] = ffmpeg.stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError) as error:
        report['blockers'].append('system FFmpeg exporter unavailable: '+str(error))
    report.update(ready=not report['blockers'], model_weights_required=False, training_imports_required=False)
    return report


def verify_qualification(root, provenance):
    from .qualification_pair import verify_robot
    from .replay import validate_pair
    config = read_json(root/'qualification.json')
    if any(config.get(key) != provenance[key] for key in ('relic_commit', 'source_sha256')):
        raise ValueError('qualification source differs from session')
    report = read_json(root/'result.json')
    if report.get('status') != 'PASS' or report.get('simulation_executed') is not True:
        raise ValueError('dual qualification did not pass')
    episodes = {}
    for robot in DOF:
        receipt = read_json(root/robot/'completed.json')
        run = Path(receipt['run_path'])
        if not run.resolve().is_relative_to((root/robot).resolve()) or hashes(run) != receipt['evidence_sha256']:
            raise ValueError('qualification raw evidence changed')
        _, episodes[robot] = verify_robot(run, robot, config)
    for index in range(20):
        validate_pair({robot: episodes[robot][index] for robot in DOF})
    return {'status': 'PASS', 'robots': {robot: {'trials': 20,
        'successes': sum(episode.outcome['success'] for episode in cases)} for robot, cases in episodes.items()}}


def verify_pilot(root, provenance):
    from .dataset import validate_export
    config = read_json(root/'pilot.json')
    if any(config.get(key) != provenance[key] for key in ('relic_commit', 'source_sha256')):
        raise ValueError('pilot source differs from session')
    result = read_json(root/'execution/result.json')
    if result.get('status') != 'VALIDATED' or result.get('training_ready') is not True:
        raise ValueError('pilot did not complete physical and upstream validation')
    reports = {}
    for robot in DOF:
        for split in ('train', 'validation', 'evaluation'):
            label = robot+'/'+split
            saved = result['collections'][label]
            dataset, raw = root/'exports'/robot/split, root/robot/split
            if hashes(dataset) != saved['dataset_files'] or hashes(raw) != saved['collection_files']:
                raise ValueError('pilot export or raw evidence changed: '+label)
            validation = validate_export(dataset)
            count = len(config['scenarios'][split])
            if (validation['embodiment'] != robot or validation['split'] != split or validation['episodes'] != count
                    or saved.get('reader_process_succeeded') is not True):
                raise ValueError('pilot dataset identity, count or upstream receipt differs')
            reports[label] = {'validation': validation, 'collection': read_json(raw/'progress.json'),
                             'bytes': sum(p.stat().st_size for p in dataset.rglob('*') if p.is_file())}
    return {'status': 'VALIDATED', 'collections': reports}


def run(root, simulation_python, reader_python, isaac_source, groot_source, robot_cache, panda_assets,
        reader_library_path=None, episodes=12, execute_stage=False, preflight=False, timeout=2400, max_attempts=2, total_timeout=14400):
    if type(episodes) is not int or not 10 <= episodes <= 20:
        raise ValueError('pilot requires 10 to 20 successful train episodes per robot')
    if type(timeout) is not int or not 1 <= timeout <= 7200 or type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError('bounded stage timeout (1..7200) and retry count (1..3) required')
    if type(total_timeout) is not int or not 1 <= total_timeout <= 86400:
        raise ValueError('total invocation timeout must be in 1..86400 seconds')
    root, isaac_source, groot_source, robot_cache, panda_assets = map(lambda p: Path(p).resolve(),
        (root, isaac_source, groot_source, robot_cache, panda_assets))
    # Preserve virtual-environment executable symlinks.
    sim, reader = str(Path(simulation_python).absolute()), str(Path(reader_python).absolute())
    provenance = source_provenance()
    configuration = {'schema': 'viper.first_session_config.v1', 'source': provenance,
        'simulation_python': sim, 'reader_python': reader, 'isaac_source': str(isaac_source), 'groot_source': str(groot_source),
        'robot_cache': str(robot_cache), 'panda_assets': str(panda_assets),
        'reader_library_path': str(Path(reader_library_path).resolve()) if reader_library_path else None,
        'episodes': episodes, 'timeout': timeout, 'max_attempts': max_attempts, 'total_timeout': total_timeout,
        'contracts': {robot: manifest(robot) for robot in DOF},
        'qualification_cases': [{'seed': i, 'target': ('red', 'green', 'blue')[i%3]} for i in range(20)],
        'pilot_cases': {split: [asdict(case) for case in plan(split, 3*episodes)] for split in ('train', 'validation', 'evaluation')}}
    configuration = json.loads(json.dumps(configuration))
    commands = {
        'simulation_host': [sim, '-m', 'embodiment.host', '--stage', 'simulation', '--volume', str(root)],
        'reader': [reader, '-m', 'embodiment.first_session', '--reader-probe', str(groot_source), '--root', str(root)],
        'qualification': [reader, '-m', 'embodiment.qualification_pair', '--root', str(root/'qualification'),
            '--python', sim, '--timeout', str(timeout), '--max-attempts', str(max_attempts), '--execute'],
        'pilot': [reader, '-m', 'embodiment.pilot', '--root', str(root/'pilot'), '--python', sim, '--data-python', reader,
            '--groot-source', str(groot_source), '--episodes', str(episodes), '--timeout', str(timeout), '--execute',
            *(['--reader-library-path', str(reader_library_path)] if reader_library_path else [])]}
    environment = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'VIPER_OFFLINE': '1',
        'WANDB_MODE': 'disabled', 'VIPER_ASSET_CACHE': str(robot_cache), 'VIPER_PANDA_USD': str(panda_assets/PANDA)}
    if reader_library_path:
        environment['LD_LIBRARY_PATH'] = os.pathsep.join(filter(None, (str(reader_library_path), environment.get('LD_LIBRARY_PATH'))))
    with locked(root):
        result = {'schema': 'viper.first_session.v1', 'status': 'NOT_EXECUTED', 'blockers': [],
            'simulation_executed': False, 'physical_pilot_verified': False, 'training_executed': False,
            'model_weights_required': False, 'provisions_hardware': False, 'downloads_models': False,
            'commands': commands, 'stages': {}, 'source': provenance,
            'execute_command': [sys.executable, '-m', 'embodiment.first_session', '--root', str(root),
                '--simulation-python', sim, '--reader-python', reader, '--isaac-source', str(isaac_source),
                '--groot-source', str(groot_source), '--robot-cache', str(robot_cache), '--panda-assets', str(panda_assets),
                '--episodes', str(episodes), '--timeout', str(timeout), '--max-attempts', str(max_attempts),
                '--total-timeout', str(total_timeout), *(['--reader-library-path', str(reader_library_path)] if reader_library_path else []), '--execute']}
        started = time.monotonic()
        deadline = started+total_timeout
        try:
            path = root/'session.json'
            if path.exists() and read_json(path) != configuration:
                raise ValueError('frozen session configuration changed; use a new root')
            atomic_json(path, configuration)
            if not execute_stage and not preflight:
                return result
            if execute_stage and provenance['relic_worktree_dirty']:
                raise ValueError('physical execution requires a clean committed source revision')
            for lease in root.glob('processes/*/attempt-*/.running'):
                with lease.open('a') as stream:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise RuntimeError('prior stage process is still running: '+str(lease.parent)) from None
            # Check every prerequisite, without training imports, weights or Kit.
            check_root = root/'preflight'/f'attempt-{len(list((root/"preflight").glob("attempt-*"))):04d}'
            check_root.mkdir(parents=True)
            for stage in ('simulation_host', 'reader'):
                command = list(commands[stage])
                if stage == 'simulation_host' and execute_stage:
                    command.append('--cuda-check')
                try:
                    process = subprocess.run(command, capture_output=True, text=True, timeout=max(.1, min(120, deadline-time.monotonic())),
                        cwd=ROOT.parent, env={**environment, **({'CUDA_VISIBLE_DEVICES': ''} if stage == 'reader' else {})})
                    (check_root/(stage+'.stdout.log')).write_text(process.stdout)
                    (check_root/(stage+'.stderr.log')).write_text(process.stderr)
                    try:
                        report = json.loads(process.stdout)
                    except ValueError as error:
                        raise ValueError('probe did not emit JSON: '+process.stderr[-1200:]) from error
                    result['stages'][stage] = report
                    if process.returncode or not report.get('ready'):
                        result['blockers'].append({'stage': stage, 'reasons': report.get('blockers', ['probe failed'])})
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    result['blockers'].append({'stage': stage, 'reasons': [str(error)]})
            try:
                from .isaac_interfaces import verify
                result['stages']['isaac_source'] = verify(isaac_source)
                from .upstream_validation import verify_source
                verify_source(groot_source)
                selected_assets = assets(robot_cache, panda_assets)
                result['stages']['assets'] = selected_assets
                asset_receipt = root/'assets.json'
                if asset_receipt.exists() and read_json(asset_receipt) != selected_assets:
                    raise ValueError('session assets changed since preflight')
                atomic_json(asset_receipt, selected_assets)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                result['blockers'].append({'stage': 'sources_and_assets', 'reasons': [str(error)]})
            if result['blockers']:
                result['status'] = 'BLOCKED'
                return result
            result['status'] = 'PREFLIGHT_READY'
            if not execute_stage:
                return result
            for stage, verifier in (('qualification', verify_qualification), ('pilot', verify_pilot)):
                receipt_path = root/(stage+'.verified.json')
                artifact_root = root/stage
                if receipt_path.exists():
                    saved = read_json(receipt_path)
                    if hashes(artifact_root) != saved['files']:
                        raise ValueError('completed stage artifacts changed: '+stage)
                    verified = verifier(artifact_root, provenance)
                    result['stages'][stage] = {**saved, 'reused': True}
                else:
                    job = root/'processes'/stage/f'attempt-{len(list((root/"processes"/stage).glob("attempt-*"))):04d}'
                    if len(list((root/'processes'/stage).glob('attempt-*'))) >= max_attempts:
                        raise ValueError('session stage retry limit reached: '+stage)
                    job.mkdir(parents=True)
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('total session invocation deadline exceeded')
                    process = execute(commands[stage], job, remaining, environment)
                    if process['returncode'] or process['timed_out']:
                        partial = artifact_root/('result.json' if stage == 'qualification' else 'execution/result.json')
                        if partial.is_file():
                            result['stages'][stage] = {'partial_report': read_json(partial), 'process': process}
                            result['simulation_executed'] |= read_json(partial).get('simulation_executed') is True
                        raise RuntimeError(stage+' failed; inspect '+str(job/'process.log'))
                    verified = verifier(artifact_root, provenance)
                    saved = {'verification': verified, 'files': hashes(artifact_root), 'process': process}
                    atomic_json(receipt_path, saved)
                    result['stages'][stage] = saved
                result['simulation_executed'] = True
                if source_provenance() != provenance or assets(robot_cache, panda_assets) != selected_assets:
                    raise ValueError('source or assets changed during session')
            result.update(status='QUALIFIED_AND_COLLECTED', physical_pilot_verified=True)
        except (Exception, KeyboardInterrupt) as error:
            result['status'] = 'BLOCKED'
            result['blockers'].append({'stage': 'session', 'reasons': [f'{type(error).__name__}: {error}']})
        finally:
            result['wall_seconds'] = time.monotonic()-started
            result['artifact_bytes'] = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
            history = root/'reports'
            history.mkdir(exist_ok=True)
            atomic_json(history/f'run-{len(list(history.glob("run-*.json"))):04d}.json', result)
            atomic_json(root/'report.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reader-probe', type=Path)
    for name in ('simulation-python', 'reader-python', 'isaac-source', 'groot-source', 'robot-cache', 'panda-assets', 'reader-library-path'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--episodes', type=int, default=12)
    parser.add_argument('--timeout', type=int, default=2400)
    parser.add_argument('--max-attempts', type=int, default=2)
    parser.add_argument('--total-timeout', type=int, default=14400, help='maximum seconds per invocation, including simulation stages; default four hours')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    if args.reader_probe:
        try:
            with redirect_stdout(sys.stderr):
                report = reader_probe(args.reader_probe, args.root)
        except Exception as error:
            report = {'ready': False, 'blockers': [f'{type(error).__name__}: {error}']}
    else:
        for name in ('simulation_python', 'reader_python', 'isaac_source', 'groot_source', 'robot_cache', 'panda_assets'):
            if getattr(args, name) is None:
                parser.error('--'+name.replace('_', '-')+' required')
        report = run(args.root, args.simulation_python, args.reader_python, args.isaac_source, args.groot_source,
            args.robot_cache, args.panda_assets, args.reader_library_path, args.episodes, args.execute, args.preflight,
            args.timeout, args.max_attempts, args.total_timeout)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 2 if report.get('status') == 'BLOCKED' or report.get('ready') is False else 0


if __name__ == '__main__':
    raise SystemExit(main())
