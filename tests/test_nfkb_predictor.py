"""Frozen data-backed reporter prediction invariants."""
from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from cellsim_v2.nfkb_observed import feature_names
from cellsim_v2.nfkb_predictor import predict_frozen


ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "runs/nfkb_model_20260926_02/frozen_candidate.json"
OVERLAY = ROOT / "runs/nfkb_model_20260926_02/comparison_overlay.json"


def fixture() -> dict:
    weights = [0.0] * len(feature_names())
    weights[0] = 0.5
    weights[3] = 1.0  # fast:high:TNF-alpha
    return {
        "schema_version": "cellsim-nfkb-frozen-state-space/1",
        "source_matrix_sha256": "a" * 64,
        "observed_artifact_sha256": "b" * 64,
        "feature_names": list(feature_names()),
        "model": {"kind": "state_space", "tau_fast_min": 48.0,
                  "tau_slow_min": 90.0, "ridge": 0.001,
                  "weights": weights},
    }


class FrozenPredictorTests(unittest.TestCase):
    def test_predicts_eighty_three_causal_points_without_weight_change(self):
        frozen = fixture()
        before = json.dumps(frozen, sort_keys=True)
        result = predict_frozen(frozen, (0, 1, 2, 3), 1,
                                frozen_candidate_sha256="c" * 64)
        self.assertEqual(len(result["time_min"]), 83)
        self.assertEqual(len(result["predicted_reporter"]), 83)
        self.assertAlmostEqual(result["predicted_reporter"][0], 1.5)
        self.assertAlmostEqual(result["predicted_reporter"][1],
                               0.5 + math.exp(-6 / 48))
        self.assertEqual(result["frozen_candidate_sha256"], "c" * 64)
        self.assertEqual(result["nominal_stimulus_schedule"][0][
            "nominal_extracellular_ng_ml"], 90.0)
        self.assertEqual(before, json.dumps(frozen, sort_keys=True))

    def test_rejects_wrong_tier_and_modified_feature_contract(self):
        frozen = fixture()
        with self.assertRaises(ValueError):
            predict_frozen(frozen, (4, 5, 6, 7), 1,
                           frozen_candidate_sha256="c" * 64)
        frozen["feature_names"][3] = "mislabeled"
        with self.assertRaises(ValueError):
            predict_frozen(frozen, (0, 1, 2, 3), 1,
                           frozen_candidate_sha256="c" * 64)

    @unittest.skipUnless(FROZEN.is_file() and OVERLAY.is_file(),
                         "local frozen model evidence is not present")
    def test_reproduces_stored_condition_2_overlay(self):
        import hashlib
        raw = FROZEN.read_bytes()
        frozen = json.loads(raw)
        overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
        condition = next(item for item in overlay["conditions"]
                         if item["condition_id"] == 2)
        result = predict_frozen(
            frozen, tuple(condition["stimulus_codes"]),
            condition["dose_tier_code"],
            frozen_candidate_sha256=hashlib.sha256(raw).hexdigest())
        self.assertLess(max(abs(a - b) for a, b in zip(
            result["predicted_reporter"], condition["model_prediction"])),
            1e-12)


if __name__ == "__main__":
    unittest.main()
