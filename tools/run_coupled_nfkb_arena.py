"""Run a three-cell seeded NF-kB proxy with tracked shared mediator exchange."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cellsim_v2.coupled_nfkb_arena import (  # noqa: E402
    CoupledNfkbArena, CoupledRejected, MEDIATOR,
)


def _hash() -> str:
    digest = hashlib.sha256()
    for relative in (
        "src/cellsim_v2/coupled_nfkb_arena.py",
        "tests/test_coupled_nfkb_arena.py",
        "tools/run_coupled_nfkb_arena.py",
    ):
        path = ROOT / relative
        digest.update(relative.encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _sample(observation: dict) -> dict:
    mediator = observation["field"][MEDIATOR]
    return {
        "time_min": observation["time_min"],
        "stimulus_code": observation["stimulus_code"],
        "mediator_field_amount_mol": mediator["amount_mol"],
        "mediator_field_concentration_mol_m3": mediator["concentration_mol_m3"],
        "mediator_waste_amount_mol": observation["waste_mediator_amount_mol"],
        "cells": [{key: cell[key] for key in (
            "cell_id", "model_id", "position_m", "nuclear_proxy",
            "feedback", "reporter_index", "mediator_inventory_mol")}
                  for cell in observation["cells"]],
    }


def _auc(samples: list[dict], cell_id: str) -> float:
    values = [next(cell["reporter_index"] for cell in item["cells"]
                   if cell["cell_id"] == cell_id) for item in samples]
    return math.fsum((values[index] + values[index + 1]) * 3.0
                     for index in range(len(values) - 1))


def _case(*, mediated: bool) -> dict:
    episode = CoupledNfkbArena(cell_count=3, seed=7)
    samples = [_sample(episode.reset())]
    ledger = []
    replay = None
    replay_equal = True
    maximum_residual = 0.0
    for index in range(82):
        rates = {f"cell_{cell}": 0.0 for cell in range(1, 4)}
        if mediated and index < 20:
            rates["cell_1"] = 0.00002
        if mediated and 40 <= index < 60:
            rates["cell_2"] = 0.000015
        action = episode.make_scheduled_action(
            sequence_key="TIPL", secretion_rates_mol_min_by_cell=rates,
            clearance_rate_min_inv=0.01)
        if index == 20:
            replay = CoupledNfkbArena.from_checkpoint(
                json.loads(json.dumps(episode.checkpoint())))
        transition = episode.step(action)
        if replay is not None:
            twin = replay.step(replay.make_scheduled_action(
                sequence_key="TIPL", secretion_rates_mol_min_by_cell=rates,
                clearance_rate_min_inv=0.01))
            replay_equal &= (transition == twin and
                             episode.checkpoint() == replay.checkpoint())
        samples.append(_sample(transition["observation"]))
        ledger.append({
            "interval_start_min": transition["info"]["interval_start_min"],
            "interval_end_min": transition["info"]["interval_end_min"],
            "sampled_mediator_concentration_mol_m3": transition["info"][
                "sampled_mediator_concentration_mol_m3"],
            "mediator_ledger": transition["info"]["mediator_ledger"],
            "core_ledger": transition["info"]["core_ledger"],
            "maximum_amount_residual_mol": transition["info"][
                "maximum_amount_residual_mol"],
        })
        maximum_residual = max(maximum_residual,
                               transition["info"]["maximum_amount_residual_mol"])
    return {
        "seed": 7, "cell_count": 3, "sequence_key": "TIPL",
        "accepted_steps": 82, "checkpoint_replay_equal": replay_equal,
        "maximum_amount_residual_mol": maximum_residual,
        "trace": samples, "ledger": ledger,
        "terminal_checkpoint_sha256": episode.checkpoint()["sha256"],
        "auc_reporter_index_min_by_cell": {
            f"cell_{cell}": _auc(samples, f"cell_{cell}") for cell in range(1, 4)},
    }


def run() -> dict:
    started = time.perf_counter()
    baseline = _case(mediated=False)
    coupled = _case(mediated=True)
    controls = {}
    for count in range(1, 6):
        episode = CoupledNfkbArena(cell_count=count)
        ids = [cell["cell_id"] for cell in episode.observe()["cells"]]
        transition = episode.step(episode.make_scheduled_action(
            sequence_key="TIPL",
            secretion_rates_mol_min_by_cell={cid: 0.00001 for cid in ids},
            clearance_rate_min_inv=0.01))
        controls[str(count)] = {
            "cell_ids": ids,
            "accepted": transition["observation"]["time_min"] == 6,
            "maximum_amount_residual_mol": transition["info"][
                "maximum_amount_residual_mol"],
        }
    rejection = CoupledNfkbArena(cell_count=3, seed=7)
    before = rejection.checkpoint()
    try:
        rejection.step(rejection.make_scheduled_action(
            sequence_key="TIPL",
            secretion_rates_mol_min_by_cell={
                "cell_1": 1.0, "cell_2": 0.0, "cell_3": 0.0},
        ))
    except CoupledRejected as exc:
        rejected_error = str(exc)
    else:
        rejected_error = None
    unchanged = rejection.checkpoint() == before
    delta_auc = {cid: coupled["auc_reporter_index_min_by_cell"][cid]
                 - baseline["auc_reporter_index_min_by_cell"][cid]
                 for cid in baseline["auc_reporter_index_min_by_cell"]}
    maximum_residual = max(
        baseline["maximum_amount_residual_mol"],
        coupled["maximum_amount_residual_mol"],
        *(row["maximum_amount_residual_mol"] for row in controls.values()),
    )
    result = {
        "status": "pass",
        "scope": "synthetic finite paracrine-mediator shared field around unchanged NF-kappa-B episode",
        "biological_qualification": "unqualified",
        "host": {"platform": platform.platform(), "python": sys.version,
                 "device": "CPU"},
        "source_test_tool_sha256": _hash(),
        "configuration": {
            "cell_count": 3, "seed": 7, "sequence_key": "TIPL",
            "horizon_steps": 82, "step_min": 6,
            "secretion_protocol": {
                "coupled_cell_1_rate_mol_min_steps_0_19": 0.00002,
                "coupled_cell_2_rate_mol_min_steps_40_59": 0.000015,
                "baseline_rates_mol_min": 0.0,
                "clearance_rate_min_inv": 0.01,
            },
        },
        "cases": {"baseline": baseline, "coupled": coupled},
        "comparison": {
            "same_seed": True,
            "same_stimulus_schedule": True,
            "cell_3_first_interval_nuclear_equal": (
                baseline["trace"][1]["cells"][2]["nuclear_proxy"] ==
                coupled["trace"][1]["cells"][2]["nuclear_proxy"]),
            "cell_3_second_interval_nuclear_delta": (
                coupled["trace"][2]["cells"][2]["nuclear_proxy"] -
                baseline["trace"][2]["cells"][2]["nuclear_proxy"]),
            "delta_auc_reporter_index_min_by_cell": delta_auc,
        },
        "cell_count_controls": controls,
        "checkpoint_replay_equal": (baseline["checkpoint_replay_equal"] and
                                    coupled["checkpoint_replay_equal"]),
        "overdraw_rejection": {"error": rejected_error, "unchanged": unchanged},
        "maximum_amount_residual_mol": maximum_residual,
        "costs": {
            "matched_full_runs": 2, "accepted_full_steps": 164,
            "accepted_cell_count_control_steps": 5,
            "attempted_rejected_steps": 1,
            "wall_s": time.perf_counter() - started,
        },
        "limitations": [
            "The mediator has no asserted cytokine or receptor identity; response modulation is illustrative.",
            "The field is one fixed voxel; cells have declared positions but no spatial gradient.",
            "The same seed controls private response variability in both matched arms; no observed variance fit is claimed.",
            "Neither the NF-kappa-B pathway proxy nor mediator exchange is calibrated to measured kinetics or drug effect.",
        ],
    }
    if (not result["checkpoint_replay_equal"] or not unchanged or not rejected_error or
            maximum_residual > 1e-12 or
            not all(row["accepted"] for row in controls.values()) or
            not result["comparison"]["cell_3_first_interval_nuclear_equal"] or
            result["comparison"]["cell_3_second_interval_nuclear_delta"] <= 0):
        result["status"] = "fail"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory already exists; preserve earlier evidence")
    result = run()
    args.output.mkdir(parents=True)
    target = args.output / "results.json"
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(target.resolve()),
                      "accepted_full_steps": result["costs"]["accepted_full_steps"],
                      "checkpoint_replay_equal": result["checkpoint_replay_equal"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
