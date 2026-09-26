"""Targeted regression for a review-discovered rule-state namespace collision."""
from pathlib import Path
import copy
import unittest

from cellsim_v2.biological_rules import evaluate_rules, load_ruleset
from cellsim_v2.state import AmountField, Cell, World
from cellsim_v2.transport import RectilinearGrid3D


ROOT = Path(__file__).resolve().parents[1]


class RuleStateRegressionTests(unittest.TestCase):
    def test_delimited_rule_ids_keep_independent_history(self):
        rules = load_ruleset(ROOT / "configs/biological_rules.synthetic.json")
        first = copy.deepcopy(rules["rules"][0])
        second = copy.deepcopy(first)
        first["id"], second["id"] = "a", "a:b"
        rules["rules"] = [first, second]
        grid = RectilinearGrid3D((1.0,), (1.0,), (1.0,))
        species = "synthetic_tracer"
        world = World(cells={"cell-a": Cell("cell-a", (0.5, 0.5, 0.5), 0.001)},
                      fields={species: AmountField.from_concentrations(species, (0.4,), grid.volumes_m3)})
        proposal = evaluate_rules(world, grid, rules, 0.1)
        self.assertEqual(sum(e.kind.startswith("rule_state:") for e in proposal.update.events), 2)
        self.assertEqual(world.events, [])
        proposal.update.commit(world, frozenset({"events"}))
        continued = evaluate_rules(world, grid, rules, 0.1)
        self.assertEqual([row["state"] for row in continued.trace], ["on", "on"])
        self.assertEqual(continued.update.events, ())

    def test_rule_edit_requires_a_new_context_after_acceptance(self):
        rules = load_ruleset(ROOT / "configs/biological_rules.synthetic.json")
        grid = RectilinearGrid3D((1.0,), (1.0,), (1.0,))
        species = "synthetic_tracer"
        world = World(cells={"cell-a": Cell("cell-a", (0.5, 0.5, 0.5), 0.001)},
                      fields={species: AmountField.from_concentrations(species, (0.9,), grid.volumes_m3)})
        proposal = evaluate_rules(world, grid, rules, 0.1)
        proposal.update.commit(world, frozenset({"cells", "fields", "events"}))
        modified = copy.deepcopy(rules)
        modified["context"]["scope"] += " Revised description."
        with self.assertRaisesRegex(ValueError, "ruleset identity"):
            evaluate_rules(world, grid, modified, 0.1)


if __name__ == "__main__":
    unittest.main()
