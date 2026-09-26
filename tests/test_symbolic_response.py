"""Parity and rejection controls for the closed illustrative response graph."""
from __future__ import annotations

import copy
import json
import math
import unittest

from cellsim_v2.nfkb_episode import DEFAULT_PARAMETERS, NfkbEpisode
from cellsim_v2.symbolic_response import (
    MAX_DEPTH, evaluate_response, nfkb_response_program,
    parse_response_json, response_digest, validate_response_program,
)


def response_inputs(previous: dict, current: dict, cell_id: str) -> dict:
    old = next(cell for cell in previous["cells"] if cell["cell_id"] == cell_id)
    new = next(cell for cell in current["cells"] if cell["cell_id"] == cell_id)
    return {
        "stimulus_concentration_mol_m3":
            current["field"]["synthetic_stimulus"]["concentration_mol_m3"],
        "payload_amount_mol": new["payload_amount_mol"],
        "previous_nuclear_proxy": old["nuclear_proxy"],
        "previous_feedback": old["feedback"],
        "previous_reporter_index": old["reporter_index"],
        "step_min": current["time_min"] - previous["time_min"],
        **{key: DEFAULT_PARAMETERS[key] for key in (
            "stimulus_half_response_mol_m3", "feedback_strength",
            "payload_half_effect_mol", "nuclear_relaxation_min",
            "feedback_relaxation_min", "reporter_relaxation_min")},
    }


class SymbolicResponseTests(unittest.TestCase):
    def test_parity_with_accepted_nfkb_episode_for_one_and_three_cells(self):
        program = nfkb_response_program()
        for count in (1, 3):
            episode = NfkbEpisode(cell_count=count, horizon_steps=4)
            ids = [cell["cell_id"] for cell in episode.observe()["cells"]]
            for interval in range(4):
                previous = episode.observe()
                if interval == 0:
                    action = episode.make_action(stimulus_code="T",
                                                 stimulus_admin_mol=0.125)
                elif interval == 1:
                    action = episode.make_action(
                        payload_admin_mol=0.02,
                        payload_uptake_rates_mol_min_by_cell={cid: 0.0001 for cid in ids})
                elif interval == 2:
                    action = episode.make_action(
                        payload_uptake_rates_mol_min_by_cell={cid: 0.0001 for cid in ids})
                else:
                    action = episode.make_action(
                        stimulus_code="I", stimulus_admin_mol=0.08,
                        stimulus_withdraw_mol=previous["field"]["synthetic_stimulus"]["amount_mol"],
                        payload_uptake_rates_mol_min_by_cell={cid: 0.0001 for cid in ids})
                current = episode.step(action)["observation"]
                for cell in current["cells"]:
                    prediction = evaluate_response(
                        program, response_inputs(previous, current, cell["cell_id"]))
                    for key in ("nuclear_proxy", "feedback", "reporter_index"):
                        self.assertAlmostEqual(prediction[key], cell[key], places=15)

    def test_canonical_roundtrip_is_deterministic_and_input_is_immutable(self):
        program = nfkb_response_program()
        before = copy.deepcopy(program)
        parsed = parse_response_json(json.dumps(program, sort_keys=True))
        self.assertEqual(response_digest(program), response_digest(parsed))
        self.assertEqual(program, before)
        self.assertEqual(len(program["nodes"]), 23)

    def test_rejects_unsupported_unknown_duplicate_forward_and_wrong_units(self):
        base = nfkb_response_program()
        variants = []
        x = copy.deepcopy(base); x["nodes"][0]["op"] = "python_eval"; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][1]["id"] = "stimulus"; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][2]["args"][0] = "missing"; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][2]["args"][0] = "nuclear_next"; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][2]["unit"] = "mol"; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][0]["source"] = "untrusted_python"; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][10]["source"] = "payload_amount_mol"; variants.append(x)
        x = copy.deepcopy(base); x["outputs"]["feedback"] = "payload"; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][7]["value"] = math.nan; variants.append(x)
        x = copy.deepcopy(base); x["nodes"][0]["extra"] = "hidden"; variants.append(x)
        for index, variant in enumerate(variants):
            with self.subTest(case=index), self.assertRaises(ValueError):
                validate_response_program(variant)
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            parse_response_json('{"schema_version":"x","schema_version":"x"}')

    def test_rejects_graph_depth_and_runtime_invalid_inputs(self):
        program = nfkb_response_program()
        long = copy.deepcopy(program)
        parent = "reporter_next"
        for index in range(MAX_DEPTH + 1):
            child = f"chain_{index}"
            long["nodes"].append({"id": child, "op": "add", "unit": "1",
                                  "args": [parent, "one"]})
            parent = child
        long["outputs"]["reporter_index"] = parent
        with self.assertRaisesRegex(ValueError, "depth"):
            validate_response_program(long)

        episode = NfkbEpisode(cell_count=1, horizon_steps=1)
        previous = episode.observe()
        current = episode.step(episode.make_action(stimulus_code="T",
                                                   stimulus_admin_mol=0.125))["observation"]
        inputs = response_inputs(previous, current, "cell_1")
        with self.assertRaisesRegex(ValueError, "exactly"):
            evaluate_response(program, {**inputs, "extra": 1.0})
        with self.assertRaisesRegex(ValueError, "positive"):
            evaluate_response(program, {**inputs, "step_min": 0.0})
        with self.assertRaisesRegex(ValueError, "finite"):
            evaluate_response(program, {**inputs, "payload_amount_mol": float("inf")})
        with self.assertRaisesRegex(ValueError, "finite"):
            evaluate_response(program, {**inputs, "feedback_strength": True})


if __name__ == "__main__":
    unittest.main()
