import unittest
from embodiment.paired import bootstrap, category


def rows(values):
    return [dict(scenario_id=f'synthetic-fixture-{index}', success=value, controller='vla_only',
                 evidence_source='unit_fixture', fallback_triggers=[]) for index, value in enumerate(values)]


class Paired(unittest.TestCase):
    def test_known_outcomes_and_reordering(self):
        left, right = rows([False]*50), rows([True]*50)
        result = bootstrap(left, right)
        self.assertEqual(result['difference'], 1.)
        self.assertEqual(result['paired_bootstrap_95'], [1., 1.])
        self.assertEqual(result['wins'], 50)
        self.assertEqual(result, bootstrap(left[::-1], right))
        negative = bootstrap(right, left)
        self.assertEqual(negative['paired_bootstrap_95'], [-1., -1.])

    def test_null_and_discordance(self):
        result = bootstrap(rows([True, False]*25), rows([False, True]*25))
        self.assertEqual((result['wins'], result['losses'], result['ties']), (25, 25, 0))
        self.assertLess(result['paired_bootstrap_95'][0], 0)
        self.assertGreater(result['paired_bootstrap_95'][1], 0)
        self.assertEqual(bootstrap(rows([True]*3), rows([True]*3))['paired_bootstrap_95'], [0., 0.])

    def test_missing_duplicates_and_interventions(self):
        with self.assertRaises(ValueError): bootstrap(rows([True]), rows([]))
        with self.assertRaises(ValueError): bootstrap(rows([True])*2, rows([True]))
        row = rows([True])[0]
        self.assertEqual(category({**row, 'rejected_policy_actions': ['workspace']}), 'safety_rejection_or_stop')
        self.assertEqual(category({**row, 'controller': 'fallback_assisted', 'fallback_triggers': ['stall']}), 'fallback_assisted_completion')
        self.assertEqual(category({**row, 'success': False, 'infrastructure_error': 'process died'}), 'infrastructure_failure')
        with self.assertRaises(ValueError): category({**row, 'policy_errors': ['TimeoutError']})


class PhysicalEvidenceGate(unittest.TestCase):
    def test_raw_episode_identity_must_match_report(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from embodiment.tests.test_benchmark_report import fixture
        from embodiment.paired import verify_evidence
        run = fixture()
        run['condition'] = 'b_only'
        run['policy_service'] = {'checkpoint_sha256': 'fixture'}
        for trial in run['trials']:
            trial.update(controller='vla_only', robot='franka_panda',
                         evidence_sha256={'fixture': 'hash'}, fallback_protocol_sha256='fixture')
        def episode(folder):
            trial = next(t for t in run['trials'] if str(folder).endswith(str(t['seed'])))
            metadata = {key: run[key] for key in ('embodiment', 'scene_revision', 'runtime_pin', 'source_sha256', 'policy_service')}
            metadata.update({key: trial[key] for key in ('scenario_id', 'seed', 'target')})
            return SimpleNamespace(metadata=metadata, outcome={k: v for k, v in trial.items() if k != 'evidence_sha256'}, rows=[])
        with patch('embodiment.collection.hashes', return_value={'fixture': 'hash'}), \
             patch('embodiment.perception.verify_trace'):
            with patch('embodiment.replay.load_episode', side_effect=episode):
                self.assertTrue(verify_evidence('/synthetic', run))
            for key, value in (('embodiment', 'openmanipulator_x'), ('runtime_pin', {'wrong': True}),
                               ('scene_revision', 'wrong'), ('scenario_id', 'wrong'),
                               ('policy_service', {'checkpoint_sha256': 'fixture', 'wrong': True})):
                def altered(folder):
                    recorded = episode(folder)
                    recorded.metadata[key] = value
                    return recorded
                with self.subTest(key=key), patch('embodiment.replay.load_episode', side_effect=altered):
                    with self.assertRaises(ValueError): verify_evidence('/synthetic', run)
            run['trials'][0]['fallback_protocol_sha256'] = 'wrong'
            with patch('embodiment.replay.load_episode', side_effect=episode), self.assertRaises(ValueError):
                verify_evidence('/synthetic', run)

    def test_report_without_raw_trial_hashes_cannot_be_published(self):
        from embodiment.tests.test_benchmark_report import fixture
        from embodiment.paired import verify_evidence
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'missing or corrupted'):
                verify_evidence(Path(temporary), fixture())
