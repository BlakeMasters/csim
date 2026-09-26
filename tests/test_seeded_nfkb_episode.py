"""Seeded per-cell response variation keeps physical transfers transactional."""
from __future__ import annotations

import json
import unittest

from cellsim_v2.seeded_nfkb_episode import SeededNfkbEpisode, SeededNfkbRejected
from run_seeded_nfkb_demo import run


class SeededNfkbTests(unittest.TestCase):
    def test_same_seed_json_checkpoint_replays_private_and_physical_state(self):
        episode = SeededNfkbEpisode(seed=17, cell_count=5, horizon_steps=22)
        episode.step(episode.make_scheduled_action(sequence_key="TIPL"))
        twin = SeededNfkbEpisode.from_checkpoint(json.loads(json.dumps(episode.checkpoint())))
        for _ in range(20):
            action = episode.make_scheduled_action(sequence_key="TIPL")
            self.assertEqual(action, twin.make_scheduled_action(sequence_key="TIPL"))
            self.assertEqual(episode.step(action), twin.step(action))
            self.assertEqual(episode.checkpoint(), twin.checkpoint())
        self.assertEqual(episode.observe()["time_min"], 126.0)
        self.assertEqual(episode.observe()["accepted_step"], 21)

    def test_different_seeds_change_responses_but_not_amount_ledger(self):
        first = SeededNfkbEpisode(seed=7, cell_count=3, horizon_steps=4)
        other = SeededNfkbEpisode(seed=29, cell_count=3, horizon_steps=4)
        first_variants = first.checkpoint()["payload"]["cell_parameters_by_id"]
        other_variants = other.checkpoint()["payload"]["cell_parameters_by_id"]
        self.assertNotEqual(first_variants, other_variants)
        for _ in range(3):
            a = first.step(first.make_scheduled_action(sequence_key="TIPL"))
            b = other.step(other.make_scheduled_action(sequence_key="TIPL"))
            self.assertEqual(a["info"]["maximum_amount_residual_mol"],
                             b["info"]["maximum_amount_residual_mol"])
            self.assertEqual(a["observation"]["field"], b["observation"]["field"])
            self.assertEqual([x["payload_amount_mol"] for x in a["observation"]["cells"]],
                             [x["payload_amount_mol"] for x in b["observation"]["cells"]])
        self.assertNotEqual([x["reporter_index"] for x in first.observe()["cells"]],
                            [x["reporter_index"] for x in other.observe()["cells"]])

    def test_rejection_preserves_seed_counter_and_accepted_state(self):
        episode = SeededNfkbEpisode(seed=7, cell_count=5)
        before = episode.checkpoint()
        with self.assertRaisesRegex(SeededNfkbRejected, "reservoir"):
            episode.step(episode.make_action(stimulus_code="T", stimulus_admin_mol=1.0))
        self.assertEqual(episode.checkpoint(), before)
        with self.assertRaisesRegex(SeededNfkbRejected, "identity"):
            forged = episode.make_action(stimulus_code="T", stimulus_admin_mol=0.125)
            forged["variability_profile_sha256"] = "wrong"
            episode.step(forged)
        self.assertEqual(episode.checkpoint(), before)

    def test_cli_replicates_show_seeded_distribution(self):
        result = run()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(set(result["cell_count_cases"]), {"1", "3", "5"})
        self.assertEqual(result["seeds"], [7, 17, 29, 43])
        self.assertTrue(result["all_replays_equal"])
        self.assertTrue(result["overdraw_rejection_unchanged"])
        self.assertTrue(all(case["terminal_reporter_span"] > 0
                            for case in result["cell_count_cases"].values()))


if __name__ == "__main__":
    unittest.main()
