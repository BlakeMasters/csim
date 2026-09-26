"""Static campaign review preserves matched metrics and escapes input data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from render_nfkb_campaign import render

ROOT = Path(__file__).resolve().parents[1]


def example() -> dict:
    return {
        "status": "pass", "manifest_sha256": "manifest-test-hash",
        "source_test_tool_sha256": "source-test-hash",
        "configuration": {"cell_counts": [1], "step_min": 6, "horizon_steps": 82,
                          "sequence_key": "TIPL", "stimulus_admin_mol_per_switch": 0.001,
                          "amount_balance_limit_mol": 1e-12,
                          "time_grid_min": list(range(0, 493, 6))},
        "pairs": [{"pair_id": "pair-1<script>alert(1)</script>", "cell_count": 1,
                   "sequence_key": "TILP", "protocol": {"id": "synthetic"}, "replicate_id": "r1",
                   "baseline": {"status": "pass", "mean_metrics": {
                       "peak_reporter_index": 0.4, "time_to_peak_min": 120,
                       "auc_reporter_index_min": 44.0},
                       "maximum_amount_residual_mol": 0.0},
                   "intervention": {"status": "pass", "mean_metrics": {
                       "peak_reporter_index": 0.7, "time_to_peak_min": 126,
                       "auc_reporter_index_min": 60.0},
                       "maximum_amount_residual_mol": 1e-17},
                   "delta_mean_metrics": {"peak_reporter_index": 0.3,
                                          "time_to_peak_min": 6,
                                          "auc_reporter_index_min": 16.0}, "matched": True}],
        "costs": {"run_count": 2, "accepted_steps": 164, "failed_steps": 0},
        "failures": [{"pair_id": "other", "reason": "declared failure"}],
        "limitations": ["Synthetic intervention, not an efficacy result."],
    }


class CampaignReviewTests(unittest.TestCase):
    def test_failed_pair_without_metrics_remains_reviewable(self):
        failed = example()
        failed["status"] = "fail"
        failed["pairs"][0]["intervention"].update(status="fail", mean_metrics=None,
                                                    accepted_steps=3)
        failed["pairs"][0]["delta_mean_metrics"] = None
        failed["pairs"][0]["matched"] = False
        page = render(failed, report_hash="failed-hash")
        self.assertIn("matched: False", page)
        self.assertIn("accepted steps — / 3", page)
        self.assertIn("declared failure", page)
        self.assertIn("Failed / incomplete", page)
        self.assertIn('<td class="num">1</td><td class="num">0</td><td class="num">1</td>', page)

    def test_render_preserves_three_matched_metrics_and_escapes_untrusted_text(self):
        page = render(example(), report_hash="input-hash", oss={
            "oss_atom_id": "atom-test", "oss_chokepoint_id": "chokepoint-test",
            "oss_verification_status": "ok"})
        self.assertIn("Peak reporter index", page)
        self.assertIn("Time to peak", page)
        self.assertIn("Reporter AUC", page)
        self.assertIn("0.4", page)
        self.assertIn("0.7", page)
        self.assertIn("0.3", page)
        self.assertIn("By protocol · synthetic descriptive summary", page)
        self.assertIn("TIPL · 82 × 6 min · cells 1", page)
        self.assertIn("<details><summary>Full numeric configuration</summary>", page)
        self.assertIn("protocol synthetic", page)
        self.assertIn("Runs<strong>2", page)
        self.assertIn("atom-test", page)
        self.assertIn("manifest-test-hash", page)
        self.assertIn("declared failure", page)
        self.assertIn("observed data", page)
        self.assertIn("synthetic", page)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_cli_creates_review_and_content_hash_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "results.json"
            source.write_text(json.dumps(example()), encoding="utf-8")
            (root / "oss_record.json").write_text(json.dumps({
                "oss_atom_id": "atom-test", "oss_chokepoint_id": "checkpoint-test",
                "verification": {"status": "ok", "logs_checked": 2, "problems": []}}),
                encoding="utf-8")
            output = root / "new-review"
            command = [sys.executable, str(ROOT / "tools/render_nfkb_campaign.py"),
                       "--input", str(source), "--output", str(output)]
            process = subprocess.run(command, cwd=ROOT, text=True,
                                     capture_output=True, check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["status"], "pass")
            self.assertEqual(receipt["pairs"], 1)
            self.assertEqual(receipt["failures"], 1)
            self.assertEqual(receipt["oss_atom_id"], "atom-test")
            self.assertEqual(receipt["oss_verification_status"], "ok")
            self.assertEqual(receipt["input_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(receipt["html_sha256"], hashlib.sha256(
                (output / "index.html").read_bytes()).hexdigest())
            repeat = subprocess.run(command, cwd=ROOT, text=True,
                                    capture_output=True, check=False)
            self.assertNotEqual(repeat.returncode, 0, "output must be create-only")

    def test_cli_rejects_oss_record_for_different_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "results.json"
            source.write_text(json.dumps(example()), encoding="utf-8")
            (root / "oss_record.json").write_text(json.dumps({
                "atom_id": "atom-unrelated", "results_sha256": "wrong-hash"}),
                encoding="utf-8")
            output = root / "new-review"
            process = subprocess.run(
                [sys.executable, str(ROOT / "tools/render_nfkb_campaign.py"),
                 "--input", str(source), "--output", str(output)],
                cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("does not match", process.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
