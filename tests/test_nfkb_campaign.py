"""Focused regressions for manifest-driven illustrative NF-kB campaigns."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from run_nfkb_campaign import run_campaign, validate_manifest  # noqa: E402


def manifest(*, amount: float = 0.02) -> dict:
    return {
        "format": "cellsim-nfkb-campaign/1",
        "campaign_id": "focused-test",
        "sequence_key": "TIPL",
        "cell_counts": [1, 3],
        "stimulus_admin_mol_per_switch": 0.125,
        "initial_stimulus_reservoir_mol": 0.5,
        "initial_payload_reservoir_mol": 0.1,
        "amount_balance_limit_mol": 1e-12,
        "protocols": [{
            "id": "payload-at-120", "payload_start_min": 120,
            "payload_amount_mol": amount,
            "uptake_rate_mol_min_per_cell": 0.00002,
        }],
        "replicates": [
            {"id": "fixed", "kind": "deterministic", "seed": None},
            {"id": "seed-7", "kind": "seeded", "seed": 7},
        ],
    }


class NfkbCampaignTests(unittest.TestCase):
    def test_manifest_rejects_bad_identity_and_schedule_before_execution(self):
        base = manifest()
        for key, replacement in (("sequence_key", "TTTT"),
                                 ("cell_counts", [1, 1]),
                                 ("cell_counts", [0, 6])):
            with self.subTest(key=key, replacement=replacement):
                bad = json.loads(json.dumps(base))
                bad[key] = replacement
                with self.assertRaises(ValueError):
                    validate_manifest(bad)
        bad = manifest()
        bad["replicates"].append({"id": "seed-7", "kind": "seeded", "seed": 7})
        with self.assertRaises(ValueError):
            validate_manifest(bad)

    def test_matched_matrix_metrics_ledgers_and_trace_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "manifest.json"
            source.write_text(json.dumps(manifest(), indent=2) + "\n", encoding="utf-8")
            result = run_campaign(source, root / "campaign")
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["manifest_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual((root / "campaign" / "manifest.json").read_bytes(), source.read_bytes())
            self.assertEqual(len(result["pairs"]), 4)
            self.assertEqual(result["costs"]["run_count"], 8)
            self.assertEqual(result["costs"]["accepted_steps"], 8 * 82)
            self.assertEqual(result["costs"]["failed_steps"], 0)
            self.assertEqual(result["failures"], [])
            for pair in result["pairs"]:
                self.assertTrue(pair["matched"])
                self.assertEqual(pair["baseline"]["seed"], pair["intervention"]["seed"])
                self.assertEqual(pair["baseline"]["accepted_steps"], 82)
                self.assertEqual(pair["intervention"]["accepted_steps"], 82)
                self.assertLessEqual(pair["baseline"]["maximum_amount_residual_mol"], 1e-12)
                self.assertLessEqual(pair["intervention"]["maximum_amount_residual_mol"], 1e-12)
                for arm in ("baseline", "intervention"):
                    run = pair[arm]
                    self.assertEqual(run["status"], "pass")
                    self.assertEqual(set(run["mean_metrics"]), {
                        "peak_reporter_index", "time_to_peak_min",
                        "auc_reporter_index_min"})
                    trace = json.loads((root / "campaign" / run["trace_path"]).read_text())
                    self.assertEqual(len(trace["samples"]), 83)
                    self.assertEqual(trace["samples"][0]["time_min"], 0)
                    self.assertEqual(trace["samples"][-1]["time_min"], 492)
                    self.assertEqual(trace["seed"], run["seed"])
                self.assertEqual(pair["baseline"]["trace_id"] != pair["intervention"]["trace_id"], True)
                baseline_trace = json.loads((root / "campaign" /
                                             pair["baseline"]["trace_path"]).read_text())
                intervention_trace = json.loads((root / "campaign" /
                                                 pair["intervention"]["trace_path"]).read_text())
                self.assertEqual(baseline_trace["samples"][:21],
                                 intervention_trace["samples"][:21])
                self.assertEqual(pair["baseline"]["mean_metrics"]["auc_reporter_index_min"]
                                 + pair["delta_mean_metrics"]["auc_reporter_index_min"],
                                 pair["intervention"]["mean_metrics"]["auc_reporter_index_min"])

    def test_failure_preserves_partial_trace_and_charges_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "manifest.json"
            one = manifest(amount=0.2)
            one["cell_counts"] = [1]
            one["replicates"] = [{"id": "fixed", "kind": "deterministic", "seed": None}]
            source.write_text(json.dumps(one) + "\n", encoding="utf-8")
            result = run_campaign(source, root / "campaign")
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["costs"]["run_count"], 2)
            self.assertEqual(result["costs"]["failed_run_count"], 1)
            self.assertEqual(result["costs"]["failed_steps"], 1)
            pair = result["pairs"][0]
            self.assertEqual(pair["baseline"]["status"], "pass")
            self.assertEqual(pair["intervention"]["status"], "fail")
            self.assertEqual(pair["intervention"]["accepted_steps"], 20)
            self.assertIn("reservoir", pair["intervention"]["failure"]["error"])
            trace = json.loads((root / "campaign" /
                                pair["intervention"]["trace_path"]).read_text())
            self.assertEqual(len(trace["samples"]), 21)
            self.assertEqual(trace["failure"]["step_index"], 20)
            self.assertIsNone(pair["delta_mean_metrics"])


if __name__ == "__main__":
    unittest.main()
