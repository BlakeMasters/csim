#!/usr/bin/env python3
"""Show synthetic continuous response memory under two ordered exposures."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.response_memory import (
    advance_response, create_relaxation_model, initialize_response,
)


def _source_hash() -> str:
    digest = hashlib.sha256()
    for path in (ROOT / "src/cellsim_v2/response_memory.py",
                 ROOT / "tests/test_response_memory.py", ROOT / "tools/run_memory_demo.py"):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _history(model: dict, schedule: list[tuple[float, float]]) -> tuple[dict, list[dict]]:
    state = initialize_response(
        model, entity_id="synthetic-cell-1", initial_memory=0.0,
        accepted_time_s=0.0,
        initialization_provenance={"kind": "declared_synthetic_initial_state",
                                   "source_id": "run_memory_demo/v1"},
    )
    trace = []
    for concentration, end_time in schedule:
        start_time = state["accepted_time_s"]
        result = advance_response(model, state,
                                  exposure_concentration_mol_m3=concentration,
                                  end_time_s=end_time)
        state = result["state"]
        trace.append({"start_time_s": start_time, "end_time_s": end_time,
                      "exposure_concentration_mol_m3": concentration,
                      "memory": state["memory"],
                      "synthetic_response_index": result["observations"][0]["value"]})
    return state, trace


def run() -> dict:
    model = create_relaxation_model(
        model_id="h02-synthetic-relaxation-v1", context_id="synthetic-context-v1",
        tau_s=2.0, target_intercept=0.0, target_slope_m3_per_mol=1.0,
    )
    # Both histories have 4 mol*s/m^3 integrated exposure; order differs.
    early_high, early_trace = _history(model, [(2.0, 2.0), (0.0, 4.0)])
    late_high, late_trace = _history(model, [(0.0, 2.0), (2.0, 4.0)])
    challenge_input = 1.0
    a = advance_response(model, early_high,
                         exposure_concentration_mol_m3=challenge_input, end_time_s=5.0)
    b = advance_response(model, late_high,
                         exposure_concentration_mol_m3=challenge_input, end_time_s=5.0)
    restored = json.loads(json.dumps(early_high, allow_nan=False))
    replay = advance_response(json.loads(json.dumps(model)), restored,
                              exposure_concentration_mol_m3=challenge_input, end_time_s=5.0)
    # Independent closed-form target for the fixed two-interval synthetic case.
    decay_2 = math.exp(-2.0 / model["parameters"]["tau_s"])
    expected_early = 2.0 * (1.0 - decay_2) * decay_2
    expected_late = 2.0 * (1.0 - decay_2)
    if not (math.isclose(early_high["memory"], expected_early, abs_tol=1e-14) and
            math.isclose(late_high["memory"], expected_late, abs_tol=1e-14) and
            a == replay and a["state"]["memory"] < b["state"]["memory"]):
        raise AssertionError("synthetic memory challenge or replay failed")
    return {
        "status": "pass", "scope": "pure offline synthetic scalar relaxation only",
        "biological_qualification": "unqualified", "device": "CPU",
        "python": sys.version, "platform": platform.platform(),
        "h02_source_test_tool_sha256": _source_hash(),
        "model": model,
        "scenario": {"exposure_unit": "mol/m^3", "time_unit": "s",
                     "memory_unit": "1", "observation_unit": "1",
                     "tau_s": 2.0, "initial_memory": 0.0,
                     "integrated_exposure_both_mol_s_m3": 4.0,
                     "challenge_concentration_mol_m3": challenge_input,
                     "challenge_start_s": 4.0, "challenge_end_s": 5.0},
        "early_high": {"history": early_trace, "challenge_observation": a["observations"][0]},
        "late_high": {"history": late_trace, "challenge_observation": b["observations"][0]},
        "challenge_difference": b["observations"][0]["value"] - a["observations"][0]["value"],
        "json_round_trip_replay_equal": a == replay,
        "exact_piecewise_constant_control_passed": True,
        "limitations": ["Synthetic parameters and response index only",
                        "No measured assay, biological fit, physical transfer, or transaction-owned rollback",
                        "Exposure must be split at every known discontinuity"],
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
        print(json.dumps({"status": result["status"], "challenge_difference": result["challenge_difference"],
                          "output": str(output)}, allow_nan=False))
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
