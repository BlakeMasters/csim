"""Training-readiness contracts; synthetic records are not biological evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cellsim_v2.training import (
    dataset_digest, freeze_campaign, validate_dataset, verify_campaign,
)


class TrainingContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.artifact("observations.jsonl", b'{"synthetic":true}\n')
        self.model = self.artifact("candidate.json", b'{"kind":"identity"}\n')
        self.preprocessing = self.artifact("preprocessing.json", b'{"transform":"none"}\n')
        self.manifest = {
            "schema_version": "1", "dataset_id": "synthetic-transport",
            "data_kind": "synthetic", "source_ref": None, "reuse_terms": None,
            "observable": {
                "id": "cell_amount", "unit": "mol", "modality": "physical",
                "observation_operator": "sum tracked intracellular amount",
                "feature_ids": ["cell_amount_mol"], "pairing": "longitudinal",
            },
            "artifacts": [self.data],
            "samples": [
                {"sample_id": f"sample-{i}", "experimental_unit_id": f"unit-{i}",
                 "trajectory_id": f"trajectory-{i}", "condition_id": f"condition-{i}",
                 "split": split, "artifact_path": "observations.jsonl",
                 "metadata": {"batch_id": f"batch-{i}"}}
                for i, split in enumerate(("train", "validation", "test"))
            ],
            "split_policy": {"held_out_dimensions": ["condition_id", "batch_id"]},
            "metadata": {"synthetic": True},
        }
        self.evaluation = {
            "metric": "mean_absolute_error", "observable_id": "cell_amount",
            "unit": "mol", "baseline_ids": ["no_change", "training_mean"],
        }
        self.campaign_path = self.root / "campaign.json"

    def artifact(self, name, contents):
        (self.root / name).write_bytes(contents)
        return {"path": name, "sha256": hashlib.sha256(contents).hexdigest()}

    def freeze(self, **overrides):
        options = {
            "manifest": self.manifest, "root": self.root, "candidate_id": "candidate-1",
            "model_artifact": self.model, "preprocessing_artifact": self.preprocessing,
            "evaluation": self.evaluation,
        }
        options.update(overrides)
        return freeze_campaign(self.campaign_path, **options)

    def verify(self, frozen, **overrides):
        options = {
            "manifest": self.manifest, "root": self.root,
            "expected_digest": frozen["campaign_sha256"],
        }
        options.update(overrides)
        return verify_campaign(self.campaign_path, **options)

    def test_physical_manifest_is_detached(self):
        validated = validate_dataset(self.manifest, self.root)
        self.assertEqual(validated, self.manifest)
        validated["samples"][0]["metadata"]["batch_id"] = "changed"
        self.assertEqual(self.manifest["samples"][0]["metadata"]["batch_id"], "batch-0")

    def test_unpaired_gene_expression_does_not_invent_trajectories(self):
        self.manifest["observable"].update(
            modality="gene_expression", unit="count", observation_operator="raw assay counts",
            pairing="unpaired", feature_ids=["gene-A", "gene-B"])
        for sample in self.manifest["samples"]:
            sample["trajectory_id"] = None
        self.assertEqual(validate_dataset(self.manifest, self.root), self.manifest)
        self.manifest["samples"][0]["trajectory_id"] = "invented-pair"
        with self.assertRaisesRegex(ValueError, "unpaired"):
            validate_dataset(self.manifest, self.root)

    def test_experimental_provenance_is_required_but_not_authenticated(self):
        self.manifest["data_kind"] = "experimental"
        for missing in ("source_ref", "reuse_terms"):
            candidate = deepcopy(self.manifest)
            candidate.update(source_ref="accession:declared-source", reuse_terms="declared-terms")
            candidate[missing] = None
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, missing):
                validate_dataset(candidate, self.root)
        self.manifest.update(source_ref="accession:declared-source", reuse_terms="declared-terms")
        self.assertEqual(validate_dataset(self.manifest, self.root), self.manifest)

    def test_required_splits_and_unique_sample_ids(self):
        for change in ("missing_split", "duplicate_id"):
            candidate = deepcopy(self.manifest)
            if change == "missing_split":
                candidate["samples"].pop()
            else:
                candidate["samples"][1]["sample_id"] = candidate["samples"][0]["sample_id"]
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_dataset(candidate, self.root)

    def test_experimental_unit_and_trajectory_leakage_rejected(self):
        for key in ("experimental_unit_id", "trajectory_id"):
            candidate = deepcopy(self.manifest)
            candidate["samples"][2][key] = candidate["samples"][0][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                validate_dataset(candidate, self.root)

    def test_repeated_frames_within_one_split_allowed(self):
        frame = deepcopy(self.manifest["samples"][0])
        frame["sample_id"] = "next-frame"
        self.manifest["samples"].append(frame)
        self.assertEqual(len(validate_dataset(self.manifest, self.root)["samples"]), 4)

    def test_trajectory_cannot_claim_multiple_experimental_units(self):
        frame = deepcopy(self.manifest["samples"][0])
        frame.update(sample_id="next-frame", experimental_unit_id="different-unit")
        self.manifest["samples"].append(frame)
        with self.assertRaisesRegex(ValueError, "trajectory"):
            validate_dataset(self.manifest, self.root)

    def test_held_out_conditions_and_metadata_dimensions(self):
        for key in ("condition_id", "batch_id"):
            candidate = deepcopy(self.manifest)
            if key == "condition_id":
                candidate["samples"][1][key] = candidate["samples"][0][key]
            else:
                candidate["samples"][1]["metadata"][key] = candidate["samples"][0]["metadata"][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                validate_dataset(candidate, self.root)

    def test_shared_conditions_allowed_without_condition_holdout_claim(self):
        self.manifest["split_policy"]["held_out_dimensions"] = []
        for sample in self.manifest["samples"]:
            sample["condition_id"] = "shared-condition"
        self.assertEqual(validate_dataset(self.manifest, self.root), self.manifest)

    def test_missing_holdout_dimension_rejected(self):
        del self.manifest["samples"][1]["metadata"]["batch_id"]
        with self.assertRaisesRegex(ValueError, "batch_id"):
            validate_dataset(self.manifest, self.root)

    def test_strict_schema_finite_json_and_feature_identity(self):
        candidates = []
        for key, value in (("surprise", True), ("schema_version", 1), ("metadata", {"bad": float("nan")}),
                           ("metadata", {"bad": float("inf")}), ("metadata", {1: "bad-key"}),
                           ("metadata", {"bad": (1, 2)})):
            candidate = deepcopy(self.manifest)
            candidate[key] = value
            candidates.append(candidate)
        for features in ([], ["duplicate", "duplicate"], [""], "not-an-array"):
            candidate = deepcopy(self.manifest)
            candidate["observable"]["feature_ids"] = features
            candidates.append(candidate)
        for candidate in candidates:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                validate_dataset(candidate, self.root)

    def test_longitudinal_requires_trajectory(self):
        self.manifest["samples"][0]["trajectory_id"] = None
        with self.assertRaisesRegex(ValueError, "trajectory_id"):
            validate_dataset(self.manifest, self.root)

    def test_artifact_hash_missing_and_corruption(self):
        for path in ("missing.json", "observations.jsonl"):
            candidate = deepcopy(self.manifest)
            candidate["artifacts"][0]["path"] = path
            candidate["artifacts"][0]["sha256"] = "0" * 64
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_dataset(candidate, self.root)

    def test_absolute_parent_and_windows_paths_rejected(self):
        for path in (str(self.root / "observations.jsonl"), "../outside.json", "/absolute.json",
                     "C:/outside.json", "folder\\observations.jsonl", "./observations.jsonl"):
            candidate = deepcopy(self.manifest)
            candidate["artifacts"][0]["path"] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "path"):
                validate_dataset(candidate, self.root)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as external_dir:
            external = Path(external_dir) / "outside.json"
            external.write_bytes(b"outside")
            link = self.root / "link.json"
            try:
                link.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"Host does not permit symlink creation: {exc}")
            self.manifest["artifacts"] = [{"path": "link.json", "sha256": hashlib.sha256(b"outside").hexdigest()}]
            with self.assertRaisesRegex(ValueError, "outside"):
                validate_dataset(self.manifest, self.root)

    def test_row_artifact_link_must_be_declared(self):
        self.manifest["samples"][0]["artifact_path"] = "untracked.json"
        with self.assertRaisesRegex(ValueError, "artifact_path"):
            validate_dataset(self.manifest, self.root)

    def test_resolved_artifact_escape_rejected_without_link_privilege(self):
        """Exercise confinement even when the host cannot create a real symlink."""
        real_resolve = Path.resolve
        source = self.root / "observations.jsonl"
        outside = self.root.parent / "outside.jsonl"

        def resolved(path, *args, **kwargs):
            return outside if path == source else real_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", resolved):
            with self.assertRaisesRegex(ValueError, "outside"):
                validate_dataset(self.manifest, self.root)

    def test_digest_stable_to_mapping_order_but_binds_feature_order(self):
        self.manifest["observable"]["feature_ids"] = ["gene-A", "gene-B"]
        digest = dataset_digest(self.manifest)
        self.assertEqual(digest, dataset_digest(dict(reversed(list(self.manifest.items())))))
        self.manifest["observable"]["feature_ids"].reverse()
        self.assertNotEqual(digest, dataset_digest(self.manifest))

    def test_campaign_verifies_and_cannot_be_overwritten(self):
        frozen = self.freeze()
        self.assertEqual(self.verify(frozen), frozen)
        before = self.campaign_path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.freeze()
        self.assertEqual(self.campaign_path.read_bytes(), before)
        self.assertEqual(frozen["campaign"]["biological_qualification"], "none")

    def test_freeze_rejects_wrong_units_observable_or_empty_baselines(self):
        for field, value in (("unit", "mmol"), ("observable_id", "wrong"), ("baseline_ids", [])):
            evaluation = deepcopy(self.evaluation)
            evaluation[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.freeze(evaluation=evaluation)
            self.assertFalse(self.campaign_path.exists())

    def test_freeze_checks_actual_candidate_and_preprocessing(self):
        for key in ("model_artifact", "preprocessing_artifact"):
            invalid = {"path": "not-present", "sha256": "0" * 64}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.freeze(**{key: invalid})
            self.assertFalse(self.campaign_path.exists())

    def test_campaign_rejects_dataset_metadata_and_split_changes(self):
        frozen = self.freeze()
        for change in ("metadata", "split", "features"):
            candidate = deepcopy(self.manifest)
            if change == "metadata":
                candidate["metadata"]["new"] = "changed"
            elif change == "split":
                candidate["samples"][0]["split"], candidate["samples"][2]["split"] = "test", "train"
            else:
                candidate["observable"]["feature_ids"] = ["changed"]
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "dataset"):
                self.verify(frozen, manifest=candidate)

    def test_campaign_rejects_mutated_artifact_bytes(self):
        for artifact in (self.data, self.model, self.preprocessing):
            with self.subTest(artifact=artifact["path"]):
                frozen = self.freeze()
                path = self.root / artifact["path"]
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaisesRegex(ValueError, "hash"):
                    self.verify(frozen)
                path.write_bytes(original)
                self.campaign_path.unlink()

    def test_external_digest_rejects_rewritten_campaign(self):
        frozen = self.freeze()
        for field in ("candidate_id", "evaluation", "biological_qualification"):
            changed = deepcopy(frozen)
            if field == "evaluation":
                changed["campaign"][field]["metric"] = "replacement"
            else:
                changed["campaign"][field] = "replacement"
            changed["campaign_sha256"] = dataset_digest(changed["campaign"])
            self.campaign_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "campaign"):
                self.verify(frozen)

    def test_duplicate_json_keys_rejected_in_campaign(self):
        frozen = self.freeze()
        text = self.campaign_path.read_text(encoding="utf-8")
        text = text.replace('"candidate_id":', '"candidate_id":"duplicate","candidate_id":')
        self.campaign_path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.verify(frozen)


if __name__ == "__main__":
    unittest.main()
