"""Synthetic NF-kB-inspired environment transaction regressions."""
from __future__ import annotations

import json
import unittest

from cellsim_v2.nfkb_episode import NfkbEpisode, NfkbRejected
from run_nfkb_demo import run


class NfkbEpisodeTests(unittest.TestCase):
    def test_one_to_five_cells_have_paired_environment_and_payload_transfers(self):
        for count in (1, 2, 3, 4, 5):
            with self.subTest(cell_count=count):
                episode = NfkbEpisode(cell_count=count, horizon_steps=4)
                before = episode.reset()
                ids = [cell["cell_id"] for cell in before["cells"]]
                self.assertEqual(len(set(ids)), count)
                self.assertEqual(len({tuple(cell["position_m"]) for cell in before["cells"]}), count)
                action = episode.make_action(
                    stimulus_code="T", stimulus_admin_mol=0.125,
                    payload_admin_mol=0.03,
                    payload_uptake_rates_mol_min_by_cell={cid: 0.0001 for cid in ids},
                )
                result = episode.step(action)
                after = result["observation"]
                self.assertEqual(after["time_min"], 6.0)
                self.assertEqual(after["stimulus_code"], "T")
                self.assertGreater(after["cells"][0]["nuclear_proxy"], 0)
                self.assertEqual(after["cells"][0]["reporter_index"], 0)
                self.assertLess(after["field"]["generic_inhibitor_payload"]["amount_mol"], 0.03)
                self.assertLess(result["info"]["maximum_amount_residual_mol"], 1e-12)
                self.assertEqual(result["info"]["ledger"]["stimulus"]["reservoir_debit_mol"], 0.125)
                credits = result["info"]["ledger"]["payload"]["cell_credits_mol_by_cell"]
                self.assertEqual(set(credits), set(ids))
                self.assertAlmostEqual(sum(credits.values()),
                                       0.03 - after["field"]["generic_inhibitor_payload"]["amount_mol"])

    def test_schedule_switch_and_delayed_response(self):
        episode = NfkbEpisode(cell_count=1, horizon_steps=22)
        first = episode.step(episode.make_action(stimulus_code="T", stimulus_admin_mol=0.125))
        self.assertEqual(first["observation"]["cells"][0]["reporter_index"], 0)
        second = episode.step(episode.make_action())
        self.assertGreater(second["observation"]["cells"][0]["reporter_index"], 0)
        for _ in range(18):
            episode.step(episode.make_action())
        self.assertEqual(episode.observe()["time_min"], 120.0)
        old_field = episode.observe()["field"]["synthetic_stimulus"]["amount_mol"]
        switched = episode.step(episode.make_action(
            stimulus_code="I", stimulus_withdraw_mol=old_field,
            stimulus_admin_mol=0.125,
        ))
        self.assertEqual(switched["info"]["interval_start_min"], 120.0)
        self.assertEqual(switched["observation"]["stimulus_code"], "I")
        self.assertAlmostEqual(switched["observation"]["field"]["synthetic_stimulus"]["amount_mol"], 0.125)
        self.assertAlmostEqual(switched["observation"]["waste_stimulus_amount_mol"], old_field)

    def test_overdraw_identity_and_stale_clock_reject_atomically(self):
        episode = NfkbEpisode(cell_count=5)
        before = episode.checkpoint()
        with self.assertRaisesRegex(NfkbRejected, "reservoir"):
            episode.step(episode.make_action(stimulus_code="T", stimulus_admin_mol=1.0))
        self.assertEqual(episode.checkpoint(), before)
        ids = [cell["cell_id"] for cell in episode.observe()["cells"]]
        with self.assertRaisesRegex(NfkbRejected, "demand"):
            episode.step(episode.make_action(
                payload_admin_mol=0.001,
                payload_uptake_rates_mol_min_by_cell={cid: 1.0 for cid in ids},
            ))
        self.assertEqual(episode.checkpoint(), before)
        action = episode.make_action(stimulus_code="T", stimulus_admin_mol=0.125)
        tampered = json.loads(json.dumps(action))
        tampered["payload_uptake_actions"][0]["model_id"] = "wrong"
        with self.assertRaisesRegex(NfkbRejected, "identity"):
            episode.step(tampered)
        self.assertEqual(episode.checkpoint(), before)
        episode.step(action)
        accepted = episode.checkpoint()
        with self.assertRaisesRegex(NfkbRejected, "clock"):
            episode.step(action)
        self.assertEqual(episode.checkpoint(), accepted)

    def test_json_replay_and_scenario_cli(self):
        episode = NfkbEpisode(cell_count=3, horizon_steps=4)
        episode.step(episode.make_action(stimulus_code="T", stimulus_admin_mol=0.125))
        resumed = NfkbEpisode.from_checkpoint(json.loads(json.dumps(episode.checkpoint())))
        for dose in (0.01, 0.0, 0.02):
            args = dict(payload_admin_mol=dose)
            self.assertEqual(episode.step(episode.make_action(**args)),
                             resumed.step(resumed.make_action(**args)))
            self.assertEqual(episode.checkpoint(), resumed.checkpoint())
        demo = run()
        self.assertEqual(demo["status"], "pass")
        self.assertTrue(demo["checkpoint_replay_equal"])
        self.assertTrue(demo["overdraw_rejection"]["accepted_state_unchanged"])
        self.assertEqual(set(demo["cell_count_cases"]), {"1", "3", "5"})
        self.assertEqual(demo["scenario_traces"]["stimulus_only"][20]["interval_start_min"], 120.0)

    def test_verified_sequence_helper_and_bounded_delivery_sweep(self):
        episode = NfkbEpisode(cell_count=2, horizon_steps=22)
        first = episode.make_scheduled_action(sequence_key="TIPL")
        self.assertEqual(first["stimulus_code"], "T")
        self.assertEqual(first["stimulus_admin_mol"], 0.125)
        self.assertEqual(first["stimulus_withdraw_mol"], 0.0)
        episode.step(first)
        for _ in range(19):
            action = episode.make_scheduled_action(sequence_key="TIPL")
            self.assertIsNone(action["stimulus_code"])
            episode.step(action)
        self.assertEqual(episode.observe()["time_min"], 120.0)
        next_action = episode.make_scheduled_action(
            sequence_key="TIPL", payload_admin_mol_at_start=0.02,
            payload_uptake_rates_mol_min_by_cell={"cell_1": 0.00002, "cell_2": 0.00002},
        )
        self.assertEqual(next_action["stimulus_code"], "I")
        self.assertEqual(next_action["stimulus_withdraw_mol"], 0.125)
        self.assertEqual(next_action["payload_admin_mol"], 0.02)
        episode.step(next_action)
        with self.assertRaisesRegex(NfkbRejected, "sequence"):
            episode.make_scheduled_action(sequence_key="TTTT")
        demo = run()
        sweep = demo["delivery_sweep"]
        self.assertEqual(len(sweep), 20)
        self.assertEqual({row["cell_count"] for row in sweep}, {1, 2, 3, 4, 5})
        self.assertEqual({row["payload_admin_mol"] for row in sweep}, {0.0, 0.01, 0.02, 0.03})
        self.assertTrue(all(row["status"] == "accepted" for row in sweep))
        self.assertTrue(all(row["maximum_amount_residual_mol"] < 1e-12 for row in sweep))


if __name__ == "__main__":
    unittest.main()
