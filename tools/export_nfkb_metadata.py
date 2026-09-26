#!/usr/bin/env python3
"""Attach directly sourced nominal stimulus doses to a frozen demo overlay."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.nfkb_metadata import (
    AUTHOR_CODE_SOURCE, NOMINAL_EXTRACELLULAR_NG_ML, PAPER_SOURCE,
    nominal_dose_schedule,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def export(overlay_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    overlay_sha = _digest(overlay_path)
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    if overlay.get("schema_version") != "cellsim-nfkb-observed-model-variability-overlay/1":
        raise ValueError("unexpected observed/model/bands overlay schema")
    conditions = []
    for condition in overlay["conditions"]:
        schedule = nominal_dose_schedule(
            tuple(condition["stimulus_codes"]), condition["dose_tier_code"])
        condition["nominal_stimulus_schedule"] = schedule
        condition["experimental_run_id"] = None
        condition["physical_chamber_id"] = None
        condition["biological_replicate_id"] = None
        conditions.append({
            "condition_id": condition["condition_id"],
            "author_group_id_column_167": condition["condition_id"],
            "dose_tier": condition["dose_tier"],
            "stimulus_codes": condition["stimulus_codes"],
            "nominal_stimulus_schedule": schedule,
            "experimental_run_id": None,
            "physical_chamber_id": None,
            "biological_replicate_id": None,
        })
    metadata = {
        "schema_version": "cellsim-nfkb-source-metadata/1",
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_matrix_sha256": overlay["source"]["sha256"],
        "input_overlay_sha256": overlay_sha,
        "paper_source": PAPER_SOURCE,
        "author_code_source": AUTHOR_CODE_SOURCE,
        "nominal_extracellular_ng_ml_by_ligand_high_mid_low": {
            key: list(values) for key, values in NOMINAL_EXTRACELLULAR_NG_ML.items()},
        "interpretation": "author-reported nominal extracellular stimulus concentrations in feeding medium; not intracellular exposure, delivered amount, or synthetic payload dose",
        "run_or_chamber_row_mapping": None,
        "reason_row_mapping_unresolved": "the supplied MAT has a single matrix and no verified per-row experimental run/physical-chamber identifier; column 167's 75 author groups encode the 72 order-by-dose conditions and three FM groups, but the plotting variable name alone does not prove chamber identity",
        "normalization_method": None,
        "code_12_control_physical_dose": None,
        "conditions": conditions,
    }
    metadata_path = output / "metadata.json"
    _write(metadata_path, metadata)
    overlay["schema_version"] = "cellsim-nfkb-demo-overlay/1"
    overlay["nominal_dose_metadata_sha256"] = _digest(metadata_path)
    overlay["dose_interpretation"] = metadata["interpretation"]
    overlay["paper_dose_source"] = PAPER_SOURCE
    overlay["author_code_mapping_source"] = AUTHOR_CODE_SOURCE
    combined_path = output / "demo_overlay.json"
    _write(combined_path, overlay)
    receipt = {
        "status": "pass",
        "input_overlay_sha256": overlay_sha,
        "frozen_candidate_sha256": overlay["frozen_candidate_sha256"],
        "metadata_sha256": _digest(metadata_path),
        "demo_overlay_sha256": _digest(combined_path),
        "source_test_tool_sha256": hashlib.sha256(
            (ROOT / "src/cellsim_v2/nfkb_metadata.py").read_bytes() +
            (ROOT / "tests/test_nfkb_metadata.py").read_bytes() +
            Path(__file__).read_bytes()).hexdigest(),
        "condition_count": len(conditions),
        "nominal_code_count": 12,
        "unresolved_row_run_chamber_count": overlay["source"]["shape"][0],
    }
    _write(output / "receipt.json", receipt)
    return {"status": "pass", "metadata": str(metadata_path),
            "demo_overlay": str(combined_path),
            "conditions": len(conditions),
            "source_test_tool_sha256": receipt["source_test_tool_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.overlay.resolve(), args.output.resolve()),
                     indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
