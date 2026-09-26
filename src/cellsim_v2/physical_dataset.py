"""Strict ingestion of the synthetic physical-amount JSONL fixture.

This module checks payloads against their dataset declarations. It performs no
fitting, biological authentication, expression-to-physics mapping, or model
execution. Filtering returned splits is workflow separation, not access
security: a shared JSONL artifact must be parsed completely to verify its rows.
Files are hashed before ingestion, parsed bytes are checked, and declarations
and artifacts are revalidated afterward. This is not a filesystem lock, and
callers must keep files stable while using the resulting dataset.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .training import dataset_digest, validate_dataset


_SPLITS = frozenset(("train", "validation", "test"))
_INPUT_UNITS = {
    "cell_amount_mol": "mol",
    "dt_s": "s",
    "extracellular_concentration_mol_m3": "mol/m^3",
    "km_mol_m3": "mol/m^3",
    "time_s": "s",
    "vmax_mol_s": "mol/s",
}
_INPUT_FIELDS = frozenset(("cell_amount_mol", "extracellular_concentration_mol_m3",
                           "km_mol_m3", "vmax_mol_s"))
_PAYLOAD_FIELDS = frozenset(("cell_id", "time_s", "dt_s", "inputs", "targets"))


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"nonfinite JSON number is unsupported: {value}")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number is unsupported")
    return result


def _parse_json(raw: bytes, label: str):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"invalid {label}: {exc}") from exc


def _object(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f"{label} must contain exactly these fields: {sorted(fields)}")


def _text(value, label):
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} must be a nonempty string without surrounding whitespace")


def _number(value, label, *, positive=False):
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a real number, excluding booleans")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValueError(f"{label} cannot be represented as a finite number") from exc
    if not finite or value < 0 or (positive and value == 0):
        constraint = "positive" if positive else "nonnegative"
        raise ValueError(f"{label} must be finite and {constraint}")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _check_contract(manifest):
    if manifest["data_kind"] != "synthetic":
        raise ValueError("physical fixture ingestion supports synthetic data only")
    observable = manifest["observable"]
    expected = {"id": "intracellular_amount_next", "unit": "mol",
                "modality": "physical_amount", "pairing": "longitudinal",
                "feature_ids": ["cell_amount_mol"]}
    if any(observable[key] != value for key, value in expected.items()):
        raise ValueError("unsupported physical fixture observable contract")
    metadata = manifest.get("metadata", {})
    if metadata.get("input_units") != _INPUT_UNITS:
        raise ValueError("physical fixture requires the exact supported input_units declaration")
    for sample in manifest["samples"]:
        if "artifact_path" not in sample:
            raise ValueError("every physical sample must declare its JSONL artifact_path")


def _check_row(row, sample, artifact_path):
    _object(row, set(sample) | _PAYLOAD_FIELDS, "physical sample payload")
    declaration = {key: row[key] for key in sample}
    if _canonical(declaration) != _canonical(sample):
        raise ValueError("physical payload sample metadata differs from the manifest")
    if row["artifact_path"] != artifact_path:
        raise ValueError("physical sample appears in an artifact other than its declaration")
    _text(row["cell_id"], "cell_id")
    _number(row["time_s"], "time_s")
    _number(row["dt_s"], "dt_s", positive=True)
    _object(row["inputs"], _INPUT_FIELDS, "physical inputs")
    _object(row["targets"], ("cell_amount_mol",), "physical targets")
    for name, value in row["inputs"].items():
        _number(value, f"inputs.{name}", positive=(name == "km_mol_m3"))
    target = row["targets"]["cell_amount_mol"]
    _number(target, "targets.cell_amount_mol")
    if target < row["inputs"]["cell_amount_mol"]:
        raise ValueError("uptake-only physical target cannot be below its current cell amount")


def load_physical_dataset(manifest_path: Path, *,
                          splits=("train", "validation", "test")) -> dict:
    """Load verified synthetic physical rows, returning only requested splits.

    Returns ``{'manifest': detached_manifest, 'root': resolved_Path,
    'rows': selected_rows}``. All manifest samples must occur exactly once in
    their declared artifacts, including samples outside the requested splits.
    Rows are returned in manifest sample order. The returned manifest contains
    all split declarations; only ``rows`` is filtered. This API does not fit
    transformations, infer units, train models, or provide holdout access control.
    """
    if type(splits) not in (tuple, list) or not splits:
        raise ValueError("splits must be a nonempty tuple or list")
    if any(type(split) is not str or split not in _SPLITS for split in splits):
        raise ValueError("requested splits must be train, validation, or test")
    if len(set(splits)) != len(splits):
        raise ValueError("requested splits must be unique")
    requested_splits = frozenset(splits)
    path = Path(manifest_path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("manifest_path must name a file")
    root = path.parent
    original_manifest_bytes = path.read_bytes()
    manifest = validate_dataset(_parse_json(original_manifest_bytes, "dataset manifest"), root)
    _check_contract(manifest)
    original_digest = dataset_digest(manifest)
    samples = {sample["sample_id"]: sample for sample in manifest["samples"]}
    artifacts = {artifact["path"]: artifact for artifact in manifest["artifacts"]}
    payload_paths = sorted({sample["artifact_path"] for sample in manifest["samples"]})
    rows = {}
    for raw_path in payload_paths:
        # validate_dataset already validates path syntax, confinement and hashes.
        # Recheck the resolved file and the exact bytes that will be parsed.
        artifact_path = (root / raw_path).resolve(strict=True)
        if not artifact_path.is_relative_to(root) or not artifact_path.is_file():
            raise ValueError("physical artifact path is invalid or outside the dataset root")
        payload = artifact_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != artifacts[raw_path]["sha256"]:
            raise ValueError("physical artifact hash changed during ingestion")
        for line_number, line in enumerate(payload.splitlines(), start=1):
            if not line.strip():
                raise ValueError(f"empty physical JSONL row at {raw_path}:{line_number}")
            row = _parse_json(line, f"physical JSONL row {raw_path}:{line_number}")
            if type(row) is not dict:
                raise ValueError("physical JSONL row must be an object")
            sample_id = row.get("sample_id")
            _text(sample_id, "payload sample_id")
            if sample_id not in samples:
                raise ValueError("physical payload contains an undeclared sample_id")
            if sample_id in rows:
                raise ValueError("physical payload contains a duplicate sample_id")
            _check_row(row, samples[sample_id], raw_path)
            rows[sample_id] = row
    if set(rows) != set(samples):
        raise ValueError("physical payload is missing declared sample rows")
    final_manifest_bytes = path.read_bytes()
    if final_manifest_bytes != original_manifest_bytes:
        raise ValueError("dataset manifest changed during physical ingestion")
    final_manifest = validate_dataset(_parse_json(final_manifest_bytes, "dataset manifest"), root)
    if dataset_digest(final_manifest) != original_digest:
        raise ValueError("dataset declarations changed during physical ingestion")
    selected = [rows[sample["sample_id"]] for sample in manifest["samples"]
                if sample["split"] in requested_splits]
    return {"manifest": manifest, "root": root, "rows": selected}
