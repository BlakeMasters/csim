"""Regression checks for development-only curriculum and frozen evaluation."""
import math
import unittest
from unittest.mock import patch

from run_virtual_cell_self_play import (
    Schedule, _train_arm, choose_adaptive, development_schedules,
    evaluation_schedules, run,
)


class VirtualCellSelfPlayTests(unittest.TestCase):
    def test_complete_demo_has_equal_budgets_and_frozen_models(self):
        result = run()
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["rl_algorithm_run"])
        self.assertEqual(result["biological_qualification"], "unqualified")
        self.assertTrue(result["source_hashes_stable"])
        self.assertFalse(set(result["development_schedule_ids"])
                         & set(result["sealed_evaluation_schedule_ids"]))
        self.assertEqual(result["costs"]["attempted_development_episodes"], 18)
        self.assertEqual(result["costs"]["attempted_evaluation_episodes"], 9)
        self.assertEqual(result["costs"]["failed_development_episodes"], 0)
        self.assertEqual(result["costs"]["failed_evaluation_episodes"], 0)
        for arm in result["arms"].values():
            self.assertEqual(arm["accepted_episodes"], 6)
            self.assertEqual(arm["generated_development_steps"], 24)
            self.assertEqual(arm["evaluation"]["generated_evaluation_steps"], 12)
            self.assertTrue(arm["evaluation"]["weights_unchanged"])
            self.assertEqual(arm["frozen_weights_sha256"],
                             arm["evaluation"]["weights_sha256_after"])
            self.assertTrue(math.isfinite(arm["evaluation"]["one_step_mae_memory_1"]))
            for attempt in arm["attempts"]:
                for row in attempt["rows"]:
                    self.assertAlmostEqual(
                        row["cell_amount_after_mol"] - row["cell_amount_before_mol"],
                        row["integrated_transfer_mol"], places=14)
                    self.assertLessEqual(row["absolute_balance_error_mol"], 1e-12)

    def test_adaptive_choice_changes_with_development_feedback(self):
        prior = Schedule("prior", "other", 0.8, (0.0, 0.0, 0.0, 0.0))
        first = Schedule("first", "steady", 0.8, (0.01, 0.01, 0.01, 0.01))
        second = Schedule("second", "pulse", 0.8, (0.01, 0.01, 0.01, 0.01))
        remaining = (first, second)
        self.assertEqual(choose_adaptive(remaining, (prior,), {"steady": 0.2, "pulse": 0.0}), first)
        self.assertEqual(choose_adaptive(remaining, (prior,), {"steady": 0.0, "pulse": 0.2}), second)

    def test_failed_development_episode_is_retained_without_replacement(self):
        pool = development_schedules()
        original = __import__("run_virtual_cell_self_play")._run_teacher
        calls = 0

        def fail_first(schedule):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("injected teacher failure")
            return original(schedule)

        with patch("run_virtual_cell_self_play._run_teacher", side_effect=fail_first):
            arm = _train_arm("fixed_coverage", pool)
        self.assertEqual(arm["attempted_episodes"], 6)
        self.assertEqual(arm["failed_episodes"], 1)
        self.assertEqual(arm["accepted_episodes"], 5)
        self.assertEqual(arm["generated_development_steps"], 20)
        self.assertEqual(arm["attempts"][0]["status"], "failed")
        self.assertEqual(arm["attempts"][0]["error"], "injected teacher failure")
        self.assertGreater(arm["failed_attempt_wall_s"], 0)

    def test_schedule_splits_are_predeclared_and_disjoint(self):
        dev = development_schedules()
        sealed = evaluation_schedules()
        self.assertEqual(len(dev), 12)
        self.assertEqual(len(sealed), 3)
        self.assertFalse({item.id for item in dev} & {item.id for item in sealed})
        self.assertTrue(all(len(item.actions_vmax_mol_s) == 4 for item in (*dev, *sealed)))


if __name__ == "__main__":
    unittest.main()
