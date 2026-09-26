"""Executable, closed NF-kB action-protocol contract; no biology fit claim."""
from __future__ import annotations

import copy
import json
import unittest

from cellsim_v2.nfkb_episode import NfkbEpisode, NfkbRejected
from cellsim_v2.symbolic_workflow import (
    lower_action, parse_protocol_json, protocol_digest, protocol_from_episode,
    run_protocol, validate_protocol,
)


class SymbolicWorkflowTests(unittest.TestCase):
    def test_protocol_lowers_exact_direct_actions_and_replays(self):
        initial = NfkbEpisode(cell_count=3, horizon_steps=82, step_min=6.0)
        checkpoint = json.loads(json.dumps(initial.checkpoint()))
        rates = {f"cell_{i}": 0.00002 for i in range(1, 4)}
        program = protocol_from_episode(initial, sequence_key="TIPL",
                                        stimulus_amount_mol=0.1,
                                        payload_start_min=120.0,
                                        payload_amount_mol=0.02,
                                        rates_mol_min_by_cell=rates)
        loaded = parse_protocol_json(json.dumps(program, sort_keys=True))
        self.assertEqual(program, loaded)
        self.assertEqual(protocol_digest(program), protocol_digest(loaded))
        direct = NfkbEpisode.from_checkpoint(checkpoint)
        lowered = NfkbEpisode.from_checkpoint(checkpoint)
        for _ in range(82):
            direct_action = direct.make_scheduled_action(
                sequence_key="TIPL", stimulus_admin_mol_per_switch=0.1,
                payload_start_min=120.0, payload_admin_mol_at_start=0.02,
                payload_uptake_rates_mol_min_by_cell=rates)
            compiled_action = lower_action(loaded, lowered)
            self.assertEqual(compiled_action, direct_action)
            self.assertEqual(lowered.step(compiled_action), direct.step(direct_action))
        self.assertEqual(lowered.checkpoint(), direct.checkpoint())
        replay = run_protocol(loaded, NfkbEpisode.from_checkpoint(checkpoint))
        self.assertEqual(replay["final_checkpoint_sha256"], direct.checkpoint()["sha256"])
        self.assertEqual(len(replay["actions"]), 82)
        self.assertLessEqual(replay["maximum_amount_residual_mol"], 1e-12)

    def test_rejects_duplicate_keys_units_effects_and_unknown_constructs(self):
        episode = NfkbEpisode(horizon_steps=2)
        program = protocol_from_episode(episode)
        for key, replacement in (("quantity_type", "concentration_mol_m3"),
                                 ("effect", "unpaired_creation")):
            bad = copy.deepcopy(program)
            bad["stimulus_transfer"][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_protocol(bad)
        bad = copy.deepcopy(program)
        bad["reaction_graph"] = {"eval": "arbitrary"}
        with self.assertRaisesRegex(ValueError, "fields"):
            validate_protocol(bad)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_protocol_json('{"schema":"x","schema":"y"}')

    def test_rejects_off_grid_identity_and_checkpoint_mismatch(self):
        episode = NfkbEpisode(cell_count=2, horizon_steps=3)
        program = protocol_from_episode(episode)
        bad = copy.deepcopy(program)
        bad["payload_transfer"]["start_min"] = 121.0
        bad["payload_uptake"]["start_min"] = 121.0
        with self.assertRaisesRegex(ValueError, "align"):
            validate_protocol(bad)
        bad = copy.deepcopy(program)
        bad["payload_uptake"]["rates_mol_min_by_cell"][1]["cell_id"] = "cell_9"
        with self.assertRaisesRegex(ValueError, "cell"):
            validate_protocol(bad)
        bad = copy.deepcopy(program)
        bad["initial_checkpoint_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            run_protocol(bad, episode)
        self.assertEqual(episode.observe()["time_min"], 0.0)

    def test_reservoir_overdraw_rejects_without_state_change(self):
        episode = NfkbEpisode(cell_count=1, horizon_steps=2)
        program = protocol_from_episode(episode, stimulus_amount_mol=1.0)
        checkpoint = episode.checkpoint()
        with self.assertRaises(NfkbRejected):
            episode.step(lower_action(program, episode))
        self.assertEqual(episode.checkpoint(), checkpoint)


if __name__ == "__main__":
    unittest.main()
