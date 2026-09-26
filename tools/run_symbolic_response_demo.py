#!/usr/bin/env python3
"""Compare a typed illustrative NF-kB response graph with accepted episodes."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cellsim_v2.nfkb_episode import DEFAULT_PARAMETERS, NfkbEpisode
from cellsim_v2.symbolic_response import (
    evaluate_response, nfkb_response_program, parse_response_json,
    response_digest, validate_response_program,
)


SOURCE_FILES = (
    "src/cellsim_v2/nfkb_episode.py",
    "src/cellsim_v2/symbolic_response.py",
    "tests/test_symbolic_response.py",
    "tools/run_symbolic_response_demo.py",
)


def _write(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component_sha() -> str:
    digest = hashlib.sha256()
    for name in SOURCE_FILES:
        digest.update(name.encode("utf-8") + b"\0" + (ROOT / name).read_bytes())
    return digest.hexdigest()


def _inputs(previous: dict, current: dict, cell_id: str) -> dict:
    old = next(row for row in previous["cells"] if row["cell_id"] == cell_id)
    new = next(row for row in current["cells"] if row["cell_id"] == cell_id)
    return {
        "stimulus_concentration_mol_m3":
            current["field"]["synthetic_stimulus"]["concentration_mol_m3"],
        "payload_amount_mol": new["payload_amount_mol"],
        "previous_nuclear_proxy": old["nuclear_proxy"],
        "previous_feedback": old["feedback"],
        "previous_reporter_index": old["reporter_index"],
        "step_min": current["time_min"] - previous["time_min"],
        **{name: DEFAULT_PARAMETERS[name] for name in (
            "stimulus_half_response_mol_m3", "feedback_strength",
            "payload_half_effect_mol", "nuclear_relaxation_min",
            "feedback_relaxation_min", "reporter_relaxation_min")},
    }


def _case(program: dict, cell_count: int) -> tuple[list[dict], int, float]:
    episode = NfkbEpisode(cell_count=cell_count, horizon_steps=4)
    ids = [cell["cell_id"] for cell in episode.observe()["cells"]]
    trace, scalar_checks, maximum_difference = [], 0, 0.0
    for interval in range(4):
        previous = episode.observe()
        if interval == 0:
            action = episode.make_action(stimulus_code="T", stimulus_admin_mol=0.125)
        elif interval == 1:
            action = episode.make_action(
                payload_admin_mol=0.02,
                payload_uptake_rates_mol_min_by_cell={cid: 0.0001 for cid in ids})
        elif interval == 2:
            action = episode.make_action(
                payload_uptake_rates_mol_min_by_cell={cid: 0.0001 for cid in ids})
        else:
            action = episode.make_action(
                stimulus_code="I", stimulus_admin_mol=0.08,
                stimulus_withdraw_mol=previous["field"]["synthetic_stimulus"]["amount_mol"],
                payload_uptake_rates_mol_min_by_cell={cid: 0.0001 for cid in ids})
        transition = episode.step(action)
        current = transition["observation"]
        for cell in current["cells"]:
            inputs = _inputs(previous, current, cell["cell_id"])
            predicted = evaluate_response(program, inputs)
            actual = {key: cell[key] for key in predicted}
            for key in predicted:
                difference = abs(predicted[key] - actual[key])
                maximum_difference = max(maximum_difference, difference)
                scalar_checks += 1
                if difference > 1e-14:
                    raise AssertionError(f"symbolic response differs for {cell['cell_id']} {key}")
            trace.append({"cell_count": cell_count, "interval": interval,
                          "cell_id": cell["cell_id"], "time_min": current["time_min"],
                          "inputs": inputs, "predicted": predicted, "actual": actual,
                          "payload_transfer_mol":
                              transition["info"]["payload_transfers_mol_by_cell"][cell["cell_id"]],
                          "maximum_amount_residual_mol":
                              transition["info"]["maximum_amount_residual_mol"]})
    return trace, scalar_checks, maximum_difference


def run(output: Path) -> dict:
    started = time.perf_counter()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    program = nfkb_response_program()
    _write(output / "program.json", program)
    if parse_response_json((output / "program.json").read_text(encoding="utf-8")) != program:
        raise AssertionError("response JSON roundtrip differs")
    invalid = copy.deepcopy(program)
    invalid["nodes"][2]["args"][0] = "missing"
    try:
        validate_response_program(invalid)
    except ValueError as exc:
        invalid_reason = str(exc)
    else:
        raise AssertionError("unknown response reference was admitted")
    traces, scalar_checks, maximum_difference = [], 0, 0.0
    for count in (1, 3):
        rows, checks, difference = _case(program, count)
        traces.extend(rows)
        scalar_checks += checks
        maximum_difference = max(maximum_difference, difference)
    _write(output / "trace.json", traces)
    result = {
        "schema_version": "cellsim-symbolic-response-demo/1",
        "status": "pass", "created_utc": datetime.now(timezone.utc).isoformat(),
        "program_sha256": response_digest(program),
        "component_source_test_tool_sha256": _component_sha(),
        "source_files": list(SOURCE_FILES),
        "cases": [1, 3], "accepted_intervals": 8,
        "cell_interval_rows": len(traces), "scalar_comparisons": scalar_checks,
        "maximum_absolute_response_difference": maximum_difference,
        "negative_control": {"unknown_reference": "rejected", "reason": invalid_reason},
        "program_file_sha256": _sha(output / "program.json"),
        "trace_file_sha256": _sha(output / "trace.json"),
        "wall_seconds_before_result": time.perf_counter() - started,
        "environment": {"platform": platform.platform(), "python": sys.version,
                        "device": "CPU"},
        "limitations": [
            "The graph evaluates only the illustrative private response recurrence",
            "Physical reservoir/field/cell transfers and accepted-state transaction remain in NfkbEpisode",
            "The formula and constants are synthetic, not biologically calibrated",
            "Parity on this host does not establish independent numerical or biological validation",
        ],
    }
    _write(output / "results.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({"status": result["status"], "accepted_intervals":
                      result["accepted_intervals"], "scalar_comparisons":
                      result["scalar_comparisons"], "output": str(Path(args.output).resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
