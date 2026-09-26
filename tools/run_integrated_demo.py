#!/usr/bin/env python3
"""Run the local synthetic cell demo directly or through Ocura Engine and OSS.

The inner run executes reviewable reference components in sequence. Engine and
OSS record the command route; component JSON files contain the numerical and
learning diagnostics. No biological qualification follows from a passing run.
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
REQUIRED_LOCAL_MAT = ROOT / "data" / "scmat_sequentialstim.mat"
REQUIRED_LOCAL_MAT_SHA256 = "69495462c1ee0f7f10eb04963803b55a7f2852833aebcd95ca166a4e3cc415fa"
sys.path.insert(0, str(ROOT / "tools"))
from prepare_training_fixture import source_fingerprint


COMPONENTS = (
    ("symbolic", "tools/run_symbolic_demo.py", "results.json"),
    ("memory", "tools/run_memory_demo.py", "results.json"),
    ("episode", "tools/run_synthetic_episode.py", "results.json"),
    ("self_play", "tools/run_virtual_cell_self_play.py", "results.json"),
    ("ligand", "tools/run_ligand_demo.py", "results.json"),
    ("splitting", "tools/uptake_splitting_study.py", "study.json"),
    ("arena", "tools/run_two_cell_arena.py", "results.json"),
    ("nfkb_observed", "tools/prepare_nfkb_observed.py", "observed_traces.json"),
    ("nfkb_fit", "tools/fit_nfkb_reporter.py", "receipt.json"),
    ("nfkb_dispersion", "tools/report_nfkb_variability.py", "receipt.json"),
    ("nfkb_metadata", "tools/export_nfkb_metadata.py", "receipt.json"),
    ("nfkb_episode", "tools/run_nfkb_demo.py", "results.json"),
    ("seeded_nfkb", "tools/run_seeded_nfkb_demo.py", "results.json"),
)


def _write_new(path: Path, payload: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        completed = subprocess.run(
            argv, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_s, check=False,
        )
        return {"argv": argv, "exit_code": completed.returncode,
                "stdout": completed.stdout, "stderr": completed.stderr,
                "wall_s": time.perf_counter() - started, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        def rendered(value: str | bytes | None) -> str:
            if isinstance(value, bytes):
                return value.decode("utf-8", "replace")
            return value or ""
        return {"argv": argv, "exit_code": None,
                "stdout": rendered(exc.stdout), "stderr": rendered(exc.stderr),
                "wall_s": time.perf_counter() - started, "timed_out": True}


def run_direct(output: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "running", "utc": datetime.now(timezone.utc).isoformat(),
        "scope": "local reference demo with synthetic episodes and a separately fitted observed NF-kappa-B reporter",
        "host": {"platform": platform.platform(), "python": sys.version,
                 "device": "CPU", "cpu_count_visible": os.cpu_count()},
        "source_test_tool_sha256_start": source_fingerprint(),
        "components": {},
    }
    for name, script, result_name in COMPONENTS:
        destination = output / name
        target = destination / result_name
        dependency = {
            "nfkb_fit": "nfkb_observed",
            "nfkb_dispersion": "nfkb_fit",
            "nfkb_metadata": "nfkb_dispersion",
            "nfkb_episode": "nfkb_metadata",
            "seeded_nfkb": "nfkb_episode",
        }.get(name)
        if dependency is not None and not result["components"][dependency]["accepted"]:
            result["components"][name] = {
                "accepted": False, "blocked_by": dependency,
                "result_path": str(target),
            }
            continue
        command = [sys.executable, str(ROOT / script), "--output",
                   str(target if name == "splitting" else destination)]
        observed_path = output / "nfkb_observed" / "observed_traces.json"
        if name == "nfkb_fit":
            command.extend(["--observed", str(observed_path)])
        elif name == "nfkb_dispersion":
            command.extend(["--source", str(REQUIRED_LOCAL_MAT),
                            "--overlay", str(output / "nfkb_fit" / "comparison_overlay.json")])
        elif name == "nfkb_metadata":
            command.extend(["--overlay", str(output / "nfkb_dispersion" /
                                              "comparison_with_bands.json")])
        elif name in {"nfkb_episode", "seeded_nfkb"}:
            command.extend(["--observed-artifact", str(observed_path)])
        call = _call(command, timeout_s=75)
        _write_new(output / f"{name}.call.json", call)
        item = {"command": command, "exit_code": call["exit_code"],
                "timed_out": call["timed_out"], "wall_s": call["wall_s"],
                "result_path": str(target)}
        if target.is_file():
            try:
                artifact = json.loads(target.read_text(encoding="utf-8"))
                item["component_status"] = artifact.get("status")
                item["result_sha256"] = _sha(target)
                item["accepted"] = (call["exit_code"] == 0
                                    and artifact.get("status") in {"pass", "passed", "completed"})
                if name == "nfkb_fit":
                    candidate = destination / "frozen_candidate.json"
                    overlay = destination / "comparison_overlay.json"
                    item["observed_input_path"] = str(observed_path)
                    item["frozen_candidate_path"] = str(candidate)
                    item["comparison_overlay_path"] = str(overlay)
                    if candidate.is_file() and overlay.is_file():
                        item["frozen_candidate_sha256"] = _sha(candidate)
                        item["comparison_overlay_sha256"] = _sha(overlay)
                        item["accepted"] &= (
                            artifact.get("observed_artifact_sha256") == _sha(observed_path)
                            and artifact.get("frozen_candidate_sha256") == item["frozen_candidate_sha256"]
                            and artifact.get("comparison_overlay_sha256") == item["comparison_overlay_sha256"]
                        )
                    else:
                        item["accepted"] = False
                        item["read_error"] = "frozen candidate or comparison overlay missing"
                elif name == "nfkb_dispersion":
                    source_overlay = output / "nfkb_fit" / "comparison_overlay.json"
                    dispersion = destination / "dispersion.json"
                    combined = destination / "comparison_with_bands.json"
                    item["input_overlay_path"] = str(source_overlay)
                    item["dispersion_path"] = str(dispersion)
                    item["combined_overlay_path"] = str(combined)
                    if dispersion.is_file() and combined.is_file():
                        item["dispersion_sha256"] = _sha(dispersion)
                        item["combined_overlay_sha256"] = _sha(combined)
                        item["accepted"] &= (
                            artifact.get("model_overlay_sha256") == _sha(source_overlay)
                            and artifact.get("dispersion_sha256") == item["dispersion_sha256"]
                            and artifact.get("combined_overlay_sha256") == item["combined_overlay_sha256"]
                        )
                    else:
                        item["accepted"] = False
                        item["read_error"] = "dispersion or combined overlay missing"
                elif name == "nfkb_metadata":
                    source_overlay = output / "nfkb_dispersion" / "comparison_with_bands.json"
                    metadata = destination / "metadata.json"
                    demo_overlay = destination / "demo_overlay.json"
                    item["input_overlay_path"] = str(source_overlay)
                    item["metadata_path"] = str(metadata)
                    item["demo_overlay_path"] = str(demo_overlay)
                    if metadata.is_file() and demo_overlay.is_file():
                        item["metadata_sha256"] = _sha(metadata)
                        item["demo_overlay_sha256"] = _sha(demo_overlay)
                        item["accepted"] &= (
                            artifact.get("input_overlay_sha256") == _sha(source_overlay)
                            and artifact.get("metadata_sha256") == item["metadata_sha256"]
                            and artifact.get("demo_overlay_sha256") == item["demo_overlay_sha256"]
                        )
                    else:
                        item["accepted"] = False
                        item["read_error"] = "source metadata or demo overlay missing"
                elif name == "nfkb_episode":
                    item["observed_input_path"] = str(observed_path)
                    item["observed_input_sha256"] = _sha(observed_path)
                    fit = result["components"]["nfkb_fit"]
                    item["frozen_candidate_path"] = fit["frozen_candidate_path"]
                    item["frozen_candidate_sha256"] = fit["frozen_candidate_sha256"]
                    item["comparison_overlay_path"] = fit["comparison_overlay_path"]
                    item["comparison_overlay_sha256"] = fit["comparison_overlay_sha256"]
                    metadata = result["components"]["nfkb_metadata"]
                    item["demo_overlay_path"] = metadata["demo_overlay_path"]
                    item["demo_overlay_sha256"] = metadata["demo_overlay_sha256"]
                    item["accepted"] &= (artifact.get("observed_overlay", {})
                                         .get("artifact_sha256") == item["observed_input_sha256"])
                elif name == "seeded_nfkb":
                    item["observed_input_path"] = str(observed_path)
                    item["observed_input_sha256"] = _sha(observed_path)
                    item["accepted"] &= (artifact.get("observed_schedule", {})
                                         .get("artifact_sha256") == item["observed_input_sha256"])
            except (OSError, ValueError, TypeError) as exc:
                item["accepted"] = False
                item["read_error"] = f"{type(exc).__name__}: {exc}"
        else:
            item["accepted"] = False
            item["read_error"] = "result JSON was not created"
        result["components"][name] = item
    result["source_test_tool_sha256_end"] = source_fingerprint()
    result["source_fingerprint_stable"] = (
        result["source_test_tool_sha256_start"] == result["source_test_tool_sha256_end"])
    result["status"] = "pass" if (result["source_fingerprint_stable"] and
        all(item["accepted"] for item in result["components"].values())) else "fail"
    result["limitations"] = [
        "The typed language executes only the currently supported synthetic rule motifs.",
        "Self-play and episode outcomes are synthetic reference behavior, not biological learning evidence.",
        "Ligand sensing is synthetic and non-consuming; receptor binding is not implemented.",
        "The RK4 control shares the fixed-grid equations and is not an external spatial solver.",
        "The observed NF-kappa-B reporter fit is a causal empirical basis, not molecular kinetics.",
        "Nominal ng/mL metadata describes source medium and is not converted into the synthetic molar reservoir.",
        "The scheduled NF-kappa-B/payload episode is illustrative; its reporter overlay is uncalibrated and its payload is not a measured treatment.",
        "Seeded per-cell variation is reproducible synthetic spread, not a fitted biological variance model.",
    ]
    _write_new(output / "results.json", result)
    return result


def run_oss_only(output: Path, *, oss: Path, python: Path) -> dict:
    """Required shared route: record the complete local workload in Ocura OSS."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    workload = output / "workload"
    receipt = {
        "status": "running", "utc": datetime.now(timezone.utc).isoformat(),
        "scope": "required local Ocura OSS execution record for the integrated reference demo",
        "host": {"platform": platform.platform(), "python": sys.version,
                 "device": "CPU", "cpu_count_visible": os.cpu_count()},
        "oss_cli": str(oss), "python_workload": str(python),
        "source_test_tool_sha256_start": source_fingerprint(),
        "limitations": [
            "Ocura OSS records and verifies command logs; it does not validate scientific results or impose Engine resource limits.",
            "Observed reporter fit is empirical and the NF-kappa-B/payload episode is illustrative, not calibrated biology.",
            "The direct workload runs locally on this host; no cloud execution or external solver is claimed.",
        ],
    }
    try:
        if not oss.is_file():
            raise FileNotFoundError(f"required Ocura OSS executable missing: {oss}")
        if not python.is_file():
            raise FileNotFoundError(f"workload Python executable missing: {python}")
        if not REQUIRED_LOCAL_MAT.is_file():
            raise FileNotFoundError(f"required local MAT input missing: {REQUIRED_LOCAL_MAT}")
        receipt["data_input_path"] = str(REQUIRED_LOCAL_MAT)
        receipt["data_input_sha256"] = _sha(REQUIRED_LOCAL_MAT)
        if receipt["data_input_sha256"] != REQUIRED_LOCAL_MAT_SHA256:
            raise ValueError("required local MAT input SHA-256 differs from the verified source")
        receipt["oss_cli_sha256"] = _sha(oss)
        receipt["python_workload_sha256"] = _sha(python)
        argv = [str(oss), "run", "--root", str(ROOT), "--json",
                "--param", "check=integrated-local-demo", "--",
                str(python), "tools/run_integrated_demo.py", "direct",
                "--output", str(workload)]
        call = _call(argv, timeout_s=300)
        _write_new(output / "oss-call.json", call)
        if call["timed_out"]:
            raise TimeoutError("Ocura OSS integrated workload timed out")
        oss_result = json.loads(call["stdout"])
        _write_new(output / "oss-result.json", oss_result)
        receipt.update(oss_atom_id=oss_result.get("atom_id"),
                       oss_chokepoint_id=oss_result.get("chokepoint_id"),
                       oss_outcome=oss_result.get("outcome"),
                       oss_cli_exit_code=call["exit_code"],
                       oss_command_duration_s=oss_result.get("duration_seconds"))
        stdout_path = ROOT / oss_result["stdout_log"]
        stderr_path = ROOT / oss_result["stderr_log"]
        receipt["oss_stdout_sha256"] = _sha(stdout_path)
        receipt["oss_stderr_sha256"] = _sha(stderr_path)
        verify_call = _call([str(oss), "verify", "--root", str(ROOT), "--json"],
                            timeout_s=30)
        _write_new(output / "oss-verify-call.json", verify_call)
        verification = json.loads(verify_call["stdout"])
        _write_new(output / "oss-verification.json", verification)
        inner_path = workload / "results.json"
        inner = json.loads(inner_path.read_text(encoding="utf-8"))
        receipt.update(
            oss_verification_status=verification.get("status"),
            oss_verification_problems=verification.get("problems"),
            oss_verified_log_count=verification.get("counts", {}).get("logs_checked"),
            workload_status=inner.get("status"),
            workload_results_path=str(inner_path),
            workload_results_sha256=_sha(inner_path),
            workload_component_statuses={name: item.get("component_status")
                                         for name, item in inner.get("components", {}).items()},
            workload_component_result_paths={name: item.get("result_path")
                                             for name, item in inner.get("components", {}).items()},
            source_test_tool_sha256_end=source_fingerprint(),
        )
        receipt["source_fingerprint_stable"] = (
            receipt["source_test_tool_sha256_start"] ==
            receipt["source_test_tool_sha256_end"] ==
            inner.get("source_test_tool_sha256_start") ==
            inner.get("source_test_tool_sha256_end"))
        receipt["status"] = "passed" if (
            call["exit_code"] == 0 and oss_result.get("outcome") == "passed"
            and verify_call["exit_code"] == 0
            and verification.get("status") == "ok"
            and not verification.get("problems")
            and inner.get("status") == "pass"
            and all(item.get("accepted") for item in inner.get("components", {}).values())
            and receipt["source_fingerprint_stable"]
        ) else "failed"
    except Exception as exc:
        receipt.update(status="failed", error_type=type(exc).__name__, error=str(exc),
                       source_test_tool_sha256_end=source_fingerprint())
        receipt["source_fingerprint_stable"] = (
            receipt["source_test_tool_sha256_start"] ==
            receipt["source_test_tool_sha256_end"])
    finally:
        receipt["artifact_sha256"] = {
            path.relative_to(output).as_posix(): _sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file() and path.name != "receipt.json"
        }
        _write_new(output / "receipt.json", receipt)
    return receipt


def run_engine(output: Path, *, engine: Path, oss: Path, python: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    workload = output / "workload"
    spec = {
        "run_root": str(output / "engine-runs"), "grace_period_s": 2.0,
        "metadata": {"project": "cellular_sim_build_v2",
                     "scope": "synthetic-reference-only", "case": "integrated-demo"},
        "probe": {"sample_interval_ms": 50, "hooks": ["process-tree"]},
        "phases": [{"name": "integrated-synthetic-demo",
                    "sandbox": {"command": [str(python), "tools/run_integrated_demo.py",
                                            "direct", "--output", str(workload)],
                                "cwd": str(ROOT), "timeout_s": 180,
                                "memory_limit_bytes": 1_000_000_000,
                                "max_child_processes": 4,
                                "tags": ["csim", "synthetic", "integrated-demo"]},
                    "tags": ["csim", "synthetic", "integrated-demo"]}],
        "checks": [],
    }
    _write_new(output / "engine-spec.json", spec)
    receipt = {
        "status": "running", "utc": datetime.now(timezone.utc).isoformat(),
        "scope": "optional local Engine execution through required Ocura OSS record; not scientific scoring",
        "host": {"platform": platform.platform(), "python": sys.version,
                 "device": "CPU", "cpu_count_visible": os.cpu_count()},
        "engine_cli": str(engine), "engine_cli_sha256": _sha(engine),
        "installed_engine_package_sha256": _installed_engine_hash(engine),
        "oss_cli": str(oss), "oss_cli_sha256": _sha(oss),
        "python_workload": str(python), "source_test_tool_sha256_start": source_fingerprint(),
        "requested_limits": {"phase_timeout_s": 180,
                             "job_memory_limit_bytes": 1_000_000_000,
                             "max_child_processes": 4},
        "limitations": ["Synthetic components only; no measured biological validation.",
                        "Engine and OSS report execution, not numerical or scientific correctness.",
                        "Windows native-process containment is best-effort; no requested limit is stress-tested."],
    }
    try:
        argv = [str(oss), "run", "--root", str(ROOT), "--json",
                "--param", "check=integrated-synthetic-demo", "--",
                str(engine), "run", "--json", str(output / "engine-spec.json")]
        call = _call(argv, timeout_s=240)
        _write_new(output / "oss-call.json", call)
        oss_result = json.loads(call["stdout"])
        _write_new(output / "oss-result.json", oss_result)
        receipt.update(oss_atom_id=oss_result.get("atom_id"),
                       oss_chokepoint_id=oss_result.get("chokepoint_id"),
                       oss_outcome=oss_result.get("outcome"),
                       oss_cli_exit_code=call["exit_code"])
        engine_report = json.loads((ROOT / oss_result["stdout_log"]).read_text(encoding="utf-8"))
        _write_new(output / "engine-report.json", engine_report)
        receipt.update(engine_run_id=engine_report.get("run_id"),
                       engine_status=engine_report.get("status"),
                       engine_degraded_capabilities=engine_report.get("degraded_capabilities", []))
        verify_call = _call([str(oss), "verify", "--root", str(ROOT), "--json"],
                            timeout_s=30)
        _write_new(output / "oss-verify-call.json", verify_call)
        verification = json.loads(verify_call["stdout"])
        _write_new(output / "oss-verification.json", verification)
        inner = json.loads((workload / "results.json").read_text(encoding="utf-8"))
        receipt.update(
            oss_atom_id=oss_result.get("atom_id"),
            oss_chokepoint_id=oss_result.get("chokepoint_id"),
            oss_outcome=oss_result.get("outcome"),
            oss_cli_exit_code=call["exit_code"],
            oss_command_duration_s=oss_result.get("duration_seconds"),
            oss_stdout_sha256=_sha(ROOT / oss_result["stdout_log"]),
            oss_stderr_sha256=_sha(ROOT / oss_result["stderr_log"]),
            engine_run_id=engine_report.get("run_id"),
            engine_status=engine_report.get("status"),
            engine_phase_status=engine_report["phases"][0].get("status"),
            engine_phase_return_code=engine_report["phases"][0].get("return_code"),
            engine_phase_duration_s=engine_report["phases"][0].get("duration_s"),
            engine_phase_sample_count=engine_report["phases"][0].get("sample_count"),
            engine_phase_peak_rss_bytes=engine_report["phases"][0].get("peak_rss_bytes"),
            engine_phase_sandbox_mode=engine_report["phases"][0].get("sandbox_mode"),
            engine_degraded_capabilities=engine_report.get("degraded_capabilities", []),
            oss_verification_status=verification.get("status"),
            oss_verification_problems=verification.get("problems"),
            oss_verified_log_count=verification.get("counts", {}).get("logs_checked"),
            workload_status=inner.get("status"),
            workload_results_path=str(workload / "results.json"),
            workload_results_sha256=_sha(workload / "results.json"),
            workload_component_statuses={name: item.get("component_status")
                                         for name, item in inner.get("components", {}).items()},
            source_test_tool_sha256_end=source_fingerprint(),
        )
        receipt["source_fingerprint_stable"] = (
            receipt["source_test_tool_sha256_start"] == receipt["source_test_tool_sha256_end"])
        receipt["status"] = "passed" if (
            call["exit_code"] == 0 and oss_result.get("outcome") == "passed"
            and engine_report.get("status") == "passed"
            and engine_report["phases"][0].get("status") == "passed"
            and engine_report["phases"][0].get("return_code") == 0
            and not engine_report.get("degraded_capabilities")
            and verify_call["exit_code"] == 0 and verification.get("status") == "ok"
            and not verification.get("problems")
            and inner.get("status") == "pass"
            and receipt["source_test_tool_sha256_start"] == receipt["source_test_tool_sha256_end"]
        ) else "failed"
    except Exception as exc:
        receipt.update(status="failed", error_type=type(exc).__name__, error=str(exc))
    finally:
        receipt["artifact_sha256"] = {
            path.relative_to(output).as_posix(): _sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file() and path.name != "receipt.json"
        }
        _write_new(output / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    direct = sub.add_parser("direct", help="internal local workload used by OSS or tests")
    direct.add_argument("--output", type=Path, required=True)
    recorded = sub.add_parser("oss", help="shared demo: run locally and record through required Ocura OSS")
    recorded.add_argument("--output", type=Path, required=True)
    recorded.add_argument("--oss-cli", type=Path, default=ROOT / ".venv/Scripts/ocura-oss.exe")
    recorded.add_argument("--python", type=Path, default=ROOT / ".venv/Scripts/python.exe")
    wrapped = sub.add_parser("engine", help="optional local Ocura Engine route through OSS")
    wrapped.add_argument("--output", type=Path, required=True)
    wrapped.add_argument("--engine-cli", type=Path, required=True)
    wrapped.add_argument("--oss-cli", type=Path, default=ROOT / ".venv/Scripts/ocura-oss.exe")
    wrapped.add_argument("--python", type=Path, default=ROOT / ".venv/Scripts/python.exe")
    args = parser.parse_args()
    if args.mode == "direct":
        result = run_direct(args.output)
        print(json.dumps({"status": result["status"], "output": str(args.output.resolve()),
                          "components": {k: v["accepted"] for k, v in result["components"].items()}},
                         indent=2))
        return 0 if result["status"] == "pass" else 1
    if args.mode == "oss":
        result = run_oss_only(args.output, oss=args.oss_cli.resolve(),
                              python=args.python.resolve())
        print(json.dumps({"status": result["status"],
                          "output": str(args.output.resolve()),
                          "oss_atom_id": result.get("oss_atom_id"),
                          "workload_status": result.get("workload_status"),
                          "error": result.get("error")}, indent=2))
        return 0 if result["status"] == "passed" else 1
    for name in ("engine_cli", "oss_cli", "python"):
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error(f"{name} does not exist: {path}")
        setattr(args, name, path)
    result = run_engine(args.output, engine=args.engine_cli, oss=args.oss_cli,
                        python=args.python)
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve()),
                      "engine_run_id": result.get("engine_run_id"),
                      "oss_atom_id": result.get("oss_atom_id"),
                      "workload_status": result.get("workload_status")}, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
