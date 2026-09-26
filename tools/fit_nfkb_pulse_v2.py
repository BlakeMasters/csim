#!/usr/bin/env python3
"""Exploratory delayed-pulse reporter fit after v1 evaluation was exposed."""
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
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from fit_nfkb_reporter import _validated_conditions
from cellsim_v2.nfkb_pulse import pulse_design, pulse_feature_names

EARLY_MIN = (18.0, 30.0, 42.0)
LATE_MIN = (60.0, 90.0)
PRIOR_MIN = (90.0, 180.0)
RIDGE = (0.001, 0.1, 1.0)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


def _design(item: dict, early: float, late: float, prior: float, np):
    return np.asarray(pulse_design(item["stimulus_codes"],
                                    item["dose_tier_code"],
                                    early, late, prior), dtype=np.float64)


def _mean_error(records: list[dict], weights, early: float,
                late: float, prior: float, np) -> float:
    return float(np.mean([
        float(np.abs(_design(item, early, late, prior, np)[1:] @ weights -
                        np.asarray(item["observed"]["mean"][1:], dtype=np.float64)).mean())
        for item in records]))


def fit(observed_path: Path, demo_overlay_path: Path,
        v1_comparison_path: Path, output: Path) -> dict:
    import numpy as np

    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    start = time.perf_counter()
    observed_sha = _digest(observed_path)
    overlay_sha = _digest(demo_overlay_path)
    v1_sha = _digest(v1_comparison_path)
    observed = json.loads(observed_path.read_text(encoding="utf-8"))
    demo_overlay = json.loads(demo_overlay_path.read_text(encoding="utf-8"))
    v1 = json.loads(v1_comparison_path.read_text(encoding="utf-8"))
    development, validation, _ = _validated_conditions(observed)
    if demo_overlay["schema_version"] != "cellsim-nfkb-demo-overlay/1":
        raise ValueError("unexpected demo overlay schema")
    if demo_overlay["source"]["sha256"] != observed["source"]["sha256"]:
        raise ValueError("source matrix differs across artifacts")
    load_seconds = time.perf_counter() - start
    search_start = time.perf_counter()
    attempts = []
    for early in EARLY_MIN:
        for late in LATE_MIN:
            if late <= early:
                continue
            for prior in PRIOR_MIN:
                x = np.vstack([_design(item, early, late, prior, np)
                               for item in development])
                y = np.concatenate([np.asarray(item["observed"]["mean"], dtype=np.float64)
                                    for item in development])
                gram = x.T @ x
                rhs = x.T @ y
                for ridge in RIDGE:
                    attempt_start = time.perf_counter()
                    attempt = {"tau_early_min": early, "tau_late_min": late,
                               "tau_prior_min": prior, "ridge": ridge}
                    try:
                        penalty = np.eye(gram.shape[0], dtype=np.float64) * ridge
                        penalty[0, 0] = 0.0
                        weights = np.linalg.solve(gram + penalty, rhs)
                        if not np.isfinite(weights).all():
                            raise ValueError("nonfinite weights")
                        attempt["weights"] = weights.tolist()
                        attempt["development_mae"] = _mean_error(
                            development, weights, early, late, prior, np)
                        attempt["validation_mae"] = _mean_error(
                            validation, weights, early, late, prior, np)
                        attempt["status"] = "pass"
                    except (ValueError, np.linalg.LinAlgError) as exc:
                        attempt["status"] = "failed"
                        attempt["error"] = str(exc)
                    attempt["fit_validation_seconds"] = time.perf_counter() - attempt_start
                    attempts.append(attempt)
    accepted = [a for a in attempts if a["status"] == "pass"]
    if not accepted:
        raise ValueError("all pulse candidates failed")
    selected = min(accepted, key=lambda a: (
        a["validation_mae"], a["tau_early_min"], a["tau_late_min"],
        a["tau_prior_min"], a["ridge"]))
    search_seconds = time.perf_counter() - search_start
    component = hashlib.sha256(
        (ROOT / "src/cellsim_v2/nfkb_pulse.py").read_bytes() +
        (ROOT / "tests/test_nfkb_pulse.py").read_bytes() +
        Path(__file__).read_bytes()).hexdigest()
    frozen = {
        "schema_version": "cellsim-nfkb-exploratory-pulse-v2/1",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_after_validation_for_posthoc_evaluation",
        "reason_not_fresh_holdout": "v1 evaluation outcomes and an evaluation chart were already exposed before this model family was designed",
        "observed_artifact_sha256": observed_sha,
        "source_matrix_sha256": observed["source"]["sha256"],
        "feature_names": list(pulse_feature_names()),
        "selected": {key: selected[key] for key in (
            "tau_early_min", "tau_late_min", "tau_prior_min", "ridge",
            "weights", "development_mae", "validation_mae")},
        "component_source_test_tool_sha256": component,
    }
    frozen_path = output / "frozen_pulse_candidate.json"
    _write(frozen_path, frozen)
    frozen_sha = _digest(frozen_path)

    posthoc_start = time.perf_counter()
    _, _, exposed_evaluation = _validated_conditions(observed)
    weights = np.asarray(selected["weights"], dtype=np.float64)
    metrics = {}
    for cohort, records in (("development", development),
                            ("validation", validation),
                            ("posthoc_exposed_evaluation", exposed_evaluation)):
        per_condition = []
        for item in records:
            pred = _design(item, selected["tau_early_min"],
                           selected["tau_late_min"],
                           selected["tau_prior_min"], np) @ weights
            truth = np.asarray(item["observed"]["mean"], dtype=np.float64)
            per_condition.append({"condition_id": item["condition_id"],
                                  "sequence_key": item["sequence_key"],
                                  "dose_tier": item["dose_tier"],
                                  "mae": float(np.abs(pred[1:] - truth[1:]).mean())})
        metrics[cohort] = {"condition_count": len(records),
                           "mae": float(np.mean([x["mae"] for x in per_condition])),
                           "per_condition": per_condition}
    for item in demo_overlay["conditions"]:
        if item["split"] == "control":
            item["pulse_v2_prediction"] = None
            continue
        item["pulse_v2_prediction"] = (
            _design(item, selected["tau_early_min"],
                    selected["tau_late_min"],
                    selected["tau_prior_min"], np) @ weights).tolist()
    demo_overlay["schema_version"] = "cellsim-nfkb-demo-overlay-pulse-v2/1"
    demo_overlay["pulse_v2_frozen_sha256"] = frozen_sha
    demo_overlay["pulse_v2_scope"] = frozen["reason_not_fresh_holdout"]
    posthoc_seconds = time.perf_counter() - posthoc_start
    if _digest(frozen_path) != frozen_sha:
        raise RuntimeError("frozen pulse candidate changed")

    overlay_path = output / "pulse_demo_overlay.json"
    _write(overlay_path, demo_overlay)
    summary = {
        "schema_version": "cellsim-nfkb-exploratory-pulse-comparison/1",
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_family": "two delayed gamma-shaped onset pulses, dose/ligand step, and prior-ligand memory interactions",
        "reason_exploratory": frozen["reason_not_fresh_holdout"],
        "selection_cohorts": {"development": len(development),
                              "validation": len(validation)},
        "candidate_count": len(attempts),
        "failed_candidate_count": len(attempts) - len(accepted),
        "selected": {key: selected[key] for key in (
            "tau_early_min", "tau_late_min", "tau_prior_min", "ridge",
            "development_mae", "validation_mae")},
        "metrics": metrics,
        "v1_frozen_reference": {
            "comparison_sha256": v1_sha,
            "validation_mae": v1["metrics"]["validation"]["state_space_mae"],
            "posthoc_exposed_evaluation_mae": v1["metrics"]["evaluation"]["state_space_mae"]},
        "source_matrix_sha256": observed["source"]["sha256"],
        "observed_artifact_sha256": observed_sha,
        "input_demo_overlay_sha256": overlay_sha,
        "frozen_pulse_candidate_sha256": frozen_sha,
        "component_source_test_tool_sha256": component,
        "cost": {"load_seconds": load_seconds,
                 "candidate_fit_and_validation_seconds": search_seconds,
                 "posthoc_scoring_and_overlay_seconds": posthoc_seconds,
                 "failed_candidate_count": len(attempts) - len(accepted),
                 "device": "CPU", "python": sys.version,
                 "numpy": np.__version__, "platform": platform.platform()},
        "limitations": [
            "Evaluation orders were already exposed before family design; posthoc only",
            "Condition-mean sequence split has no independently identified runs/chambers",
            "No molecular-kinetic, drug-efficacy or stochastic-law interpretation",
            "Pulse basis is a phenomenological response proxy",
        ],
    }
    summary_path = output / "comparison.json"
    _write(summary_path, summary)
    attempts_path = output / "candidate_search.json"
    _write(attempts_path, attempts)
    receipt = {"status": "pass", "frozen_pulse_candidate_sha256": frozen_sha,
               "comparison_sha256": _digest(summary_path),
               "pulse_demo_overlay_sha256": _digest(overlay_path),
               "candidate_search_sha256": _digest(attempts_path),
               "component_source_test_tool_sha256": component,
               "candidate_count": len(attempts),
               "failed_candidate_count": len(attempts) - len(accepted),
               "output_bytes": sum(p.stat().st_size for p in output.iterdir()
                                   if p.is_file()),
               "total_seconds_before_receipt": time.perf_counter() - start}
    _write(output / "receipt.json", receipt)
    return {"status": "pass", "comparison": str(summary_path),
            "overlay": str(overlay_path), "candidate_count": len(attempts),
            "validation_mae": metrics["validation"]["mae"],
            "posthoc_exposed_evaluation_mae": metrics[
                "posthoc_exposed_evaluation"]["mae"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed", type=Path, required=True)
    parser.add_argument("--demo-overlay", type=Path, required=True)
    parser.add_argument("--v1-comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(fit(args.observed.resolve(), args.demo_overlay.resolve(),
                         args.v1_comparison.resolve(), args.output.resolve()),
                     indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
