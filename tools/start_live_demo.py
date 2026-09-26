#!/usr/bin/env python3
"""Preflight and supervise the two loopback Csim demo pages on this laptop."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAT_SHA256 = "69495462c1ee0f7f10eb04963803b55a7f2852833aebcd95ca166a4e3cc415fa"
DEFAULT_CAMPAIGN = ROOT / "runs/nfkb_campaign_20260926_02/results.json"
DEFAULT_COUPLED = ROOT / "runs/coupled_nfkb_arena_20260926_04/results.json"
DEFAULT_REPORT = ROOT / "runs/nfkb_campaign_review_20260926_04/index.html"
DEFAULT_RUN = ROOT / "runs/integrated_demo_oss_20260926T2119Z/workload/results.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _launcher_hashes() -> dict[str, str]:
    names = ("tools/start_live_demo.py", "tests/test_start_live_demo.py",
             "docs/LIVE_DEMO_RUNBOOK.md")
    return {name: _sha(ROOT / name) for name in names}


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"expected JSON object: {path}")
    return value


def preflight(*, oss: Path, report: Path, run: Path, engine: Path | None) -> dict:
    """Verify local artifacts and OSS logs before either server is started."""
    paths = {
        "source_mat": ROOT / "data/scmat_sequentialstim.mat",
        "observed_overlay": ROOT / "runs/nfkb_metadata_20260926_01/demo_overlay.json",
        "frozen_candidate": ROOT / "runs/nfkb_model_20260926_02/frozen_candidate.json",
        "campaign_results": DEFAULT_CAMPAIGN,
        "campaign_oss_record": DEFAULT_CAMPAIGN.parent / "oss_record.json",
        "coupled_results": DEFAULT_COUPLED,
        "coupled_oss_record": DEFAULT_COUPLED.parent / "oss_record.json",
        "campaign_report": report,
        "campaign_report_receipt": report.parent / "receipt.json",
        "integrated_run": run,
        "oss_cli": oss,
    }
    if engine is not None:
        paths["engine_cli_optional"] = engine
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"required {name} is missing: {path}")
    hashes = {name: _sha(path) for name, path in paths.items()}
    if hashes["source_mat"] != MAT_SHA256:
        raise ValueError("local NF-kappa-B MAT hash differs from verified source")
    observed = _json(paths["observed_overlay"])
    frozen = _json(paths["frozen_candidate"])
    campaign = _json(paths["campaign_results"])
    sidecar = _json(paths["campaign_oss_record"])
    coupled = _json(paths["coupled_results"])
    coupled_sidecar = _json(paths["coupled_oss_record"])
    report_receipt = _json(paths["campaign_report_receipt"])
    integrated = _json(paths["integrated_run"])
    if observed.get("status") != "pass" or observed.get("source", {}).get("sha256") != MAT_SHA256:
        raise ValueError("observed overlay is not the accepted local source")
    if frozen.get("source_matrix_sha256") != MAT_SHA256 or (
        observed.get("frozen_candidate_sha256") != hashes["frozen_candidate"]):
        raise ValueError("frozen reporter candidate does not match observed overlay")
    if campaign.get("status") != "pass" or sidecar.get("status") != "passed":
        raise ValueError("campaign result or OSS record is not passed")
    if sidecar.get("results_sha256") != hashes["campaign_results"] or (
        sidecar.get("manifest_sha256") != campaign.get("manifest_sha256")):
        raise ValueError("campaign OSS record hashes do not match the results")
    if (coupled.get("status") != "pass" or coupled_sidecar.get("status") != "passed"
            or coupled_sidecar.get("results_sha256") != hashes["coupled_results"]
            or coupled_sidecar.get("source_test_tool_sha256") != coupled.get("source_test_tool_sha256")
            or coupled_sidecar.get("verification", {}).get("status") != "ok"):
        raise ValueError("coupled arena result or OSS record is not the accepted pair")
    if not all(coupled.get("cases", {}).get(name, {}).get("accepted_steps") == 82 and
               coupled["cases"][name].get("checkpoint_replay_equal") is True
               for name in ("baseline", "coupled")):
        raise ValueError("coupled arena pair lacks complete replayed cases")
    if report_receipt.get("status") != "pass" or (
        report_receipt.get("input_sha256") != hashes["campaign_results"] or
        report_receipt.get("html_sha256") != hashes["campaign_report"] or
        report_receipt.get("oss_record_sha256") != hashes["campaign_oss_record"]):
        raise ValueError("campaign report receipt does not match preserved inputs")
    if integrated.get("status") != "pass":
        raise ValueError("integrated run is not passed")
    verify = subprocess.run([str(oss), "verify", "--root", str(ROOT), "--json"],
                            cwd=ROOT, capture_output=True, text=True, timeout=30,
                            check=False)
    if verify.returncode != 0:
        raise RuntimeError(f"Ocura OSS verification failed: {verify.stderr[:500]}")
    verification = json.loads(verify.stdout)
    if verification.get("status") != "ok" or verification.get("problems"):
        raise RuntimeError("Ocura OSS ledger has verification problems")
    return {"status": "pass", "paths": {key: str(value.resolve()) for key, value in paths.items()},
            "sha256": hashes, "launcher_source_test_tool_sha256": _launcher_hashes(),
            "oss_verification_status": verification["status"],
            "oss_logs_checked": verification.get("counts", {}).get("logs_checked"),
            "campaign_pairs": len(campaign.get("pairs", [])),
            "coupled_cases": 2,
            "integrated_components": len(integrated.get("components", {}))}


def _occupied(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def probe(port: int, kind: str, expected_report_sha256: str) -> str:
    """Return free/reusable, or reject an unrelated/stale port occupant."""
    if not _occupied(port):
        return "free"
    try:
        base = f"http://127.0.0.1:{port}"
        if kind == "board":
            body = urllib.request.urlopen(base + "/", timeout=2).read(2_000_000)
            valid = b"Agent work board" in body and b"Completed activity" in body
        else:
            state = json.load(urllib.request.urlopen(base + "/api/state", timeout=2))
            campaign = urllib.request.urlopen(base + "/campaign", timeout=2).read(20_000_001)
            valid = (state.get("status") == "ok" and state.get("recording_available") is True
                     and hashlib.sha256(campaign).hexdigest() == expected_report_sha256)
        if valid:
            return "reused"
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        pass
    raise RuntimeError(f"port {port} is occupied by an unrecognized or stale {kind} service; leave it running and choose another port")


def _wait_ready(port: int, kind: str, report_hash: str, child: subprocess.Popen) -> None:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f"{kind} service exited during startup with code {child.returncode}")
        try:
            if probe(port, kind, report_hash) == "reused":
                return
        except RuntimeError:
            pass
        time.sleep(0.2)
    raise TimeoutError(f"{kind} service did not become ready on port {port}")


def _stop(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    try:
        if os.name == "nt":
            child.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            child.send_signal(signal.SIGINT)
        child.wait(timeout=4)
    except (OSError, subprocess.TimeoutExpired):
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="validate inputs and ports without starting servers")
    parser.add_argument("--board-port", type=int, default=8765)
    parser.add_argument("--playground-port", type=int, default=8766)
    parser.add_argument("--campaign-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--oss-cli", type=Path, default=ROOT / ".venv/Scripts/ocura-oss.exe")
    parser.add_argument("--engine-cli", type=Path, help="optional installed local Engine CLI")
    parser.add_argument("--output", type=Path, help="new run directory; default uses UTC time and launcher PID")
    args = parser.parse_args()
    if (not 1024 <= args.board_port <= 65535 or not 1024 <= args.playground_port <= 65535
            or args.board_port == args.playground_port):
        parser.error("choose two distinct ports in [1024, 65535]")
    try:
        report = args.campaign_report.resolve()
        run = args.run.resolve()
        oss = args.oss_cli.resolve()
        engine = args.engine_cli.resolve() if args.engine_cli is not None else None
        checked = preflight(oss=oss, report=report, run=run, engine=engine)
        ports = {"board": probe(args.board_port, "board", checked["sha256"]["campaign_report"]),
                 "playground": probe(args.playground_port, "playground",
                                     checked["sha256"]["campaign_report"])}
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "error": str(exc)}), file=sys.stderr)
        return 1
    urls = {"board": f"http://127.0.0.1:{args.board_port}/",
            "playground": f"http://127.0.0.1:{args.playground_port}/",
            "campaign": f"http://127.0.0.1:{args.playground_port}/campaign"}
    if args.check_only:
        print(json.dumps({"status": "pass", "mode": "check-only", "ports": ports,
                          "urls": urls, "preflight": checked}, indent=2))
        return 0
    output = args.output or (ROOT / "runs" /
        f"live_demo_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{os.getpid()}")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    launched: dict[str, subprocess.Popen] = {}
    logs = []
    try:
        for kind, port, argv in (
            ("board", args.board_port, [sys.executable, "tools/agent_dashboard.py", "--port", str(args.board_port)]),
            ("playground", args.playground_port,
             [sys.executable, "tools/run_interactive_demo.py", "--port", str(args.playground_port),
              "--run", str(run), "--oss-cli", str(oss), "--campaign-report", str(report)]
             + ["--board-url", urls["board"]]
             + (["--engine-cli", str(engine)] if engine else [])),
        ):
            if ports[kind] == "reused":
                continue
            log = (output / f"{kind}.log").open("x", encoding="utf-8")
            logs.append(log)
            flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                     if os.name == "nt" else 0)
            child = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=flags, start_new_session=os.name != "nt")
            launched[kind] = child
            _wait_ready(port, kind, checked["sha256"]["campaign_report"], child)
        receipt = {"status": "ready", "utc": datetime.now(timezone.utc).isoformat(),
                   "platform": platform.platform(), "python": sys.version,
                   "ports": ports, "urls": urls, "preflight": checked,
                   "owned_process_ids": {key: child.pid for key, child in launched.items()},
                   "stop": "Press Ctrl+C in this launcher terminal; only its owned child processes stop.",
                   "limitations": "Reused services keep their existing state and are never stopped by this launcher."}
        with (output / "launch.json").open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": "ready", "urls": urls, "ports": ports,
                          "owned_process_ids": receipt["owned_process_ids"],
                          "receipt": str(output / "launch.json")}), flush=True)
        while True:
            for kind, child in launched.items():
                if child.poll() is not None:
                    raise RuntimeError(f"owned {kind} service exited with code {child.returncode}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(json.dumps({"status": "stopping", "owned_process_ids":
                          {key: child.pid for key, child in launched.items()}}), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "error": str(exc)}), file=sys.stderr, flush=True)
        return 1
    finally:
        for child in reversed(list(launched.values())):
            _stop(child)
        for stream in logs:
            stream.close()


if __name__ == "__main__":
    raise SystemExit(main())
