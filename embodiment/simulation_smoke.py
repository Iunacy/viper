"""One camera-enabled expert scene per arm before the expensive qualification gate."""
import math
from pathlib import Path
import time
from .collection import atomic_json, execute, hashes, locked
from .dataset import DOF, read_json
from .qualify import source_provenance
from .replay import load_episode
from .recording import validate_sensor_sample


def verify(root, provenance):
    result = {}
    for robot in DOF:
        saved = read_json(root/robot/'completed.json')
        run = Path(saved['run'])
        if not run.is_relative_to(root/robot) or hashes(run) != saved['files']:
            raise ValueError('simulation smoke evidence changed')
        result[robot] = verify_robot(run, robot, provenance)
    return {'status': 'PASS', 'robots': result, 'simulation_executed': True}


def verify_robot(run, robot, provenance):
    report, articulation = read_json(run/'report.json'), read_json(run/'articulation.json')
    if (report.get('mode') != 'smoke' or report.get('status') != 'COMPLETE' or
            report.get('simulation_executed') is not True or report.get('completed') is not True or
            report.get('source_changed_during_run') != [] or report.get('error') or
            report.get('source_sha256') != provenance['source_sha256'] or report.get('relic_commit') != provenance['relic_commit'] or
            report.get('embodiment') != robot or len(report.get('trials', [])) != 1):
        raise ValueError('real completed single-scene smoke required')
    for key in ('fixed_base', 'physical_checks_executed', 'camera_verified', 'native_state_verified', 'sensors_verified'):
        if articulation.get(key) is not True:
            raise ValueError('physical articulation check missing: '+key)
    episode = load_episode(run/'trial_00')
    if (episode.outcome != report['trials'][0] or episode.metadata.get('purpose') != 'smoke' or
            episode.metadata.get('sensor_contract') != 'viper.physical_sensors.v1' or
            episode.metadata.get('source_sha256') != provenance['source_sha256'] or
            episode.metadata.get('embodiment') != robot or episode.metadata.get('seed') != 0 or
            episode.metadata.get('target') != 'red' or episode.outcome.get('success') is not True):
        raise ValueError('smoke raw identity or task completion missing')
    for row, physical in zip(episode.rows, episode.telemetry, strict=True):
        validate_sensor_sample(row, physical, robot)
        if physical['unsafe'] or physical['safety_events']:
            raise ValueError('unsafe smoke motion')
    if not any(math.dist(episode.rows[0]['ee_position'], row['ee_position']) > .001 for row in episode.rows):
        raise ValueError('smoke has no measured end-effector movement')
    # The dataset validator checks RGB, uniform cadence, bilateral grasp and placement.
    from .dataset import load_episode as validate_episode
    validated = validate_episode(run/'trial_00')
    if validated.shape != (480, 640, 3):
        raise ValueError('smoke camera resolution differs')
    return {'successes': 1, 'raw_frames': len(episode.rows), 'scope': 'startup diagnostic; does not replace 20-scene qualification'}


def run(root, python, execute_stage=False, timeout=600, max_attempts=2, *, deadline=None):
    if not 1 <= timeout <= 1200 or not 1 <= max_attempts <= 3:
        raise ValueError('smoke timeout 1..1200 and attempts 1..3 required')
    if deadline is not None and not math.isfinite(deadline):
        raise ValueError('finite invocation deadline required')
    root = Path(root).resolve()
    provenance = source_provenance()
    config = {'source': provenance, 'python': str(python), 'timeout': timeout, 'max_attempts': max_attempts}
    with locked(root):
        path = root/'configuration.json'
        if path.exists() and read_json(path) != config:
            raise ValueError('smoke configuration changed')
        atomic_json(path, config)
        result = {'status': 'NOT_EXECUTED', 'simulation_executed': False, 'commands': {}}
        for robot in DOF:
            result['commands'][robot] = [str(python), '-m', 'embodiment.qualify', '--mode', 'smoke', '--episodes', '1',
                '--robot', robot, '--output', str(root/robot/'attempt-0000/run'), '--headless', '--enable_cameras', '--device', 'cuda:0']
        try:
            if not execute_stage:
                return result
            from .rental import no_live_workers
            no_live_workers(root)
            if provenance['relic_worktree_dirty']:
                raise ValueError('clean committed source required')
            for robot in DOF:
                job = root/robot
                job.mkdir(exist_ok=True)
                receipt = job/'completed.json'
                if receipt.exists():
                    saved = read_json(receipt)
                    folder = Path(saved['run'])
                    if not folder.is_relative_to(job) or hashes(folder) != saved['files']:
                        raise ValueError('completed smoke evidence changed')
                    verify_robot(folder, robot, provenance)
                    continue
                remaining = timeout if deadline is None else deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('total session invocation deadline exceeded')
                attempts = sorted(job.glob('attempt-*'))
                if len(attempts) >= max_attempts:
                    raise RuntimeError('smoke attempt limit reached: '+robot)
                attempt = job/f'attempt-{len(attempts):04d}'
                attempt.mkdir()
                command = list(result['commands'][robot])
                command[command.index('--output')+1] = str(attempt/'run')
                measured = execute(command, attempt, min(timeout, remaining), resource_monitor=True)
                if measured['returncode'] or measured['timed_out']:
                    raise RuntimeError('smoke failed: '+str(attempt/'process.log'))
                verify_robot(attempt/'run', robot, provenance)
                atomic_json(receipt, {'run': str(attempt/'run'), 'files': hashes(attempt/'run'), 'process': measured})
            result.update(verify(root, provenance))
            if source_provenance() != provenance:
                raise ValueError('smoke source changed during execution')
        except (Exception, KeyboardInterrupt) as error:
            result.update(status='BLOCKED', error=f'{type(error).__name__}: {error}')
        finally:
            atomic_json(root/'result.json', result)
        return result
