"""Synthetic M0 boundary tests; no model, GPU or real experimental results."""
from dataclasses import asdict
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from embodiment.collection import atomic_json
from embodiment.m0 import counterfactual_cases, verify
from embodiment.perception import condition
from embodiment.scenarios import plan


class M0Admission(unittest.TestCase):
    def test_counterfactuals_change_only_instruction_on_three_disjoint_validation_layouts(self):
        cases = counterfactual_cases()
        self.assertEqual(len(cases), 9)
        self.assertEqual(len({case.seed for case in cases}), 3)
        self.assertEqual(len({case.scenario_id for case in cases}), 9)
        self.assertFalse({case.seed for case in cases} & {case.seed for case in plan('evaluation', 50)})
        for seed in {case.seed for case in cases}:
            self.assertEqual({case.target for case in cases if case.seed == seed}, {'red', 'green', 'blue'})

    def evaluate(self, successes, flip=True):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'counterfactual').mkdir()
            report = {'condition': 'a', 'embodiment': 'openmanipulator_x', 'trials': [{}]*50,
                'policy_service': {'checkpoint_sha256': 'synthetic'}, 'observation_condition': condition()}
            atomic_json(root/'report.json', report)
            atomic_json(root/'counterfactual_plan.json', [asdict(case) for case in counterfactual_cases()])
            atomic_json(root/'counterfactual/report.json', {'completed': True,
                'cases': [asdict(case) for case in counterfactual_cases()], 'trials': [{}]*9})
            classes = ['vla_only_success']*successes+['policy_failure']*(50-successes)
            classes += ['vla_only_success']*8+['vla_only_success' if flip else 'policy_failure']
            with patch('embodiment.m0.verify_evidence'), patch('embodiment.m0.verify_trial', side_effect=classes), \
                 patch('embodiment.replay.load_episode', return_value=SimpleNamespace(telemetry=[{'cube_poses': {c: [0., 0., 0.] for c in ('red', 'green', 'blue')}}])):
                return verify(root)

    def test_completed_evaluation_does_not_imply_learning_and_instructions_are_required(self):
        self.assertEqual(self.evaluate(24)['status'], 'FAIL')
        self.assertEqual(self.evaluate(25)['status'], 'PASS')
        self.assertEqual(self.evaluate(50, False)['status'], 'FAIL')
        self.assertEqual(self.evaluate(14)['learning_band'], 'not_demonstrated')

    def test_summary_only_or_wrong_robot_cannot_claim_learning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            atomic_json(root/'report.json', {'condition': 'a', 'embodiment': 'franka_panda', 'trials': [{}]*50})
            with self.assertRaisesRegex(ValueError, 'source robot'): verify(root)


class FirstActionRejection(unittest.TestCase):
    def test_rejection_before_any_step_remains_failed_physical_evidence_not_a_demo(self):
        # Deliberately fabricated PhysX envelope, temporary files only.
        import numpy as np
        from embodiment.assets import ARM, FINGERS
        from embodiment.benchmark import Action, COLORS, CONTROL_DT, Observation, layout
        from dataclasses import replace
        from embodiment.dataset import load_episode
        from embodiment.evaluate import run_trial
        from embodiment.execution import ExecutionConfig
        from embodiment.safety import SafetyConfig
        from embodiment.replay import load_episode as replay
        from embodiment.scenarios import plan
        class Backend:
            embodiment = 'openmanipulator_x'
            evidence_source = 'isaac_lab_physx'
            arm_names, finger_names = ARM, FINGERS
            safety_config = SafetyConfig(((-3., 3.),)*4+((-.011, .02),)*2, 4)
            def __init__(self, mode): self.mode = mode
            def reset(self, seed):
                self.observation = Observation(0., (.17, 0., .085), (0.,)*4+(.004, .004), (0.,)*6,
                    {c: (*p, 1., 0., 0., 0.) for c, p in layout(seed).items()},
                    {c: 0. for c in COLORS}, contacts={c: False for c in COLORS},
                    contact_forces={c: (0., 0.) for c in COLORS}, gripper_open=1., ee_quaternion=(1., 0., 0., 0.))
                return self.observation
            def step(self, action):
                if self.mode == 'policy': raise AssertionError('rejected action cannot reach physics')
                self.observation = replace(self.observation, time=0. if self.mode == 'zero' else CONTROL_DT/2, unsafe=True, safety_events=('synthetic_stop',))
                return self.observation
            def frame(self): return np.zeros((480, 640, 3), dtype=np.uint8)
            def safe_stop(self): pass
        class Policy:
            metadata = {'checkpoint_sha256': 'synthetic-fixture-no-inference'}
            def __init__(self, mode): self.mode = mode
            def reset(self): pass
            def actions(self, observation):
                if self.mode == 'policy': raise ValueError('synthetic invalid chunk')
                return (Action((0., 0., 0.), 1.),)
        with tempfile.TemporaryDirectory() as temp:
            case = plan('evaluation', 1)[0]
            for mode in ('policy', 'zero', 'partial'):
                with self.subTest(mode=mode):
                    folder = Path(temp)/mode
                    provenance = {'source_sha256': {'fixture': 'synthetic'}, 'relic_commit': 'synthetic'}
                    result = run_trial(Backend(mode), Policy(mode), case, folder,
                        provenance, ExecutionConfig(fallback_enabled=False), lambda: True)
                    self.assertFalse(result['success'])
                    if mode == 'policy': self.assertEqual(result['policy_errors'], ['ValueError'])
                    self.assertEqual(len(load_episode(folder, expert_only=False).rows), 2 if mode == 'partial' else 1)
                    self.assertEqual(len(replay(folder).rows), 2 if mode == 'partial' else 1)
                    from embodiment.m0 import verify_trial
                    summary = verify_trial(folder, result, {**provenance, 'policy_service': Policy.metadata}, case)
                    self.assertEqual(summary, 'policy_failure' if mode == 'policy' else 'safety_rejection_or_stop')
                    with self.assertRaises(ValueError): load_episode(folder)
