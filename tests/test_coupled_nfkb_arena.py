"""Coupled synthetic mediator field regressions."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from cellsim_v2.checkpoint import encode_world  # noqa: E402
from cellsim_v2.coupled_nfkb_arena import (  # noqa: E402
    CoupledNfkbArena, CoupledRejected, MEDIATOR,
    mediator_clearance_update, mediator_secretion_update,
)
from run_coupled_nfkb_arena import run  # noqa: E402


class CoupledArenaTests(unittest.TestCase):
    def test_physical_processes_are_pure_updates_with_paired_amounts(self):
        arena = CoupledNfkbArena(cell_count=2)
        world = arena._mediator_world
        before = encode_world(world)
        proposed = mediator_secretion_update(world, {"cell_1": 0.00012,
                                                      "cell_2": 0.0})
        self.assertEqual(encode_world(world), before)
        candidate = world.clone()
        proposed.commit(candidate, frozenset({"cells", "fields"}))
        self.assertEqual(candidate.fields[MEDIATOR].amounts_mol[0], 0.00012)
        self.assertAlmostEqual(candidate.cells["cell_1"].amounts_mol[MEDIATOR],
                               0.01 - 0.00012)
        before_clearance = encode_world(candidate)
        clearance = mediator_clearance_update(candidate, 0.00002)
        self.assertEqual(encode_world(candidate), before_clearance)
        clearance.commit(candidate, frozenset({"fields", "ledger"}))
        self.assertAlmostEqual(candidate.fields[MEDIATOR].amounts_mol[0], 0.0001)
        self.assertEqual(candidate.ledger[-1].change_mol, -0.00002)

    def test_secretion_clearance_balance_and_next_interval_sensing(self):
        control = CoupledNfkbArena(cell_count=3)
        coupled = CoupledNfkbArena(cell_count=3)
        zeros = {f"cell_{i}": 0.0 for i in range(1, 4)}
        secreted = dict(zeros, cell_1=0.00002)
        first_control = control.step(control.make_scheduled_action(
            sequence_key="TIPL", secretion_rates_mol_min_by_cell=zeros,
            clearance_rate_min_inv=0.01))
        first_coupled = coupled.step(coupled.make_scheduled_action(
            sequence_key="TIPL", secretion_rates_mol_min_by_cell=secreted,
            clearance_rate_min_inv=0.01))
        self.assertEqual(first_coupled["observation"]["cells"][2]["nuclear_proxy"],
                         first_control["observation"]["cells"][2]["nuclear_proxy"])
        self.assertAlmostEqual(first_coupled["info"]["mediator_ledger"]["cell_1_secretion_debit_mol"],
                               0.00012)
        self.assertAlmostEqual(first_coupled["observation"]["field"]["generic_paracrine_mediator"]["amount_mol"],
                               0.00012)
        second_control = control.step(control.make_scheduled_action(
            sequence_key="TIPL", secretion_rates_mol_min_by_cell=zeros,
            clearance_rate_min_inv=0.01))
        second_coupled = coupled.step(coupled.make_scheduled_action(
            sequence_key="TIPL", secretion_rates_mol_min_by_cell=zeros,
            clearance_rate_min_inv=0.01))
        self.assertGreater(second_coupled["observation"]["cells"][2]["nuclear_proxy"],
                           second_control["observation"]["cells"][2]["nuclear_proxy"])
        self.assertGreater(second_coupled["observation"]["waste_mediator_amount_mol"], 0)
        self.assertLess(second_coupled["info"]["maximum_amount_residual_mol"], 1e-12)

    def test_mediator_and_core_rejections_leave_joint_state_unchanged(self):
        arena = CoupledNfkbArena(cell_count=3, seed=7)
        before = arena.checkpoint()
        rates = {"cell_1": 1.0, "cell_2": 0.0, "cell_3": 0.0}
        with self.assertRaisesRegex(CoupledRejected, "inventory"):
            arena.step(arena.make_scheduled_action(
                sequence_key="TIPL", secretion_rates_mol_min_by_cell=rates))
        self.assertEqual(arena.checkpoint(), before)
        with self.assertRaisesRegex(CoupledRejected, "reservoir"):
            action = arena.make_action(
                secretion_rates_mol_min_by_cell={cid: 0.0 for cid in rates},
                core_action=arena._core.make_action(stimulus_admin_mol=1.0))
            arena.step(action)
        self.assertEqual(arena.checkpoint(), before)
        accepted = arena.step(arena.make_scheduled_action(
            sequence_key="TIPL", secretion_rates_mol_min_by_cell={cid: 0.0 for cid in rates}))
        self.assertEqual(accepted["observation"]["time_min"], 6.0)

    def test_json_checkpoint_seeded_replay_and_cli(self):
        arena = CoupledNfkbArena(cell_count=3, seed=7, horizon_steps=4)
        rates = {"cell_1": 0.00002, "cell_2": 0.0, "cell_3": 0.0}
        arena.step(arena.make_scheduled_action(
            sequence_key="TIPL", secretion_rates_mol_min_by_cell=rates))
        twin = CoupledNfkbArena.from_checkpoint(json.loads(json.dumps(arena.checkpoint())))
        for _ in range(3):
            action = arena.make_scheduled_action(
                sequence_key="TIPL", secretion_rates_mol_min_by_cell=rates,
                clearance_rate_min_inv=0.01)
            twin_action = twin.make_scheduled_action(
                sequence_key="TIPL", secretion_rates_mol_min_by_cell=rates,
                clearance_rate_min_inv=0.01)
            self.assertEqual(action, twin_action)
            self.assertEqual(arena.step(action), twin.step(twin_action))
            self.assertEqual(arena.checkpoint(), twin.checkpoint())
        demo = run()
        self.assertEqual(demo["status"], "pass")
        self.assertEqual(demo["cases"]["coupled"]["accepted_steps"], 82)
        self.assertEqual(demo["cases"]["baseline"]["accepted_steps"], 82)
        self.assertTrue(demo["checkpoint_replay_equal"])
        self.assertTrue(demo["overdraw_rejection"]["unchanged"])


if __name__ == "__main__":
    unittest.main()
