#!/usr/bin/env python3
"""Execute the two-motif synthetic symbolic IR through the existing interpreter."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from cellsim_v2.biological_rules import load_ruleset
from cellsim_v2.symbolic_logic import (
    canonical_digest, from_ruleset, parse_symbolic_json, to_ruleset,
)
from prepare_training_fixture import source_fingerprint
from run_rule_demo import run as run_rule_demo


def _write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output: Path) -> dict:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    report = {"status": "running", "utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version, "platform": platform.platform(), "device": "CPU",
              "source_test_tool_sha256": source_fingerprint(),
              "scope": "closed synthetic switch plus gated same-species transfer IR",
              "biological_qualification": "unqualified", "external_engines_run": []}
    try:
        source_path = ROOT / "configs/biological_rules.synthetic.json"
        source = load_ruleset(source_path)
        ir = from_ruleset(source)
        ir_path = output / "symbolic_ir.json"
        _write_new(ir_path, ir)
        parsed = parse_symbolic_json(ir_path.read_text(encoding="utf-8"))
        lowered = to_ruleset(parsed)
        lowered_path = output / "lowered_rules.json"
        _write_new(lowered_path, lowered)

        unsupported = json.loads(json.dumps(parsed))
        unsupported["statements"][0]["kind"] = "ligand_receptor_binding"
        unsupported_path = output / "rejected_unsupported.json"
        _write_new(unsupported_path, unsupported)
        try:
            parse_symbolic_json(unsupported_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            rejection = {"status": "rejected", "error_type": type(exc).__name__,
                         "reason": str(exc), "attempt_file": unsupported_path.name,
                         "attempt_sha256": _sha(unsupported_path)}
        else:
            raise AssertionError("unsupported symbolic statement was admitted")

        direct = run_rule_demo(output / "direct", source_path)
        roundtripped = run_rule_demo(output / "roundtripped", lowered_path)
        direct_trace = output / "direct/trace.jsonl"
        roundtrip_trace = output / "roundtripped/trace.jsonl"
        direct_world = output / "direct/final_world.json"
        roundtrip_world = output / "roundtripped/final_world.json"
        trace_equal = direct_trace.read_bytes() == roundtrip_trace.read_bytes()
        world_equal = direct_world.read_bytes() == roundtrip_world.read_bytes()
        digest_equal = (ir["ruleset_sha256"] == direct["readiness"]["ruleset_sha256"] ==
                        roundtripped["readiness"]["ruleset_sha256"])
        if not (trace_equal and world_equal and digest_equal and
                direct["status"] == roundtripped["status"] == "completed"):
            raise AssertionError("direct and symbolic-lowered execution differ")
        report.update({
            "status": "completed", "source_rules_file_sha256": _sha(source_path),
            "symbolic_ir_sha256": canonical_digest(parsed),
            "lowered_ruleset_sha256": ir["ruleset_sha256"],
            "accepted_intervals": roundtripped["accepted_intervals"],
            "accepted_rule_events": roundtripped["accepted_rule_events"],
            "final_cell_amount_mol": roundtripped["final_cell_amount_mol"],
            "total_balance_residual_mol": roundtripped["total_balance_residual_mol"],
            "trace_bytes_equal": trace_equal, "final_world_bytes_equal": world_equal,
            "accepted_history_digest_equal": digest_equal,
            "unsupported_construct": rejection,
            "artifacts": [{"path": path.relative_to(output).as_posix(), "sha256": _sha(path)}
                          for path in sorted(output.rglob("*")) if path.is_file()],
            "limitations": ["Only concentration_switch and saturable_transfer lower",
                            "Executable synthetic example only; no ligand/receptor behavior",
                            "Static IR checks do not prove biological law or numerical accuracy"],
        })
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report["wall_seconds_before_report"] = time.perf_counter() - started
        _write_new(output / "results.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new evidence directory")
    args = parser.parse_args()
    try:
        result = run(args.output)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"],
                      "accepted_intervals": result["accepted_intervals"],
                      "accepted_history_digest_equal": result["accepted_history_digest_equal"],
                      "trace_bytes_equal": result["trace_bytes_equal"],
                      "final_world_bytes_equal": result["final_world_bytes_equal"],
                      "output": str(Path(args.output).resolve())}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
