#!/usr/bin/env python3
"""Run 1/2/3/5-cell shared-field traces and bounded synthetic controls."""
from __future__ import annotations

import argparse
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
from cellsim_v2.shared_cell_arena import ArenaRejected, SharedCellArena


COUNTS = (1, 2, 3, 5)
HORIZON_STEPS = 6
STEP_S = 0.25
DEVELOPMENT = (("dev-low", 0.8), ("dev-high", 1.2))
EVALUATION = (("eval-mid-low", 0.9), ("eval-mid-high", 1.1))
CANDIDATE_RATES_MOL_S = (0.006, 0.012, 0.018)
FIXED_RATE_MOL_S = 0.012
RANDOM_SEED = 19


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _source_hash() -> str:
    digest = hashlib.sha256()
    for relative in (
        "src/cellsim_v2/checkpoint.py",
        "src/cellsim_v2/response_memory.py",
        "src/cellsim_v2/state.py",
        "src/cellsim_v2/transport.py",
        "src/cellsim_v2/shared_cell_arena.py",
        "tests/test_shared_cell_arena.py",
        "tools/run_two_cell_arena.py",
    ):
        digest.update(relative.encode("utf-8"))
        digest.update((ROOT / relative).read_bytes())
    return digest.hexdigest()


def _rates(policy: str, observation: dict, step: int, *,
           base_rate: float = FIXED_RATE_MOL_S,
           rng: random.Random | None = None) -> dict[str, float]:
    cells = observation["cells"]
    if policy == "demo_heterogeneous":
        return {cell["cell_id"]: 0.005 + 0.003 * index + 0.002 * (step % 2)
                for index, cell in enumerate(cells)}
    if policy == "proposer_selected":
        return {cell["cell_id"]: base_rate * (1 + 0.1 * index)
                for index, cell in enumerate(cells)}
    if policy == "fixed_rate":
        return {cell["cell_id"]: FIXED_RATE_MOL_S for cell in cells}
    if policy == "seeded_random" and rng is not None:
        return {cell["cell_id"]: rng.uniform(0.004, 0.02) for cell in cells}
    raise ValueError("unsupported arena policy")


def _episode(count: int, condition_id: str, concentration: float, policy: str,
             *, base_rate: float = FIXED_RATE_MOL_S,
             seed: int = RANDOM_SEED) -> dict:
    started = time.perf_counter()
    arena = SharedCellArena(cell_count=count, horizon_steps=HORIZON_STEPS,
                            step_s=STEP_S,
                            initial_concentration_mol_m3=concentration)
    observation = arena.reset()
    rng = random.Random(seed)
    trace = []
    for step in range(HORIZON_STEPS):
        rates = _rates(policy, observation, step, base_rate=base_rate, rng=rng)
        actions = arena.make_actions(rates)
        try:
            transition = arena.step(actions)
        except ArenaRejected as exc:
            return {
                "status": "rejected",
                "condition_id": condition_id,
                "cell_count": count,
                "policy": policy,
                "error": str(exc),
                "attempted_steps": step + 1,
                "accepted_steps": step,
                "round_trace": trace,
                "wall_s": time.perf_counter() - started,
            }
        trace.append({
            "round": step + 1,
            "before": observation,
            "actions": list(actions),
            "after": transition["observation"],
            "transfers_mol_by_cell": transition["info"]["transfers_mol_by_cell"],
            "closed_amount_ledger": transition["info"]["closed_amount_ledger"],
            "diagnostic_score": transition["diagnostic_score"],
            "absolute_balance_error_mol": transition["info"]["absolute_balance_error_mol"],
        })
        observation = transition["observation"]
    scores = [row["diagnostic_score"] for row in trace]
    return {
        "status": "accepted",
        "condition_id": condition_id,
        "cell_count": count,
        "policy": policy,
        "initial_concentration_mol_m3": concentration,
        "attempted_steps": HORIZON_STEPS,
        "accepted_steps": HORIZON_STEPS,
        "mean_diagnostic_score": math.fsum(scores) / len(scores),
        "terminal_diagnostic_score": scores[-1],
        "maximum_balance_error_mol": max(row["absolute_balance_error_mol"] for row in trace),
        "round_trace": trace,
        "final_observation": observation,
        "wall_s": time.perf_counter() - started,
    }


def _control_comparison() -> tuple[dict, dict, dict]:
    """Use only development conditions to select rates, then freeze identities."""
    attempts = []
    proposer_rates: dict[str, float] = {}
    for count in COUNTS:
        candidate_scores = []
        for candidate in CANDIDATE_RATES_MOL_S:
            candidate_runs = []
            for condition_id, concentration in DEVELOPMENT:
                result = _episode(count, condition_id, concentration,
                                  "proposer_selected", base_rate=candidate)
                attempts.append({"arm": "proposer_selected", "candidate_rate_mol_s": candidate,
                                 "condition_id": condition_id, "cell_count": count,
                                 "status": result["status"],
                                 "mean_diagnostic_score": result.get("mean_diagnostic_score"),
                                 "wall_s": result["wall_s"],
                                 "error": result.get("error")})
                candidate_runs.append(result)
            if all(run["status"] == "accepted" for run in candidate_runs):
                candidate_scores.append((math.fsum(run["mean_diagnostic_score"]
                                                   for run in candidate_runs) / len(candidate_runs),
                                         candidate))
        if not candidate_scores:
            raise RuntimeError(f"no accepted development candidate for {count} cells")
        proposer_rates[str(count)] = max(candidate_scores)[1]
        # Match six development episode attempts per arm/count. Controls do not
        # use their development scores for selection.
        for repeat in range(3):
            for condition_id, concentration in DEVELOPMENT:
                fixed = _episode(count, condition_id, concentration, "fixed_rate")
                attempts.append({"arm": "fixed_rate", "candidate_rate_mol_s": FIXED_RATE_MOL_S,
                                 "condition_id": condition_id, "cell_count": count,
                                 "status": fixed["status"],
                                 "mean_diagnostic_score": fixed.get("mean_diagnostic_score"),
                                 "wall_s": fixed["wall_s"], "error": fixed.get("error")})
                random_seed = RANDOM_SEED + count * 100 + repeat * 10 + int(concentration * 10)
                random_run = _episode(count, condition_id, concentration,
                                      "seeded_random", seed=random_seed)
                attempts.append({"arm": "seeded_random", "seed": random_seed,
                                 "condition_id": condition_id, "cell_count": count,
                                 "status": random_run["status"],
                                 "mean_diagnostic_score": random_run.get("mean_diagnostic_score"),
                                 "wall_s": random_run["wall_s"],
                                 "error": random_run.get("error")})
    frozen = {
        "proposer_selected": {"selected_rates_mol_s_by_count": proposer_rates,
                              "selection": "highest mean development score among three declared rates"},
        "fixed_rate": {"rate_mol_s": FIXED_RATE_MOL_S},
        "seeded_random": {"seed": RANDOM_SEED, "range_mol_s": [0.004, 0.02]},
    }
    identities = {name: _digest(value) for name, value in frozen.items()}
    evaluation: dict[str, dict] = {}
    for name, policy in frozen.items():
        rows = []
        for count in COUNTS:
            for condition_id, concentration in EVALUATION:
                seed = RANDOM_SEED + count * 1000 + int(concentration * 100)
                trial = _episode(count, condition_id, concentration, name,
                                 base_rate=proposer_rates[str(count)] if name == "proposer_selected"
                                 else FIXED_RATE_MOL_S,
                                 seed=seed)
                rows.append(trial)
        accepted = [row for row in rows if row["status"] == "accepted"]
        evaluation[name] = {
            "policy": policy,
            "policy_sha256_before": identities[name],
            "policy_sha256_after": _digest(policy),
            "policy_identity_unchanged": identities[name] == _digest(policy),
            "attempted_episodes": len(rows),
            "accepted_episodes": len(accepted),
            "failed_episodes": len(rows) - len(accepted),
            "mean_diagnostic_score": (
                math.fsum(row["mean_diagnostic_score"] for row in accepted) / len(accepted)
                if accepted else None),
            "rows": rows,
        }
    return {"attempts": attempts, "frozen_policies": frozen,
            "policy_sha256": identities}, evaluation, proposer_rates


def _failure_and_replay() -> tuple[dict, bool]:
    arena = SharedCellArena(cell_count=5)
    ids = [cell["cell_id"] for cell in arena.observe()["cells"]]
    before = arena.checkpoint()
    error = None
    try:
        arena.step(arena.make_actions({cid: 1.0 for cid in ids}))
    except ArenaRejected as exc:
        error = str(exc)
    unchanged = arena.checkpoint() == before
    valid = arena.step(arena.make_actions({cid: 0.01 for cid in ids}))
    saved = json.loads(json.dumps(arena.checkpoint(), allow_nan=False))
    resumed = SharedCellArena.from_checkpoint(saved)
    actions_a = arena.make_actions({cid: 0.015 for cid in ids})
    actions_b = resumed.make_actions({cid: 0.015 for cid in ids})
    replay_equal = (arena.step(actions_a) == resumed.step(actions_b) and
                    arena.checkpoint() == resumed.checkpoint())
    return {
        "error": error,
        "accepted_state_unchanged": unchanged,
        "valid_retry_accepted": valid["observation"]["time_s"] == STEP_S,
    }, replay_equal


def run() -> dict:
    count_cases = {str(count): _episode(count, f"demo-{count}", 1.0,
                                       "demo_heterogeneous")
                   for count in COUNTS}
    development, evaluation, selected = _control_comparison()
    overdraw, replay = _failure_and_replay()
    accepted_dev = sum(row["status"] == "accepted" for row in development["attempts"])
    failed_dev = len(development["attempts"]) - accepted_dev
    accepted_eval = sum(arm["accepted_episodes"] for arm in evaluation.values())
    failed_eval = sum(arm["failed_episodes"] for arm in evaluation.values())
    passed = (all(case["status"] == "accepted" and case["accepted_steps"] == HORIZON_STEPS
                  and case["maximum_balance_error_mol"] < 1e-12
                  for case in count_cases.values())
              and set(selected) == {str(count) for count in COUNTS}
              and accepted_dev == 72 and failed_dev == 0
              and accepted_eval == 24 and failed_eval == 0
              and all(arm["policy_identity_unchanged"] for arm in evaluation.values())
              and overdraw["error"] is not None and "demand" in overdraw["error"]
              and overdraw["accepted_state_unchanged"] and overdraw["valid_retry_accepted"]
              and replay)
    return {
        "status": "pass" if passed else "fail",
        "scope": "synthetic 1-5 cell shared-field reference and bounded policy controls",
        "biological_qualification": "unqualified",
        "rl_algorithm_run": False,
        "external_solver_run": False,
        "device": "CPU",
        "python": sys.version,
        "platform": platform.platform(),
        "source_test_tool_sha256": _source_hash(),
        "configuration": {
            "cell_counts": list(COUNTS),
            "grid_shape": [1, 1, 1],
            "voxel_volume_m3": 0.125,
            "declared_cell_positions_m": [[0.1, 0.1, 0.1], [0.4, 0.1, 0.1],
                                          [0.1, 0.4, 0.1], [0.1, 0.1, 0.4],
                                          [0.4, 0.4, 0.4]],
            "species": "synthetic_tracer",
            "uptake_km_mol_m3": 0.5,
            "initial_field_concentration_mol_m3": 1.0,
            "step_s": STEP_S,
            "horizon_steps": HORIZON_STEPS,
            "diagnostic_target_memory": 0.5,
            "score_role": "synthetic training feedback only",
            "scarcity_policy": "reject all collective overdraw; never scale or clip individual demands",
            "action_quantity_type": "vmax_mol_s",
        },
        "round_trace": count_cases["2"]["round_trace"],
        "count_cases": count_cases,
        "development_condition_ids": [item[0] for item in DEVELOPMENT],
        "evaluation_condition_ids": [item[0] for item in EVALUATION],
        "development": development,
        "frozen_evaluation": evaluation,
        "costs": {
            "attempted_development_episodes": len(development["attempts"]),
            "accepted_development_episodes": accepted_dev,
            "failed_development_episodes": failed_dev,
            "attempted_evaluation_episodes": accepted_eval + failed_eval,
            "accepted_evaluation_episodes": accepted_eval,
            "failed_evaluation_episodes": failed_eval,
            "development_wall_s": math.fsum(row["wall_s"] for row in development["attempts"]),
            "evaluation_wall_s": math.fsum(
                row["wall_s"] for arm in evaluation.values() for row in arm["rows"]),
        },
        "overdraw_rejection": overdraw,
        "checkpoint_replay_equal": replay,
        "limitations": [
            "All cells occupy distinct declared positions within one fixed 3D voxel; no spatial gradients",
            "The same illustrative response equation is instantiated under distinct cell/model/context IDs",
            "Collective demand is rejected; no scarcity allocation or metabolism is modeled",
            "Development-selected rates and diagnostic scores are synthetic training information",
            "Frozen evaluation conditions are synthetic and do not represent biological holdout validation",
            "No RL algorithm, cell division, receptor interaction, external engine or scaling claim",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        help="create a new directory containing results.json")
    args = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        (output / "results.json").write_text(rendered, encoding="utf-8", newline="\n")
        print(json.dumps({"status": result["status"], "output": str(output),
                          "cell_counts": result["configuration"]["cell_counts"],
                          "checkpoint_replay_equal": result["checkpoint_replay_equal"]},
                         allow_nan=False))
    else:
        print(rendered, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
