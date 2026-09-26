#!/usr/bin/env python3
"""Replay a bounded browser uptake session directly, via OSS, or via Engine/OSS.

Input is data, never a shell command. This replays accepted synthetic actions
under the fixed one-cell episode and retains rejection evidence if replay fails.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.synthetic_cell_episode import EpisodeRejected, make_synthetic_episode

SCHEMA = "cellsim.interactive-uptake-trace.v1"
MAX_INPUT_BYTES = 65_536
MAX_STEPS = 32
MAX_RATE_MOL_S = 10.0
VOXEL_VOLUME_M3 = 0.125
REQUIRED = {"schema", "initial_concentration_mol_m3", "initial_memory", "step_s",
            "target_response_index", "horizon_steps", "rates_mol_s"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _finite(value: object, name: str, *, minimum: float = 0.0,
            maximum: float) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a numeric JSON value")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return number


def validate_export(value: object) -> dict:
    if type(value) is not dict or not REQUIRED <= set(value) or set(value) - REQUIRED - {"session_id"}:
        raise ValueError("session export has missing or unsupported fields")
    if value["schema"] != SCHEMA:
        raise ValueError("unsupported session export schema")
    if "session_id" in value and (type(value["session_id"]) is not str or
                                  not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value["session_id"])):
        raise ValueError("session_id must be a short display-only identifier")
    steps = value["horizon_steps"]
    if type(steps) is not int or not 1 <= steps <= MAX_STEPS:
        raise ValueError(f"horizon_steps must be an integer in [1, {MAX_STEPS}]")
    rates = value["rates_mol_s"]
    if type(rates) is not list or len(rates) != steps:
        raise ValueError("rates_mol_s must contain one accepted rate per horizon step")
    return {
        "schema": SCHEMA,
        **({"session_id": value["session_id"]} if "session_id" in value else {}),
        "initial_concentration_mol_m3": _finite(value["initial_concentration_mol_m3"],
                                                 "initial concentration", maximum=10.0),
        "initial_memory": _finite(value["initial_memory"], "initial memory", maximum=10.0),
        "step_s": _finite(value["step_s"], "step_s", minimum=0.001, maximum=2.0),
        "target_response_index": _finite(value["target_response_index"],
                                          "target response index", maximum=10.0),
        "horizon_steps": steps,
        "rates_mol_s": [_finite(rate, f"rate[{index}]", maximum=MAX_RATE_MOL_S)
                        for index, rate in enumerate(rates)],
    }


def _load_export(path: Path) -> tuple[dict, bytes]:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"session export exceeds {MAX_INPUT_BYTES} bytes")
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError(f"session export exceeds {MAX_INPUT_BYTES} bytes")
    def reject_constant(token: str):
        raise ValueError(f"non-JSON numeric constant {token} is forbidden")
    return validate_export(json.loads(raw.decode("utf-8"), parse_constant=reject_constant)), raw


def _source_hashes() -> dict[str, str]:
    paths = (
        "src/cellsim_v2/synthetic_cell_episode.py",
        "src/cellsim_v2/response_memory.py",
        "src/cellsim_v2/state.py",
        "src/cellsim_v2/transport.py",
        "tools/replay_interactive_trace.py",
        "tests/test_interactive_trace_replay.py",
    )
    return {relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in paths}


def replay_trace(export: dict) -> dict:
    """Return a complete synthetic trace or an explicit rejected prefix."""
    config = validate_export(export)
    started = time.perf_counter()
    episode = make_synthetic_episode(
        initial_concentration_mol_m3=config["initial_concentration_mol_m3"],
        initial_memory=config["initial_memory"],
        horizon_steps=config["horizon_steps"], step_s=config["step_s"],
        target_response_index=config["target_response_index"],
    )
    before = episode.reset()
    initial_observation = before
    rows: list[dict] = []
    rejected = None
    for index, rate in enumerate(config["rates_mol_s"]):
        checkpoint_before = episode.checkpoint()
        try:
            action = episode.make_action(rate)
            transition = episode.step(action)
            after = transition["observation"]
            transfer = float(transition["info"]["integrated_transfer_mol"])
            field_loss = (float(before["local_concentration_mol_m3"])
                          - float(after["local_concentration_mol_m3"])) * VOXEL_VOLUME_M3
            cell_gain = float(after["cell_amount_mol"]) - float(before["cell_amount_mol"])
            residual = float(transition["info"]["absolute_balance_error_mol"])
            if (abs(field_loss - transfer) > 1e-12 or abs(cell_gain - transfer) > 1e-12
                    or residual > 1e-12):
                raise AssertionError("replayed transfer failed amount accounting")
            rows.append({"step": index + 1, "before": before, "action": action,
                         "after": after, "diagnostic_score": transition["diagnostic_score"],
                         "integrated_transfer_mol": transfer,
                         "absolute_balance_error_mol": residual,
                         "field_loss_mol": field_loss, "cell_gain_mol": cell_gain})
            before = after
        except (EpisodeRejected, AssertionError, ValueError) as exc:
            rejected = {"step": index + 1, "rate_mol_s": rate,
                        "error_type": type(exc).__name__, "error": str(exc),
                        "checkpoint_unchanged": checkpoint_before == episode.checkpoint()}
            break
    final = episode.observe()
    status = "pass" if rejected is None and final["terminated"] and len(rows) == config["horizon_steps"] else "failed"
    return {"status": status, "schema": SCHEMA,
            "scope": "synthetic one-cell accepted-action replay only",
            "biological_qualification": "unqualified", "device": "CPU",
            "platform": platform.platform(), "python": sys.version,
            "configuration": config, "initial_observation": initial_observation,
            "trace": rows, "accepted_steps": len(rows), "rejected_attempt": rejected,
            "final_observation": final,
            "final_checkpoint_sha256": episode.checkpoint()["sha256"],
            "max_absolute_balance_error_mol": max(
                (row["absolute_balance_error_mol"] for row in rows), default=0.0),
            "execution_wall_s_before_persistence": time.perf_counter() - started,
            "limitations": ["Deterministic one-cell/one-voxel synthetic episode only.",
                            "Only accepted browser rates are exported; rejected UI attempts stay in the UI session.",
                            "No biological model, numeric validation beyond this case, or sandbox claim."]}


def run_direct(input_path: Path, output: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_before = _source_hashes()
    report: dict = {"status": "running", "utc": datetime.now(timezone.utc).isoformat(),
                    "input_path": str(input_path.resolve()),
                    "source_test_tool_hashes_before": source_before}
    try:
        config, raw = _load_export(input_path)
        (output / "requested_session.json").write_bytes(raw)
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        report.update(replay_trace(config))
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    report["source_test_tool_hashes_after"] = _source_hashes()
    report["source_hashes_stable"] = source_before == report["source_test_tool_hashes_after"]
    if not report["source_hashes_stable"]:
        report["status"] = "failed"
        report["source_drift_error"] = "source/test/tool file changed during replay"
    _write_new(output / "results.json", report)
    return report


def _installed_engine_hash(exe: Path) -> str:
    package = exe.parent.parent / "Lib" / "site-packages" / "ocura"
    if not package.is_dir():
        raise FileNotFoundError(f"installed Ocura package missing beside {exe}")
    digest = hashlib.sha256()
    for path in sorted([*package.rglob("*.py"), *package.rglob("*.json")]):
        digest.update(path.relative_to(package).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _call(argv: list[str], *, timeout_s: float) -> dict:
    started = time.perf_counter()
    try:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout_s,
                                check=False)
        return {"argv": argv, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr,
                "wall_s": time.perf_counter() - started, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        def render(value: str | bytes | None) -> str:
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""
        return {"argv": argv, "exit_code": None,
                "stdout": render(exc.stdout), "stderr": render(exc.stderr),
                "wall_s": time.perf_counter() - started, "timed_out": True}


def run_oss(input_path: Path, output: Path, oss: Path, python: Path) -> dict:
    """Record the exact bounded replay command through OSS without Engine."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt: dict = {"status": "running", "utc": datetime.now(timezone.utc).isoformat(),
                     "scope": "local synthetic interactive accepted-action replay only",
                     "route": "oss_only", "host": {"platform": platform.platform(),
                                                   "python": sys.version, "device": "CPU"},
                     "oss_cli": str(oss), "oss_cli_sha256": _sha(oss),
                     "python_executable": str(python), "python_executable_sha256": _sha(python),
                     "source_test_tool_hashes_before": _source_hashes(),
                     "limitations": ["Synthetic one-cell/one-voxel replay, not biological qualification.",
                                     "OSS records and verifies the command route; Csim checks paired amount transfers.",
                                     "No Engine execution or resource-containment claim on this route."]}
    try:
        config, raw = _load_export(input_path)
        (output / "requested_session.json").write_bytes(raw)
        receipt["input_sha256"] = hashlib.sha256(raw).hexdigest()
        receipt["validated_configuration"] = config
        command = [str(oss), "run", "--root", str(ROOT), "--json",
                   "--param", "check=interactive-uptake-replay", "--",
                   str(python), "tools/replay_interactive_trace.py", "direct",
                   "--input", str(output / "requested_session.json"),
                   "--output", str(output / "workload")]
        call = _call(command, timeout_s=60)
        _write_new(output / "oss-call.json", call)
        oss_result = json.loads(call["stdout"])
        _write_new(output / "oss-result.json", oss_result)
        receipt.update(oss_atom_id=oss_result.get("atom_id"),
                       oss_chokepoint_id=oss_result.get("chokepoint_id"),
                       oss_outcome=oss_result.get("outcome"),
                       oss_cli_exit_code=call["exit_code"],
                       oss_command_duration_s=oss_result.get("duration_seconds"),
                       oss_stdout_sha256=_sha(ROOT / oss_result["stdout_log"]),
                       oss_stderr_sha256=_sha(ROOT / oss_result["stderr_log"]))
        verify_call = _call([str(oss), "verify", "--root", str(ROOT), "--json"], timeout_s=30)
        _write_new(output / "oss-verify-call.json", verify_call)
        verification = json.loads(verify_call["stdout"])
        _write_new(output / "oss-verification.json", verification)
        receipt.update(oss_verification_status=verification.get("status"),
                       oss_verification_problems=verification.get("problems"),
                       oss_verified_log_count=verification.get("counts", {}).get("logs_checked"))
        inner_path = output / "workload/results.json"
        inner = json.loads(inner_path.read_text(encoding="utf-8"))
        receipt.update(workload_status=inner.get("status"),
                       workload_results_sha256=_sha(inner_path),
                       accepted_steps=inner.get("accepted_steps"),
                       source_test_tool_hashes_after=_source_hashes())
        receipt["source_hashes_stable"] = (receipt["source_test_tool_hashes_before"]
                                           == receipt["source_test_tool_hashes_after"])
        receipt["status"] = "passed" if (
            call["exit_code"] == 0 and oss_result.get("outcome") == "passed"
            and verify_call["exit_code"] == 0 and verification.get("status") == "ok"
            and not verification.get("problems") and inner.get("status") == "pass"
            and inner.get("input_sha256") == receipt["input_sha256"]
            and inner.get("source_hashes_stable") and receipt["source_hashes_stable"]
        ) else "failed"
    except Exception as exc:
        receipt.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    finally:
        receipt["artifact_sha256"] = {path.relative_to(output).as_posix(): _sha(path)
            for path in sorted(output.rglob("*")) if path.is_file() and path.name != "receipt.json"}
        _write_new(output / "receipt.json", receipt)
    return receipt


def run_engine(input_path: Path, output: Path, engine: Path, oss: Path, python: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt: dict = {"status": "running", "utc": datetime.now(timezone.utc).isoformat(),
                     "scope": "local synthetic interactive action-trace replay only",
                     "host": {"platform": platform.platform(), "python": sys.version,
                              "device": "CPU", "cpu_count_visible": os.cpu_count()},
                     "engine_cli": str(engine), "engine_cli_sha256": _sha(engine),
                     "installed_engine_package_sha256": _installed_engine_hash(engine),
                     "oss_cli": str(oss), "oss_cli_sha256": _sha(oss),
                     "source_test_tool_hashes_before": _source_hashes(),
                     "requested_limits": {"phase_timeout_s": 30,
                                          "job_memory_limit_bytes": 512_000_000,
                                          "max_child_processes": 1},
                     "limitations": ["Synthetic one-cell/one-voxel replay, not biological qualification.",
                                     "Engine/OSS record the command route; Csim checks the amount transfers.",
                                     "Windows native-process containment is best-effort; limits were not stress-tested."]}
    try:
        config, raw = _load_export(input_path)
        (output / "requested_session.json").write_bytes(raw)
        receipt["input_sha256"] = hashlib.sha256(raw).hexdigest()
        receipt["validated_configuration"] = config
        spec = {"run_root": str(output / "engine-runs"), "grace_period_s": 2.0,
                "metadata": {"project": "cellular_sim_build_v2", "scope": "synthetic-reference-only",
                             "case": "interactive-uptake-replay"},
                "probe": {"sample_interval_ms": 50, "hooks": ["process-tree"]},
                "phases": [{"name": "interactive-uptake-replay",
                            "sandbox": {"command": [str(python), "tools/replay_interactive_trace.py",
                                                    "direct", "--input", str(output / "requested_session.json"),
                                                    "--output", str(output / "workload")],
                                        "cwd": str(ROOT), "timeout_s": 30,
                                        "memory_limit_bytes": 512_000_000,
                                        "max_child_processes": 1,
                                        "tags": ["csim", "synthetic", "interactive-replay"]},
                            "tags": ["csim", "synthetic", "interactive-replay"]}],
                "checks": []}
        _write_new(output / "engine-spec.json", spec)
        command = [str(oss), "run", "--root", str(ROOT), "--json",
                   "--param", "check=interactive-uptake-replay", "--",
                   str(engine), "run", "--json", str(output / "engine-spec.json")]
        call = _call(command, timeout_s=60)
        _write_new(output / "oss-call.json", call)
        oss_result = json.loads(call["stdout"])
        _write_new(output / "oss-result.json", oss_result)
        receipt.update(oss_atom_id=oss_result.get("atom_id"),
                       oss_chokepoint_id=oss_result.get("chokepoint_id"),
                       oss_outcome=oss_result.get("outcome"),
                       oss_cli_exit_code=call["exit_code"],
                       oss_command_duration_s=oss_result.get("duration_seconds"),
                       oss_stdout_sha256=_sha(ROOT / oss_result["stdout_log"]),
                       oss_stderr_sha256=_sha(ROOT / oss_result["stderr_log"]))
        engine_report = json.loads((ROOT / oss_result["stdout_log"]).read_text(encoding="utf-8"))
        _write_new(output / "engine-report.json", engine_report)
        phase = engine_report["phases"][0]
        receipt.update(engine_run_id=engine_report.get("run_id"),
                       engine_status=engine_report.get("status"),
                       engine_phase_status=phase.get("status"),
                       engine_phase_return_code=phase.get("return_code"),
                       engine_phase_duration_s=phase.get("duration_s"),
                       engine_phase_peak_rss_bytes=phase.get("peak_rss_bytes"),
                       engine_phase_sample_count=phase.get("sample_count"),
                       engine_phase_sandbox_mode=phase.get("sandbox_mode"),
                       engine_degraded_capabilities=engine_report.get("degraded_capabilities", []))
        verify_call = _call([str(oss), "verify", "--root", str(ROOT), "--json"], timeout_s=30)
        _write_new(output / "oss-verify-call.json", verify_call)
        verification = json.loads(verify_call["stdout"])
        _write_new(output / "oss-verification.json", verification)
        receipt.update(oss_verification_status=verification.get("status"),
                       oss_verification_problems=verification.get("problems"),
                       oss_verified_log_count=verification.get("counts", {}).get("logs_checked"))
        inner = json.loads((output / "workload/results.json").read_text(encoding="utf-8"))
        receipt.update(workload_status=inner.get("status"),
                       workload_results_sha256=_sha(output / "workload/results.json"),
                       accepted_steps=inner.get("accepted_steps"),
                       source_test_tool_hashes_after=_source_hashes())
        receipt["source_hashes_stable"] = (receipt["source_test_tool_hashes_before"]
                                           == receipt["source_test_tool_hashes_after"])
        receipt["status"] = "passed" if (
            call["exit_code"] == 0 and oss_result.get("outcome") == "passed"
            and engine_report.get("status") == "passed"
            and phase.get("status") == "passed" and phase.get("return_code") == 0
            and not engine_report.get("degraded_capabilities")
            and verify_call["exit_code"] == 0 and verification.get("status") == "ok"
            and not verification.get("problems") and inner.get("status") == "pass"
            and inner.get("input_sha256") == receipt["input_sha256"]
            and inner.get("source_hashes_stable") and receipt["source_hashes_stable"]
        ) else "failed"
    except Exception as exc:
        receipt.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    finally:
        receipt["artifact_sha256"] = {path.relative_to(output).as_posix(): _sha(path)
            for path in sorted(output.rglob("*")) if path.is_file() and path.name != "receipt.json"}
        _write_new(output / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    direct = sub.add_parser("direct", help="replay without Engine or OSS")
    direct.add_argument("--input", type=Path, required=True)
    direct.add_argument("--output", type=Path, required=True)
    wrapped = sub.add_parser("engine", help="record the replay via Engine and OSS")
    wrapped.add_argument("--input", type=Path, required=True)
    wrapped.add_argument("--output", type=Path, required=True)
    wrapped.add_argument("--engine-cli", type=Path, required=True)
    wrapped.add_argument("--oss-cli", type=Path, default=ROOT / ".venv/Scripts/ocura-oss.exe")
    wrapped.add_argument("--python", type=Path, default=ROOT / ".venv/Scripts/python.exe")
    oss_only = sub.add_parser("oss", help="record the replay via OSS without Engine")
    oss_only.add_argument("--input", type=Path, required=True)
    oss_only.add_argument("--output", type=Path, required=True)
    oss_only.add_argument("--oss-cli", type=Path, default=ROOT / ".venv/Scripts/ocura-oss.exe")
    oss_only.add_argument("--python", type=Path, default=ROOT / ".venv/Scripts/python.exe")
    args = parser.parse_args()
    if args.mode == "direct":
        result = run_direct(args.input, args.output)
        print(json.dumps({"status": result["status"], "output": str(args.output.resolve()),
                          "accepted_steps": result.get("accepted_steps"),
                          "rejected_attempt": result.get("rejected_attempt")}, allow_nan=False))
        return 0 if result["status"] == "pass" else 1
    for name in (("engine_cli", "oss_cli", "python") if args.mode == "engine" else ("oss_cli", "python")):
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error(f"{name} does not exist: {path}")
        setattr(args, name, path)
    receipt = (run_engine(args.input, args.output, args.engine_cli, args.oss_cli, args.python)
               if args.mode == "engine" else run_oss(args.input, args.output, args.oss_cli, args.python))
    print(json.dumps({"status": receipt["status"], "output": str(args.output.resolve()),
                      "engine_run_id": receipt.get("engine_run_id"),
                      "oss_atom_id": receipt.get("oss_atom_id"),
                      "oss_chokepoint_id": receipt.get("oss_chokepoint_id"),
                      "accepted_steps": receipt.get("accepted_steps")}, allow_nan=False))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
