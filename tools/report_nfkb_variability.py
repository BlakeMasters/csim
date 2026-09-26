#!/usr/bin/env python3
"""Export observed p10/median/p90 bands without fitting a stochastic law."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.nfkb_observed import TIME_MIN, VARIABLE
from cellsim_v2.nfkb_variability import finite_percentile_bands


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def report(source: Path, overlay_path: Path, output: Path) -> dict:
    import numpy as np
    import scipy
    from scipy.io import loadmat

    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    start = time.perf_counter()
    source_sha = _digest(source)
    overlay_sha = _digest(overlay_path)
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    if overlay.get("schema_version") != "cellsim-nfkb-observed-model-overlay/1":
        raise ValueError("unexpected model-overlay schema")
    if overlay["source"]["sha256"] != source_sha:
        raise ValueError("raw matrix source hash differs from model overlay")
    matrix = loadmat(source, verify_compressed_data_integrity=True)[VARIABLE]
    if matrix.shape != (11267, 172):
        raise ValueError("supplied matrix shape changed")
    conditions = []
    for condition in overlay["conditions"]:
        condition_id = condition["condition_id"]
        rows = matrix[matrix[:, 166] == condition_id, :83]
        if len(rows) != condition["row_count"]:
            raise ValueError("condition row count changed")
        bands = finite_percentile_bands(rows)
        if bands["finite_count"] != condition["observed"]["finite_count_by_time"]:
            raise ValueError("finite counts differ from observed means")
        conditions.append({
            "condition_id": condition_id,
            "dose_tier": condition["dose_tier"],
            "sequence_key": condition["sequence_key"],
            "split": condition["split"],
            "row_count": condition["row_count"],
            "time_min": list(TIME_MIN),
            "p10": bands["p10"],
            "p50": bands["p50"],
            "p90": bands["p90"],
            "finite_count_by_time": bands["finite_count"],
            "example_source_row_keys": [item["row_key"]
                                        for item in condition["sample_traces"]],
        })
        condition["observed"]["p10"] = bands["p10"]
        condition["observed"]["p50"] = bands["p50"]
        condition["observed"]["p90"] = bands["p90"]
    result = {
        "schema_version": "cellsim-nfkb-observed-dispersion/1",
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "descriptive across source rows; biological, measurement and environment contributions unresolved",
        "not_an_intrinsic_stochastic_law": True,
        "quantile_method": "linear interpolation at (n-1)*p among finite values at each time",
        "observable": overlay["observable"],
        "source_matrix_sha256": source_sha,
        "model_overlay_sha256": overlay_sha,
        "frozen_candidate_sha256": overlay["frozen_candidate_sha256"],
        "source_row_index": "../nfkb_observed_20260926_02/row_index.jsonl",
        "condition_count": len(conditions),
        "conditions": conditions,
        "environment": {"python": sys.version, "numpy": np.__version__,
                        "scipy": scipy.__version__, "platform": platform.platform(),
                        "device": "CPU"},
        "calculation_seconds_before_write": time.perf_counter() - start,
    }
    dispersion_path = output / "dispersion.json"
    _write(dispersion_path, result)
    overlay["schema_version"] = "cellsim-nfkb-observed-model-variability-overlay/1"
    overlay["dispersion_artifact_sha256"] = _digest(dispersion_path)
    overlay["dispersion_interpretation"] = result["interpretation"]
    combined_path = output / "comparison_with_bands.json"
    _write(combined_path, overlay)
    receipt = {
        "status": "pass",
        "source_matrix_sha256": source_sha,
        "model_overlay_sha256": overlay_sha,
        "frozen_candidate_sha256": overlay["frozen_candidate_sha256"],
        "dispersion_sha256": _digest(dispersion_path),
        "combined_overlay_sha256": _digest(combined_path),
        "source_test_tool_sha256": hashlib.sha256(
            (ROOT / "src/cellsim_v2/nfkb_variability.py").read_bytes() +
            (ROOT / "tests/test_nfkb_variability.py").read_bytes() +
            Path(__file__).read_bytes()).hexdigest(),
        "condition_count": len(conditions),
        "source_row_count": matrix.shape[0],
        "wall_seconds_before_receipt": time.perf_counter() - start,
        "output_bytes_before_receipt": (dispersion_path.stat().st_size +
                                        combined_path.stat().st_size),
    }
    _write(output / "receipt.json", receipt)
    return {"status": "pass", "dispersion": str(dispersion_path),
            "combined_overlay": str(combined_path),
            "conditions": len(conditions),
            "source_rows": matrix.shape[0],
            "source_test_tool_sha256": receipt["source_test_tool_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=ROOT / "data/scmat_sequentialstim.mat")
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(report(args.source.resolve(), args.overlay.resolve(),
                            args.output.resolve()), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
