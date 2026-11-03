"""M0 admission: 25/50 frozen VLA-only source successes plus instruction flips.

Three frozen validation layouts are each reset for red, green and blue instructions.
All nine unassisted tasks must succeed for the conservative instruction diagnostic.
These diagnostics are separate from the fifty held-out trials and never enter its
success denominator. A completed failing evaluation is retained, never retried by
this workflow. Development after a failed M0 requires a newly predeclared protocol.
"""
from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path
from .benchmark import COLORS, CONTROL_DT, layout
from .collection import hashes
from .dataset import load_episode, read_json
from .paired import category, verify_evidence
from .scenarios import Scenario, identity, plan, region


def counterfactual_cases():
    return [Scenario(case.seed, color, region(layout(case.seed)[color]), 'validation', identity(case.seed, color))
            for case in plan('validation', 3) for color in COLORS]


def verify_trial(folder, trial, report, case):
    if (any(trial.get(k) != v for k, v in asdict(case).items()) or trial.get('evidence_sha256') != hashes(folder)):
        raise ValueError('M0 trial identity or raw integrity differs')
    episode = load_episode(folder, expert_only=False)
    if (episode.outcome != {k: v for k, v in trial.items() if k != 'evidence_sha256'} or
            episode.metadata.get('source_sha256') != report['source_sha256'] or
            episode.metadata.get('policy_service') != report['policy_service'] or
            episode.metadata.get('sensor_contract') != 'viper.physical_sensors.v1'):
        raise ValueError('M0 raw checkpoint/sensor/source evidence differs')
    if episode.shape != (480, 640, 3):
        raise ValueError('M0 camera differs from frozen RGB resolution')
    from .perception import verify_trace
    verify_trace(folder/'perception.jsonl', episode.metadata, episode.rows)
    traces = [json.loads(line) for line in (folder/'execution.jsonl').read_text().splitlines()]
    applied = [row for row in traces if row.get('applied_action') is not None]
    if len(applied) != len(episode.rows)-1:
        raise ValueError('M0 execution trace lacks a commanded tick')
    for index, (trace, row, following) in enumerate(zip(applied, episode.rows, episode.rows[1:], strict=False)):
        interval = following['timestamp']-row['timestamp']
        cadence = math.isclose(interval, CONTROL_DT, abs_tol=1e-8)
        partial_stop = (index == len(applied)-1 and not trial['success'] and trial.get('failure_reason') == 'unsafe_movement'
                        and trial.get('safety_events') and 0 < interval <= CONTROL_DT)
        if (trace.get('timestamp') != row['timestamp'] or trace['applied_action'] != row['action'] or
                trace.get('safety_validated_action') != row['action'] or trace.get('controller') != 'vla_only' or
                trace.get('requested_action') != row['action'] or
                trace.get('response_timestamp') != following['timestamp'] or not (cadence or partial_stop) or
                trace.get('observed_next_ee') != following['ee_position']):
            raise ValueError('M0 requested/validated/applied action evidence differs')
    if any(trace.get('applied_action') is None and not trace.get('intervention') for trace in traces):
        raise ValueError('M0 rejected action lacks an intervention reason')
    return category(trial)


def verify(root):
    root = Path(root)
    report = read_json(root/'report.json')
    if (report.get('condition') != 'a' or report.get('embodiment') != 'openmanipulator_x' or
            len(report.get('trials', [])) != 50):
        raise ValueError('M0 requires the source robot and all fifty frozen held-out scenes')
    from .perception import condition
    if report.get('observation_condition') != condition():
        raise ValueError('M0 requires baseline policy observations')
    if read_json(root/'counterfactual_plan.json') != [asdict(case) for case in counterfactual_cases()]:
        raise ValueError('M0 counterfactual declaration differs')
    verify_evidence(root, report)
    classes = []
    for case, trial in zip(plan('evaluation', 50), report['trials'], strict=True):
        classes.append(verify_trial(root/f'trial_{case.seed}', trial, report, case))
    flips = read_json(root/'counterfactual/report.json')
    if flips.get('completed') is not True or flips.get('cases') != [asdict(case) for case in counterfactual_cases()]:
        raise ValueError('complete frozen counterfactual protocol required')
    if len(flips.get('trials', [])) != 9:
        raise ValueError('all nine instruction trials required')
    flip_classes = []
    for case, trial in zip(counterfactual_cases(), flips['trials'], strict=True):
        flip_classes.append(verify_trial(root/f'counterfactual/{case.seed}/{case.target}', trial, report, case))
    # Same seed must truly start with the same measured scene, not just an ID.
    from .replay import load_episode as replay
    for case in plan('validation', 3):
        starts = [replay(root/f'counterfactual/{case.seed}/{color}').telemetry[0]['cube_poses'] for color in COLORS]
        for start in starts[1:]:
            if any(math.dist(starts[0][color][:3], start[color][:3]) > .001 for color in COLORS):
                raise ValueError('counterfactual resets changed the physical scene')
    successes = classes.count('vla_only_success')
    instruction_pass = all(value == 'vla_only_success' for value in flip_classes)
    return {'schema': 'viper.m0.v1', 'status': 'PASS' if successes >= 25 and instruction_pass else 'FAIL',
        'evaluation_completed': True, 'heldout_trials': 50, 'vla_only_successes': successes,
        'learning_band': 'demonstrated' if successes >= 25 and instruction_pass else 'instruction_grounding_failed' if successes >= 25 else 'partial' if successes >= 15 else 'not_demonstrated',
        'counterfactual_pass': instruction_pass, 'counterfactual_categories': dict(Counter(flip_classes)),
        'categories': dict(Counter(classes)), 'simulation_executed': True,
        'checkpoint_sha256': report['policy_service']['checkpoint_sha256'],
        'claim': 'source-policy learning gate only; no cross-embodiment transfer claim'}
