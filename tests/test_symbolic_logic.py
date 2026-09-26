"""Closed synthetic symbolic IR roundtrip and rejection controls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from cellsim_v2.biological_rules import evaluate_rules, load_ruleset
from cellsim_v2.state import AmountField, Cell, World
from cellsim_v2.symbolic_logic import (
    canonical_digest, from_ruleset, parse_symbolic_json, to_ruleset,
    validate_symbolic,
)
from cellsim_v2.training import dataset_digest
from cellsim_v2.transport import RectilinearGrid3D


ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return load_ruleset(ROOT / "configs/biological_rules.synthetic.json")


class SymbolicLogicTests(unittest.TestCase):
    def test_roundtrip_preserves_ruleset_digest_trace_and_accepted_history(self):
        original = fixture()
        ir = from_ruleset(original)
        lowered = to_ruleset(ir)
        self.assertEqual(lowered, original)
        self.assertEqual(ir["ruleset_sha256"], dataset_digest(original))
        self.assertEqual([item["kind"] for item in ir["statements"]],
                         ["concentration_switch", "saturable_transfer"])
        transfer = ir["statements"][1]["effect"]
        self.assertEqual(transfer["kind"], "paired_integrated_amount_transfer")
        self.assertEqual(transfer["integrated_amount_unit"], "mol")
        self.assertEqual(transfer["rate_unit"], "mol/s")
        grid = RectilinearGrid3D((1.0,), (1.0,), (1.0,))
        world = World(cells={"cell-a": Cell("cell-a", (0.5, 0.5, 0.5), 0.001)},
                      fields={"synthetic_tracer": AmountField.from_concentrations(
                          "synthetic_tracer", (0.9,), grid.volumes_m3)})
        before = evaluate_rules(world, grid, original, 0.1)
        after = evaluate_rules(world, grid, lowered, 0.1)
        self.assertEqual(after, before)
        after.update.commit(world, frozenset({"cells", "fields", "events"}))
        continued = evaluate_rules(world, grid, lowered, 0.1)
        self.assertEqual(continued.ruleset_sha256, before.ruleset_sha256)
        self.assertEqual(continued.update.events, ())

    def test_canonical_json_parse_and_digest_are_order_insensitive(self):
        ir = from_ruleset(fixture())
        direct = canonical_digest(ir)
        compact = json.dumps(ir, separators=(",", ":"), allow_nan=False)
        sorted_pretty = json.dumps(ir, sort_keys=True, indent=2, allow_nan=False)
        self.assertEqual(parse_symbolic_json(compact), ir)
        self.assertEqual(canonical_digest(parse_symbolic_json(sorted_pretty)), direct)
        self.assertEqual(to_ruleset(parse_symbolic_json(compact)), fixture())

    def test_duplicate_json_keys_and_nonfinite_values_fail(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            parse_symbolic_json('{"schema_version":"0","schema_version":"0"}')
        with self.assertRaises(ValueError):
            parse_symbolic_json(json.dumps(from_ruleset(fixture())).replace(
                '"value": 0.5', '"value": NaN', 1))

    def test_undefined_identity_unit_effect_pairing_and_ownership_fail(self):
        base = from_ruleset(fixture())
        variants = []

        x = copy.deepcopy(base); x["symbols"]["cells"] = []; variants.append(x)
        x = copy.deepcopy(base); x["symbols"]["species"] = []; variants.append(x)
        x = copy.deepcopy(base); x["statements"][0]["input"]["compartment_id"] = "missing"; variants.append(x)
        x = copy.deepcopy(base); x["symbols"]["cells"].append(copy.deepcopy(x["symbols"]["cells"][0])); variants.append(x)
        x = copy.deepcopy(base); x["symbols"]["compartments"].append(
            {**x["symbols"]["compartments"][0], "id": "ambiguous-second-field"}); variants.append(x)
        x = copy.deepcopy(base); x["statements"][0]["input"]["unit"] = "mol"; variants.append(x)
        x = copy.deepcopy(base); x["statements"][1]["effect"]["kind"] = "secretion"; variants.append(x)
        x = copy.deepcopy(base); del x["statements"][1]["effect"]["destination_compartment_id"]; variants.append(x)
        x = copy.deepcopy(base); x["statements"][1]["effect"]["accounting"] = "source_only"; variants.append(x)
        x = copy.deepcopy(base); x["statements"][1]["parameters"]["vmax"]["value"] = None; variants.append(x)
        x = copy.deepcopy(base); x["statements"][1]["parameters"]["vmax"]["unit"] = "mol/m^3"; variants.append(x)
        x = copy.deepcopy(base); x["statements"][1]["gate"]["rule_id"] = "unknown"; variants.append(x)
        x = copy.deepcopy(base); x["ruleset_sha256"] = "0" * 64; variants.append(x)
        for index, variant in enumerate(variants):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    validate_symbolic(variant)

    def test_malformed_reference_type_is_rejected_as_validation_error(self):
        ir = from_ruleset(fixture())
        ir["statements"][0]["input"]["compartment_id"] = ["extracellular-field"]
        with self.assertRaises(ValueError):
            validate_symbolic(ir)

    def test_duplicate_transfer_ownership_and_unsupported_source_ruleset_fail(self):
        original = fixture()
        duplicate = copy.deepcopy(original["rules"][1])
        duplicate["id"] = "second_transfer"
        original["rules"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "multiple transfer rules"):
            from_ruleset(original)
        planning = fixture()
        planning["runnable"] = False
        with self.assertRaises(ValueError):
            from_ruleset(planning)
        unsupported = fixture()
        unsupported["rules"][0]["kind"] = "ligand_binding"
        with self.assertRaises(ValueError):
            from_ruleset(unsupported)


if __name__ == "__main__":
    unittest.main()
