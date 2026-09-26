"""Synthetic one-cell memory/amount transaction and replay controls."""
from __future__ import annotations

import json
import hashlib
import math
import unittest

from cellsim_v2.checkpoint import canonical_bytes
from cellsim_v2.synthetic_cell_episode import (
    EpisodeRejected, SyntheticCellEpisode, make_synthetic_episode,
)


class SyntheticCellEpisodeTests(unittest.TestCase):
    def test_causal_observation_and_joint_physical_memory_acceptance(self):
        episode = make_synthetic_episode(horizon_steps=3, step_s=0.25,
                                         target_response_index=0.5)
        before = episode.reset()
        self.assertEqual(before["time_s"], 0.0)
        self.assertEqual(before["next_time_s"], 0.25)
        self.assertEqual(before["local_concentration_mol_m3"], 1.0)
        self.assertNotIn("target_response_index", before)
        self.assertNotIn("model", before)
        self.assertNotIn("tau_s", before)
        action = episode.make_action(0.1)
        first = episode.step(action)
        after = first["observation"]
        self.assertEqual(first["terminated"], False)
        self.assertEqual(first["truncated"], False)
        self.assertEqual(after["time_s"], 0.25)
        self.assertAlmostEqual(after["accepted_memory"], 1 - math.exp(-0.5), places=14)
        self.assertAlmostEqual(after["cell_amount_mol"], 0.1 * (1 / 1.5) * 0.25)
        self.assertAlmostEqual(after["local_concentration_mol_m3"],
                               1 - after["cell_amount_mol"] / 0.125)
        self.assertEqual(first["info"]["exposure_sample_time_s"], 0.0)
        self.assertEqual(first["info"]["memory_interval_end_s"], 0.25)
        self.assertEqual(first["info"]["transfer_interval_end_s"], 0.25)
        self.assertEqual(first["info"]["absolute_balance_error_mol"], 0.0)
        self.assertEqual(first["diagnostic_score"],
                         -abs(after["accepted_memory"] - 0.5))

        # The first memory update sees the same pre-step exposure for both actions.
        control = make_synthetic_episode(horizon_steps=3, step_s=0.25)
        control.reset()
        control_first = control.step(control.make_action(0.0))
        self.assertEqual(control_first["observation"]["accepted_memory"],
                         after["accepted_memory"])
        second = episode.step(episode.make_action(0.1))
        control_second = control.step(control.make_action(0.0))
        self.assertLess(second["observation"]["accepted_memory"],
                        control_second["observation"]["accepted_memory"])

    def test_overdraw_and_identity_rejection_leave_all_accepted_state_unchanged(self):
        episode = make_synthetic_episode()
        episode.reset()
        before = episode.checkpoint()
        with self.assertRaisesRegex(EpisodeRejected, "demand"):
            episode.step(episode.make_action(100.0))
        self.assertEqual(episode.checkpoint(), before)
        bad = episode.make_action(0.1) | {"context_id": "wrong-context"}
        with self.assertRaisesRegex(EpisodeRejected, "identity"):
            episode.step(bad)
        self.assertEqual(episode.checkpoint(), before)
        valid = episode.make_action(0.1)
        episode.step(valid)
        after = episode.checkpoint()
        with self.assertRaisesRegex(EpisodeRejected, "interval"):
            episode.step(valid)
        self.assertEqual(episode.checkpoint(), after)

    def test_json_checkpoint_restores_complete_deterministic_continuation(self):
        episode = make_synthetic_episode(initial_concentration_mol_m3=1.2,
                                         initial_memory=0.15, horizon_steps=3,
                                         step_s=0.25, target_response_index=0.55)
        episode.reset()
        episode.step(episode.make_action(0.1))
        saved = json.loads(json.dumps(episode.checkpoint(), allow_nan=False))
        resumed = SyntheticCellEpisode.from_checkpoint(saved)
        self.assertEqual(resumed.checkpoint(), episode.checkpoint())
        self.assertEqual(resumed.observe(), episode.observe())
        for rate in (0.05, 0.0):
            self.assertEqual(episode.step(episode.make_action(rate)),
                             resumed.step(resumed.make_action(rate)))
            self.assertEqual(episode.checkpoint(), resumed.checkpoint())
        self.assertTrue(episode.observe()["terminated"])
        with self.assertRaisesRegex(EpisodeRejected, "terminated"):
            episode.step({})
        self.assertEqual(episode.reset()["time_s"], 0.0)

    def test_checkpoint_rejects_unsupported_cell_material_even_with_new_checksum(self):
        episode = make_synthetic_episode()
        saved = episode.checkpoint()
        saved["payload"]["world"]["cells"]["cell-1"]["amounts_mol"]["other"] = 1.0
        saved["sha256"] = hashlib.sha256(canonical_bytes(saved["payload"])).hexdigest()
        with self.assertRaisesRegex(ValueError, "physical state"):
            SyntheticCellEpisode.from_checkpoint(saved)


if __name__ == "__main__":
    unittest.main()
