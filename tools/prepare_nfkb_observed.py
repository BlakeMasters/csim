#!/usr/bin/env python3
"""Export a provenance-preserving, compact observed NF-κB reporter overlay.

Requires the separately qualified optional NumPy/SciPy reader environment.
The raw MAT file is read only. Output must be a new directory.
"""
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
from cellsim_v2.nfkb_observed import (
    MATLAB_COLUMNS, SWITCH_TIMES_MIN, TIME_MIN, VARIABLE,
    adapt_source_row, frozen_sequence_split,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _component_digest() -> str:
    digest = hashlib.sha256()
    for relative in ("src/cellsim_v2/nfkb_observed.py",
                     "tests/test_nfkb_observed.py",
                     "tools/prepare_nfkb_observed.py"):
        path = ROOT / relative
        digest.update(relative.encode("ascii"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def export(source: Path, output: Path, *, samples_per_condition: int = 5) -> dict:
    start = time.perf_counter()
    import numpy as np
    import scipy
    from scipy.io import loadmat

    if not 1 <= samples_per_condition <= 5:
        raise ValueError("sample count must be 1 to 5")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    source_digest = _digest(source)
    values = loadmat(source, verify_compressed_data_integrity=True)[VARIABLE]
    source_read_seconds = time.perf_counter() - start
    if values.shape != (11267, 172) or values.dtype != np.float64:
        raise ValueError("supplied sequential matrix shape/dtype contract failed")
    split = frozen_sequence_split()
    rows_by_condition: dict[int, list[dict]] = {key: [] for key in range(1, 76)}
    nonfinite_counts = {"NaN": 0, "+Inf": 0, "-Inf": 0}
    row_index_path = output / "row_index.jsonl"
    with row_index_path.open("x", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(values):
            adapted = adapt_source_row(row, source_sha256=source_digest,
                                       source_row_1based=index + 1)
            rows_by_condition[adapted["condition_id"]].append(adapted)
            bad = np.flatnonzero(~np.isfinite(row))
            all_nonfinite = []
            for column in bad:
                kind = ("NaN" if np.isnan(row[column]) else
                        "+Inf" if np.isposinf(row[column]) else "-Inf")
                nonfinite_counts[kind] += 1
                all_nonfinite.append({"matlab_column_1based": int(column + 1),
                                      "kind": kind})
            record = {key: adapted[key] for key in (
                "row_key", "source_row_1based", "condition_id",
                "stimulus_codes", "ligand_sequence", "sequence_key",
                "dose_tier_code", "dose_tier", "author_control_label",
                "nonfinite_trace_samples")}
            record["nonfinite_all_columns"] = all_nonfinite
            stream.write(json.dumps(record, allow_nan=False,
                                    ensure_ascii=False, separators=(",", ":")) + "\n")
    row_index_seconds = time.perf_counter() - start - source_read_seconds

    conditions = []
    for condition_id, rows in rows_by_condition.items():
        if not rows:
            raise ValueError(f"condition {condition_id} has no rows")
        metadata = rows[0]
        for row in rows[1:]:
            if (row["stimulus_codes"], row["dose_tier_code"]) != (
                    metadata["stimulus_codes"], metadata["dose_tier_code"]):
                raise ValueError(f"condition {condition_id} metadata varies by row")
        trace = values[np.array([r["source_row_1based"] - 1 for r in rows]), :83]
        finite = np.isfinite(trace)
        count = finite.sum(axis=0)
        total = np.where(finite, trace, 0).sum(axis=0)
        mean = [float(t / n) if n else None for t, n in zip(total, count)]
        selected = [r for r in rows if not r["nonfinite_trace_samples"]][
            :samples_per_condition]
        conditions.append({
            "condition_id": condition_id,
            "stimulus_codes": metadata["stimulus_codes"],
            "ligand_sequence": metadata["ligand_sequence"],
            "sequence_key": metadata["sequence_key"],
            "dose_tier_code": metadata["dose_tier_code"],
            "dose_tier": metadata["dose_tier"],
            "author_control_label": metadata["author_control_label"],
            "split": ("control" if metadata["sequence_key"] is None else
                      split[metadata["sequence_key"]]),
            "row_count": len(rows),
            "complete_trace_row_count": int(finite.all(axis=1).sum()),
            "nonfinite_trace_entry_count": int((~finite).sum()),
            "observed": {"time_min": list(TIME_MIN), "mean": mean,
                         "finite_count_by_time": count.astype(int).tolist()},
            "sample_traces": [{"row_key": r["row_key"],
                               "source_row_1based": r["source_row_1based"],
                               "values": r["values"]} for r in selected],
            "model_prediction": None,
        })
    source_meta = {
        "file": source.name,
        "variable": VARIABLE,
        "shape": list(values.shape),
        "dtype": str(values.dtype),
        "sha256": source_digest,
        "git_blob_sha1": _git_blob(source),
        "matlab_columns_1based": MATLAB_COLUMNS,
        "author_code": "https://raw.githubusercontent.com/tay-lab/Sequential_NF-kB_stim/main/f1and2_supps.m",
        "author_code_lines": {"trace_and_time": [14, 22],
                              "condition_and_stimuli": [42, 52],
                              "dose_tier": [74, 80],
                              "ligand_decoder": [428, 469]},
        "primary_paper": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10794069/",
        "source_row_key_format": "sha256:<source-sha256>:scmatcomb_norm:row:<MATLAB-1-based-row>",
        "feature_file_join": "not performed; feature matrix has 11265 rows and lacks proven stable row keys",
    }
    result = {
        "schema_version": "cellsim-nfkb-observed-traces/1",
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": source_meta,
        "observable": {
            "id": "author_normalized_p65_nuclear_cytoplasmic_reporter",
            "label": "Nuc/Cyto p65 (author-normalized)",
            "unit": "dimensionless",
            "normalization_method": None,
            "interpretation": "fluorescent reporter trajectory; not a molar concentration or secretion rate",
            "time_unit": "minute",
        },
        "switch_times_min": list(SWITCH_TIMES_MIN),
        "dose_tiers": {"1": "high", "2": "mid", "3": "low"},
        "physical_dose_values": None,
        "conditions": conditions,
        "split": {
            "unit": "four-ligand order across all dose tiers",
            "assignment": split,
            "development_orders": sum(x == "development" for x in split.values()),
            "validation_orders": sum(x == "validation" for x in split.values()),
            "evaluation_orders": sum(x == "evaluation" for x in split.values()),
            "run_or_chamber_holdout": False,
            "control_condition_ids": [25, 50, 75],
        },
        "missingness": {
            "all_matrix_entries": nonfinite_counts,
            "trace_entries": int((~np.isfinite(values[:, :83])).sum()),
            "complete_trace_rows": int(np.isfinite(values[:, :83]).all(axis=1).sum()),
            "row_index_file": row_index_path.name,
            "aggregate_policy": "finite observations only at each time; no imputation or clipping",
        },
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "numpy": np.__version__, "scipy": scipy.__version__,
                        "device": "CPU"},
        "component_source_test_tool_sha256": _component_digest(),
    }
    artifact = output / "observed_traces.json"
    _json(artifact, result)
    observed_export_seconds = (time.perf_counter() - start -
                               source_read_seconds - row_index_seconds)
    receipt = {"status": "pass", "source_sha256": source_digest,
               "component_source_test_tool_sha256": _component_digest(),
               "observed_traces_sha256": _digest(artifact),
               "row_index_sha256": _digest(row_index_path),
               "source_bytes": source.stat().st_size,
               "source_read_seconds": source_read_seconds,
               "row_index_seconds": row_index_seconds,
               "observed_export_seconds": observed_export_seconds,
               "wall_seconds_before_receipt": time.perf_counter() - start,
               "output_bytes_before_receipt": artifact.stat().st_size + row_index_path.stat().st_size,
               "condition_count": len(conditions),
               "source_row_count": len(values),
               "commands": [".venv/Scripts/python.exe tools/prepare_nfkb_observed.py --output <new-dir>"],
               "limitations": ["No experimental run/chamber identifiers in the inspected matrix",
                               "No row-aligned join to author-derived featmat",
                               "Author normalization procedure and physical doses unresolved"]}
    _json(output / "receipt.json", receipt)
    return {"status": "pass", "observed_traces": str(artifact),
            "row_index": str(row_index_path),
            "conditions": len(conditions), "source_rows": len(values),
            "nonfinite": nonfinite_counts,
            "component_source_test_tool_sha256": _component_digest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=ROOT / "data/scmat_sequentialstim.mat")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples-per-condition", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(export(args.source.resolve(), args.output.resolve(),
                            samples_per_condition=args.samples_per_condition),
                     indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
