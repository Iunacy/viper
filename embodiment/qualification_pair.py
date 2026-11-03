"""Qualify both robots on one clean, frozen revision without reusing legacy reports."""
import argparse
import json
from pathlib import Path
import sys
from .assets import MANIFEST
from .collection import atomic_json, execute, hashes, locked
from .dataset import DOF, read_json
from .preflight import LAB_COMMIT, SIM
from .qualify import campaign_cases, source_provenance
from .replay import load_episode, validate_pair


def verify_robot(run, robot, configuration):
    from PIL import Image
    from .qualification_evidence import verify_campaign
    evidence = verify_campaign(run)
    report = read_json(run/'report.json')
    if (report.get('relic_commit') != configuration['relic_commit'] or
            report.get('source_sha256') != configuration['source_sha256'] or
            report.get('runtime_pin') != configuration['runtime_pin'] or
            report.get('embodiment') != robot or
            [dict(seed=row['seed'], target=row['target']) for row in report['trials']] != configuration['cases']):
        raise ValueError('qualification identity or frozen scenarios differ')
    articulation = report_articulation = evidence['articulation']
    if not all(articulation.get(key) is True for key in ('camera_verified', 'native_state_verified', 'sensors_verified')):
        raise ValueError('camera, sensor and native-state articulation checks required')
    episodes = []
    for case in configuration['cases']:
        episode = load_episode(run/f"trial_{case['seed']:02d}")
        if episode.metadata.get('source_sha256') != configuration['source_sha256']:
            raise ValueError('trial source differs from qualification')
        if episode.metadata.get('sensor_contract') != 'viper.physical_sensors.v1':
            raise ValueError('measured end-effector orientation and gripper state required')
        from .recording import validate_sensor_sample
        for row, physical in zip(episode.rows, episode.telemetry, strict=True):
            validate_sensor_sample(row, physical, robot)
        for index, row in enumerate(episode.rows):
            if row['frame'] != f'camera/{index:06d}.png':
                raise ValueError('qualification camera frames are missing or misaligned')
            with Image.open(episode.path/row['frame']) as image:
                image.load()
                if image.mode != 'RGB' or image.size != (640, 480):
                    raise ValueError('qualification camera differs from frozen RGB resolution')
        episodes.append(episode)
    return {'report': report, 'articulation': report_articulation, 'run_path': str(run),
            'evidence_sha256': hashes(run)}, episodes


def qualify(root, python=sys.executable, run=False, timeout=2400, max_attempts=2):
    if type(timeout) is not int or timeout <= 0 or type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError('positive timeout and one to three qualification attempts required')
    root = Path(root).resolve()
    provenance = source_provenance()
    configuration = {'schema': 'viper.common_qualification.v2', **provenance,
                     'max_attempts': max_attempts, 'timeout': timeout,
                     'python': str(python), 'camera_required': True,
                     'cases': campaign_cases('qualification', 'train', 20),
                     'runtime_pin': {'isaacsim': SIM, 'isaaclab_commit': LAB_COMMIT, 'robot_commit': MANIFEST['commit']}}
    with locked(root):
        path = root/'qualification.json'
        if path.exists() and read_json(path) != configuration:
            raise ValueError('qualification source revision or frozen inputs changed')
        atomic_json(path, configuration)
        result = {'schema': 'viper.common_qualification_result.v2', 'status': 'NOT_EXECUTED',
                  'common_revision': provenance['relic_commit'], 'simulation_executed': False,
                  'robots': {}, 'errors': [], 'commands': {}}
        for robot in DOF:
            result['commands'][robot] = [str(python), '-m', 'embodiment.qualify', '--mode', 'qualification',
                '--robot', robot, '--output', str(root/robot/'attempt-0000/run'),
                '--headless', '--enable_cameras', '--device', 'cuda:0']
        try:
            if not run:
                return result
            if provenance['relic_worktree_dirty']:
                raise ValueError('qualification requires a clean committed revision')
            episodes = {}
            for robot in DOF:
                job = root/robot
                job.mkdir(exist_ok=True)
                receipt = job/'completed.json'
                if receipt.exists():
                    saved = read_json(receipt)
                    folder = Path(saved['run_path'])
                    if hashes(folder) != saved['evidence_sha256']:
                        raise ValueError('completed qualification artifacts changed: '+robot)
                else:
                    attempts = sorted(job.glob('attempt-*'))
                    if attempts:
                        # A crash after worker completion may be recovered, but
                        # its evidence must pass exactly the same admission checks.
                        candidate = attempts[-1]/'run'
                        try:
                            saved, _ = verify_robot(candidate, robot, configuration)
                            folder = candidate
                        except (OSError, ValueError, KeyError):
                            folder = None
                    else:
                        folder = None
                    if folder is None:
                        if len(attempts) >= max_attempts:
                            raise ValueError('qualification retry limit reached: '+robot)
                        attempt = job/f'attempt-{len(attempts):04d}'
                        attempt.mkdir()
                        command = list(result['commands'][robot])
                        command[command.index('--output')+1] = str(attempt/'run')
                        atomic_json(attempt/'command.json', command)
                        process = execute(command, attempt, timeout, resource_monitor=True)
                        if process['returncode'] or process['timed_out']:
                            partial = attempt/'run/report.json'
                            if partial.is_file():
                                result['simulation_executed'] |= read_json(partial).get('simulation_executed') is True
                            raise RuntimeError('qualification failed; evidence preserved in '+str(attempt))
                        folder = attempt/'run'
                saved, episodes[robot] = verify_robot(folder, robot, configuration)
                saved['process'] = read_json(folder.parent/'process.json') if (folder.parent/'process.json').exists() else None
                atomic_json(receipt, saved)
                result['robots'][robot] = saved
                result['simulation_executed'] = True
            for index in range(20):
                validate_pair({robot: episodes[robot][index] for robot in DOF})
            if source_provenance() != provenance:
                raise ValueError('source changed during common qualification')
            result.update(status='PASS')
        except (Exception, KeyboardInterrupt) as error:
            result.update(status='BLOCKED')
            result['errors'].append(f'{type(error).__name__}: {error}')
        finally:
            atomic_json(root/'result.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--timeout', type=int, default=2400)
    parser.add_argument('--max-attempts', type=int, default=2)
    args = parser.parse_args()
    result = qualify(args.root, args.python, args.execute, args.timeout, args.max_attempts)
    print(json.dumps(result, indent=2))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__': raise SystemExit(main())
