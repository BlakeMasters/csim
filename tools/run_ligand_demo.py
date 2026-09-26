#!/usr/bin/env python3
"""Run a synthetic two-cell secretion/sensing trace with replay and failure."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.ligand_communication import LigandCommunicationEpisode, LigandRejected


def _source_hash() -> str:
    digest = hashlib.sha256()
    for relative in (
        "src/cellsim_v2/checkpoint.py",
        "src/cellsim_v2/response_memory.py",
        "src/cellsim_v2/state.py",
        "src/cellsim_v2/transport.py",
        "src/cellsim_v2/ligand_communication.py",
        "tests/test_ligand_communication.py",
        "tools/run_ligand_demo.py",
    ):
        path = ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run() -> dict:
    episode = LigandCommunicationEpisode()
    initial = episode.reset()
    rates = (0.04, 0.0, 0.02)
    trace = []
    saved = None
    for index, rate in enumerate(rates):
        if index == 1:
            saved = json.loads(json.dumps(episode.checkpoint(), allow_nan=False))
        action = episode.make_action(rate)
        trace.append({"action": action, "transition": episode.step(action)})
    assert saved is not None
    replay = LigandCommunicationEpisode.from_checkpoint(saved)
    replayed = [replay.step(replay.make_action(rate)) for rate in rates[1:]]
    replay_equal = (replayed == [row["transition"] for row in trace[1:]] and
                    replay.checkpoint() == episode.checkpoint())

    failed = LigandCommunicationEpisode()
    failed.reset()
    before = failed.checkpoint()
    rejection = None
    try:
        failed.step(failed.make_action(1.0))
    except LigandRejected as exc:
        rejection = str(exc)
    unchanged = failed.checkpoint() == before
    retry = failed.step(failed.make_action(0.04))
    balances = [row["transition"]["info"]["absolute_balance_error_mol"]
                for row in trace]
    first = trace[0]["transition"]["observation"]
    second = trace[1]["transition"]["observation"]
    passed = (replay_equal and rejection is not None and "inventory" in rejection
              and unchanged and retry["observation"]["time_s"] == 0.5
              and first["field_concentration_mol_m3"] > 0
              and first["receiver_memory"] == 0
              and second["receiver_memory"] > 0
              and all(row["transition"]["observation"]["receiver_amount_mol"] == 0
                      for row in trace)
              and all(error < 1e-12 for error in balances))
    return {
        "status": "pass" if passed else "fail",
        "scope": "synthetic two-cell finite secretion and non-consuming sensing only",
        "biological_qualification": "unqualified",
        "receptor_binding_implemented": False,
        "external_solver_run": False,
        "device": "CPU",
        "python": sys.version,
        "platform": platform.platform(),
        "source_test_tool_sha256": _source_hash(),
        "configuration": {
            "grid_shape": [1, 1, 1],
            "voxel_width_m": 0.5,
            "voxel_volume_m3": 0.125,
            "species": "synthetic_ligand",
            "initial_sender_amount_mol": 0.1,
            "initial_field_amount_mol": 0.0,
            "initial_receiver_amount_mol": 0.0,
            "initial_receiver_memory": 0.0,
            "receiver_memory_unit": "1",
            "response_tau_s": 0.5,
            "response_target": "pre-step field concentration numerically mapped to dimensionless target by a synthetic slope of 1 m^3/mol",
            "step_s": 0.5,
            "horizon_steps": 3,
            "secretion_rate_actions_mol_s": list(rates),
            "stages": "sample accepted pre-step concentration; propose response memory and paired secretion on copies; validate; publish both",
        },
        "initial_observation": initial,
        "trace": trace,
        "json_checkpoint_replay_equal": replay_equal,
        "overdraw_rejection": {
            "error": rejection,
            "world_private_state_clock_unchanged": unchanged,
            "valid_retry_accepted": retry["observation"]["time_s"] == 0.5,
        },
        "maximum_closed_amount_balance_error_mol": max(balances),
        "limitations": [
            "One fixed 3D voxel; no diffusion, receptor binding, ligand degradation, gradients or moving geometry",
            "Receiver concentration sensing does not bind or consume ligand",
            "Synthetic amounts and response parameters have no measured cell identity or calibration",
            "Deterministic wrapper has no RNG or external solver-private state to replay",
            "No tissue-level, population-level or biological validation claim",
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
                          "overdraw_unchanged": result["overdraw_rejection"]["world_private_state_clock_unchanged"],
                          "output": str(output)}, allow_nan=False))
    else:
        print(rendered, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
