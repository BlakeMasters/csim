#!/usr/bin/env python3
"""Bounded synthetic proposer-versus-learner curriculum; no RL or biology claim.

The proposer selects development histories using prior development residuals.
The learner fits a small one-step numeric response model. Evaluation histories
are generated only after all three curricula and model weights are frozen.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.synthetic_cell_episode import make_synthetic_episode

HORIZON_STEPS = 4
STEP_S = 0.25
TARGET_RESPONSE_INDEX = 0.5
DEVELOPMENT_EPISODES_PER_ARM = 6
RANDOM_SEED = 19
RIDGE = 1e-6


@dataclass(frozen=True)
class Schedule:
    id: str
    family: str
    initial_concentration_mol_m3: float
    actions_vmax_mol_s: tuple[float, float, float, float]


def development_schedules() -> tuple[Schedule, ...]:
    """Predeclared finite development pool; no evaluation history appears here."""
    patterns = (
        ("none", (0.0, 0.0, 0.0, 0.0)),
        ("steady", (0.015, 0.015, 0.015, 0.015)),
        ("pulse", (0.03, 0.0, 0.03, 0.0)),
        ("ramp", (0.0, 0.01, 0.02, 0.03)),
    )
    return tuple(Schedule(f"dev-{family}-{index}", family, concentration, actions)
                 for family, actions in patterns
                 for index, concentration in enumerate((0.4, 0.8, 1.2), start=1))


def evaluation_schedules() -> tuple[Schedule, ...]:
    """Sealed synthetic histories, never passed to the proposer or fitter."""
    return (
        Schedule("eval-low-alternating", "sealed", 0.6, (0.025, 0.005, 0.02, 0.0)),
        Schedule("eval-mid-late-pulse", "sealed", 1.0, (0.0, 0.0, 0.025, 0.025)),
        Schedule("eval-high-early-pulse", "sealed", 1.4, (0.025, 0.025, 0.0, 0.0)),
    )


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = (
        "src/cellsim_v2/synthetic_cell_episode.py",
        "src/cellsim_v2/response_memory.py",
        "src/cellsim_v2/state.py",
        "src/cellsim_v2/scheduler.py",
        "src/cellsim_v2/transport.py",
        "tools/run_virtual_cell_self_play.py",
        "tests/test_virtual_cell_self_play.py",
    )
    return {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in paths}


def _features(observation: dict, vmax_mol_s: float) -> tuple[float, float, float, float]:
    """Only causal public observation fields and the proposed typed action."""
    return (1.0, float(observation["accepted_memory"]),
            float(observation["local_concentration_mol_m3"]), vmax_mol_s / 0.03)


def _run_teacher(schedule: Schedule) -> tuple[list[dict], float, float]:
    started = time.perf_counter()
    episode = make_synthetic_episode(
        initial_concentration_mol_m3=schedule.initial_concentration_mol_m3,
        initial_memory=0.0, horizon_steps=HORIZON_STEPS, step_s=STEP_S,
        target_response_index=TARGET_RESPONSE_INDEX,
    )
    observation = episode.reset()
    rows: list[dict] = []
    diagnostic_scores: list[float] = []
    for index, vmax in enumerate(schedule.actions_vmax_mol_s):
        features = _features(observation, vmax)
        action = episode.make_action(vmax)
        result = episode.step(action)
        next_observation = result["observation"]
        label = float(next_observation["accepted_memory"])
        if not math.isfinite(label):
            raise ValueError("teacher produced a nonfinite response memory")
        score = float(result["diagnostic_score"])
        if not math.isfinite(score):
            raise ValueError("teacher produced a nonfinite diagnostic score")
        rows.append({"step": index + 1, "features": list(features),
                     "label_next_memory": label,
                     "before_time_s": float(observation["time_s"]),
                     "after_time_s": float(next_observation["time_s"]),
                     "field_concentration_before_mol_m3": float(observation["local_concentration_mol_m3"]),
                     "field_concentration_after_mol_m3": float(next_observation["local_concentration_mol_m3"]),
                     "cell_amount_before_mol": float(observation["cell_amount_mol"]),
                     "cell_amount_after_mol": float(next_observation["cell_amount_mol"]),
                     "integrated_transfer_mol": float(result["info"]["integrated_transfer_mol"]),
                     "absolute_balance_error_mol": float(result["info"]["absolute_balance_error_mol"]),
                     "action": action, "diagnostic_score": score})
        diagnostic_scores.append(score)
        if bool(result["terminated"]) != (index == HORIZON_STEPS - 1):
            raise AssertionError("episode termination did not match the declared horizon")
        if result.get("truncated"):
            raise AssertionError("bounded synthetic episode unexpectedly truncated")
        observation = next_observation
    return rows, time.perf_counter() - started, math.fsum(diagnostic_scores) / len(diagnostic_scores)


def _predict(weights: tuple[float, ...], features: list[float] | tuple[float, ...]) -> float:
    return math.fsum(weight * feature for weight, feature in zip(weights, features))


def _solve(matrix: list[list[float]], rhs: list[float]) -> tuple[float, ...]:
    """Small dense ridge system, using pivoted elimination rather than a dependency."""
    size = len(rhs)
    augmented = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda index: abs(augmented[index][col]))
        if abs(augmented[pivot][col]) < 1e-15:
            raise ArithmeticError("response fit is singular")
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        for item in range(col, size + 1):
            augmented[col][item] /= scale
        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col]
            for item in range(col, size + 1):
                augmented[row][item] -= factor * augmented[col][item]
    result = tuple(augmented[row][-1] for row in range(size))
    if not all(math.isfinite(value) for value in result):
        raise ArithmeticError("response fit is nonfinite")
    return result


def _fit(rows: list[dict]) -> tuple[float, float, float, float]:
    if not rows:
        return (0.0, 1.0, 0.0, 0.0)  # no-change memory control before the first label
    size = 4
    normal = [[0.0 for _ in range(size)] for _ in range(size)]
    rhs = [0.0 for _ in range(size)]
    for row in rows:
        features = row["features"]
        label = row["label_next_memory"]
        for i in range(size):
            rhs[i] += features[i] * label
            for j in range(size):
                normal[i][j] += features[i] * features[j]
    for i in range(size):
        normal[i][i] += RIDGE
    return _solve(normal, rhs)


def _mae(weights: tuple[float, ...], rows: list[dict]) -> float:
    return math.fsum(abs(_predict(weights, row["features"]) - row["label_next_memory"])
                     for row in rows) / len(rows)


def choose_adaptive(remaining: tuple[Schedule, ...], selected: tuple[Schedule, ...],
                    family_errors: dict[str, float]) -> Schedule:
    """Use development error and novelty only; never inspect held-out labels."""
    if not selected:
        return remaining[0]
    seen_families = {schedule.family for schedule in selected}

    def score(schedule: Schedule) -> float:
        novelty = min(
            abs(schedule.initial_concentration_mol_m3 - prior.initial_concentration_mol_m3)
            + math.fsum(abs(a - b) / 0.03 for a, b in zip(
                schedule.actions_vmax_mol_s, prior.actions_vmax_mol_s))
            for prior in selected
        )
        return (1.0 if schedule.family not in seen_families else 0.0) + 0.05 * novelty + (
            family_errors.get(schedule.family, 0.0) * 10.0)

    return max(enumerate(remaining), key=lambda pair: (score(pair[1]), -pair[0]))[1]


def _train_arm(name: str, pool: tuple[Schedule, ...]) -> dict:
    selection_started = time.perf_counter()
    if name == "fixed_coverage":
        fixed_ids = ("dev-none-1", "dev-steady-2", "dev-pulse-3", "dev-ramp-1",
                     "dev-none-3", "dev-steady-1")
        fixed = [next(schedule for schedule in pool if schedule.id == item) for item in fixed_ids]
    elif name == "seeded_random":
        fixed = random.Random(RANDOM_SEED).sample(list(pool), DEVELOPMENT_EPISODES_PER_ARM)
    else:
        fixed = []
    proposal_selection_s = time.perf_counter() - selection_started
    records: list[dict] = []
    attempts: list[dict] = []
    chosen: list[Schedule] = []
    family_errors: dict[str, float] = {}
    weights = _fit(records)
    generation_s = fitting_s = 0.0
    for round_number in range(DEVELOPMENT_EPISODES_PER_ARM):
        if name == "adaptive_proposer":
            selection_started = time.perf_counter()
            remaining = tuple(schedule for schedule in pool if schedule not in chosen)
            schedule = choose_adaptive(remaining, tuple(chosen), family_errors)
            proposal_selection_s += time.perf_counter() - selection_started
        else:
            schedule = fixed[round_number]
        chosen.append(schedule)
        attempt_started = time.perf_counter()
        try:
            rows, elapsed, mean_score = _run_teacher(schedule)
            generation_s += elapsed
            prefit_mae = _mae(weights, rows)
            records.extend(rows)
            fit_started = time.perf_counter()
            weights = _fit(records)
            fitting_s += time.perf_counter() - fit_started
            family_errors[schedule.family] = prefit_mae
            attempts.append({"round": round_number + 1, "schedule": asdict(schedule),
                             "status": "accepted", "prefit_mae_memory_1": prefit_mae,
                             "mean_teacher_diagnostic_score": mean_score,
                             "generated_steps": len(rows), "generation_s": elapsed,
                             "attempt_wall_s": time.perf_counter() - attempt_started,
                             "rows": rows})
        except Exception as exc:
            attempts.append({"round": round_number + 1, "schedule": asdict(schedule),
                             "status": "failed", "error_type": type(exc).__name__,
                             "error": str(exc), "generated_steps": 0,
                             "attempt_wall_s": time.perf_counter() - attempt_started})
    return {"name": name, "attempts": attempts, "attempted_episodes": len(attempts),
            "accepted_episodes": sum(item["status"] == "accepted" for item in attempts),
            "failed_episodes": sum(item["status"] == "failed" for item in attempts),
            "failed_attempt_wall_s": math.fsum(item["attempt_wall_s"] for item in attempts
                                               if item["status"] == "failed"),
            "generated_development_steps": len(records), "generation_s": generation_s,
            "fitting_s": fitting_s, "proposal_selection_s": proposal_selection_s,
            "weights": list(weights),
            "frozen_weights_sha256": _digest(list(weights)),
            "selected_schedule_ids": [item.id for item in chosen]}


def _evaluate_arm(arm: dict, sealed: tuple[Schedule, ...]) -> dict:
    weights = tuple(arm["weights"])
    before = _digest(list(weights))
    generation_s = inference_s = 0.0
    cases: list[dict] = []
    all_errors: list[float] = []
    for schedule in sealed:
        attempt_started = time.perf_counter()
        try:
            rows, elapsed, mean_score = _run_teacher(schedule)
            generation_s += elapsed
            tick = time.perf_counter()
            errors = [abs(_predict(weights, row["features"]) - row["label_next_memory"])
                      for row in rows]
            inference_s += time.perf_counter() - tick
            all_errors.extend(errors)
            cases.append({"schedule": asdict(schedule), "status": "accepted",
                          "generated_steps": len(rows), "mae_memory_1": math.fsum(errors) / len(errors),
                          "mean_teacher_diagnostic_score": mean_score,
                          "generation_s": elapsed,
                          "attempt_wall_s": time.perf_counter() - attempt_started})
        except Exception as exc:
            cases.append({"schedule": asdict(schedule), "status": "failed",
                          "generated_steps": 0, "error_type": type(exc).__name__,
                          "error": str(exc),
                          "attempt_wall_s": time.perf_counter() - attempt_started})
    after = _digest(list(weights))
    return {"cases": cases, "attempted_episodes": len(cases),
            "failed_episodes": sum(case["status"] == "failed" for case in cases),
            "failed_attempt_wall_s": math.fsum(case["attempt_wall_s"] for case in cases
                                               if case["status"] == "failed"),
            "generated_evaluation_steps": len(all_errors),
            "one_step_mae_memory_1": math.fsum(all_errors) / len(all_errors) if all_errors else None,
            "generation_s": generation_s, "inference_s": inference_s,
            "weights_sha256_before": before, "weights_sha256_after": after,
            "weights_unchanged": before == after == arm["frozen_weights_sha256"]}


def run() -> dict:
    started = time.perf_counter()
    source_before = _source_hashes()
    development = development_schedules()
    sealed = evaluation_schedules()
    if {item.id for item in development} & {item.id for item in sealed}:
        raise AssertionError("development and evaluation IDs overlap")
    schedule_digest = _digest([asdict(item) for item in sealed])
    arms = {name: _train_arm(name, development) for name in
            ("adaptive_proposer", "fixed_coverage", "seeded_random")}
    for arm in arms.values():
        arm["evaluation"] = _evaluate_arm(arm, sealed)
    source_after = _source_hashes()
    all_complete = all(
        arm["accepted_episodes"] == DEVELOPMENT_EPISODES_PER_ARM
        and arm["failed_episodes"] == 0
        and arm["evaluation"]["failed_episodes"] == 0
        and arm["evaluation"]["weights_unchanged"]
        and arm["evaluation"]["one_step_mae_memory_1"] is not None
        for arm in arms.values()
    )
    return {
        "status": "pass" if all_complete and source_before == source_after else "failed",
        "utc": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic one-step numeric cell-response model and adaptive curriculum only",
        "biological_qualification": "unqualified", "rl_algorithm_run": False,
        "device": "CPU", "platform": platform.platform(), "python": sys.version,
        "configuration": {"horizon_steps": HORIZON_STEPS, "step_s": STEP_S,
                          "target_response_index": TARGET_RESPONSE_INDEX,
                          "development_pool_size": len(development),
                          "development_episodes_per_arm": DEVELOPMENT_EPISODES_PER_ARM,
                          "evaluation_schedule_count": len(sealed),
                          "random_seed": RANDOM_SEED, "ridge": RIDGE,
                          "learner_features": ["intercept", "accepted_memory",
                                               "local_concentration_mol_m3", "vmax_mol_s/0.03"],
                          "metric": "teacher-forced one-step next-memory MAE, dimensionless"},
        "development_schedule_ids": [item.id for item in development],
        "sealed_evaluation_schedule_sha256": schedule_digest,
        "sealed_evaluation_schedule_ids": [item.id for item in sealed],
        "source_test_tool_hashes_before": source_before,
        "source_test_tool_hashes_after": source_after,
        "source_hashes_stable": source_before == source_after,
        "arms": arms,
        "costs": {"total_wall_s_before_persistence": time.perf_counter() - started,
                  "development_generation_s": math.fsum(arm["generation_s"] for arm in arms.values()),
                  "fitting_s": math.fsum(arm["fitting_s"] for arm in arms.values()),
                  "proposal_selection_s": math.fsum(arm["proposal_selection_s"] for arm in arms.values()),
                  "evaluation_generation_s": math.fsum(arm["evaluation"]["generation_s"] for arm in arms.values()),
                  "evaluation_inference_s": math.fsum(arm["evaluation"]["inference_s"] for arm in arms.values()),
                  "attempted_development_episodes": sum(arm["attempted_episodes"] for arm in arms.values()),
                  "failed_development_episodes": sum(arm["failed_episodes"] for arm in arms.values()),
                  "attempted_evaluation_episodes": sum(arm["evaluation"]["attempted_episodes"] for arm in arms.values()),
                  "failed_evaluation_episodes": sum(arm["evaluation"]["failed_episodes"] for arm in arms.values()),
                  "failed_attempt_wall_s": math.fsum(arm["failed_attempt_wall_s"]
                      + arm["evaluation"]["failed_attempt_wall_s"] for arm in arms.values())},
        "limitations": ["Synthetic teacher and fixed numeric actions; no measured assay or biological validity.",
                        "A fitted ridge one-step predictor is used; no reinforcement-learning update is implemented.",
                        "Evaluation is teacher-forced; recursive rollout, physical outcome benefit, and scale are untested.",
                        "The sealed schedule is fixed in source code, not an access-controlled secret."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    try:
        result = run()
    except Exception as exc:
        result = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                  "utc": datetime.now(timezone.utc).isoformat(),
                  "biological_qualification": "unqualified"}
    result["command"] = [sys.executable, *sys.argv]
    result["output"] = str(output)
    write_started = time.perf_counter()
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    results_write_s = time.perf_counter() - write_started
    results_bytes = (output / "results.json").read_bytes()
    with (output / "artifact_receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"results_sha256": hashlib.sha256(results_bytes).hexdigest(),
                   "results_bytes": len(results_bytes),
                   "results_write_s": results_write_s,
                   "cost_scope": "Write time excludes output directory creation, read-back hash and receipt write."},
                  stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "output": str(output),
                      "one_step_mae_memory_1": {
                          name: arm["evaluation"]["one_step_mae_memory_1"]
                          for name, arm in result.get("arms", {}).items()},
                      "failed_episodes": result.get("costs", {}).get("failed_development_episodes", 0)
                      + result.get("costs", {}).get("failed_evaluation_episodes", 0)},
                     allow_nan=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
