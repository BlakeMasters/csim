#!/usr/bin/env python3
"""Fit a small causal reporter state-space basis on frozen sequence groups.

The fitted states are reduced response coordinates, not molecular NF-κB/IκB
kinetic parameters. No physical-dose or drug response is inferred. The CLI
requires the optional NumPy reader environment and a create-only output dir.
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
    TIME_MIN, causal_design, current_only_design, feature_names,
    frozen_sequence_split,
)

FAST_CANDIDATES_MIN = (12.0, 24.0, 36.0, 48.0)
SLOW_CANDIDATES_MIN = (90.0, 180.0, 360.0)
RIDGE_CANDIDATES = (0.001, 0.1, 1.0, 10.0)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component_digest() -> str:
    digest = hashlib.sha256()
    for relative in ("src/cellsim_v2/nfkb_observed.py",
                     "tests/test_nfkb_observed.py",
                     "tools/prepare_nfkb_observed.py",
                     "tools/fit_nfkb_reporter.py"):
        digest.update(relative.encode("ascii"))
        digest.update((ROOT / relative).read_bytes())
    return digest.hexdigest()


def _write(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def _validated_conditions(observed: dict) -> tuple[list[dict], list[dict], list[dict]]:
    if observed.get("schema_version") != "cellsim-nfkb-observed-traces/1":
        raise ValueError("unsupported observed-trace schema")
    expected = frozen_sequence_split()
    groups = {"development": [], "validation": [], "evaluation": []}
    conditions = observed["conditions"]
    if len(conditions) != 75:
        raise ValueError("75 observed conditions required")
    for condition in conditions:
        key = condition["sequence_key"]
        group = condition["split"]
        if key is None:
            if group != "control":
                raise ValueError("FM control split mismatch")
            continue
        if group != expected[key]:
            raise ValueError("frozen sequence split changed")
        mean = condition["observed"]["mean"]
        if len(mean) != len(TIME_MIN) or any(value is None for value in mean):
            raise ValueError("condition mean has an unsupported missing point")
        if condition["observed"]["time_min"] != list(TIME_MIN):
            raise ValueError("time grid changed")
        groups[group].append(condition)
    if [len(groups[key]) for key in groups] != [48, 12, 12]:
        raise ValueError("expected 48/12/12 noncontrol dose conditions")
    return groups["development"], groups["validation"], groups["evaluation"]


def _design(condition: dict, kind: str, fast: float, slow: float | None):
    codes = condition["stimulus_codes"]
    dose = condition["dose_tier_code"]
    if kind == "state_space":
        return causal_design(codes, dose, fast, slow)
    return current_only_design(codes, dose, fast)


def _matrix(records: list[dict], kind: str, fast: float, slow: float | None,
            np):
    designs = [np.asarray(_design(item, kind, fast, slow), dtype=np.float64)
               for item in records]
    truth = [np.asarray(item["observed"]["mean"], dtype=np.float64)
             for item in records]
    return np.vstack(designs), np.concatenate(truth)


def _fit(records: list[dict], kind: str, fast: float, slow: float | None,
         ridge: float, np):
    x, y = _matrix(records, kind, fast, slow, np)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("nonfinite training design or target")
    gram = x.T @ x
    penalty = np.eye(gram.shape[0], dtype=np.float64) * ridge
    penalty[0, 0] = 0.0  # Leave the overall offset unpenalized.
    weights = np.linalg.solve(gram + penalty, x.T @ y)
    if not np.isfinite(weights).all():
        raise ValueError("nonfinite fitted weights")
    return weights


def _predict(condition: dict, kind: str, fast: float,
             slow: float | None, weights, np):
    return np.asarray(_design(condition, kind, fast, slow),
                      dtype=np.float64) @ weights


def _mae(records: list[dict], kind: str, fast: float,
         slow: float | None, weights, np) -> float:
    # Exclude t=0 because the no-change control sees that first observation.
    errors = []
    for condition in records:
        truth = np.asarray(condition["observed"]["mean"], dtype=np.float64)
        pred = _predict(condition, kind, fast, slow, weights, np)
        errors.append(float(np.abs(truth[1:] - pred[1:]).mean()))
    return float(np.mean(errors))


def _search(development: list[dict], validation: list[dict],
            kind: str, np) -> tuple[dict, list[dict]]:
    candidate_records = []
    slow_values = SLOW_CANDIDATES_MIN if kind == "state_space" else (None,)
    for fast in FAST_CANDIDATES_MIN:
        for slow in slow_values:
            for ridge in RIDGE_CANDIDATES:
                start = time.perf_counter()
                record = {"kind": kind, "tau_fast_min": fast,
                          "tau_slow_min": slow, "ridge": ridge}
                try:
                    weights = _fit(development, kind, fast, slow, ridge, np)
                    record["development_mae"] = _mae(
                        development, kind, fast, slow, weights, np)
                    record["validation_mae"] = _mae(
                        validation, kind, fast, slow, weights, np)
                    record["weights"] = weights.tolist()
                    record["status"] = "pass"
                except (ValueError, np.linalg.LinAlgError) as exc:
                    record["status"] = "failed"
                    record["error"] = str(exc)
                record["fit_and_validation_seconds"] = time.perf_counter() - start
                candidate_records.append(record)
    accepted = [record for record in candidate_records if record["status"] == "pass"]
    if not accepted:
        raise ValueError(f"all {kind} candidates failed")
    selected = min(accepted, key=lambda record: (
        record["validation_mae"], record["tau_fast_min"],
        record["tau_slow_min"] or 0, record["ridge"]))
    return selected, candidate_records


def fit(observed_path: Path, output: Path) -> dict:
    import numpy as np

    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    start_total = time.perf_counter()
    observed_sha = _digest(observed_path)
    observed_receipt = json.loads((observed_path.parent / "receipt.json").read_text(
        encoding="utf-8"))
    if observed_receipt["observed_traces_sha256"] != observed_sha:
        raise ValueError("observed artifact does not match its receipt")
    observed = json.loads(observed_path.read_text(encoding="utf-8"))
    development, validation, _ = _validated_conditions(observed)
    load_seconds = time.perf_counter() - start_total

    search_start = time.perf_counter()
    full, full_search = _search(development, validation, "state_space", np)
    control, control_search = _search(development, validation, "current_only", np)
    search_seconds = time.perf_counter() - search_start
    component_sha = _component_digest()
    frozen = {
        "schema_version": "cellsim-nfkb-frozen-state-space/1",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "observed_artifact_sha256": observed_sha,
        "source_matrix_sha256": observed["source"]["sha256"],
        "component_source_test_tool_sha256": component_sha,
        "training_unit": "condition mean trace; equal condition weights",
        "development_conditions": [item["condition_id"] for item in development],
        "validation_conditions": [item["condition_id"] for item in validation],
        "heldout_unit": "four-ligand order across all dose tiers",
        "feature_names": list(feature_names()),
        "model": {key: full[key] for key in (
            "kind", "tau_fast_min", "tau_slow_min", "ridge", "weights",
            "development_mae", "validation_mae")},
        "current_only_control": {key: control[key] for key in (
            "kind", "tau_fast_min", "tau_slow_min", "ridge", "weights",
            "development_mae", "validation_mae")},
        "scope": "Causal reporter basis; coefficients have no molecular-kinetic meaning",
    }
    frozen_path = output / "frozen_candidate.json"
    _write(frozen_path, frozen)  # Immutable candidate written before evaluation targets are used.
    frozen_sha = _digest(frozen_path)

    eval_start = time.perf_counter()
    inference_seconds = 0.0
    # No candidate selection, refitting or coefficient edits below this point.
    _, _, evaluation = _validated_conditions(observed)
    model_weights = np.asarray(full["weights"], dtype=np.float64)
    control_weights = np.asarray(control["weights"], dtype=np.float64)
    cohorts = {"development": development, "validation": validation,
               "evaluation": evaluation}
    metrics = {}
    for name, records in cohorts.items():
        full_errors = []
        control_errors = []
        no_change_errors = []
        for condition in records:
            truth = np.asarray(condition["observed"]["mean"], dtype=np.float64)
            inference_start = time.perf_counter()
            full_pred = _predict(condition, "state_space",
                                 full["tau_fast_min"], full["tau_slow_min"],
                                 model_weights, np)
            control_pred = _predict(condition, "current_only",
                                    control["tau_fast_min"], None,
                                    control_weights, np)
            inference_seconds += time.perf_counter() - inference_start
            full_errors.append(float(np.abs(truth[1:] - full_pred[1:]).mean()))
            control_errors.append(float(np.abs(truth[1:] - control_pred[1:]).mean()))
            no_change_errors.append(float(np.abs(truth[1:] - truth[0]).mean()))
        metrics[name] = {
            "condition_count": len(records),
            "state_space_mae": float(np.mean(full_errors)),
            "current_only_mae": float(np.mean(control_errors)),
            "no_change_mae": float(np.mean(no_change_errors)),
            "per_condition": [
                {"condition_id": condition["condition_id"],
                 "sequence_key": condition["sequence_key"],
                 "dose_tier": condition["dose_tier"],
                 "state_space_mae": full_errors[i],
                 "current_only_mae": control_errors[i],
                 "no_change_mae": no_change_errors[i]}
                for i, condition in enumerate(records)],
        }

    overlay = dict(observed)
    overlay["schema_version"] = "cellsim-nfkb-observed-model-overlay/1"
    overlay["frozen_candidate_sha256"] = frozen_sha
    overlay["model_scope"] = frozen["scope"]
    for condition in overlay["conditions"]:
        if condition["split"] == "control":
            continue
        inference_start = time.perf_counter()
        model_pred = _predict(condition, "state_space",
                              full["tau_fast_min"], full["tau_slow_min"],
                              model_weights, np)
        current_pred = _predict(condition, "current_only",
                                control["tau_fast_min"], None,
                                control_weights, np)
        inference_seconds += time.perf_counter() - inference_start
        condition["model_prediction"] = model_pred.tolist()
        condition["current_only_prediction"] = current_pred.tolist()
        condition["no_change_prediction"] = [
            condition["observed"]["mean"][0]] * len(TIME_MIN)
    evaluation_seconds = time.perf_counter() - eval_start
    if _digest(frozen_path) != frozen_sha:
        raise RuntimeError("frozen candidate changed during evaluation")

    persist_start = time.perf_counter()
    overlay_path = output / "comparison_overlay.json"
    _write(overlay_path, overlay)
    summary = {
        "schema_version": "cellsim-nfkb-model-comparison/1",
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "observable": observed["observable"],
        "source": observed["source"],
        "split": observed["split"],
        "metric": "mean absolute error of condition mean normalized reporter, minutes 6–492; equal weight per condition",
        "selected": {"state_space": {key: full[key] for key in (
                         "tau_fast_min", "tau_slow_min", "ridge", "validation_mae")},
                     "current_only": {key: control[key] for key in (
                         "tau_fast_min", "ridge", "validation_mae")}},
        "metrics": metrics,
        "candidate_counts": {
            "state_space": len(full_search),
            "current_only": len(control_search),
            "failed": sum(item["status"] != "pass"
                          for item in full_search + control_search),
        },
        "frozen_candidate_sha256": frozen_sha,
        "observed_artifact_sha256": observed_sha,
        "component_source_test_tool_sha256": component_sha,
        "cost": {"load_seconds": load_seconds,
                 "source_observation_generation_seconds": observed_receipt["wall_seconds_before_receipt"],
                 "source_bytes": observed_receipt["source_bytes"],
                 "observed_export_bytes": observed_receipt["output_bytes_before_receipt"],
                 "fit_and_validation_seconds": search_seconds,
                 "evaluation_and_overlay_seconds": evaluation_seconds,
                 "prediction_inference_seconds_within_evaluation_and_overlay": inference_seconds,
                 "device": "CPU",
                 "python": sys.version,
                 "numpy": np.__version__,
                 "platform": platform.platform()},
        "limitations": [
            "Sequence-order holdout only; experimental run/chamber identifiers absent",
            "No independent biological validation or calibrated molecular kinetics",
            "Author normalization and physical dose values unresolved",
            "Current-only and state-space predictions use known ligand schedule; drug effects unmeasured",
            "No-change uses the first heldout observation; other models do not",
            "The split and candidate freeze are procedural, not access controlled",
        ],
    }
    summary_path = output / "comparison.json"
    _write(summary_path, summary)
    candidate_path = output / "candidate_search.json"
    _write(candidate_path, {"state_space": full_search,
                            "current_only": control_search})
    persist_seconds = time.perf_counter() - persist_start
    receipt = {"status": "pass", "observed_artifact_sha256": observed_sha,
               "frozen_candidate_sha256": frozen_sha,
               "comparison_sha256": _digest(summary_path),
               "comparison_overlay_sha256": _digest(overlay_path),
               "candidate_search_sha256": _digest(candidate_path),
               "component_source_test_tool_sha256": component_sha,
               "candidate_count": len(full_search) + len(control_search),
               "failed_candidate_count": summary["candidate_counts"]["failed"],
               "persist_seconds": persist_seconds,
               "output_bytes": sum(path.stat().st_size for path in output.iterdir()
                                   if path.is_file()),
               "command": ".venv/Scripts/python.exe tools/fit_nfkb_reporter.py --observed <observed_traces.json> --output <new-dir>"}
    _write(output / "receipt.json", receipt)
    return {"status": "pass", "comparison": str(summary_path),
            "overlay": str(overlay_path),
            "frozen_candidate": str(frozen_path),
            "evaluation": {key: metrics["evaluation"][key] for key in (
                "state_space_mae", "current_only_mae", "no_change_mae")},
            "candidate_count": len(full_search) + len(control_search),
            "failed_candidate_count": summary["candidate_counts"]["failed"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(fit(args.observed.resolve(), args.output.resolve()),
                     indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
