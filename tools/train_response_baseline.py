#!/usr/bin/env python3
"""Fit, select, freeze and evaluate small synthetic response baselines offline.

Targets are teacher-forced one-step intracellular amounts from the fixed uptake
fixture. Predictions are endpoints, not conservative simulation updates. This
run establishes no biological accuracy, rollout stability, treatment effect,
independent-solver agreement or computational savings.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from cellsim_v2.physical_dataset import load_physical_dataset
from cellsim_v2.response import fit_models, predict
from cellsim_v2.training import dataset_digest, freeze_campaign, validate_dataset, verify_campaign
from prepare_training_fixture import prepare, source_fingerprint


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"nonfinite JSON value: {value}")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def _read_json(raw: bytes):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                      parse_constant=_reject_constant, parse_float=_finite_float)


def _write_json(path: Path, value: dict, *, replace=False):
    with path.open("w" if replace else "x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _validate_config(config: dict) -> dict:
    if type(config) is not dict or set(config) != {"schema_version", "knn_neighbors"}:
        raise ValueError("response config requires only schema_version and knn_neighbors")
    if config["schema_version"] != "1":
        raise ValueError("response config schema_version must be '1'")
    neighbors = config["knn_neighbors"]
    if type(neighbors) is not list or not neighbors:
        raise ValueError("knn_neighbors must be a nonempty array")
    if any(type(k) is not int or k <= 0 for k in neighbors) or len(set(neighbors)) != len(neighbors):
        raise ValueError("knn_neighbors must contain unique positive integers")
    return {"schema_version": "1", "knn_neighbors": sorted(neighbors)}


def _artifact(path: Path, root: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _rebase_manifest(manifest: dict, root: Path) -> dict:
    """Campaign declarations reference dataset files from the output root.

    The original dataset/manifest.json remains the ingestion manifest, whose
    payload artifact_path fields are relative to the dataset directory.
    """
    rebased = json.loads(json.dumps(manifest, allow_nan=False))
    for artifact in rebased["artifacts"]:
        artifact["path"] = "dataset/" + artifact["path"]
    for sample in rebased["samples"]:
        sample["artifact_path"] = "dataset/" + sample["artifact_path"]
    return validate_dataset(rebased, root)


def _error_metrics(errors: list[float]) -> dict:
    if not errors:
        raise ValueError("evaluation requires nonempty rows")
    absolute = [abs(value) for value in errors]
    if any(not math.isfinite(value) for value in absolute):
        raise ValueError("evaluation error must be finite")
    maximum = max(absolute)
    if maximum == 0:
        mae, rmse = 0.0, 0.0
    else:
        scaled = [value / maximum for value in absolute]
        mae = maximum * (math.fsum(scaled) / len(scaled))
        rmse = maximum * math.sqrt(math.fsum(value * value for value in scaled) / len(scaled))
        if mae == 0 or rmse == 0:
            raise ValueError("positive evaluation metric underflow is unsupported")
    return {"row_count": len(errors), "mae_mol": mae, "rmse_mol": rmse,
            "max_absolute_error_mol": maximum}


def _score(rows: list[dict], predictions: list[dict]) -> dict:
    if len(rows) != len(predictions) or not rows:
        raise ValueError("one prediction is required for every evaluation row")
    grouped, errors, outside = {}, [], 0
    for row, prediction in zip(rows, predictions):
        error = prediction["amount_mol"] - row["targets"]["cell_amount_mol"]
        errors.append(error)
        group = grouped.setdefault(row["condition_id"], {"errors": [], "outside": 0})
        group["errors"].append(error)
        group["outside"] += int(prediction["outside_training_range"])
        outside += int(prediction["outside_training_range"])
    per_condition = {
        condition: {**_error_metrics(group["errors"]),
                    "outside_training_range_count": group["outside"]}
        for condition, group in sorted(grouped.items())
    }
    # The mean of nonnegative condition MAEs is computed with scaled arithmetic.
    condition_maes = [metrics["mae_mol"] for metrics in per_condition.values()]
    macro_mae = _error_metrics(condition_maes)["mae_mol"]
    return {"aggregate": {**_error_metrics(errors), "condition_count": len(grouped),
                           "macro_condition_mae_mol": macro_mae,
                           "outside_training_range_count": outside},
            "per_condition": per_condition}


def run(output: Path, config: dict | None = None, *, config_path: Path | None = None,
        fixture_config_path: Path | None = None) -> dict:
    """Create one new dataset, fit on train, select on validation, then test once.

    Existing output directories are refused. All models, including fixed
    controls, are frozen before test rows are passed to prediction/evaluation.
    Shared JSONL is parsed during development ingestion for integrity checks;
    split filtering is workflow separation, not filesystem access security.
    Failures retain outputs and a results.json failure record.
    """
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    summary = {
        "status": "running", "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(), "device": "CPU",
        "command_template": "python tools/train_response_baseline.py --output NEWDIR [--config PATH] [--fixture-config PATH]",
        "process_argv": list(sys.argv), "source_test_tool_sha256": source_fingerprint(),
        "model_trained": False, "biological_validation": False, "qualification": "unqualified",
        "evaluation_scope": "teacher-forced one-step synthetic endpoint predictions",
        "costs_seconds": {key: 0.0 for key in (
            "dataset_preparation", "development_ingestion", "fit", "selection",
            "freeze_and_verify", "test_ingestion", "evaluation", "persistence")},
        "fixture_costs_seconds": None,
        "cost_accounting_scope": (
            "Runner phase timings are disjoint. Nested fixture costs are reported separately and overlap "
            "dataset_preparation, so do not add them to runner phases. Total starts after output-directory "
            "creation and excludes imports, interpreter startup, argument parsing and final result/failure report writes. "
            "Failed-attempt total is nonadditive. Memory/storage size and amortized savings are not measured."),
    }

    @contextmanager
    def timed(stage):
        begin = time.perf_counter()
        try:
            yield
        finally:
            summary["costs_seconds"][stage] += time.perf_counter() - begin

    def persist(name, value):
        with timed("persistence"):
            _write_json(output / name, value)

    def requested_json(path, retained_name):
        raw = Path(path).read_bytes()
        with timed("persistence"):
            with (output / retained_name).open("xb") as stream:
                stream.write(raw)
        return _read_json(raw)

    _write_json(output / "results.json", summary)
    try:
        if config is not None and config_path is not None:
            raise ValueError("supply config or config_path, not both")
        if config is None:
            config = requested_json(config_path or ROOT / "configs/response_baseline.example.json",
                                    "requested_response_config.json")
        config = _validate_config(config)
        persist("response_config.json", config)
        fixture_config = requested_json(fixture_config_path or ROOT / "configs/training_fixture.example.json",
                                        "requested_fixture_config.json")
        with timed("dataset_preparation"):
            fixture_summary = prepare(output / "dataset", config=fixture_config)
        summary["fixture_costs_seconds"] = fixture_summary["costs_seconds"]
        summary["generated_sample_count"] = fixture_summary["sample_count"]
        dataset_path = output / "dataset" / "manifest.json"
        with timed("development_ingestion"):
            development = load_physical_dataset(dataset_path, splits=("train", "validation"))
            physical_manifest = development["manifest"]
            train_rows = [row for row in development["rows"] if row["split"] == "train"]
            validation_rows = [row for row in development["rows"] if row["split"] == "validation"]
            campaign_manifest = _rebase_manifest(physical_manifest, output)
        summary["physical_dataset_sha256"] = dataset_digest(physical_manifest)
        summary["campaign_dataset_sha256"] = dataset_digest(campaign_manifest)
        summary["train_row_count"] = len(train_rows)
        summary["validation_row_count"] = len(validation_rows)
        persist("campaign_manifest.json", campaign_manifest)
        with timed("fit"):
            models, preprocessing = fit_models(train_rows, ks=tuple(config["knn_neighbors"]))
        summary["model_trained"] = True
        candidate_ids = ["no_change", "training_mean_increment",
                         *[f"knn_k{k}" for k in config["knn_neighbors"]]]
        control_ids = ["no_change", "training_mean_increment", "synthetic_uptake_law"]
        selection_rule = {
            "split": "validation", "metric": "macro_condition_mae_mol",
            "definition": "unweighted mean of per-condition mean absolute endpoint errors",
            "candidate_ids": candidate_ids,
            "tie_break": "declared candidate order: no_change, training_mean_increment, ascending k",
            "excluded_positive_control": "synthetic_uptake_law",
        }
        with timed("selection"):
            validation_scores = {}
            for model_id in [*candidate_ids, "synthetic_uptake_law"]:
                predictions = [predict(models[model_id], preprocessing, row) for row in validation_rows]
                validation_scores[model_id] = _score(validation_rows, predictions)
            selected_id = min(candidate_ids, key=lambda name: (
                validation_scores[name]["aggregate"]["macro_condition_mae_mol"], candidate_ids.index(name)))
        summary["selected_model_id"] = selected_id
        persist("validation_scores.json", {"selection_rule": selection_rule,
                "selected_model_id": selected_id, "scores": validation_scores,
                "positive_control_scope": "Exact synthetic generator law; excluded from selection."})
        bundle = {
            "schema_version": "1", "models": models, "selected_model_id": selected_id,
            "control_ids": control_ids, "selection_rule": selection_rule, "config": config,
            "source_test_tool_sha256": summary["source_test_tool_sha256"],
            "physical_dataset_sha256": summary["physical_dataset_sha256"],
            "campaign_dataset_sha256": summary["campaign_dataset_sha256"],
            "fit_scope": {"split": "train", "sample_ids": sorted(row["sample_id"] for row in train_rows),
                          "condition_ids": sorted({row["condition_id"] for row in train_rows}),
                          "training_row_count": len(train_rows), "preprocessing_fit_split": "train",
                          "method": "memorized k-nearest-neighbor increments and simple controls"},
            "evaluation_scope": summary["evaluation_scope"],
            "biological_validation": False, "qualification": "unqualified",
        }
        persist("model_bundle.json", bundle)
        persist("preprocessing.json", preprocessing)
        evaluation_contract = {
            "metric": "macro_condition_mae_mol", "observable_id": "intracellular_amount_next",
            "unit": "mol", "baseline_ids": control_ids,
            "metadata": {"selection": selection_rule, "test_split": "test",
                         "reported_metrics": ["row_mae_mol", "row_rmse_mol", "maximum_absolute_error_mol",
                                              "per_condition_metrics", "macro_condition_mae_mol",
                                              "outside_training_range_count"],
                         "acceptance_tolerance": None, "qualification": "unqualified",
                         "evaluation_scope": summary["evaluation_scope"],
                         "positive_control_scope": "Same synthetic generator law; no independent evidence."},
        }
        with timed("freeze_and_verify"):
            frozen = freeze_campaign(output / "campaign.json", manifest=campaign_manifest, root=output,
                candidate_id=selected_id, model_artifact=_artifact(output / "model_bundle.json", output),
                preprocessing_artifact=_artifact(output / "preprocessing.json", output),
                evaluation=evaluation_contract)
        frozen_digest = frozen["campaign_sha256"]
        summary["campaign_sha256"] = frozen_digest
        persist("freeze_receipt.json", {"campaign_sha256": frozen_digest,
                "retention_instruction": "Keep this original digest in an independently trusted record.",
                "not_a_filesystem_lock": True})
        with timed("freeze_and_verify"):
            verify_campaign(output / "campaign.json", manifest=campaign_manifest, root=output,
                            expected_digest=frozen_digest)
            frozen_bundle = _read_json((output / "model_bundle.json").read_bytes())
            frozen_preprocessing = _read_json((output / "preprocessing.json").read_bytes())
        with timed("test_ingestion"):
            testing = load_physical_dataset(dataset_path, splits=("test",))
            if dataset_digest(testing["manifest"]) != summary["physical_dataset_sha256"]:
                raise ValueError("physical dataset changed after candidate freeze")
            test_rows = testing["rows"]
        with timed("evaluation"):
            evaluated_ids = list(dict.fromkeys([frozen_bundle["selected_model_id"], *frozen_bundle["control_ids"]]))
            test_scores, prediction_rows = {}, []
            for model_id in evaluated_ids:
                predictions = [predict(frozen_bundle["models"][model_id], frozen_preprocessing, row)
                               for row in test_rows]
                test_scores[model_id] = _score(test_rows, predictions)
                for row, prediction in zip(test_rows, predictions):
                    prediction_rows.append({"sample_id": row["sample_id"], "condition_id": row["condition_id"],
                        "trajectory_id": row["trajectory_id"], "experimental_unit_id": row["experimental_unit_id"],
                        "cell_id": row["cell_id"], "split": "test", "model_id": model_id,
                        "selected_candidate": model_id == frozen_bundle["selected_model_id"],
                        "positive_control": model_id == "synthetic_uptake_law",
                        "current_amount_mol": row["inputs"]["cell_amount_mol"],
                        "target_amount_mol": row["targets"]["cell_amount_mol"],
                        "predicted_amount_mol": prediction["amount_mol"],
                        "predicted_increment_mol": prediction["increment_mol"],
                        "error_mol": prediction["amount_mol"] - row["targets"]["cell_amount_mol"],
                        "outside_training_range": prediction["outside_training_range"]})
        with timed("freeze_and_verify"):
            verify_campaign(output / "campaign.json", manifest=campaign_manifest, root=output,
                            expected_digest=frozen_digest)
        with timed("persistence"):
            with (output / "predictions.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
                for row in prediction_rows:
                    stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        persist("evaluation.json", {
            "campaign_sha256": frozen_digest, "selected_model_id": frozen_bundle["selected_model_id"],
            "test_row_count": len(test_rows), "test_condition_count": len({row["condition_id"] for row in test_rows}),
            "scores": test_scores, "evaluation_scope": summary["evaluation_scope"],
            "endpoint_and_increment_errors": "Algebraically equal given observed current amount; subtraction may differ by roundoff.",
            "positive_control_scope": "Exact synthetic generator law; no independent solver or biology evidence.",
            "outside_training_range_scope": "Feature range diagnostic; not an error bound or qualification.",
            "acceptance_tolerance": None, "biological_validation": False, "qualification": "unqualified",
            "limitations": ["Tiny synthetic grouped holdout; no statistical biological-generalization claim",
                            "Observed inputs supplied at each step; no learned rollout",
                            "Endpoint predictions do not debit fields or establish conservation",
                            "No reward learning, policy learning or causal treatment-effect claim"],
        })
        summary["test_row_count"] = len(test_rows)
        summary["evaluated_model_ids"] = evaluated_ids
        summary["campaign_verified_before_and_after_evaluation"] = True
        summary["status"] = "pass"
        summary["total_wall_seconds_before_final_report"] = time.perf_counter() - started
        _write_json(output / "results.json", summary, replace=True)
        return summary
    except Exception as error:
        summary["status"] = "failed"
        summary["error"] = f"{type(error).__name__}: {error}"
        summary["failed_attempt_total_seconds"] = time.perf_counter() - started
        summary["failed_attempt_is_total_not_additive"] = True
        fixture_report = output / "dataset" / "results.json"
        if summary["fixture_costs_seconds"] is None and fixture_report.is_file():
            try:
                summary["fixture_costs_seconds"] = _read_json(fixture_report.read_bytes()).get("costs_seconds")
            except (ValueError, OSError):
                pass
        with (output / "failure.log").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(traceback.format_exc())
        _write_json(output / "results.json", summary, replace=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing paths are rejected")
    parser.add_argument("--config", type=Path, help="Response baseline neighbor configuration")
    parser.add_argument("--fixture-config", type=Path, help="Synthetic fixture configuration; default project example")
    args = parser.parse_args()
    result = run(args.output, config_path=args.config, fixture_config_path=args.fixture_config)
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve()),
                      "selected_model_id": result["selected_model_id"],
                      "campaign_sha256": result["campaign_sha256"],
                      "qualification": "unqualified", "biological_validation": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
