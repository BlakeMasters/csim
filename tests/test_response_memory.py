"""Synthetic H02 continuous-memory contract and failure controls."""
from __future__ import annotations

import copy
import json
import math
import unittest

from cellsim_v2.response_memory import (
    advance_response,
    create_relaxation_model,
    initialize_response,
)


def model(**changes):
    values = dict(model_id="synthetic-relaxation-v1", context_id="synthetic-cell-context",
                  tau_s=2.0, target_intercept=0.0,
                  target_slope_m3_per_mol=1.0,
                  observation_offset=0.0, observation_scale=1.0)
    values.update(changes)
    return create_relaxation_model(**values)


def initial(mdl, memory=0.0):
    return initialize_response(
        mdl, entity_id="cell-1", initial_memory=memory, accepted_time_s=0.0,
        initialization_provenance={"kind": "declared_synthetic_initial_state",
                                   "source_id": "test-fixture-v1"},
    )


def step(mdl, state, concentration, end):
    return advance_response(mdl, state,
                            exposure_concentration_mol_m3=concentration,
                            end_time_s=end)


class ContinuousResponseMemoryTests(unittest.TestCase):
    def test_exact_relaxation_zero_interval_and_interval_splitting(self):
        mdl = model()
        start = initial(mdl, 0.25)
        original = copy.deepcopy(start)
        zero = step(mdl, start, 1.5, 0.0)
        self.assertEqual(zero["state"], start)
        self.assertEqual(start, original)
        whole = step(mdl, start, 1.5, 3.0)
        expected = 1.5 + (0.25 - 1.5) * math.exp(-3.0 / 2.0)
        self.assertAlmostEqual(whole["state"]["memory"], expected, places=14)
        self.assertEqual(whole["state"]["memory_unit"], "1")
        self.assertEqual(whole["observations"], [{"name": "synthetic_response_index",
                                                   "value": whole["state"]["memory"],
                                                   "unit": "1", "time_s": 3.0}])
        first = step(mdl, start, 1.5, 0.7)["state"]
        split = step(mdl, first, 1.5, 3.0)
        self.assertAlmostEqual(split["state"]["memory"], expected, places=14)

    def test_same_current_input_and_total_dose_distinguish_ordered_histories(self):
        mdl = model()
        a = step(mdl, initial(mdl), 2.0, 2.0)["state"]
        a = step(mdl, a, 0.0, 4.0)["state"]
        b = step(mdl, initial(mdl), 0.0, 2.0)["state"]
        b = step(mdl, b, 2.0, 4.0)["state"]
        # Both histories last four seconds and have total exposure 4 mol*s/m^3.
        # At the challenge interval both see the same current concentration.
        self.assertLess(a["memory"], b["memory"])
        a_next = step(mdl, a, 1.0, 5.0)
        b_next = step(mdl, b, 1.0, 5.0)
        self.assertLess(a_next["observations"][0]["value"],
                        b_next["observations"][0]["value"])

    def test_json_round_trip_replays_without_mutating_inputs(self):
        mdl = model()
        first = step(mdl, initial(mdl), 2.0, 1.3)["state"]
        saved = json.loads(json.dumps(first, allow_nan=False))
        model_copy = copy.deepcopy(mdl)
        state_copy = copy.deepcopy(first)
        continuous = step(mdl, first, 0.2, 3.1)
        resumed = step(json.loads(json.dumps(mdl)), saved, 0.2, 3.1)
        self.assertEqual(continuous, resumed)
        self.assertEqual(mdl, model_copy)
        self.assertEqual(first, state_copy)
        self.assertEqual(first["initialization"], continuous["state"]["initialization"])
        self.assertEqual(first["initial_time_s"], continuous["state"]["initial_time_s"])

    def test_invalid_initialization_state_identity_and_time_fail(self):
        mdl = model()
        with self.assertRaisesRegex(ValueError, "initialization"):
            initialize_response(mdl, entity_id="cell-1", initial_memory=0.0,
                                accepted_time_s=0.0, initialization_provenance=None)
        state = initial(mdl)
        for changed in (
            {**state, "initialization": {}},
            {**state, "memory_unit": "mol"},
            {**state, "context_id": "another-context"},
            {**state, "model_digest_sha256": "0" * 64},
            {**state, "initial_time_s": 2.0},
            {**state, "extra": "hidden"},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    step(mdl, changed, 1.0, 1.0)
        with self.assertRaisesRegex(ValueError, "model"):
            step(model(tau_s=3.0), state, 1.0, 1.0)
        with self.assertRaisesRegex(ValueError, "time"):
            step(mdl, step(mdl, state, 1.0, 1.0)["state"], 1.0, 0.5)

    def test_nonfinite_and_unsupported_numeric_inputs_fail(self):
        for bad in (0.0, -1.0, float("nan"), float("inf"), True):
            with self.subTest(tau_s=bad):
                with self.assertRaises(ValueError):
                    model(tau_s=bad)
        mdl = model()
        with self.assertRaises(ValueError):
            initial(mdl, float("nan"))
        for bad in (-1.0, float("nan"), float("inf"), True):
            with self.subTest(concentration=bad):
                with self.assertRaises(ValueError):
                    step(mdl, initial(mdl), bad, 1.0)
        with self.assertRaises(ValueError):
            step(mdl, initial(mdl), 1.0, float("inf"))
        with self.assertRaises(ValueError):
            step(model(target_slope_m3_per_mol=1e308), initial(model(target_slope_m3_per_mol=1e308)),
                 1e308, 1.0)


if __name__ == "__main__":
    unittest.main()
