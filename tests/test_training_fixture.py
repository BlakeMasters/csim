"""End-to-end checks for synthetic data preparation, without biological claims."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from prepare_training_fixture import default_config, prepare
from cellsim_v2.training import dataset_digest, validate_dataset


class TrainingFixtureTests(unittest.TestCase):
    def test_reproducible_records_and_grouped_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            a, b = Path(temporary) / "a", Path(temporary) / "b"
            config = default_config()
            original = copy.deepcopy(config)
            first, second = prepare(a, config), prepare(b, config)
            self.assertEqual(config, original)
            self.assertEqual(first["status"], "pass")
            self.assertEqual(second["status"], "pass")
            self.assertEqual((a / "samples.jsonl").read_bytes(),
                             (b / "samples.jsonl").read_bytes())
            manifest = json.loads((a / "manifest.json").read_text())
            self.assertEqual(validate_dataset(manifest, a), manifest)
            self.assertEqual(first["dataset_sha256"], dataset_digest(manifest))
            records = [json.loads(line) for line in
                       (a / "samples.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), first["sample_count"])
            self.assertEqual({r["sample_id"] for r in records},
                             {s["sample_id"] for s in manifest["samples"]})
            expected = len(config["conditions"]) * config["steps"] * len(config["cells"])
            self.assertEqual(len(records), expected)
            for record in records:
                self.assertGreaterEqual(record["targets"]["cell_amount_mol"],
                                        record["inputs"]["cell_amount_mol"])
                # This fixture's target uses pre-diffusion uptake, never future inputs.
                inputs = record["inputs"]
                c = inputs["extracellular_concentration_mol_m3"]
                increment = (record["dt_s"] * inputs["vmax_mol_s"] * c /
                             (inputs["km_mol_m3"] + c))
                self.assertAlmostEqual(record["targets"]["cell_amount_mol"],
                                       inputs["cell_amount_mol"] + increment, places=14)
            for result in first["trajectories"]:
                self.assertLess(result["balance_error_mol"], 1e-12)
            self.assertFalse(first["biological_validation"])
            self.assertFalse(first["model_trained"])

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            sentinel = output / "owner.txt"
            sentinel.write_text("preserve")
            with self.assertRaises(FileExistsError):
                prepare(output, default_config())
            self.assertEqual(sentinel.read_text(), "preserve")

    def test_failed_generation_keeps_configuration_and_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failed"
            config = default_config()
            config["cells"][0]["vmax_mol_s"] = 1e8
            with self.assertRaises(ValueError):
                prepare(output, config)
            failure = json.loads((output / "results.json").read_text())
            self.assertEqual(failure["status"], "failed")
            self.assertTrue(failure["error"])
            self.assertEqual(json.loads((output / "simulation_config.json").read_text()), config)
            self.assertFalse((output / "manifest.json").exists())

    def test_leaking_condition_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "invalid"
            config = default_config()
            config["conditions"][-1]["id"] = config["conditions"][0]["id"]
            with self.assertRaises(ValueError):
                prepare(output, config)
            self.assertEqual(json.loads((output / "results.json").read_text())["status"], "failed")

    def test_malformed_cli_config_is_preserved_with_failure_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "invalid-json"
            config = Path(temporary) / "config.json"
            config.write_bytes(b'{"broken":')
            result = subprocess.run([
                sys.executable, str(Path(__file__).resolve().parents[1] / "tools/prepare_training_fixture.py"),
                "--config", str(config), "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((output / "results.json").is_file())
            failure = json.loads((output / "results.json").read_text())
            self.assertEqual(failure["status"], "failed")
            self.assertEqual((output / "requested_config.json").read_bytes(), config.read_bytes())
