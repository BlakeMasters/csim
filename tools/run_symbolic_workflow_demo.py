#!/usr/bin/env python3
"""Execute the closed synthetic NF-kB action protocol and direct control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.nfkb_episode import NfkbEpisode, NfkbRejected
from cellsim_v2.symbolic_workflow import (
    lower_action, parse_protocol_json, protocol_digest, protocol_from_episode,
    run_protocol, validate_protocol,
)


def fingerprint() -> str:
    digest = hashlib.sha256()
    for path in sorted([*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py"),
                        *ROOT.glob("tools/*.py")]):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run() -> tuple[dict, dict]:
    initial = NfkbEpisode(cell_count=3, horizon_steps=82, step_min=6.0)
    initial_checkpoint = json.loads(json.dumps(initial.checkpoint()))
    rates = {f"cell_{i}": 0.00002 for i in range(1, 4)}
    program = protocol_from_episode(initial, sequence_key="TIPL",
                                    stimulus_amount_mol=0.1,
                                    payload_start_min=120.0,
                                    payload_amount_mol=0.02,
                                    rates_mol_min_by_cell=rates)
    parsed = parse_protocol_json(json.dumps(program, sort_keys=True))
    lowered_episode = NfkbEpisode.from_checkpoint(initial_checkpoint)
    lowered = run_protocol(parsed, lowered_episode)
    direct_episode = NfkbEpisode.from_checkpoint(initial_checkpoint)
    direct_actions, direct_transitions = [], []
    for _ in range(82):
        action = direct_episode.make_scheduled_action(
            sequence_key="TIPL", stimulus_admin_mol_per_switch=0.1,
            payload_start_min=120.0, payload_admin_mol_at_start=0.02,
            payload_uptake_rates_mol_min_by_cell=rates)
        direct_actions.append(action)
        direct_transitions.append(direct_episode.step(action))
    direct_equal = (lowered["actions"] == direct_actions and
                    lowered["transitions"] == direct_transitions and
                    lowered_episode.checkpoint() == direct_episode.checkpoint())
    replayed = run_protocol(parsed, NfkbEpisode.from_checkpoint(
        json.loads(json.dumps(initial_checkpoint))))
    replay_equal = replayed == lowered
    bad = copy.deepcopy(parsed)
    bad["stimulus_transfer"]["quantity_type"] = "concentration_mol_m3"
    try:
        validate_protocol(bad)
    except ValueError as exc:
        rejected_unit = str(exc)
    else:
        rejected_unit = None
    overdraw_episode = NfkbEpisode(cell_count=1, horizon_steps=2)
    overdraw_program = protocol_from_episode(overdraw_episode,
                                             stimulus_amount_mol=1.0)
    before = overdraw_episode.checkpoint()
    try:
        overdraw_episode.step(lower_action(overdraw_program, overdraw_episode))
    except NfkbRejected as exc:
        rejected_overdraw = str(exc)
    else:
        rejected_overdraw = None
    outcome = {
        "status": "pass" if all((direct_equal, replay_equal, rejected_unit,
                                   rejected_overdraw,
                                   overdraw_episode.checkpoint() == before)) else "fail",
        "schema": "cellsim.nfkb-action-protocol-demo/1",
        "program_sha256": protocol_digest(parsed),
        "configuration": initial_checkpoint["payload"]["configuration"],
        "accepted_intervals": len(lowered["actions"]),
        "direct_actions_transitions_and_checkpoint_equal": direct_equal,
        "json_checkpoint_replay_equal": replay_equal,
        "maximum_amount_residual_mol": lowered["maximum_amount_residual_mol"],
        "final_checkpoint_sha256": lowered["final_checkpoint_sha256"],
        "rejected_unit": rejected_unit,
        "rejected_overdraw": rejected_overdraw,
        "rejected_overdraw_state_unchanged": overdraw_episode.checkpoint() == before,
        "first_action": lowered["actions"][0],
        "switch_actions": [action for action in lowered["actions"]
                           if action["stimulus_code"] is not None],
        "source_test_tool_sha256": fingerprint(),
        "environment": {"python": sys.version.split()[0],
                        "platform": platform.platform(), "device": "local CPU"},
        "limitations": [
            "The protocol expresses timed actions and typed transfers, not the NF-kB feedback equations.",
            "Its author stimulus codes have no inferred physical dose; synthetic amounts and rates are declared demo inputs.",
            "The response graph, observed p65 trajectories and frozen empirical predictor are separate artifacts; no drug efficacy or biological validation is established."
        ],
    }
    return outcome, program


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="new output directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must name a new directory")
    result, program = run()
    args.output.mkdir(parents=True)
    (args.output / "results.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (args.output / "program.json").write_text(
        json.dumps(program, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output),
                      "accepted_intervals": result["accepted_intervals"],
                      "program_sha256": result["program_sha256"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
