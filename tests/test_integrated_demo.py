"""Integrated local demo preserves observed -> frozen fit -> episode dependencies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_integrated_demo


class IntegratedDemoTests(unittest.TestCase):
    def test_oss_only_route_emits_failed_receipt_when_cli_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "oss-run"
            receipt = run_integrated_demo.run_oss_only(
                output,
                oss=Path(temporary) / "missing-oss.exe",
                python=Path(temporary) / "missing-python.exe",
            )
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["error_type"], "FileNotFoundError")
            self.assertTrue((output / "receipt.json").is_file())
            saved = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "failed")

    def test_oss_only_route_identifies_missing_local_mat_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            oss = temporary / "oss.exe"
            python = temporary / "python.exe"
            oss.write_bytes(b"test")
            python.write_bytes(b"test")
            output = temporary / "oss-run"
            with patch.object(run_integrated_demo, "REQUIRED_LOCAL_MAT",
                              temporary / "missing-scmat.mat"):
                receipt = run_integrated_demo.run_oss_only(output, oss=oss, python=python)
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["error_type"], "FileNotFoundError")
            self.assertIn("required local MAT input missing", receipt["error"])
            self.assertTrue((output / "receipt.json").is_file())

    def test_fresh_observed_and_frozen_model_precede_nfkb_episode(self):
        called = []

        def fake_call(argv, *, timeout_s):
            script = Path(argv[1]).name
            called.append(script)
            target = Path(argv[argv.index("--output") + 1])
            if script == "uptake_splitting_study.py":
                target.parent.mkdir(parents=True)
                target.write_text('{"status":"pass"}', encoding="utf-8")
            else:
                target.mkdir(parents=True)
                filename = {
                    "prepare_nfkb_observed.py": "observed_traces.json",
                    "fit_nfkb_reporter.py": "receipt.json",
                    "report_nfkb_variability.py": "receipt.json",
                    "export_nfkb_metadata.py": "receipt.json",
                }.get(script, "results.json")
                (target / filename).write_text('{"status":"pass"}', encoding="utf-8")
                if script == "fit_nfkb_reporter.py":
                    (target / "frozen_candidate.json").write_text(
                        '{"schema_version":"test"}', encoding="utf-8")
                    (target / "comparison_overlay.json").write_text(
                        '{"status":"pass"}', encoding="utf-8")
                    def digest(path):
                        return hashlib.sha256(path.read_bytes()).hexdigest()
                    (target / "receipt.json").write_text(json.dumps({
                        "status": "pass",
                        "observed_artifact_sha256": digest(
                            target.parent / "nfkb_observed" / "observed_traces.json"),
                        "frozen_candidate_sha256": digest(target / "frozen_candidate.json"),
                        "comparison_overlay_sha256": digest(target / "comparison_overlay.json"),
                    }), encoding="utf-8")
                if script == "run_nfkb_demo.py":
                    self.assertEqual(Path(argv[argv.index("--observed-artifact") + 1]),
                                     target.parent / "nfkb_observed" / "observed_traces.json")
                    self.assertTrue((target.parent / "nfkb_fit" /
                                     "comparison_overlay.json").is_file())
                    (target / "results.json").write_text(json.dumps({
                        "status": "pass",
                        "observed_overlay": {"artifact_sha256": hashlib.sha256((
                            target.parent / "nfkb_observed" / "observed_traces.json"
                        ).read_bytes()).hexdigest()},
                    }), encoding="utf-8")
                if script == "report_nfkb_variability.py":
                    (target / "dispersion.json").write_text('{}', encoding="utf-8")
                    (target / "comparison_with_bands.json").write_text(
                        '{}', encoding="utf-8")
                    def digest(path):
                        return hashlib.sha256(path.read_bytes()).hexdigest()
                    (target / "receipt.json").write_text(json.dumps({
                        "status": "pass",
                        "model_overlay_sha256": digest(
                            target.parent / "nfkb_fit" / "comparison_overlay.json"),
                        "dispersion_sha256": digest(target / "dispersion.json"),
                        "combined_overlay_sha256": digest(
                            target / "comparison_with_bands.json"),
                    }), encoding="utf-8")
                if script == "export_nfkb_metadata.py":
                    (target / "metadata.json").write_text('{}', encoding="utf-8")
                    (target / "demo_overlay.json").write_text('{}', encoding="utf-8")
                    def digest(path):
                        return hashlib.sha256(path.read_bytes()).hexdigest()
                    (target / "receipt.json").write_text(json.dumps({
                        "status": "pass",
                        "input_overlay_sha256": digest(
                            target.parent / "nfkb_dispersion" / "comparison_with_bands.json"),
                        "metadata_sha256": digest(target / "metadata.json"),
                        "demo_overlay_sha256": digest(target / "demo_overlay.json"),
                    }), encoding="utf-8")
                if script == "run_seeded_nfkb_demo.py":
                    (target / "results.json").write_text(json.dumps({
                        "status": "pass",
                        "observed_schedule": {"artifact_sha256": hashlib.sha256((
                            target.parent / "nfkb_observed" / "observed_traces.json"
                        ).read_bytes()).hexdigest()},
                    }), encoding="utf-8")
            return {"argv": argv, "exit_code": 0, "stdout": "",
                    "stderr": "", "wall_s": 0.0, "timed_out": False}

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(run_integrated_demo, "_call", side_effect=fake_call), \
                    patch.object(run_integrated_demo, "source_fingerprint", return_value="stable"):
                result = run_integrated_demo.run_direct(Path(temporary) / "new-run")
        self.assertEqual(result["status"], "pass")
        self.assertLess(called.index("prepare_nfkb_observed.py"),
                        called.index("fit_nfkb_reporter.py"))
        self.assertLess(called.index("fit_nfkb_reporter.py"),
                        called.index("report_nfkb_variability.py"))
        self.assertLess(called.index("report_nfkb_variability.py"),
                        called.index("export_nfkb_metadata.py"))
        self.assertLess(called.index("export_nfkb_metadata.py"),
                        called.index("run_nfkb_demo.py"))
        self.assertLess(called.index("run_nfkb_demo.py"),
                        called.index("run_seeded_nfkb_demo.py"))
        self.assertIn("comparison_overlay_sha256", result["components"]["nfkb_fit"])
        self.assertIn("demo_overlay_sha256", result["components"]["nfkb_metadata"])
        self.assertEqual(result["components"]["nfkb_episode"]["demo_overlay_sha256"],
                         result["components"]["nfkb_metadata"]["demo_overlay_sha256"])
        self.assertIn("arena", result["components"])

    def test_failed_observed_artifact_blocks_fit_and_nfkb_episode(self):
        called = []

        def fake_call(argv, *, timeout_s):
            script = Path(argv[1]).name
            called.append(script)
            target = Path(argv[argv.index("--output") + 1])
            if script == "prepare_nfkb_observed.py":
                target.mkdir(parents=True)
                (target / "observed_traces.json").write_text('{"status":"fail"}',
                                                               encoding="utf-8")
            elif script == "uptake_splitting_study.py":
                target.parent.mkdir(parents=True)
                target.write_text('{"status":"pass"}', encoding="utf-8")
            else:
                target.mkdir(parents=True)
                (target / "results.json").write_text('{"status":"pass"}',
                                                      encoding="utf-8")
            return {"argv": argv, "exit_code": 0, "stdout": "",
                    "stderr": "", "wall_s": 0.0, "timed_out": False}

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(run_integrated_demo, "_call", side_effect=fake_call), \
                    patch.object(run_integrated_demo, "source_fingerprint", return_value="stable"):
                result = run_integrated_demo.run_direct(Path(temporary) / "new-run")
        self.assertEqual(result["status"], "fail")
        self.assertNotIn("fit_nfkb_reporter.py", called)
        self.assertNotIn("report_nfkb_variability.py", called)
        self.assertNotIn("export_nfkb_metadata.py", called)
        self.assertNotIn("run_nfkb_demo.py", called)
        self.assertNotIn("run_seeded_nfkb_demo.py", called)
        self.assertEqual(result["components"]["nfkb_fit"]["blocked_by"], "nfkb_observed")
        self.assertEqual(result["components"]["nfkb_dispersion"]["blocked_by"], "nfkb_fit")
        self.assertEqual(result["components"]["nfkb_metadata"]["blocked_by"], "nfkb_dispersion")
        self.assertEqual(result["components"]["nfkb_episode"]["blocked_by"], "nfkb_metadata")
        self.assertEqual(result["components"]["seeded_nfkb"]["blocked_by"], "nfkb_episode")


if __name__ == "__main__":
    unittest.main()
