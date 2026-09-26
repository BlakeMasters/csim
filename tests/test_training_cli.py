"""Command-line contract workflow over generated synthetic trajectories."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from prepare_training_fixture import default_config, prepare
from training_manifest import _artifact_reference, _load_json


ROOT = Path(__file__).resolve().parents[1]


class TrainingCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/training_manifest.py"), *map(str, args)],
            capture_output=True, text=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=30,
        )

    def success(self, *args):
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["biological_qualification"], "none")
        return output

    def test_generated_fixture_validate_freeze_verify_then_reject_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data = directory / "dataset"
            prepared = prepare(data, default_config())
            manifest = data / "manifest.json"
            validated = self.success("validate", "--manifest", manifest)
            self.assertEqual(validated["status"], "valid")
            self.assertEqual(validated["dataset_sha256"], prepared["dataset_sha256"])
            # The explicit root also works with a manifest stored elsewhere.
            alternate = directory / "manifest-copy.json"
            alternate.write_bytes(manifest.read_bytes())
            explicit = self.success("validate", "--manifest", alternate, "--root", data)
            self.assertEqual(explicit["dataset_sha256"], validated["dataset_sha256"])

            model = data / "candidate.json"
            preprocessing = data / "preprocessing.json"
            model.write_text('{"kind":"untrained-test-artifact"}\n', encoding="utf-8")
            preprocessing.write_text('{"transform":"identity"}\n', encoding="utf-8")
            evaluation = directory / "evaluation.json"
            evaluation.write_text(json.dumps({
                "metric": "mean_absolute_error", "observable_id": "intracellular_amount_next",
                "unit": "mol", "baseline_ids": ["no_change", "training_mean_amount_increment"],
            }), encoding="utf-8")
            campaign = directory / "campaign.json"
            freeze_args = ("freeze", "--manifest", manifest, "--candidate-id", "test-candidate",
                           "--model", "candidate.json", "--preprocessing", "preprocessing.json",
                           "--evaluation", evaluation, "--output", campaign)
            frozen = self.success(*freeze_args)
            self.assertEqual(frozen["status"], "frozen")
            snapshot = json.loads(campaign.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["campaign"]["model_artifact"]["sha256"],
                             hashlib.sha256(model.read_bytes()).hexdigest())
            verify_args = ("verify", "--manifest", manifest, "--campaign", campaign,
                           "--expected-digest", frozen["campaign_sha256"])
            verified = self.success(*verify_args)
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["campaign_sha256"], frozen["campaign_sha256"])
            before = campaign.read_bytes()
            duplicate = self.run_cli(*freeze_args)
            self.assertEqual(duplicate.returncode, 1)
            self.assertEqual(json.loads(duplicate.stderr)["status"], "error")
            self.assertEqual(campaign.read_bytes(), before)

            model.write_text('{"kind":"changed-candidate"}\n', encoding="utf-8")
            rejected = self.run_cli(*verify_args)
            self.assertEqual(rejected.returncode, 1)
            self.assertEqual(rejected.stdout, "")
            self.assertIn("hash mismatch", json.loads(rejected.stderr)["error"])

    def test_artifact_escape_rejected_before_opening_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for raw in ("../outside.json", str(root.parent / "outside.json"),
                        "C:/outside.json", "inside\\file.json"):
                with self.subTest(path=raw), patch.object(Path, "open") as opened:
                    with self.assertRaisesRegex(ValueError, "path"):
                        _artifact_reference(root, raw)
                    opened.assert_not_called()

    def test_resolved_artifact_escape_rejected_before_opening_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "link.json"
            outside = root.parent / "outside.json"
            real_resolve = Path.resolve

            def resolved(path, *args, **kwargs):
                return outside if path == source else real_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", resolved), patch.object(Path, "open") as opened:
                with self.assertRaisesRegex(ValueError, "outside"):
                    _artifact_reference(root, "link.json")
                opened.assert_not_called()

    def test_json_reader_rejects_ambiguous_and_nonfinite_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            for raw in ('{"key":1,"key":2}', '{"value":NaN}', '{"value":Infinity}',
                        '{"value":-Infinity}', '{"value":1e999}', '["not-an-object"]'):
                path.write_text(raw, encoding="utf-8")
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    _load_json(path)
            result = self.run_cli("validate", "--manifest", path)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stderr)["status"], "error")


if __name__ == "__main__":
    unittest.main()
