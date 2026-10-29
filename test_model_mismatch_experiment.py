"""Tests for the controlled model-mismatch experiment."""

import unittest
from unittest.mock import patch

import model_mismatch_experiment as experiment
import simulator


class ModelMismatchTests(unittest.TestCase):
    def test_case_targets_and_controls(self):
        self.assertEqual(len(experiment.cases()), 16)
        for case in experiment.cases():
            guard = simulator.check_action_python(case.world, case.candidate)
            expected = experiment.MUTATIONS[case.mutation] if case.violated else None
            self.assertEqual(guard, expected, case.case_id)
            self.assertIsNone(experiment.checker(case.world, case.candidate, expected))

    def test_guard_remains_unmodified_during_mismatch(self):
        case = next(c for c in experiment.cases() if c.violated)
        mutated = lambda w, a: experiment.checker(w, a, experiment.MUTATIONS[case.mutation])
        with patch.object(simulator, "check_action", side_effect=mutated):
            accepted, reason, disturbance = experiment.execute_guarded(case.world, case.candidate)
        self.assertFalse(accepted)
        self.assertEqual(reason, experiment.MUTATIONS[case.mutation])
        self.assertFalse(disturbance)

    def test_matched_vs_mismatch_for_all_cases(self):
        for case in experiment.cases():
            baseline = experiment.run_case(case, False)
            mutated = experiment.run_case(case, True)
            self.assertTrue(baseline["success"], case.case_id)
            self.assertTrue(mutated["success"], case.case_id)
            self.assertEqual(baseline["guard_rejections"], 0, case.case_id)
            self.assertEqual(mutated["guard_rejections"], int(case.violated), case.case_id)
            self.assertEqual(mutated["original_action_retained_first"], True, case.case_id)
            self.assertEqual(baseline["original_action_retained_first"], not case.violated, case.case_id)


if __name__ == "__main__":
    unittest.main()
