import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .dataset import DOF, export, file_digest, load_episode, read_json, validate_collection
from .qualify import source_provenance
from .scenarios import SPLITS, plan


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root/'.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('another collector owns this collection') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def hashes(path):
    if path.is_symlink():
        raise ValueError('symlink episode directories are not permitted')
    result = {}
    for file in sorted(path.rglob('*')):
        if file.is_symlink():
            raise ValueError('symlinks are not permitted in collected episodes')
        if file.is_file():
            digest = hashlib.sha256()
            with file.open('rb') as stream:
                while chunk := stream.read(1024*1024):
                    digest.update(chunk)
            result[str(file.relative_to(path))] = digest.hexdigest()
    return result


def inspect_job(job, robot, split, source_hashes):
    with (job/'.running').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'simulator still owns unfinished job: {job}') from None
    request = read_json(job/'request.json')
    if not isinstance(request, dict) or set(request) != {'robot', 'split', 'start', 'count', 'cases'}:
        raise ValueError('invalid collection job request')
    expected = [asdict(case) for case in plan(split, request['count'], request['start'])]
    if request['robot'] != robot or request['split'] != split or request['cases'] != expected:
        raise ValueError('collection job scenario identity changed')
    receipt_path = job/'receipt.json'
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if not isinstance(receipt, dict) or set(receipt) != {'request', 'successes', 'failures'} or receipt['request'] != request:
            raise ValueError('collection receipt request changed')
        if not isinstance(receipt['successes'], list) or not isinstance(receipt['failures'], list):
            raise ValueError('invalid collection receipt entries')
        assigned = {case['scenario_id']: case for case in expected}
        seen = set()
        for item in [*receipt['successes'], *receipt['failures']]:
            case = item.get('case') if isinstance(item, dict) else None
            if not isinstance(case, dict) or assigned.get(case.get('scenario_id')) != case or case['scenario_id'] in seen:
                raise ValueError('collection receipt contains duplicate or unassigned scenarios')
            seen.add(case['scenario_id'])
        if seen != set(assigned):
            raise ValueError('collection receipt omits assigned scenarios')
        if any(not isinstance(item.get('reason'), str) or not item['reason'] for item in receipt['failures']):
            raise ValueError('collection receipt failure reason missing')
        for failed in receipt['failures']:
            if 'evidence_sha256' in failed:
                folder = job/'run'/f"trial_{failed['case']['seed']:02d}"
                current = hashes(folder) if folder.exists() else None
                rejected_file = job/'run/rejected_scenes.jsonl'
                rejected_digest = file_digest(rejected_file) if rejected_file.exists() else None
                if current != failed['evidence_sha256'] or rejected_digest != failed.get('rejection_report_sha256'):
                    raise ValueError('failed or rejected attempt evidence changed')
            if failed.get('category', 'legacy_unclassified') not in ('expert_failure', 'rejected_scene', 'incomplete_episode', 'legacy_unclassified'):
                raise ValueError('unknown failure category')
        for accepted in receipt['successes']:
            if accepted.get('folder') != f"trial_{accepted['case']['seed']:02d}":
                raise ValueError('collection receipt folder differs from assigned case')
            path = job/'run'/accepted['folder']
            if hashes(path) != accepted['sha256']:
                raise ValueError(f'accepted episode was corrupted: {path}')
            episode = load_episode(path)
            validate_assignment(episode, accepted['case'], robot, source_hashes)
            if episode.outcome['success'] is not True:
                raise ValueError('collection receipt accepts a failed episode')
            validate_collection([path])
        return receipt
    successes, failures = [], []
    rejected_file = job/'run/rejected_scenes.jsonl'
    rejected = {}
    if rejected_file.exists():
        for line in rejected_file.read_text().splitlines():
            entry = json.loads(line)
            if not isinstance(entry, dict):
                raise ValueError('malformed scene rejection')
            case = entry.get('case')
            if case not in expected or case['scenario_id'] in rejected or not isinstance(entry.get('reason'), str):
                raise ValueError('scene rejection is duplicate, unassigned or malformed')
            rejected[case['scenario_id']] = entry['reason']
    def failure(case, reason, category, folder):
        return {'case': case, 'reason': reason, 'category': category,
                'evidence_sha256': hashes(folder) if folder.exists() else None,
                'rejection_report_sha256': file_digest(rejected_file) if rejected_file.exists() else None}
    for case in expected:
        folder = f"trial_{case['seed']:02d}"
        path = job/'run'/folder
        try:
            episode = load_episode(path)
            validate_assignment(episode, case, robot, source_hashes)
            if not episode.outcome['success']:
                failures.append(failure(case, episode.outcome.get('failure_reason', 'physical_failure'), 'expert_failure', path))
                continue
            validate_collection([path])
            successes.append({'case': case, 'folder': folder, 'sha256': hashes(path)})
        except (OSError, ValueError, KeyError, TypeError) as error:
            reason = rejected.get(case['scenario_id'])
            failures.append(failure(case, reason or f'{type(error).__name__}: {error}',
                                    'rejected_scene' if reason else 'incomplete_episode', path))
    receipt = {'request': request, 'successes': successes, 'failures': failures}
    atomic_json(receipt_path, receipt)
    return receipt


def validate_assignment(episode, case, robot, source_hashes):
    if any(episode.metadata.get(key) != value for key, value in case.items()):
        raise ValueError('episode scenario differs from assigned case')
    if episode.metadata.get('source_sha256') != source_hashes:
        raise ValueError('episode source differs from frozen collection source')
    if episode.metadata['embodiment'] != robot or episode.metadata.get('purpose') != 'collection':
        raise ValueError('episode embodiment or purpose mismatch')


def storage_budget(root, count, jobs, reserve_bytes):
    measurements = []
    for job in jobs:
        request = read_json(job/'request.json')
        size = sum(path.stat().st_size for path in job.rglob('*') if path.is_file())
        measurements.append(size / request['count'])
    per_episode = max([256 * 1024**2, *(int(size * 2) for size in measurements)])
    free = shutil.disk_usage(root).free
    return {'free_bytes': free, 'reserve_bytes': reserve_bytes,
            'estimated_batch_bytes': count * per_episode,
            'measured_jobs': len(measurements),
            'sufficient': free >= reserve_bytes + count * per_episode}


def balanced_selection(paths, split, target):
    quotas = Counter((case.target, case.region) for case in plan(split, target))
    selected, surplus = [], []
    for path in paths:
        metadata = read_json(path/'metadata.json')
        pair = metadata['target'], metadata['region']
        if quotas[pair] > 0:
            selected.append(path)
            quotas[pair] -= 1
        else:
            surplus.append(path)
    return selected, surplus


def progress(root, robot, split, verified_jobs=None):
    successes, failures, jobs = [], [], []
    verified_jobs = {} if verified_jobs is None else verified_jobs
    fingerprints = set()
    next_index = 0
    source_hashes = read_json(root/'collection.json')['source_sha256']
    if source_provenance()['source_sha256'] != source_hashes:
        raise ValueError('collection source changed during execution')
    for job in sorted((root/'jobs').glob('job-*')):
        if not (job/'request.json').exists():
            continue
        if job not in verified_jobs:
            verified_jobs[job] = inspect_job(job, robot, split, source_hashes)
        receipt = verified_jobs[job]
        request = receipt['request']
        if request['start'] != next_index:
            raise ValueError('job ranges overlap or contain a gap')
        next_index += request['count']
        for item in receipt['successes']:
            fingerprint = item['case']['scenario_id']
            if fingerprint in fingerprints:
                raise ValueError('duplicate successful scenario')
            fingerprints.add(fingerprint)
            successes.append(job/'run'/item['folder'])
        failures.extend(receipt['failures'])
        jobs.append(job)
    return successes, failures, next_index, jobs


def stop_process_tree(process):
    """Terminate nested simulator sessions as well as their orchestration parent."""
    import signal
    parents = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parent = next(line.split()[1] for line in (entry/'status').read_text().splitlines() if line.startswith('PPid:'))
            parents[int(entry.name)] = int(parent)
        except (OSError, StopIteration, ValueError):
            pass
    descendants = {process.pid}
    changed = True
    while changed:
        previous = len(descendants)
        descendants.update(pid for pid, parent in parents.items() if parent in descendants)
        changed = len(descendants) != previous
    groups = {process.pid}
    for pid in descendants:
        try:
            group = os.getpgid(pid)
            if group != os.getpgrp():
                groups.add(group)
        except ProcessLookupError:
            pass
    for group in groups:
        try: os.killpg(group, signal.SIGTERM)
        except ProcessLookupError: pass
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        pass
    # Descendants may have independent sessions and cannot be reaped by us;
    # signal every discovered group even if the direct parent already exited.
    for group in groups:
        try: os.killpg(group, signal.SIGKILL)
        except ProcessLookupError: pass
    process.wait()


def execute(command, job, timeout, environment=None, shutdown_timeout=30, resource_monitor=False):
    if timeout <= 0 or shutdown_timeout <= 0:
        raise ValueError('process deadlines must be positive')
    started = time.monotonic()
    samples = []
    peak_rss = None
    def sample(pid):
        nonlocal peak_rss
        if not resource_monitor:
            return
        try:
            values = Path(f'/proc/{pid}/status').read_text().splitlines()
            rss = next(int(line.split()[1])*1024 for line in values if line.startswith('VmHWM:'))
            peak_rss = max(peak_rss or 0, rss)
        except (OSError, StopIteration, ValueError):
            pass
        try:
            value = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                text=True, capture_output=True, timeout=3, check=True)
            samples.append([int(row.strip())*1024**2 for row in value.stdout.splitlines()])
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    terminal_since = None
    interrupted_error = None
    shutdown_expired = False
    with (job/'process.log').open('xb') as log, (job/'.running').open('a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        child_environment = dict(os.environ if environment is None else environment)
        inherited = []
        for value in child_environment.get('VIPER_RUNNING_LEASE_FDS', '').split(','):
            if not value.isdigit(): continue
            try:
                if os.readlink('/proc/self/fd/'+value).endswith('/.running'):
                    inherited.append(int(value))
            except OSError:
                pass
        leases = sorted(set([*inherited, lease.fileno()]))
        child_environment['VIPER_RUNNING_LEASE_FDS'] = ','.join(map(str, leases))
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                                   pass_fds=tuple(leases), cwd=Path(__file__).resolve().parents[1], env=child_environment)
        try:
            sample(process.pid)
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    code = process.wait(timeout=min(1., remaining, shutdown_timeout))
                    break
                except subprocess.TimeoutExpired:
                    sample(process.pid)
                    report_path = job/'run/report.json'
                    try:
                        report = read_json(report_path)
                    except (OSError, ValueError):
                        report = {}
                    if (report.get('completed') is True or report.get('error')) and report.get('source_changed_during_run') == []:
                        terminal_since = time.monotonic() if terminal_since is None else terminal_since
                    if terminal_since is not None and time.monotonic() - terminal_since >= shutdown_timeout:
                        shutdown_expired = True
                        raise subprocess.TimeoutExpired(command, shutdown_timeout)
            result = {'returncode': code, 'timed_out': False, 'shutdown_timeout': False}
        except BaseException as error:
            stop_process_tree(process)
            if not isinstance(error, subprocess.TimeoutExpired):
                interrupted_error = error
                result = {'returncode': process.returncode or 130, 'timed_out': False, 'shutdown_timeout': False,
                    'interrupted': type(error).__name__, 'error': str(error)}
            else:
                result = {'returncode': process.returncode, 'timed_out': True, 'shutdown_timeout': shutdown_expired}
    # An inherited lease outlives the direct parent when a descendant remains.
    # Never let a successful parent exit admit another GPU stage in that case.
    with (job/'.running').open('a') as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result['descendant_processes_live'] = False
        except BlockingIOError:
            result['descendant_processes_live'] = True
            if result['returncode'] == 0:
                result['returncode'] = 2
    result['wall_seconds'] = time.monotonic() - started
    if resource_monitor:
        result['resources'] = {'sampled_child_peak_rss_bytes': peak_rss,
            'sampled_device_peak_used_bytes': [max(row[i] for row in samples if len(row)>i) for i in range(max(map(len, samples), default=0))],
            'gpu_samples': len(samples), 'scope': 'sampled system-wide GPU usage, including unrelated processes; child RSS sampled from /proc; not a per-process CUDA allocator peak'}
    atomic_json(job/'process.json', result)
    if interrupted_error is not None:
        raise interrupted_error
    return result


def collect(root, robot, split, target, batch_size=10, max_jobs=30, timeout=3600,
            python=sys.executable, device='cuda:0', runner=execute, reserve_bytes=8 * 1024**3, attempt_limit=None):
    if robot not in DOF or split not in SPLITS:
        raise ValueError('invalid embodiment or split')
    if any(type(value) is not int or value <= 0 for value in (target, batch_size, max_jobs, timeout)):
        raise ValueError('collection counts and timeout must be positive integers')
    if type(reserve_bytes) is not int or reserve_bytes < 0:
        raise ValueError('storage reserve must be a nonnegative integer')
    if attempt_limit is not None and (type(attempt_limit) is not int or not target <= attempt_limit <= 100000):
        raise ValueError('attempt limit must cover the target and remain within the scenario schedule')
    root = Path(root).resolve()
    with locked(root):
        configuration = {'schema': 'relic.collection.v1', 'embodiment': robot, 'split': split,
                         'source_sha256': source_provenance()['source_sha256']}
        if attempt_limit is not None:
            configuration.update(attempt_limit=attempt_limit, target=target)
        config_path = root/'collection.json'
        if config_path.exists():
            if read_json(config_path) != configuration:
                raise ValueError('collection source, embodiment or split changed; use a new collection root')
        else:
            if (root/'jobs').exists():
                raise ValueError('existing jobs lack collection provenance')
            atomic_json(config_path, configuration)
        (root/'jobs').mkdir(exist_ok=True)
        verified_jobs = {}
        paths, failures, offset, jobs = progress(root, robot, split, verified_jobs)
        stalled = 0
        for _ in range(max_jobs):
            selected, _ = balanced_selection(paths, split, target)
            if len(selected) >= target or stalled >= 3 or (attempt_limit is not None and offset >= attempt_limit):
                break
            count = min(batch_size if jobs else 1, target - len(selected))
            if attempt_limit is not None:
                count = min(count, attempt_limit-offset)
            storage = storage_budget(root, count, jobs, reserve_bytes)
            atomic_json(root/'storage.json', storage)
            if not storage['sufficient']:
                summary = summarize(root, target, paths, failures, jobs)
                summary['stop_reason'] = 'insufficient_storage_reserve'
                atomic_json(root/'progress.json', summary)
                return summary
            cases = [asdict(case) for case in plan(split, count, offset)]
            sequence = max((int(path.name.split('-')[1]) for path in (root/'jobs').glob('job-*')), default=-1) + 1
            job = root/'jobs'/f'job-{sequence:06d}'
            job.mkdir(exist_ok=False)
            request = {'robot': robot, 'split': split, 'start': offset, 'count': count, 'cases': cases}
            atomic_json(job/'request.json', request)
            command = [str(python), '-m', 'embodiment.qualify', '--mode', 'collection',
                       '--robot', robot, '--split', split, '--episodes', str(count),
                       '--start-index', str(offset), '--output', str(job/'run'),
                       '--headless', '--enable_cameras', '--device', device]
            atomic_json(job/'command.json', command)
            before = len(paths)
            if runner is execute:
                runner(command, job, timeout, resource_monitor=True)
            else:
                runner(command, job, timeout)
            paths, failures, offset, jobs = progress(root, robot, split, verified_jobs)
            stalled = stalled + 1 if len(paths) == before else 0
            summarize(root, target, paths, failures, jobs)
        paths, failures, offset, jobs = progress(root, robot, split)
        return summarize(root, target, paths, failures, jobs)


def summarize(root, target, paths, failures, jobs):
    measurements = [read_json(job/'process.json') for job in jobs if (job/'process.json').exists()]
    seconds = sum(item['wall_seconds'] for item in measurements)
    complete_timing = len(measurements) == len(jobs) and bool(jobs)
    metadata = [read_json(path/'metadata.json') for path in paths]
    split = read_json(root/'collection.json')['split']
    selected, surplus = balanced_selection(paths, split, target)
    gpu_peaks = [item.get('resources', {}).get('sampled_device_peak_used_bytes', []) for item in measurements]
    summary = {'schema': 'relic.collection_progress.v1', 'target_successes': target,
               'successful_episodes': len(paths), 'failed_or_incomplete_attempts': len(failures),
               'balanced_successful_episodes': len(selected),
               'status': 'COMPLETE' if len(selected) >= target else 'INCOMPLETE',
               'attempted_scenes': len(paths)+len(failures),
               'accepted_demonstration_rate': len(selected)/(len(paths)+len(failures)) if paths or failures else None,
               'artifact_bytes': sum(path.stat().st_size for path in root.rglob('*') if path.is_file() and path.name not in ('progress.json', 'export.json')),
               'jobs': len(jobs), 'measured_process_seconds': seconds,
               'successful_colors': dict(Counter(item['target'] for item in metadata)),
               'successful_regions': dict(Counter(str(item['region']) for item in metadata)),
               'successful_episodes_per_hour': len(paths)*3600/seconds if complete_timing and seconds > 0 else None,
               'throughput_scope': 'simulator startup, physics, camera rendering and episode writing; export excluded',
               'resources': {'sampled_device_peak_used_bytes': [max(row[i] for row in gpu_peaks if len(row)>i) for i in range(max(map(len, gpu_peaks), default=0))],
                    'scope': 'sampled system-wide GPU usage during simulator jobs; not isolated to this collection'},
               'failure_categories': dict(Counter(item.get('category', 'legacy_unclassified') for item in failures)),
               'timing_complete': complete_timing, 'failures': failures,
               'episodes': [str(path.relative_to(root)) for path in paths],
               'balanced_episodes': [str(path.relative_to(root)) for path in selected],
               'surplus_episodes': [str(path.relative_to(root)) for path in surplus]}
    atomic_json(root/'progress.json', summary)
    print(json.dumps({key: value for key, value in summary.items()
                      if key not in ('failures', 'episodes', 'balanced_episodes', 'surplus_episodes')}, allow_nan=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--robot', choices=DOF, required=True)
    parser.add_argument('--split', choices=SPLITS, required=True)
    parser.add_argument('--target', type=int)
    parser.add_argument('--batch-size', type=int, default=10)
    parser.add_argument('--max-jobs', type=int, default=30)
    parser.add_argument('--attempt-limit', type=int)
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument('--reserve-gib', type=int, default=8)
    parser.add_argument('--export', type=Path)
    args = parser.parse_args()
    target = args.target if args.target is not None else {'train': 60, 'validation': 12, 'evaluation': 20}[args.split]
    summary = collect(args.root, args.robot, args.split, target, args.batch_size, args.max_jobs,
                      args.timeout, args.python, args.device, reserve_bytes=args.reserve_gib * 1024**3, attempt_limit=args.attempt_limit)
    if args.export and summary['status'] == 'COMPLETE':
        with locked(args.root):
            paths, _, _, _ = progress(args.root.resolve(), args.robot, args.split)
            paths, _ = balanced_selection(paths, args.split, target)
            if not paths:
                raise ValueError('no successful physical camera episodes to export')
            started = time.monotonic()
            if args.export.exists():
                from .dataset import validate_export
                validate_export(args.export)
                sources = [json.loads(line) for line in (args.export/'meta/relic_sources.jsonl').read_text().splitlines()]
                if [row['scenario_id'] for row in sources] != [read_json(path/'metadata.json')['scenario_id'] for path in paths]:
                    raise ValueError('existing export differs from the selected collection')
            else:
                export(paths, args.export)
            export_seconds = time.monotonic() - started
            total_seconds = summary['measured_process_seconds'] + export_seconds
            atomic_json(args.root/'export.json', {'output': str(args.export.resolve()),
                        'episodes': len(paths), 'export_wall_seconds': export_seconds,
                        'measured_process_and_export_seconds': total_seconds if summary['timing_complete'] else None,
                        'throughput_scope': 'simulator process and export; admission validation excluded',
                        'successful_episodes_per_hour': len(paths)*3600/total_seconds if summary['timing_complete'] else None})
    return 0 if summary['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    sys.exit(main())
