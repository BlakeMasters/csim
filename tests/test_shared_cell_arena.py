"""Synthetic N-cell shared-voxel simultaneous uptake and replay checks."""
from __future__ import annotations

import json
import math
import unittest

from cellsim_v2.shared_cell_arena import ArenaRejected, SharedCellArena
from run_two_cell_arena import run


class SharedCellArenaTests(unittest.TestCase):
    def test_one_two_three_and_five_cell_paired_transfers_and_private_memory(self):
        for count in (1, 2, 3, 5):
            with self.subTest(cell_count=count):
                arena = SharedCellArena(cell_count=count)
                before = arena.reset()
                self.assertEqual(len(before["cells"]), count)
                positions = [tuple(cell["position_m"]) for cell in before["cells"]]
                self.assertEqual(len(set(positions)), count)
                self.assertEqual(len({cell["model_id"] for cell in before["cells"]}), count)
                rates = {cell["cell_id"]: 0.02 for cell in before["cells"]}
                first = arena.step(arena.make_actions(rates))
                after = first["observation"]
                self.assertEqual(len(after["cells"]), count)
                total_cell_credit = sum(cell["amount_mol"] for cell in after["cells"])
                self.assertAlmostEqual(before["field_amount_mol"] - after["field_amount_mol"],
                                       total_cell_credit)
                self.assertLess(first["info"]["absolute_balance_error_mol"], 1e-12)
                self.assertEqual(set(first["info"]["transfers_mol_by_cell"]), set(rates))
                ledger = first["info"]["closed_amount_ledger"]
                self.assertAlmostEqual(ledger["field_debit_mol"],
                                       sum(ledger["cell_credits_mol_by_cell"].values()))
                self.assertEqual(ledger["external_change_mol"], 0.0)
                self.assertTrue(all(cell["amount_mol"] > 0 for cell in after["cells"]))
                self.assertNotIn("target_response_index", after)

    def test_action_order_does_not_change_simultaneous_result(self):
        a = SharedCellArena(cell_count=3)
        b = SharedCellArena(cell_count=3)
        a.reset()
        b.reset()
        rates = {"cell_1": 0.01, "cell_2": 0.02, "cell_3": 0.03}
        actions = a.make_actions(rates)
        self.assertEqual(a.step(actions), b.step(tuple(reversed(actions))))
        self.assertEqual(a.checkpoint(), b.checkpoint())

    def test_collective_overdraw_and_missing_action_reject_without_mutation(self):
        arena = SharedCellArena(cell_count=5)
        before = arena.checkpoint()
        ids = [cell["cell_id"] for cell in arena.observe()["cells"]]
        with self.assertRaisesRegex(ArenaRejected, "demand"):
            arena.step(arena.make_actions({cell_id: 1.0 for cell_id in ids}))
        self.assertEqual(arena.checkpoint(), before)
        with self.assertRaisesRegex(ArenaRejected, "exactly one"):
            arena.step(arena.make_actions({cell_id: 0.01 for cell_id in ids})[:-1])
        self.assertEqual(arena.checkpoint(), before)
        valid = arena.make_actions({cell_id: 0.01 for cell_id in ids})
        arena.step(valid)
        accepted = arena.checkpoint()
        with self.assertRaisesRegex(ArenaRejected, "interval"):
            arena.step(valid)
        self.assertEqual(arena.checkpoint(), accepted)

    def test_json_checkpoint_replays_all_cells_field_memory_and_clocks(self):
        arena = SharedCellArena(cell_count=5, horizon_steps=4)
        ids = [cell["cell_id"] for cell in arena.reset()["cells"]]
        arena.step(arena.make_actions({cell_id: 0.01 for cell_id in ids}))
        saved = json.loads(json.dumps(arena.checkpoint(), allow_nan=False))
        replay = SharedCellArena.from_checkpoint(saved)
        self.assertEqual(replay.checkpoint(), arena.checkpoint())
        for rate in (0.02, 0.0, 0.01):
            proposed = {cell_id: rate for cell_id in ids}
            self.assertEqual(arena.step(arena.make_actions(proposed)),
                             replay.step(replay.make_actions(proposed)))
            self.assertEqual(replay.checkpoint(), arena.checkpoint())
        self.assertTrue(arena.observe()["terminated"])

    def test_bounded_comparison_preserves_count_cases_and_frozen_evaluation(self):
        result = run()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(set(result["count_cases"]), {"1", "2", "3", "5"})
        self.assertEqual(result["round_trace"], result["count_cases"]["2"]["round_trace"])
        self.assertEqual(len(result["round_trace"]), 6)
        self.assertFalse(set(result["development_condition_ids"])
                         & set(result["evaluation_condition_ids"]))
        self.assertTrue(result["checkpoint_replay_equal"])
        self.assertTrue(result["overdraw_rejection"]["accepted_state_unchanged"])
        for study in result["count_cases"].values():
            self.assertEqual(len(study["round_trace"]), 6)
            self.assertLess(study["maximum_balance_error_mol"], 1e-12)
        for arm in result["frozen_evaluation"].values():
            self.assertTrue(arm["policy_identity_unchanged"])
            self.assertTrue(math.isfinite(arm["mean_diagnostic_score"]))


if __name__ == "__main__":
    unittest.main()
