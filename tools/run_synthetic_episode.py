#!/usr/bin/env python3
"""Run one bounded synthetic cell episode, replay, and rejected-step control."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.synthetic_cell_episode import (
    EpisodeRejected, SyntheticCellEpisode, make_synthetic_episode,
)


def _source_hash() -> str:
    digest = hashlib.sha256()
    for relative in (
        "src/cellsim_v2/checkpoint.py",
        "src/cellsim_v2/response_memory.py",
        "src/cellsim_v2/state.py",
        "src/cellsim_v2/transport.py",
        "src/cellsim_v2/synthetic_cell_episode.py",
        "tests/test_synthetic_cell_episode.py",
        "tools/run_synthetic_episode.py",
    ):
        path = ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run() -> dict:
    episode = make_synthetic_episode(horizon_steps=4, step_s=0.25,
                                     target_response_index=0.5)
    initial_observation = episode.reset()
    rates_mol_s = (0.1, 0.1, 0.05, 0.0)
    trace = []
    saved = None
    for index, rate in enumerate(rates_mol_s):
        if index == 1:
            saved = json.loads(json.dumps(episode.checkpoint(), allow_nan=False))
        action = episode.make_action(rate)
        transition = episode.step(action)
        trace.append({"action": action, "transition": transition})
    assert saved is not None
    resumed = SyntheticCellEpisode.from_checkpoint(saved)
    replay = []
    for rate in rates_mol_s[1:]:
        replay.append(resumed.step(resumed.make_action(rate)))
    replay_equal = (replay == [row["transition"] for row in trace[1:]] and
                    resumed.checkpoint() == episode.checkpoint())

    failure_episode = make_synthetic_episode()
    failure_episode.reset()
    before = failure_episode.checkpoint()
    rejection = None
    try:
        failure_episode.step(failure_episode.make_action(100.0))
    except EpisodeRejected as exc:
        rejection = str(exc)
    rejection_unchanged = before == failure_episode.checkpoint()
    recovery = failure_episode.step(failure_episode.make_action(0.1))
    all_balances = [row["transition"]["info"]["absolute_balance_error_mol"]
                    for row in trace]
    passed = (replay_equal and rejection is not None and "demand" in rejection
              and rejection_unchanged and recovery["observation"]["time_s"] == 0.25
              and trace[-1]["transition"]["terminated"]
              and all(error < 1e-12 for error in all_balances)
              and all("target_response_index" not in row["transition"]["observation"]
                      for row in trace))
    return {
        "status": "pass" if passed else "fail",
        "scope": "deterministic fixed-topology synthetic one-cell episode transaction",
        "biological_qualification": "unqualified",
        "training_performed": False,
        "self_play_performed": False,
        "external_solver_run": False,
        "device": "CPU",
        "python": sys.version,
        "platform": platform.platform(),
        "source_test_tool_sha256": _source_hash(),
        "configuration": {
            "grid_shape": [1, 1, 1],
            "voxel_width_m": 0.5,
            "voxel_volume_m3": 0.125,
            "species": "synthetic_tracer",
            "one_cell_initial_concentration_mol_m3": 1.0,
            "initial_memory": 0.0,
            "memory_tau_s": 0.5,
            "uptake_km_mol_m3": 0.5,
            "step_s": 0.25,
            "horizon_steps": 4,
            "diagnostic_target_response_index": 0.5,
            "diagnostic_score": "negative absolute synthetic response-index error; training feedback only",
            "action_quantity_type": "vmax_mol_s",
            "rates_mol_s": list(rates_mol_s),
            "stages": "sample accepted pre-step concentration; propose memory and uptake on copies; validate; publish both",
        },
        "initial_observation": initial_observation,
        "trace": trace,
        "json_checkpoint_replay_equal": replay_equal,
        "overdraw_rejection": {
            "error": rejection,
            "world_memory_clock_unchanged": rejection_unchanged,
            "valid_retry_accepted": recovery["observation"]["time_s"] == 0.25,
        },
        "maximum_closed_amount_balance_error_mol": max(all_balances),
        "limitations": [
            "One deterministic synthetic cell and one 3D voxel; no diffusion, division or topology changes",
            "No stochastic policy, RNG, external solver or backend-private state to replay",
            "The diagnostic target supplies synthetic training feedback, not measured assay evidence",
            "This is a transaction precursor, not a trained virtual cell or completed V01 environment",
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
        print(json.dumps({"status": result["status"],
                          "json_checkpoint_replay_equal": result["json_checkpoint_replay_equal"],
                          "overdraw_unchanged": result["overdraw_rejection"]["world_memory_clock_unchanged"],
                          "output": str(output)}, allow_nan=False))
    else:
        print(rendered, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
