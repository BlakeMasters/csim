"""Synthetic cell-to-field secretion and non-consuming sensing controls."""
from __future__ import annotations

import json
import math
import unittest

from cellsim_v2.state import AmountField, Cell, World, total_amount
from cellsim_v2.transport import RectilinearGrid3D
from cellsim_v2.ligand_communication import (
    LigandCommunicationEpisode, LigandRejected, SecretionRate,
    secretion_step,
)


class LigandCommunicationTests(unittest.TestCase):
    def test_pure_finite_secretion_is_paired_amount_transfer(self):
        grid = RectilinearGrid3D((0.5,), (0.5,), (0.5,))
        species = "synthetic_ligand"
        world = World(
            cells={
                "sender": Cell("sender", grid.center_m(0), 1e-6, {species: 0.1}),
                "receiver": Cell("receiver", grid.center_m(0), 1e-6),
            },
            fields={species: AmountField(species, (0.0,), grid.volumes_m3)},
        )
        original = world.clone()
        proposal = secretion_step(world, grid, SecretionRate("sender", species, 0.04), 0.5)
        self.assertEqual(world, original)
        self.assertEqual(proposal.ledger, ())
        proposal.commit(world, frozenset({"cells", "fields"}))
        self.assertAlmostEqual(world.cells["sender"].amounts_mol[species], 0.08)
        self.assertEqual(world.cells["receiver"].amounts_mol.get(species, 0.0), 0.0)
        self.assertAlmostEqual(world.fields[species].amounts_mol[0], 0.02)
        self.assertEqual(total_amount(world, species), total_amount(original, species))

    def test_receiver_senses_pre_step_field_without_consuming_ligand(self):
        episode = LigandCommunicationEpisode()
        initial = episode.reset()
        self.assertEqual(initial["field_concentration_mol_m3"], 0.0)
        self.assertEqual(initial["receiver_memory"], 0.0)
        first = episode.step(episode.make_action(0.04))
        self.assertEqual(first["observation"]["receiver_memory"], 0.0)
        self.assertAlmostEqual(first["observation"]["field_concentration_mol_m3"], 0.16)
        self.assertAlmostEqual(first["observation"]["sender_amount_mol"], 0.08)
        second = episode.step(episode.make_action(0.0))
        expected = 0.16 * (1 - math.exp(-1.0))
        self.assertAlmostEqual(second["observation"]["receiver_memory"], expected)
        self.assertEqual(second["observation"]["receiver_amount_mol"], 0.0)
        self.assertEqual(second["info"]["integrated_transfer_mol"], 0.0)
        self.assertLess(second["info"]["absolute_balance_error_mol"], 1e-12)
        self.assertEqual(second["info"]["sense_sample_time_s"], 0.5)

    def test_overdraw_identity_and_stale_clock_reject_atomically(self):
        episode = LigandCommunicationEpisode()
        episode.reset()
        before = episode.checkpoint()
        with self.assertRaisesRegex(LigandRejected, "inventory"):
            episode.step(episode.make_action(1.0))
        self.assertEqual(episode.checkpoint(), before)
        bad = episode.make_action(0.04) | {"source_cell_id": "receiver"}
        with self.assertRaisesRegex(LigandRejected, "identity"):
            episode.step(bad)
        self.assertEqual(episode.checkpoint(), before)
        action = episode.make_action(0.04)
        episode.step(action)
        accepted = episode.checkpoint()
        with self.assertRaisesRegex(LigandRejected, "interval"):
            episode.step(action)
        self.assertEqual(episode.checkpoint(), accepted)

    def test_checkpoint_roundtrip_replays_world_private_state_and_clocks(self):
        episode = LigandCommunicationEpisode()
        episode.reset()
        episode.step(episode.make_action(0.04))
        saved = json.loads(json.dumps(episode.checkpoint(), allow_nan=False))
        replay = LigandCommunicationEpisode.from_checkpoint(saved)
        self.assertEqual(replay.checkpoint(), episode.checkpoint())
        for rate in (0.0, 0.02):
            self.assertEqual(episode.step(episode.make_action(rate)),
                             replay.step(replay.make_action(rate)))
            self.assertEqual(episode.checkpoint(), replay.checkpoint())
        self.assertTrue(episode.observe()["terminated"])
        with self.assertRaisesRegex(LigandRejected, "terminated"):
            episode.step({})


if __name__ == "__main__":
    unittest.main()
