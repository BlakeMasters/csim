#!/usr/bin/env python3
"""Run one bounded synthetic Csim command through local Ocura Engine and OSS.

This is execution/ledger qualification, not a biological experiment or a
general Csim adapter. Each invocation creates a new, retained output directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_training_fixture import source_fingerprint


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _installed_engine_hash(exe: Path) -> str:
    package = exe.parent.parent / "Lib" / "site-packages" / "ocura"
    if not package.is_dir():
        raise FileNotFoundError(f"installed Ocura package missing beside {exe}")
    digest = hashlib.sha256()
    for path in sorted([*package.rglob("*.py"), *package.rglob("*.json")]):
        digest.update(path.relative_to(package).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _invoke(argv: list[str], *, timeout: float = 60) -> dict:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False,
        )
        return {"argv": argv, "exit_code": completed.returncode,
                "stdout": completed.stdout, "stderr": completed.stderr,
                "wall_s": time.perf_counter() - started}
    except subprocess.TimeoutExpired as exc:
        return {"argv": argv, "exit_code": None,
                "stdout": (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else exc.stdout or "",
                "stderr": (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else exc.stderr or "",
                "wall_s": time.perf_counter() - started, "timeout": True}


def _spec(output: Path, python: Path, *, failing: bool) -> dict:
    role = "expected-failure" if failing else "synthetic-transfer"
    command = [str(python), "tools/run_rule_demo.py", "--output", str(output / role / "csim")]
    if failing:
        command.extend(["--rules", "configs/biological_rules.oxygen.template.json"])
    else:
        command.extend(["--rules", "configs/biological_rules.synthetic.json"])
    return {
        "run_root": str(output / "engine-runs"), "grace_period_s": 2.0,
        "metadata": {"project": "cellular_sim_build_v2", "scope": "synthetic-reference-only",
                     "case": role},
        "probe": {"sample_interval_ms": 50, "hooks": ["process-tree"]},
        "phases": [{"name": role,
                    "sandbox": {"command": command, "cwd": str(ROOT),
                                "timeout_s": 15, "memory_limit_bytes": 512_000_000,
                                "max_child_processes": 1,
                                "tags": ["csim", "synthetic", role]},
                    "tags": ["csim", "synthetic", role]}],
        "checks": [],
    }


def _record_engine_attempt(output: Path, oss: Path, engine: Path, label: str) -> dict:
    spec_path = output / f"{label}.run-spec.json"
    argv = [str(oss), "run", "--root", str(ROOT), "--json",
            "--param", f"check=local01-{label}", "--",
            str(engine), "run", "--json", str(spec_path)]
    call = _invoke(argv)
    _write(output / f"{label}.oss-call.json", call)
    try:
        oss_result = json.loads(call["stdout"])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OSS did not return JSON for {label}; see retained call") from exc
    _write(output / f"{label}.oss-result.json", oss_result)
    log_path = ROOT / oss_result["stdout_log"]
    stderr_path = ROOT / oss_result["stderr_log"]
    try:
        engine_report = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Engine did not return JSON for {label}; see {log_path}") from exc
    _write(output / f"{label}.engine-report.json", engine_report)
    return {"oss": oss_result, "engine": engine_report, "oss_cli_exit": call["exit_code"],
            "oss_wall_s": call["wall_s"], "stdout_sha256": _sha(log_path),
            "stderr_sha256": _sha(stderr_path)}


def _transfer_evaluation(output: Path) -> dict:
    csim = output / "synthetic-transfer" / "csim"
    result = json.loads((csim / "results.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (csim / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    amounts = [0.0, *[row["cell_amount_mol"] for row in rows]]
    integrated_transfer = sum(after - before for before, after in zip(amounts, amounts[1:]))
    interval_residuals = [row["interval_balance_residual_mol"] for row in rows]
    return {
        "observable": "integrated field-to-cell synthetic tracer transfer", "unit": "mol",
        "integrated_transfer_mol": integrated_transfer,
        "final_cell_amount_mol": result["final_cell_amount_mol"],
        "total_amount_ledger_residual_mol": result["total_balance_residual_mol"],
        "max_interval_amount_residual_mol": max(map(abs, interval_residuals)),
        "accepted_intervals": result["accepted_intervals"],
        "accepted_rule_events": result["accepted_rule_events"],
        "csim_status": result["status"],
        "source_test_tool_sha256": result["source_test_tool_sha256"],
        "acceptance": (result["status"] == "completed" and len(rows) == 5
                       and integrated_transfer > 0
                       and abs(integrated_transfer - result["final_cell_amount_mol"]) <= 1e-12
                       and abs(result["total_balance_residual_mol"]) <= 1e-12
                       and max(map(abs, interval_residuals)) <= 1e-12),
    }


def run(output: Path, engine: Path, oss: Path, python: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt: dict = {
        "status": "running", "utc": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "synthetic reference and local command-route qualification only",
        "host": {"os": platform.platform(), "python": sys.version, "device": "CPU",
                 "cpu_count_visible": os.cpu_count()},
        "source_test_tool_sha256_at_wrapper_start": source_fingerprint(),
        "rules_sha256": _sha(ROOT / "configs/biological_rules.synthetic.json"),
        "nonrunnable_rules_sha256": _sha(ROOT / "configs/biological_rules.oxygen.template.json"),
        "engine_cli": str(engine), "engine_cli_sha256": _sha(engine),
        "installed_engine_package_sha256": _installed_engine_hash(engine),
        "oss_cli": str(oss), "oss_cli_sha256": _sha(oss),
        "python_workload": str(python),
        "limits_per_engine_attempt": {"timeout_s": 15, "memory_limit_bytes": 512_000_000,
                                      "max_child_processes": 1},
        "limitations": ["Synthetic tracer and synthetic switch parameters only; no biological calibration or validation.",
                        "Engine performs command execution and resource reporting, not numerical evaluation.",
                        "Windows native-process enforcement is best-effort; inspect run diagnostics and sandbox mode."],
    }
    try:
        info_call = _invoke([str(engine), "engine", "info", "--json"], timeout=15)
        _write(output / "engine-info-call.json", info_call)
        if info_call["exit_code"] != 0:
            raise RuntimeError("Engine info command failed")
        info = json.loads(info_call["stdout"])
        _write(output / "engine-info.json", info)
        receipt["engine_identity"] = info["engine"]
        for label, failing in (("synthetic-transfer", False), ("expected-failure", True)):
            (output / label).mkdir()
            _write(output / f"{label}.run-spec.json", _spec(output, python, failing=failing))
        receipt["success"] = _record_engine_attempt(output, oss, engine, "synthetic-transfer")
        receipt["failure_control"] = _record_engine_attempt(output, oss, engine, "expected-failure")
        receipt["evaluation"] = _transfer_evaluation(output)
        failure = json.loads((output / "expected-failure" / "csim" / "results.json").read_text(encoding="utf-8"))
        receipt["failure_control"]["csim_status"] = failure["status"]
        receipt["failure_control"]["csim_error_type"] = failure.get("error_type")
        receipt["failure_control"]["source_test_tool_sha256"] = failure.get("source_test_tool_sha256")
        verify_call = _invoke([str(oss), "verify", "--root", str(ROOT), "--json"], timeout=30)
        _write(output / "oss-verify-call.json", verify_call)
        if verify_call["exit_code"] != 0:
            raise RuntimeError("OSS state verification failed")
        verify = json.loads(verify_call["stdout"])
        _write(output / "oss-verification.json", verify)
        receipt["oss_verification"] = verify
        receipt["source_test_tool_sha256_at_wrapper_end"] = source_fingerprint()
        receipt["source_fingerprint_stable"] = (
            receipt["source_test_tool_sha256_at_wrapper_start"]
            == receipt["source_test_tool_sha256_at_wrapper_end"]
            == receipt["evaluation"]["source_test_tool_sha256"]
            == failure.get("source_test_tool_sha256")
        )
        passed = receipt["success"]
        failed = receipt["failure_control"]
        receipt["engine_resource_diagnostics"] = {
            "success": passed["engine"].get("degraded_capabilities", []),
            "failure": failed["engine"].get("degraded_capabilities", []),
            "requested_limits_without_degradation": (
                not passed["engine"].get("degraded_capabilities")
                and not failed["engine"].get("degraded_capabilities")
            ),
        }
        receipt["status"] = "passed" if (
            passed["engine"]["status"] == "passed"
            and passed["engine"]["phases"][0]["status"] == "passed"
            and passed["engine"]["phases"][0]["return_code"] == 0
            and passed["oss"]["outcome"] == "passed" and passed["oss_cli_exit"] == 0
            and failed["engine"]["status"] == "failed"
            and failed["engine"]["phases"][0]["status"] == "failed"
            and failed["engine"]["phases"][0]["return_code"] == 1
            and failed["oss"]["outcome"] == "failed" and failed["oss_cli_exit"] == 1
            and failed["csim_status"] == "failed"
            and receipt["evaluation"]["acceptance"]
            and receipt["source_fingerprint_stable"]
            and receipt["engine_resource_diagnostics"]["requested_limits_without_degradation"]
            and verify["status"] == "ok" and not verify["problems"]
        ) else "failed"
    except Exception as exc:
        receipt.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    finally:
        receipt["artifact_sha256"] = {path.relative_to(output).as_posix(): _sha(path)
            for path in sorted(output.rglob("*")) if path.is_file() and path.name != "receipt.json"}
        _write(output / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new run directory")
    parser.add_argument("--engine-cli", type=Path, required=True, help="Installed Ocura Engine CLI")
    parser.add_argument("--oss-cli", type=Path, default=ROOT / ".venv/Scripts/ocura-oss.exe")
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/Scripts/python.exe")
    args = parser.parse_args()
    for name in ("engine_cli", "oss_cli", "python"):
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error(f"{name} does not exist: {path}")
        setattr(args, name, path)
    receipt = run(args.output, args.engine_cli, args.oss_cli, args.python)
    print(json.dumps({"status": receipt["status"], "output": str(args.output.resolve()),
                      "integrated_transfer_mol": receipt.get("evaluation", {}).get("integrated_transfer_mol"),
                      "ledger_residual_mol": receipt.get("evaluation", {}).get("total_amount_ledger_residual_mol"),
                      "success_atom": receipt.get("success", {}).get("oss", {}).get("atom_id"),
                      "failure_atom": receipt.get("failure_control", {}).get("oss", {}).get("atom_id")}, indent=2))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
