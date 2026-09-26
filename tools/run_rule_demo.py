#!/usr/bin/env python3
"""Inspect a ruleset, or run a small synthetic switch/transfer scenario on CPU."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.biological_rules import evaluate_rules, load_ruleset, propose_rules, rule_readiness
from cellsim_v2.checkpoint import encode_world
from cellsim_v2.scheduler import Process, WindowStepper
from cellsim_v2.state import AmountField, Cell, LedgerEntry, Update, World, total_amount
from cellsim_v2.transport import RectilinearGrid3D
from prepare_training_fixture import source_fingerprint


def _write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def run(output: Path, rules_path: Path) -> dict:
    """Create-only example with prescribed reservoir replacements and ledgers.

    The fixed geometry, cells, signal schedule and interval are synthetic demo
    choices. Use the Python rule API for other supported worlds. This is not a
    configurable biological experiment runner.
    """
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    results = {"status": "running", "utc": datetime.now(timezone.utc).isoformat(),
               "python": sys.version, "platform": platform.platform(), "device": "CPU",
               "source_test_tool_sha256": source_fingerprint(),
               "biological_qualification": "unqualified", "external_engines_run": [],
               "scenario": {"grid_widths_m": [1.0, 1.0, 1.0], "cell_id": "cell-a",
                            "species": "synthetic_tracer", "dt_s": 0.1,
                            "reservoir_concentrations_mol_m3": [0.4, 0.65, 0.9, 0.65, 0.4]},
               "costs_seconds": {"rule_evaluation": 0.0, "stepping": 0.0, "persistence": 0.0}}
    try:
        raw = Path(rules_path).read_bytes()
        (output / "requested_rules.json").write_bytes(raw)
        results["rules_file_sha256"] = hashlib.sha256(raw).hexdigest()
        rules = load_ruleset(output / "requested_rules.json")
        results["readiness"] = rule_readiness(rules)
        if not results["readiness"]["runnable"]:
            raise ValueError("ruleset cannot execute: " + "; ".join(results["readiness"]["issues"]))
        if rules["execution_mode"] != "synthetic":
            raise ValueError("this demonstration accepts synthetic rules only")
        grid = RectilinearGrid3D((1.0,), (1.0,), (1.0,))
        species = results["scenario"]["species"]
        world = World(cells={"cell-a": Cell("cell-a", (0.5, 0.5, 0.5), 0.001, {species: 0.0})},
                      fields={species: AmountField.from_concentrations(species, (0.4,), grid.volumes_m3)})
        initial_total = total_amount(world, species)
        interval = Fraction("0.1")
        stepper = WindowStepper([Process("declarative-rules", interval,
            frozenset({"cells", "fields", "events"}),
            lambda snapshot, dt: propose_rules(snapshot, grid, rules, dt))], interval)
        records = []
        with (output / "trace.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for concentration in results["scenario"]["reservoir_concentrations_mol_m3"]:
                before = total_amount(world, species)
                replacement = AmountField.from_concentrations(species, (concentration,), grid.volumes_m3)
                delta = replacement.amounts_mol[0] - world.fields[species].amounts_mol[0]
                Update(replace_fields={species: replacement}, ledger=(LedgerEntry(species, delta,
                    "boundary", "Prescribed synthetic reservoir replacement for rule demonstration"),)).commit(
                        world, frozenset({"fields", "ledger"}))
                tick = time.perf_counter()
                proposal = evaluate_rules(world, grid, rules, float(interval))
                results["costs_seconds"]["rule_evaluation"] += time.perf_counter() - tick
                tick = time.perf_counter()
                stepper.advance(world, world.time_s + interval)
                results["costs_seconds"]["stepping"] += time.perf_counter() - tick
                row = {"time_s": float(world.time_s), "input_concentration_mol_m3": concentration,
                       "decisions": list(proposal.trace), "cell_amount_mol": world.cells["cell-a"].amounts_mol[species],
                       "field_amount_mol": world.fields[species].amounts_mol[0],
                       "boundary_change_mol": delta, "accepted_event_count": len(world.events),
                       "interval_balance_residual_mol": total_amount(world, species) - before - delta}
                tick = time.perf_counter()
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                results["costs_seconds"]["persistence"] += time.perf_counter() - tick
                records.append(row)
        tick = time.perf_counter()
        _write(output / "final_world.json", encode_world(world))
        results["costs_seconds"]["persistence"] += time.perf_counter() - tick
        results.update(status="completed", accepted_intervals=len(records),
                       accepted_rule_events=len(world.events),
                       final_cell_amount_mol=world.cells["cell-a"].amounts_mol[species],
                       total_balance_residual_mol=total_amount(world, species) - initial_total
                           - sum(e.change_mol for e in world.ledger))
        results["artifacts"] = [{"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                for p in sorted(output.iterdir()) if p.is_file()]
    except Exception as exc:
        results.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        results["wall_seconds_before_final_report"] = time.perf_counter() - started
        results["cost_scope"] = ("Wall timer starts after output directory creation; includes loading, "
            "initialization, evaluation, stepping and intermediate writes. Excludes interpreter/imports, "
            "directory creation and final results write. Rule trace evaluation is repeated by the stepper; "
            "both are charged. Failed attempt wall time is retained; no performance claim.")
        _write(output / "results.json", results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", type=Path, help="Inspect readiness without executing any rule")
    parser.add_argument("--rules", type=Path, default=ROOT / "configs/biological_rules.synthetic.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.inspect is not None:
        if args.output is not None:
            parser.error("--inspect does not accept --output")
        print(json.dumps(rule_readiness(load_ruleset(args.inspect)), indent=2))
        return 0
    if args.output is None:
        parser.error("--output NEWDIR is required for execution")
    try:
        result = run(args.output, args.rules)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
