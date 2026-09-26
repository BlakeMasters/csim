"""Offline dataset declarations and frozen evaluation contracts, using JSON only.

Supports longitudinal physical trajectories and unpaired assay observations.
Validation checks declared sample groups and artifact hashes; it does not parse
observation files, authenticate biology, fit models, or provide access control.
Callers must keep the returned campaign digest in an independently trusted record
and verify immediately before evaluation. Files must not be edited concurrently.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re


_SPLITS = frozenset(("train", "validation", "test"))


def _json_value(value, label="JSON"):
    """Reject Python coercions and nonfinite values before JSON detachment."""
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{label} must contain finite numbers")
        return
    if type(value) is list:
        for item in value:
            _json_value(item, label)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{label} keys must be strings")
            _json_value(item, label)
        return
    raise ValueError(f"{label} contains a non-JSON value")


def _canonical(value):
    _json_value(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def dataset_digest(manifest: dict) -> str:
    """Hash JSON content with mapping keys sorted and array order preserved.

    This is a content hash, not dataset validation; call validate_dataset first
    when establishing readiness. The same canonical encoding pins campaigns.
    """
    if type(manifest) is not dict:
        raise ValueError("manifest must be an object")
    return hashlib.sha256(_canonical(manifest).encode("utf-8")).hexdigest()


def _text(value, label):
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} must be a nonempty string without surrounding whitespace")
    return value


def _object(value, required, label, optional=()):
    if type(value) is not dict:
        raise ValueError(f"{label} must be an object")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(f"{label} fields: missing {sorted(missing)}, unknown {sorted(unknown)}")


def _strings(value, label, *, nonempty=True):
    if type(value) is not list or (nonempty and not value):
        raise ValueError(f"{label} must be {'a nonempty' if nonempty else 'an'} array")
    for item in value:
        _text(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f"{label} must contain unique values")


def _sha256(value, label):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")


def _root(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("artifact root must be an existing directory")
    return root


def _artifact(record, root, label):
    _object(record, ("path", "sha256"), label)
    raw = _text(record["path"], f"{label} path")
    posix = PurePosixPath(raw)
    # Use a portable spelling and also reject Windows drive-relative/ADS paths.
    if (posix.is_absolute() or PureWindowsPath(raw).drive or "\\" in raw or ":" in raw
            or ".." in posix.parts or posix.as_posix() != raw or raw == "."):
        raise ValueError(f"{label} path must be a normalized relative path")
    _sha256(record["sha256"], f"{label} sha256")
    try:
        path = (root / raw).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"{label} path is missing or invalid") from exc
    if not path.is_relative_to(root):
        raise ValueError(f"{label} path resolves outside the artifact root")
    if not path.is_file():
        raise ValueError(f"{label} path must name a file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != record["sha256"]:
        raise ValueError(f"{label} hash mismatch")
    return path


def _metadata(value, label):
    if type(value) is not dict:
        raise ValueError(f"{label} must be an object")
    for key in value:
        _text(key, f"{label} key")


def validate_dataset(manifest: dict, root: Path) -> dict:
    """Validate runnable declarations and return a detached JSON manifest.

    All train/validation/test splits must be present. Experimental units and
    trajectories cannot cross splits. Additional held_out_dimensions refer to
    condition_id or keys in every sample's metadata, with nonempty string values.
    Experimental source_ref/reuse_terms are required declarations, not verified
    rights or experimental authentication. Null provenance is allowed only for
    synthetic records. Incomplete planning templates are intentionally rejected.
    Unit strings are explicit labels; no conversion or dimensional inference is
    performed. Optional artifact_path associates sample metadata with a declared
    artifact; file contents require a format-specific reader outside this API.
    """
    _object(manifest, ("schema_version", "dataset_id", "data_kind", "observable",
                       "artifacts", "samples", "split_policy", "source_ref", "reuse_terms"),
            "dataset", ("metadata",))
    normalized = json.loads(_canonical(manifest))
    if normalized["schema_version"] != "1":
        raise ValueError("dataset schema_version must be '1'")
    _text(normalized["dataset_id"], "dataset_id")
    if normalized["data_kind"] not in ("synthetic", "experimental"):
        raise ValueError("data_kind must be synthetic or experimental")
    for key in ("source_ref", "reuse_terms"):
        value = normalized[key]
        if value is not None or normalized["data_kind"] == "experimental":
            _text(value, key)
    if "metadata" in normalized:
        _metadata(normalized["metadata"], "dataset metadata")

    observable = normalized["observable"]
    _object(observable, ("id", "unit", "observation_operator", "modality", "feature_ids", "pairing"),
            "observable")
    for key in ("id", "unit", "observation_operator", "modality"):
        _text(observable[key], f"observable {key}")
    _strings(observable["feature_ids"], "feature_ids")
    if observable["pairing"] not in ("longitudinal", "unpaired"):
        raise ValueError("observable pairing must be longitudinal or unpaired")

    root = _root(root)
    artifacts = normalized["artifacts"]
    if type(artifacts) is not list or not artifacts:
        raise ValueError("artifacts must be a nonempty array")
    artifact_paths = set()
    resolved_paths = set()
    for artifact in artifacts:
        path = _artifact(artifact, root, "dataset artifact")
        if path in resolved_paths:
            raise ValueError("duplicate dataset artifact path")
        artifact_paths.add(artifact["path"])
        resolved_paths.add(path)

    policy = normalized["split_policy"]
    _object(policy, ("held_out_dimensions",), "split_policy")
    _strings(policy["held_out_dimensions"], "held_out_dimensions", nonempty=False)
    reserved = {"sample_id", "experimental_unit_id", "trajectory_id", "split", "artifact_path", "metadata"}
    if reserved.intersection(policy["held_out_dimensions"]):
        raise ValueError("held_out_dimensions must name condition_id or sample metadata keys")
    samples = normalized["samples"]
    if type(samples) is not list or not samples:
        raise ValueError("samples must be a nonempty array")
    sample_ids, present_splits = set(), set()
    owners = {key: {} for key in ("experimental_unit_id", "trajectory_id", *policy["held_out_dimensions"])}
    trajectory_units = {}
    for sample in samples:
        _object(sample, ("sample_id", "experimental_unit_id", "trajectory_id", "condition_id", "split"),
                "sample", ("metadata", "artifact_path"))
        for key in ("sample_id", "experimental_unit_id", "condition_id", "split"):
            _text(sample[key], key)
        if sample["sample_id"] in sample_ids:
            raise ValueError("sample_id must be unique")
        sample_ids.add(sample["sample_id"])
        split = sample["split"]
        if split not in _SPLITS:
            raise ValueError("sample split must be train, validation, or test")
        present_splits.add(split)
        trajectory = sample["trajectory_id"]
        if observable["pairing"] == "longitudinal":
            _text(trajectory, "trajectory_id for longitudinal sample")
        elif trajectory is not None:
            raise ValueError("unpaired samples must have null trajectory_id")
        if trajectory is not None:
            unit = sample["experimental_unit_id"]
            if trajectory_units.setdefault(trajectory, unit) != unit:
                raise ValueError("trajectory_id must belong to one experimental_unit_id")
        metadata = sample.get("metadata", {})
        _metadata(metadata, "sample metadata")
        if "artifact_path" in sample:
            _text(sample["artifact_path"], "artifact_path")
            if sample["artifact_path"] not in artifact_paths:
                raise ValueError("sample artifact_path must reference a declared artifact")
        for key, assignments in owners.items():
            value = sample.get(key) if key in sample else metadata.get(key)
            if key == "trajectory_id" and value is None:
                continue
            _text(value, f"sample dimension {key}")
            if assignments.setdefault(value, split) != split:
                raise ValueError(f"{key} leaks across dataset splits")
    if present_splits != _SPLITS:
        raise ValueError("dataset requires nonempty train, validation, and test splits")
    return normalized


def _evaluation(value, manifest):
    _object(value, ("metric", "observable_id", "unit", "baseline_ids"), "evaluation", ("metadata",))
    for key in ("metric", "observable_id", "unit"):
        _text(value[key], f"evaluation {key}")
    _strings(value["baseline_ids"], "evaluation baseline_ids")
    if "metadata" in value:
        _metadata(value["metadata"], "evaluation metadata")
    if value["observable_id"] != manifest["observable"]["id"]:
        raise ValueError("evaluation observable_id does not match the dataset observable")
    if value["unit"] != manifest["observable"]["unit"]:
        raise ValueError("evaluation unit does not match the dataset observable unit")


def freeze_campaign(path: Path, *, manifest: dict, root: Path, candidate_id: str,
                    model_artifact: dict, preprocessing_artifact: dict, evaluation: dict) -> dict:
    """Create a new campaign snapshot after checking files and declarations.

    The evaluation unit labels the observable, not necessarily the metric's
    output dimension. Metric/baseline IDs are declarations; no model or metric is
    executed. Keep campaign_sha256 independently to detect replacement. An
    existing path is never overwritten. This is not a filesystem write barrier.
    """
    normalized = validate_dataset(manifest, root)
    _text(candidate_id, "candidate_id")
    root = _root(root)
    _artifact(model_artifact, root, "model artifact")
    _artifact(preprocessing_artifact, root, "preprocessing artifact")
    _evaluation(evaluation, normalized)
    campaign = {
        "schema_version": "1", "dataset": normalized, "dataset_sha256": dataset_digest(normalized),
        "candidate_id": candidate_id, "model_artifact": model_artifact,
        "preprocessing_artifact": preprocessing_artifact, "evaluation": evaluation,
        "biological_qualification": "none",
    }
    campaign = json.loads(_canonical(campaign))
    frozen = {"campaign_sha256": dataset_digest(campaign), "campaign": campaign}
    serialized = json.dumps(frozen, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
    return frozen


def _unique_pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key {key}")
        output[key] = value
    return output


def verify_campaign(path: Path, *, manifest: dict, root: Path, expected_digest: str) -> dict:
    """Verify a saved campaign against a trusted digest and current dataset/files.

    Caller-supplied expected_digest must come from the original freeze, not from
    the file currently being checked. Any new candidate or preprocessing requires
    a new campaign. Verification does not prevent edits after this function ends.
    """
    _sha256(expected_digest, "expected campaign digest")
    frozen = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs)
    _object(frozen, ("campaign_sha256", "campaign"), "frozen campaign")
    _sha256(frozen["campaign_sha256"], "campaign_sha256")
    campaign = frozen["campaign"]
    if frozen["campaign_sha256"] != expected_digest or dataset_digest(campaign) != expected_digest:
        raise ValueError("campaign digest mismatch")
    _object(campaign, ("schema_version", "dataset", "dataset_sha256", "candidate_id", "model_artifact",
                       "preprocessing_artifact", "evaluation", "biological_qualification"), "campaign")
    if campaign["schema_version"] != "1" or campaign["biological_qualification"] != "none":
        raise ValueError("unsupported campaign version or biological qualification")
    _text(campaign["candidate_id"], "candidate_id")
    _sha256(campaign["dataset_sha256"], "dataset_sha256")
    normalized = validate_dataset(manifest, root)
    digest = dataset_digest(normalized)
    if campaign["dataset_sha256"] != digest or dataset_digest(campaign["dataset"]) != digest:
        raise ValueError("dataset changed since campaign freeze")
    _evaluation(campaign["evaluation"], normalized)
    root = _root(root)
    _artifact(campaign["model_artifact"], root, "model artifact")
    _artifact(campaign["preprocessing_artifact"], root, "preprocessing artifact")
    return frozen
