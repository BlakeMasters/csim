#!/usr/bin/env python3
"""Post-freeze descriptive residuals; never refits or selects a candidate."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import time


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _means(records: list[dict]) -> dict:
    keys = ("state_space_mae", "current_only_mae", "no_change_mae")
    return {key: sum(float(record[key]) for record in records) / len(records)
            for key in keys}


def _phase_mean(values: list[float], phase: int) -> float:
    # Stimulation changes at 0, 120, 240, and 360 minutes on the 6-min grid.
    first = (phase - 1) * 20
    last = min(phase * 20, 83)
    subset = values[first:last]
    return sum(float(value) for value in subset) / len(subset)


def report(comparison_path: Path, overlay_path: Path, output: Path) -> dict:
    start = time.perf_counter()
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    comparison_sha = _digest(comparison_path)
    overlay_sha = _digest(overlay_path)
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    if comparison["status"] != "pass" or overlay["schema_version"] != "cellsim-nfkb-observed-model-overlay/1":
        raise ValueError("frozen model artifacts have unexpected schemas")
    if (comparison["frozen_candidate_sha256"] !=
            overlay["frozen_candidate_sha256"]):
        raise ValueError("frozen candidate identity mismatch")
    heldout = comparison["metrics"]["evaluation"]["per_condition"]
    heldout_ids = {record["condition_id"] for record in heldout}
    observed = [item for item in overlay["conditions"]
                if item["condition_id"] in heldout_ids]
    if len(heldout) != 12 or len(observed) != 12 or any(
            item["split"] != "evaluation" for item in observed):
        raise ValueError("expected twelve unchanged evaluation conditions")
    grouped_dose = defaultdict(list)
    grouped_order = defaultdict(list)
    for item in heldout:
        grouped_dose[item["dose_tier"]].append(item)
        grouped_order[item["sequence_key"]].append(item)
    per_dose = [{"dose_tier": dose, "condition_count": len(grouped_dose[dose]),
                 **_means(grouped_dose[dose]),
                 "state_space_minus_current_only_mae": (
                     _means(grouped_dose[dose])["state_space_mae"] -
                     _means(grouped_dose[dose])["current_only_mae"])}
                for dose in ("high", "mid", "low")]
    per_order = [{"sequence_key": key, "condition_count": len(grouped_order[key]),
                  **_means(grouped_order[key])}
                 for key in sorted(grouped_order)]
    failures = [dict(item, state_space_minus_current_only_mae=(
                item["state_space_mae"] - item["current_only_mae"]))
                for item in heldout
                if item["state_space_mae"] > item["current_only_mae"]]

    # Show every same-current-ligand pair among held-out orders, not a
    # maximized contrast selected from evaluation outcomes.
    same_ligand_pairs = []
    for dose in ("high", "mid", "low"):
        cohort = [item for item in observed if item["dose_tier"] == dose]
        for phase in range(1, 5):
            for left, right in itertools.combinations(
                    sorted(cohort, key=lambda item: item["sequence_key"]), 2):
                ligand = left["ligand_sequence"][phase - 1]
                if ligand != right["ligand_sequence"][phase - 1]:
                    continue
                fields = ("mean", "model_prediction", "current_only_prediction")
                phase_values = {}
                for item in (left, right):
                    phase_values[item["sequence_key"]] = {
                        field: _phase_mean(
                            item["observed"]["mean"] if field == "mean" else item[field],
                            phase) for field in fields}
                observed_difference = (phase_values[left["sequence_key"]]["mean"] -
                                       phase_values[right["sequence_key"]]["mean"])
                full_difference = (
                    phase_values[left["sequence_key"]]["model_prediction"] -
                    phase_values[right["sequence_key"]]["model_prediction"])
                current_difference = (
                    phase_values[left["sequence_key"]]["current_only_prediction"] -
                    phase_values[right["sequence_key"]]["current_only_prediction"])
                if abs(current_difference) > 1e-12:
                    raise ValueError("current-only control retained earlier ligand history")
                same_ligand_pairs.append({
                    "dose_tier": dose,
                    "phase_1based": phase,
                    "phase_start_min": (phase - 1) * 120,
                    "phase_end_min_inclusive": 492 if phase == 4 else phase * 120 - 6,
                    "current_ligand": ligand,
                    "left": {"condition_id": left["condition_id"],
                             "sequence_key": left["sequence_key"],
                             "sample_row_key": left["sample_traces"][0]["row_key"]},
                    "right": {"condition_id": right["condition_id"],
                              "sequence_key": right["sequence_key"],
                              "sample_row_key": right["sample_traces"][0]["row_key"]},
                    "left_minus_right_phase_mean": {
                        "observed": observed_difference,
                        "state_space": full_difference,
                        "current_only": current_difference,
                    },
                })

    result = {
        "schema_version": "cellsim-nfkb-postfreeze-residuals/1",
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_type": "posthoc descriptive; no fitting, selection or candidate update",
        "comparison_sha256": comparison_sha,
        "overlay_sha256": overlay_sha,
        "frozen_candidate_sha256": comparison["frozen_candidate_sha256"],
        "observable": comparison["observable"],
        "per_dose": per_dose,
        "per_order": per_order,
        "per_condition": heldout,
        "state_space_worse_than_current_only_conditions": failures,
        "all_heldout_same_current_ligand_pairs": same_ligand_pairs,
        "notes": [
            "All four held-out orders and three dose tiers are retained, including losses",
            "Pair contrasts compare condition means with the same current ligand and dose; they do not prove causal cross-ligand mechanism",
            "Current-only pair contrast is zero by construction within a phase",
            "No replicate/chamber uncertainty is available from the inspected matrix",
            "No physical dose or measured drug effect is inferred",
        ],
        "wall_seconds_before_write": time.perf_counter() - start,
    }
    path = output / "residuals.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False,
                               ensure_ascii=False) + "\n", encoding="utf-8")
    receipt = {"status": "pass", "residuals_sha256": _digest(path),
               "comparison_sha256": comparison_sha,
               "overlay_sha256": overlay_sha,
               "frozen_candidate_sha256": comparison["frozen_candidate_sha256"],
               "condition_count": len(heldout),
               "same_current_ligand_pair_count": len(same_ligand_pairs),
               "source_tool_sha256": _digest(Path(__file__)),
               "output_bytes": path.stat().st_size}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                    allow_nan=False) + "\n",
                                           encoding="utf-8")
    return {"status": "pass", "artifact": str(path),
            "dose_groups": len(per_dose), "orders": len(per_order),
            "heldout_conditions": len(heldout),
            "low_dose_state_space_minus_current_only_mae": per_dose[2]["state_space_minus_current_only_mae"],
            "same_current_ligand_pairs": len(same_ligand_pairs)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(report(args.comparison.resolve(), args.overlay.resolve(),
                            args.output.resolve()), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
