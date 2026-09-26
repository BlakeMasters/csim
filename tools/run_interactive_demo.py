#!/usr/bin/env python3
"""Local, bounded browser playground for synthetic virtual-cell episodes.

Only declared reset, typed rate step, deterministic replay, and accepted-session
export are exposed. The service listens on loopback and runs no client command.
Episode modes are explicit; their numerical and biological limits still apply.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import uuid
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.biological_rules import load_ruleset
from cellsim_v2.ligand_communication import LigandCommunicationEpisode
from cellsim_v2.nfkb_episode import NfkbEpisode
from cellsim_v2.nfkb_predictor import predict_frozen
from cellsim_v2.shared_cell_arena import SharedCellArena
from cellsim_v2.symbolic_logic import from_ruleset
from cellsim_v2.synthetic_cell_episode import make_synthetic_episode
from run_symbolic_demo import run as run_symbolic_demo
from cellsim_v2.symbolic_logic import canonical_digest


def _finite(value: object, name: str, *, minimum: float = 0.0,
            maximum: float = 100.0, strict_minimum: bool = False) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or result < minimum or (strict_minimum and result == minimum) or result > maximum:
        raise ValueError(f"{name} must be within the declared demo range")
    return result


def _steps(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 32:
        raise ValueError("horizon_steps must be an integer from 1 to 32")
    return value


@dataclass(frozen=True)
class ModeSpec:
    key: str
    title: str
    action_label: str
    default_rate_mol_s: float
    defaults: dict
    control_labels: dict

    def configuration(self, supplied: object) -> dict:
        if type(supplied) is not dict or set(supplied) != set(self.defaults):
            raise ValueError(f"{self.key} reset requires exactly {sorted(self.defaults)}")
        c = dict(supplied)
        if self.key == "nfkb":
            if type(c["horizon_steps"]) is not int or not 1 <= c["horizon_steps"] <= 100:
                raise ValueError("NF-kB horizon_steps must be an integer from 1 to 100")
        else:
            c["horizon_steps"] = _steps(c["horizon_steps"])
        if self.key == "arena" and c["horizon_steps"] > 8:
            raise ValueError("arena horizon_steps must be at most 8")
        if self.key == "nfkb":
            c["step_min"] = _finite(c["step_min"], "step_min", minimum=0.1, maximum=120.0)
        else:
            c["step_s"] = _finite(c["step_s"], "step_s", minimum=0.001, maximum=2.0)
        if self.key == "uptake":
            c["initial_concentration_mol_m3"] = _finite(
                c["initial_concentration_mol_m3"], "initial concentration", maximum=10.0)
            c["initial_memory"] = _finite(c["initial_memory"], "initial memory", maximum=10.0)
            c["target_response_index"] = _finite(
                c["target_response_index"], "target response index", maximum=10.0)
        elif self.key == "ligand":
            c["initial_sender_amount_mol"] = _finite(
                c["initial_sender_amount_mol"], "initial sender amount", maximum=10.0)
        elif self.key == "arena":
            if type(c["cell_count"]) is not int or not 1 <= c["cell_count"] <= 5:
                raise ValueError("arena cell_count must be an integer from 1 to 5")
            c["initial_concentration_mol_m3"] = _finite(
                c["initial_concentration_mol_m3"], "initial concentration", maximum=10.0)
            c["diagnostic_target_memory"] = _finite(
                c["diagnostic_target_memory"], "diagnostic target memory", maximum=10.0)
        elif self.key == "nfkb":
            if type(c["cell_count"]) is not int or not 1 <= c["cell_count"] <= 5:
                raise ValueError("NF-kB cell_count must be an integer from 1 to 5")
            c["initial_stimulus_reservoir_mol"] = _finite(
                c["initial_stimulus_reservoir_mol"], "initial stimulus reservoir", maximum=10.0)
            c["initial_payload_reservoir_mol"] = _finite(
                c["initial_payload_reservoir_mol"], "initial payload reservoir", maximum=10.0)
        return c

    def make(self, config: dict):
        if self.key == "uptake":
            return make_synthetic_episode(**config)
        if self.key == "ligand":
            return LigandCommunicationEpisode(**config)
        if self.key == "arena":
            return SharedCellArena(**config)
        if self.key == "nfkb":
            return NfkbEpisode(**config)
        raise ValueError("unsupported episode mode")

    def restore(self, checkpoint: dict):
        if self.key == "uptake":
            from cellsim_v2.synthetic_cell_episode import SyntheticCellEpisode
            return SyntheticCellEpisode.from_checkpoint(copy.deepcopy(checkpoint))
        if self.key == "ligand":
            return LigandCommunicationEpisode.from_checkpoint(copy.deepcopy(checkpoint))
        if self.key == "arena":
            return SharedCellArena.from_checkpoint(copy.deepcopy(checkpoint))
        if self.key == "nfkb":
            return NfkbEpisode.from_checkpoint(copy.deepcopy(checkpoint))
        raise ValueError("unsupported episode mode")


MODES = {
    "uptake": ModeSpec(
        "uptake", "Cell uptake", "Maximum field-to-cell uptake rate (mol/s)", 0.1,
        {"initial_concentration_mol_m3": 1.0, "initial_memory": 0.0,
         "horizon_steps": 4, "step_s": 0.25, "target_response_index": 0.5},
        {"initial_concentration_mol_m3": "Initial field concentration (mol/m³)",
         "initial_memory": "Initial response memory (1)",
         "horizon_steps": "Horizon steps", "step_s": "Step duration (s, 0.001–2)",
         "target_response_index": "Synthetic score target (1)"}),
    "ligand": ModeSpec(
        "ligand", "Ligand release and sensing", "Sender secretion rate (mol/s)", 0.04,
        {"horizon_steps": 3, "step_s": 0.5, "initial_sender_amount_mol": 0.1},
        {"horizon_steps": "Horizon steps", "step_s": "Step duration (s, 0.001–2)",
         "initial_sender_amount_mol": "Initial sender inventory (mol)"}),
    "arena": ModeSpec(
        "arena", "Shared-field cell arena", "Per-cell maximum uptake rate (mol/s)", 0.01,
        {"cell_count": 2, "horizon_steps": 6, "step_s": 0.25,
         "initial_concentration_mol_m3": 1.0, "diagnostic_target_memory": 0.5},
        {"cell_count": "Independent cell instances (1–5)",
         "horizon_steps": "Horizon steps (1–8)", "step_s": "Step duration (s, 0.001–2)",
         "initial_concentration_mol_m3": "Initial shared-field concentration (mol/m³)",
         "diagnostic_target_memory": "Synthetic score target per cell (1)"}),
    "nfkb": ModeSpec(
        "nfkb", "NF-κB response + payload (synthetic)", "Typed stimulus/payload interval", 0.0,
        {"cell_count": 3, "horizon_steps": 82, "step_min": 6.0,
         "initial_stimulus_reservoir_mol": 0.5, "initial_payload_reservoir_mol": 0.1},
        {"cell_count": "Independent cell instances (1–5)",
         "horizon_steps": "Horizon steps (1–100; 82 aligns with 492 min observed axis)",
         "step_min": "Step duration (min; default 6)",
         "initial_stimulus_reservoir_mol": "Finite synthetic stimulus reservoir (mol)",
         "initial_payload_reservoir_mol": "Finite generic payload reservoir (mol)"}),
}


def _json_pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _read_json(path: Path) -> dict | None:
    if not path.is_file() or path.stat().st_size > 10_000_000:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=_json_pairs, parse_constant=_reject_constant)
    except (OSError, ValueError):
        return None
    return value if type(value) is dict else None


def _load_coupled_arena(path: Path) -> dict:
    """Bind one completed synthetic arena result to its verified OSS sidecar."""
    path = path.resolve()
    if path.name != "results.json" or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("--coupled-arena-result must name one existing results.json under 2 MB")
    raw = path.read_bytes()
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_pairs,
                            parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("coupled arena result must be strict UTF-8 JSON") from exc
    receipt = _read_json(path.with_name("oss_record.json"))
    if type(result) is not dict or result.get("status") != "pass" or receipt is None:
        raise ValueError("coupled arena requires a passed result and adjacent OSS record")
    digest = hashlib.sha256(raw).hexdigest()
    if (receipt.get("results_sha256") != digest or receipt.get("status") != "passed"
            or receipt.get("source_test_tool_sha256") != result.get("source_test_tool_sha256")):
        raise ValueError("coupled arena result/OSS SHA-256 or status does not match")
    verification = receipt.get("verification")
    if (type(verification) is not dict or verification.get("status") != "ok"
            or verification.get("problems") != []
            or type(receipt.get("atom_id")) is not str
            or type(receipt.get("chokepoint_id")) is not str):
        raise ValueError("coupled arena OSS verification is incomplete")
    config = result.get("configuration")
    if type(config) is not dict or type(config.get("cell_count")) is not int or not 1 <= config["cell_count"] <= 5:
        raise ValueError("coupled arena cell count is invalid")
    horizon = config.get("horizon_steps")
    if type(horizon) is not int or not 1 <= horizon <= 100:
        raise ValueError("coupled arena horizon is invalid")
    expected_ids = {f"cell_{i}" for i in range(1, config["cell_count"] + 1)}
    cases = result.get("cases")
    if type(cases) is not dict or set(cases) != {"baseline", "coupled"}:
        raise ValueError("coupled arena requires matched baseline/coupled cases")
    selected_cases = {}
    for name in ("baseline", "coupled"):
        case = cases[name]
        if type(case) is not dict or case.get("accepted_steps") != horizon:
            raise ValueError("coupled arena case has an incomplete accepted horizon")
        trace = case.get("trace")
        if type(trace) is not list or len(trace) != horizon + 1:
            raise ValueError("coupled arena case trace length is invalid")
        selected_trace = []
        for sample in trace:
            if type(sample) is not dict or type(sample.get("cells")) is not list:
                raise ValueError("coupled arena sample is invalid")
            cells = sample["cells"]
            if len(cells) != config["cell_count"] or {c.get("cell_id") for c in cells} != expected_ids:
                raise ValueError("coupled arena cell identities are invalid")
            selected_cells = []
            for cell in cells:
                position = cell.get("position_m")
                if type(position) is not list or len(position) != 3:
                    raise ValueError("coupled arena cell position is invalid")
                selected_cells.append({"cell_id": cell["cell_id"], "model_id": cell.get("model_id"),
                                       "position_m": [_finite(v, "position_m", maximum=1e9) for v in position],
                                       "nuclear_proxy": _finite(cell.get("nuclear_proxy"), "nuclear_proxy", maximum=1e9),
                                       "feedback": _finite(cell.get("feedback"), "feedback", maximum=1e9),
                                       "reporter_index": _finite(cell.get("reporter_index"), "reporter_index", maximum=1e9),
                                       "mediator_inventory_mol": _finite(cell.get("mediator_inventory_mol"), "mediator_inventory_mol", maximum=1e9)})
            selected_trace.append({"time_min": _finite(sample.get("time_min"), "time_min", maximum=1e9),
                                   "stimulus_code": sample.get("stimulus_code"),
                                   "mediator_field_amount_mol": _finite(sample.get("mediator_field_amount_mol"), "mediator amount", maximum=1e9),
                                   "mediator_field_concentration_mol_m3": _finite(sample.get("mediator_field_concentration_mol_m3"), "mediator concentration", maximum=1e9),
                                   "mediator_waste_amount_mol": _finite(sample.get("mediator_waste_amount_mol"), "mediator waste", maximum=1e9),
                                   "cells": selected_cells})
        selected_cases[name] = {"trace": selected_trace, "accepted_steps": horizon,
                                "checkpoint_replay_equal": case.get("checkpoint_replay_equal"),
                                "maximum_amount_residual_mol": case.get("maximum_amount_residual_mol")}
    if ([item["time_min"] for item in selected_cases["baseline"]["trace"]]
            != [item["time_min"] for item in selected_cases["coupled"]["trace"]]):
        raise ValueError("coupled arena case clocks differ")
    return {"status": "available", "scope": "synthetic coupled NF-κB arena; not a measured or fitted mediator model",
            "artifact_path": str(path), "result_sha256": digest,
            "source_test_tool_sha256": result.get("source_test_tool_sha256"),
            "oss_atom_id": receipt["atom_id"], "oss_chokepoint_id": receipt["chokepoint_id"],
            "oss_verified_logs": verification.get("logs_checked"),
            "configuration": config, "comparison": result.get("comparison"),
            "maximum_amount_residual_mol": result.get("maximum_amount_residual_mol"),
            "cases": selected_cases}


def _latest_evidence(explicit: Path | None) -> dict:
    runs = ROOT / "runs"
    candidates = [explicit.resolve()] if explicit is not None else [
        p for p in runs.glob("integrated_demo*") if p.is_dir()]
    records = []
    for candidate in candidates:
        if candidate.is_file() and candidate.name in ("results.json", "receipt.json"):
            candidate = candidate.parent
        workload = candidate / "workload" if (candidate / "workload/results.json").is_file() else candidate
        result_path = workload / "results.json"
        result = _read_json(result_path)
        if result is None or type(result.get("components")) is not dict:
            continue
        receipt_path = candidate / "receipt.json" if workload != candidate else None
        receipt = _read_json(receipt_path) if receipt_path is not None else None
        modified = receipt_path.stat().st_mtime if receipt_path is not None and receipt_path.is_file() else result_path.stat().st_mtime
        records.append((modified, workload, result, receipt))
    if not records:
        return {"status": "not_available", "description": "No completed integrated run found yet",
                "symbolic": {}, "self_play": {}}
    # A newer failed attempt must not hide a completed OSS/Engine receipt.
    _, workload, result, receipt = max(records, key=lambda item: (
        item[3] is not None and item[3].get("status") == "passed",
        item[3] is not None, item[0]))
    symbolic_result = _read_json(workload / "symbolic/results.json") or {}
    play_result = _read_json(workload / "self_play/results.json") or {}
    arms = {}
    for name, raw in (play_result.get("arms") or {}).items():
        if type(raw) is not dict:
            continue
        attempts = []
        for attempt in raw.get("attempts", []):
            if type(attempt) is dict:
                schedule = attempt.get("schedule") if type(attempt.get("schedule")) is dict else {}
                attempts.append({"round": attempt.get("round"), "schedule": schedule.get("id"),
                                 "prefit_mae_memory_1": attempt.get("prefit_mae_memory_1"),
                                 "mean_teacher_diagnostic_score": attempt.get("mean_teacher_diagnostic_score"),
                                 "status": attempt.get("status")})
        evaluation = raw.get("evaluation") if type(raw.get("evaluation")) is dict else {}
        arms[name] = {"attempts": attempts,
                      "one_step_mae_memory_1": evaluation.get("one_step_mae_memory_1"),
                      "weights_unchanged": evaluation.get("weights_unchanged")}
    return {
        "status": "available", "workload_path": str(workload),
        "workload_status": result.get("status"),
        "engine_run_id": receipt.get("engine_run_id") if receipt else None,
        "engine_status": receipt.get("engine_status") if receipt else None,
        "oss_atom_id": receipt.get("oss_atom_id") if receipt else None,
        "oss_chokepoint_id": receipt.get("oss_chokepoint_id") if receipt else None,
        "oss_verification_status": receipt.get("oss_verification_status") if receipt else None,
        "symbolic": {"status": symbolic_result.get("status"),
                     "accepted_intervals": symbolic_result.get("accepted_intervals"),
                     "trace_bytes_equal": symbolic_result.get("trace_bytes_equal"),
                     "rejection": symbolic_result.get("unsupported_construct")},
        "self_play": {"status": play_result.get("status"),
                      "rl_algorithm_run": play_result.get("rl_algorithm_run"),
                      "arms": arms},
    }


def _observed_artifact() -> dict | None:
    """Load only an agent-produced, provenance-preserving local trace artifact."""
    metadata = sorted((ROOT / "runs").glob("nfkb_metadata_*/demo_overlay.json"),
                      key=lambda path: path.stat().st_mtime, reverse=True)
    banded = sorted((ROOT / "runs").glob("nfkb_variability_*/comparison_with_bands.json"),
                    key=lambda path: path.stat().st_mtime, reverse=True)
    modeled = sorted((ROOT / "runs").glob("nfkb_model_*/comparison_overlay.json"),
                     key=lambda path: path.stat().st_mtime, reverse=True)
    raw = sorted((ROOT / "runs").glob("nfkb_observed_*/observed_traces.json"),
                 key=lambda path: path.stat().st_mtime, reverse=True)
    candidates = metadata + banded + modeled + raw
    for path in candidates:
        data = _read_json(path)
        if data is not None and data.get("status") == "pass" and type(data.get("conditions")) is list:
            data["_artifact_path"] = str(path)
            return data
    return None


def _observed_response(condition_id: str | None) -> dict:
    data = OBSERVED
    if data is None:
        return {"status": "not_available", "description": "No qualified local observed-trace artifact is loaded"}
    identity = {"status": "available", "schema_version": data.get("schema_version"),
                "artifact_path": data["_artifact_path"], "source": data.get("source"),
                "observable": data.get("observable"), "switch_times_min": data.get("switch_times_min"),
                "split": data.get("split"), "physical_dose_values": data.get("physical_dose_values"),
                "frozen_candidate_sha256": data.get("frozen_candidate_sha256"),
                "model_scope": data.get("model_scope"),
                "posthoc_residuals": ({"per_dose": RESIDUAL.get("per_dose"),
                                       "worse_than_current_only": RESIDUAL.get("state_space_worse_than_current_only_conditions"),
                                       "artifact_path": RESIDUAL.get("_artifact_path")}
                                      if RESIDUAL is not None else None)}
    if condition_id is None:
        identity["conditions"] = [{key: item.get(key) for key in
                                   ("condition_id", "ligand_sequence", "sequence_key", "dose_tier",
                                    "split", "row_count", "complete_trace_row_count")}
                                  for item in data["conditions"]]
        return identity
    if not condition_id.isdecimal() or not 1 <= int(condition_id) <= 75:
        raise ValueError("condition_id must be an integer from 1 to 75")
    condition = next((item for item in data["conditions"]
                      if item.get("condition_id") == int(condition_id)), None)
    if condition is None:
        raise ValueError("observed condition not found")
    identity["condition"] = condition
    return identity


class DemoSession:
    def __init__(self, evidence_path: Path | None):
        self.lock = threading.RLock()
        self.evidence_path = evidence_path
        self.mode = "nfkb"
        self.config = dict(MODES[self.mode].defaults)
        self.episode = MODES[self.mode].make(self.config)
        self.initial_checkpoint = self.episode.checkpoint()
        self.accepted: list[dict] = []
        self.timeline: list[dict] = []
        self.last_replay: dict | None = None
        self.last_record: dict | None = None
        self.revision = 0
        self.symbolic_ir = from_ruleset(load_ruleset(
            ROOT / "configs/biological_rules.synthetic.json"))

    def _snapshot_unlocked(self) -> dict:
        spec = MODES[self.mode]
        return {
            "status": "ok", "mode": self.mode,
            "modes": [{"key": m.key, "title": m.title, "action_label": m.action_label,
                       "default_rate_mol_s": m.default_rate_mol_s,
                       "defaults": m.defaults, "control_labels": m.control_labels}
                      for m in MODES.values()],
            "configuration": dict(self.config), "observation": self.episode.observe(),
            "accepted_steps": len(self.accepted), "timeline": copy.deepcopy(self.timeline),
            "last_replay": copy.deepcopy(self.last_replay),
            "last_record": copy.deepcopy(self.last_record),
            "recording_available": (OSS_CLI is not None and
                                    (ROOT / "tools/replay_interactive_trace.py").is_file()),
            "engine_recording_available": ENGINE_CLI is not None,
            "campaign_report_available": CAMPAIGN_HTML is not None,
            "coupled_arena_available": COUPLED_ARENA is not None,
            "symbolic_program": {"schema_version": self.symbolic_ir["schema_version"],
                                 "kind": self.symbolic_ir["kind"],
                                 "ruleset_sha256": self.symbolic_ir["ruleset_sha256"],
                                 "symbols": self.symbolic_ir["symbols"],
                                 "statements": self.symbolic_ir["statements"]},
        }

    def snapshot(self) -> dict:
        with self.lock:
            result = self._snapshot_unlocked()
        result["evidence"] = _latest_evidence(self.evidence_path)
        return result

    def reset(self, request: dict) -> dict:
        if set(request) != {"mode", "configuration"}:
            raise ValueError("reset requires mode and configuration only")
        mode = request["mode"]
        if type(mode) is not str or mode not in MODES:
            raise ValueError("unsupported episode mode")
        spec = MODES[mode]
        config = spec.configuration(request["configuration"])
        episode = spec.make(config)
        checkpoint = episode.checkpoint()
        with self.lock:
            self.mode, self.config, self.episode = mode, config, episode
            self.initial_checkpoint = checkpoint
            self.accepted = []
            self.timeline = []
            self.last_replay = None
            self.last_record = None
            self.revision += 1
        return self.snapshot()

    def step(self, request: dict) -> dict:
        with self.lock:
            if self.mode == "nfkb":
                expected_keys = {"stimulus_code", "stimulus_admin_mol", "stimulus_withdraw_mol",
                                 "payload_admin_mol", "payload_uptake_rates_mol_min_by_cell"}
                if set(request) != expected_keys or type(request["payload_uptake_rates_mol_min_by_cell"]) is not dict:
                    raise ValueError("NF-kB step requires typed stimulus/payload interval controls only")
                ids = {f"cell_{i}" for i in range(1, self.config["cell_count"] + 1)}
                if set(request["payload_uptake_rates_mol_min_by_cell"]) != ids:
                    raise ValueError(f"NF-kB payload rates require exactly {sorted(ids)}")
                code = request["stimulus_code"]
                if code is not None and (type(code) is not str or code not in {"T", "I", "L", "P", "FM"}):
                    raise ValueError("stimulus_code must be T, I, L, P, FM, or null")
                proposal = {"stimulus_code": code,
                            "stimulus_admin_mol": _finite(request["stimulus_admin_mol"], "stimulus_admin_mol", maximum=10.0),
                            "stimulus_withdraw_mol": _finite(request["stimulus_withdraw_mol"], "stimulus_withdraw_mol", maximum=10.0),
                            "payload_admin_mol": _finite(request["payload_admin_mol"], "payload_admin_mol", maximum=10.0),
                            "payload_uptake_rates_mol_min_by_cell": {
                                cid: _finite(value, cid, maximum=10.0)
                                for cid, value in request["payload_uptake_rates_mol_min_by_cell"].items()}}
            elif self.mode == "arena":
                if set(request) != {"rates_mol_s"} or type(request["rates_mol_s"]) is not dict:
                    raise ValueError("arena step requires rates_mol_s by cell identity only")
                expected = {f"cell_{i}" for i in range(1, self.config["cell_count"] + 1)}
                if set(request["rates_mol_s"]) != expected:
                    raise ValueError(f"arena rates_mol_s requires exactly {sorted(expected)}")
                proposal = {key: _finite(value, key, maximum=10.0)
                            for key, value in request["rates_mol_s"].items()}
            else:
                if set(request) != {"rate_mol_s"}:
                    raise ValueError("step requires rate_mol_s only")
                proposal = _finite(request["rate_mol_s"], "rate_mol_s", maximum=10.0)
            before = self.episode.observe()
            checkpoint_before = self.episode.checkpoint()
            try:
                action = (self.episode.make_actions(proposal) if self.mode == "arena"
                          else self.episode.make_action(**proposal) if self.mode == "nfkb"
                          else self.episode.make_action(proposal))
                transition = self.episode.step(action)
            except (ValueError, TypeError, PermissionError) as exc:
                unchanged = (self.episode.observe() == before and
                             self.episode.checkpoint() == checkpoint_before)
                event = {"index": len(self.timeline) + 1, "kind": "rejected",
                         "mode": self.mode,
                         "before": before, "state_unchanged": unchanged,
                         "reason": str(exc)}
                event["attempted_proposal" if self.mode == "nfkb" else "attempted_rates_mol_s"] = proposal
                self.timeline.append(event)
                if not unchanged:
                    raise RuntimeError("episode state changed during rejected action") from exc
                response = {"status": "rejected", "event": copy.deepcopy(event),
                            "state": self._snapshot_unlocked()}
            else:
                event = {"index": len(self.timeline) + 1, "kind": "accepted",
                         "mode": self.mode, "before": before,
                         "action": action, "transition": transition}
                event["proposal" if self.mode == "nfkb" else "rates_mol_s"] = proposal
                self.accepted.append(event)
                self.timeline.append(event)
                self.last_replay = None
                self.last_record = None
                self.revision += 1
                response = {"status": "accepted", "event": copy.deepcopy(event),
                            "state": self._snapshot_unlocked()}
        response["state"]["evidence"] = _latest_evidence(self.evidence_path)
        return response

    def replay(self) -> dict:
        with self.lock:
            spec = MODES[self.mode]
            clone = spec.restore(self.initial_checkpoint)
            replayed = []
            for accepted in self.accepted:
                action = (clone.make_actions(accepted["rates_mol_s"])
                          if self.mode == "arena" else clone.make_action(**accepted["proposal"])
                          if self.mode == "nfkb" else clone.make_action(accepted["rates_mol_s"]))
                transition = clone.step(action)
                replayed.append({"action": action, "transition": transition})
            equal = (clone.checkpoint() == self.episode.checkpoint() and
                     all(item["action"] == accepted["action"] and
                         item["transition"] == accepted["transition"]
                         for item, accepted in zip(replayed, self.accepted)))
            self.last_replay = {"equal": equal, "accepted_steps": len(replayed),
                                "current_state_unchanged": True,
                                "checkpoint_sha256": clone.checkpoint().get("sha256")}
        return self.snapshot()

    def session_export(self) -> dict:
        with self.lock:
            if not self.accepted or not self.episode.observe().get("terminated"):
                raise ValueError("complete at least one accepted episode before export")
            if len(self.accepted) != self.config["horizon_steps"]:
                raise ValueError("export requires a complete accepted horizon")
            if self.mode != "uptake":
                raise ValueError("Engine/OSS session replay currently supports uptake mode only")
            return {"schema": "cellsim.interactive-uptake-trace.v1",
                    "initial_concentration_mol_m3": self.config["initial_concentration_mol_m3"],
                    "initial_memory": self.config["initial_memory"],
                    "step_s": self.config["step_s"],
                    "target_response_index": self.config["target_response_index"],
                    "horizon_steps": self.config["horizon_steps"],
                    "rates_mol_s": [event["rates_mol_s"] for event in self.accepted]}


SESSION: DemoSession | None = None
ENGINE_CLI: Path | None = None
OSS_CLI: Path | None = None
RUN_PYTHON: Path | None = None
OBSERVED: dict | None = None
RESIDUAL: dict | None = None
FROZEN: dict | None = None
CAMPAIGN_HTML: bytes | None = None
COUPLED_ARENA: dict | None = None
BOARD_URL = "http://127.0.0.1:8765/"
PORT = 8766


def _run_symbolic_experiment(session: DemoSession) -> dict:
    """Run the displayed, fixed synthetic IR through its checked lowering path."""
    output = ROOT / "runs" / ("interactive_symbolic_" +
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8])
    report = run_symbolic_demo(output)
    if (report["status"] != "completed" or not report["trace_bytes_equal"] or
            report["symbolic_ir_sha256"] != canonical_digest(session.symbolic_ir) or
            report["lowered_ruleset_sha256"] != session.symbolic_ir["ruleset_sha256"]):
        raise RuntimeError("symbolic execution did not match the displayed program")
    trace = [json.loads(line) for line in
             (output / "roundtripped/trace.jsonl").read_text(encoding="utf-8").splitlines()]
    return {"status": "completed", "scope": report["scope"],
            "symbolic_ir_sha256": report["symbolic_ir_sha256"],
            "ruleset_sha256": report["lowered_ruleset_sha256"],
            "accepted_intervals": report["accepted_intervals"],
            "trace_bytes_equal": report["trace_bytes_equal"],
            "balance_residual_mol": report["total_balance_residual_mol"],
            "artifact_path": str(output), "trace": trace}


def _validate_board_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("--board-url must be loopback HTTP with an explicit port") from exc
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or port is None or not 1 <= port <= 65535
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("--board-url must be loopback HTTP with an explicit port and root path")
    return f"http://{parsed.hostname}:{port}/"


def _page_html() -> bytes:
    page = PAGE.replace('href="http://127.0.0.1:8765/"', f'href="{BOARD_URL}"')
    if CAMPAIGN_HTML is None:
        return page.encode("utf-8")
    link = ('<nav aria-label="Campaign review" class="campaign-link">'
            '<a href="/campaign">Open the read-only NF-κB campaign review ↗</a>'
            '<span>Preserved local report with its input, result, and OSS receipt provenance.</span>'
            '</nav>')
    return page.replace("</header>", link + "</header>", 1).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "CsimLocalDemo/1"

    def _origin_ok(self) -> bool:
        host = self.headers.get("Host", "")
        allowed = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        origin = self.headers.get("Origin")
        return host in allowed and (origin is None or origin in {f"http://{item}" for item in allowed})

    def _send(self, status: int, payload: bytes, content_type: str,
              *, attachment: str | None = None,
              content_security_policy: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if content_security_policy is not None:
            self.send_header("Content-Security-Policy", content_security_policy)
        if attachment is not None:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, value: object, *, attachment: str | None = None) -> None:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(status, payload, "application/json; charset=utf-8", attachment=attachment)

    def _request(self) -> dict:
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("Content-Type must be application/json")
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit() or int(length) > 4096:
            raise ValueError("JSON request must be at most 4096 bytes")
        raw = self.rfile.read(int(length))
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_pairs,
                           parse_constant=_reject_constant)
        if type(value) is not dict:
            raise ValueError("request body must be a JSON object")
        return value

    def do_GET(self) -> None:
        if not self._origin_ok():
            self._json(403, {"status": "error", "error": "loopback origin required"})
            return
        try:
            parsed = urlsplit(self.path)
            if parsed.path == "/" and not parsed.query:
                self._send(200, _page_html(), "text/html; charset=utf-8")
            elif parsed.path == "/campaign" and not parsed.query and CAMPAIGN_HTML is not None:
                self._send(200, CAMPAIGN_HTML, "text/html; charset=utf-8",
                           content_security_policy="default-src 'none'; script-src 'none'; "
                           "style-src 'unsafe-inline'; img-src data:; base-uri 'none'; "
                           "form-action 'none'; frame-ancestors 'none'")
            elif parsed.path == "/app.js" and not parsed.query:
                self._send(200, APP_JS.encode("utf-8"), "text/javascript; charset=utf-8")
            elif parsed.path == "/pixel_renderer.js" and not parsed.query:
                self._send(200, (ROOT / "tools/pixel_renderer.js").read_bytes(), "text/javascript; charset=utf-8")
            elif parsed.path == "/pixel_renderer.css" and not parsed.query:
                self._send(200, (ROOT / "tools/pixel_renderer.css").read_bytes(), "text/css; charset=utf-8")
            elif parsed.path == "/playground_pixel_theme.css" and not parsed.query:
                self._send(200, (ROOT / "tools/playground_pixel_theme.css").read_bytes(), "text/css; charset=utf-8")
            elif parsed.path == "/api/state" and not parsed.query:
                self._json(200, SESSION.snapshot())
            elif parsed.path == "/api/observed":
                query = parse_qs(parsed.query, keep_blank_values=True)
                if set(query) - {"condition_id"} or len(query.get("condition_id", [])) > 1:
                    raise ValueError("observed query accepts one condition_id only")
                self._json(200, _observed_response(query.get("condition_id", [None])[0]))
            elif parsed.path == "/api/coupled-arena" and not parsed.query and COUPLED_ARENA is not None:
                self._json(200, COUPLED_ARENA)
            elif parsed.path == "/api/session.json" and not parsed.query:
                self._json(200, SESSION.session_export(), attachment="cellsim-session.json")
            else:
                self._json(404, {"status": "error", "error": "unknown endpoint"})
        except ValueError as exc:
            self._json(409, {"status": "error", "error": str(exc)})

    def do_POST(self) -> None:
        if not self._origin_ok():
            self._json(403, {"status": "error", "error": "loopback origin required"})
            return
        try:
            request = self._request()
            if self.path == "/api/reset":
                self._json(200, SESSION.reset(request))
            elif self.path == "/api/step":
                response = SESSION.step(request)
                self._json(200 if response["status"] == "accepted" else 409, response)
            elif self.path == "/api/replay":
                if request:
                    raise ValueError("replay takes no request fields")
                self._json(200, SESSION.replay())
            elif self.path == "/api/record":
                if request:
                    raise ValueError("record takes no request fields")
                self._json(200, _record_session("oss"))
            elif self.path == "/api/record-engine":
                if request:
                    raise ValueError("record-engine takes no request fields")
                self._json(200, _record_session("engine"))
            elif self.path == "/api/nfkb/compare":
                self._json(200, _nfkb_compare(request))
            elif self.path == "/api/nfkb/predict":
                self._json(200, _nfkb_predict(request))
            elif self.path == "/api/symbolic/run":
                if request:
                    raise ValueError("symbolic run takes no request fields")
                self._json(200, _run_symbolic_experiment(SESSION))
            else:
                self._json(404, {"status": "error", "error": "unknown endpoint"})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"status": "error", "error": str(exc)})


def _record_session(route: str) -> dict:
    if route not in {"oss", "engine"}:
        raise ValueError("unsupported recording route")
    if OSS_CLI is None:
        raise ValueError("Ocura OSS is required for session recording")
    if route == "engine" and ENGINE_CLI is None:
        raise ValueError("optional Engine recording is unavailable; launch with --engine-cli")
    wrapper = ROOT / "tools/replay_interactive_trace.py"
    if not wrapper.is_file():
        raise ValueError("session replay wrapper is not available yet")
    with SESSION.lock:
        record = SESSION.session_export()
        revision = SESSION.revision
    base = ROOT / "runs" / ("interactive_session_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    base.mkdir(parents=True, exist_ok=False)
    source = base / "session.json"
    source.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output = base / route
    argv = [sys.executable, str(wrapper), route, "--input", str(source),
            "--output", str(output), "--oss-cli", str(OSS_CLI),
            "--python", str(RUN_PYTHON)]
    if route == "engine":
        argv.extend(("--engine-cli", str(ENGINE_CLI)))
    try:
        completed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=240, check=False)
    except subprocess.TimeoutExpired as exc:
        return {"status": "timed_out", "source": str(source), "output": str(output),
                "error": f"Engine replay exceeded 240 seconds: {exc}"}
    receipt = _read_json(output / "receipt.json") or {}
    response = {"status": "passed" if completed.returncode == 0 else "failed",
                "route": route,
                "source": str(source), "output": str(output),
                "exit_code": completed.returncode,
                "engine_run_id": receipt.get("engine_run_id"),
                "oss_atom_id": receipt.get("oss_atom_id"),
                "oss_chokepoint_id": receipt.get("oss_chokepoint_id"),
                "receipt_status": receipt.get("status"),
                "stdout_tail": completed.stdout[-1200:],
                "stderr_tail": completed.stderr[-1200:]}
    with SESSION.lock:
        response["attached_to_current_session"] = SESSION.revision == revision
        if response["attached_to_current_session"]:
            SESSION.last_record = response
    return response


def _nfkb_compare(request: dict) -> dict:
    """Run a bounded paired synthetic schedule without mutating the live episode."""
    expected = {"sequence_key", "stimulus_admin_mol_per_switch", "payload_start_min",
                "payload_admin_mol_at_start", "payload_uptake_rate_mol_min"}
    if set(request) != expected:
        raise ValueError(f"NF-kB comparison requires exactly {sorted(expected)}")
    sequence = request["sequence_key"]
    if type(sequence) is not str or len(sequence) != 4 or set(sequence) != {"T", "I", "L", "P"}:
        raise ValueError("sequence_key must be a T/I/L/P permutation")
    per_switch = _finite(request["stimulus_admin_mol_per_switch"],
                         "stimulus amount per switch", maximum=1.0)
    start = _finite(request["payload_start_min"], "payload start minute", maximum=486.0)
    payload_amount = _finite(request["payload_admin_mol_at_start"],
                             "payload amount at start", maximum=1.0)
    uptake_rate = _finite(request["payload_uptake_rate_mol_min"],
                          "payload uptake rate", maximum=1.0)
    if start % 6 != 0:
        raise ValueError("payload start minute must align to the 6-minute comparison step")
    with SESSION.lock:
        live = dict(SESSION.config) if SESSION.mode == "nfkb" else dict(MODES["nfkb"].defaults)
        revision = SESSION.revision
    cell_count = live["cell_count"]
    if 4 * per_switch > live["initial_stimulus_reservoir_mol"]:
        raise ValueError("four stimulus pulses exceed the declared finite reservoir")
    if payload_amount > live["initial_payload_reservoir_mol"]:
        raise ValueError("payload pulse exceeds the declared finite reservoir")
    config = {"cell_count": cell_count, "horizon_steps": 82, "step_min": 6.0,
              "initial_stimulus_reservoir_mol": live["initial_stimulus_reservoir_mol"],
              "initial_payload_reservoir_mol": live["initial_payload_reservoir_mol"]}
    arms = {}
    for name, treatment in (("stimulus_only", False), ("stimulus_plus_generic_payload", True)):
        episode = NfkbEpisode(**config)
        observations = [episode.observe()]
        switch_actions = []
        maximum_balance_error = 0.0
        rates = {f"cell_{i}": uptake_rate if treatment else 0.0
                 for i in range(1, cell_count + 1)}
        for _ in range(82):
            action = episode.make_scheduled_action(
                sequence_key=sequence,
                stimulus_admin_mol_per_switch=per_switch,
                payload_start_min=start,
                payload_admin_mol_at_start=payload_amount if treatment else 0.0,
                payload_uptake_rates_mol_min_by_cell=rates)
            transition = episode.step(action)
            observations.append(transition["observation"])
            maximum_balance_error = max(maximum_balance_error,
                                        transition["info"]["maximum_amount_residual_mol"])
            if action["stimulus_code"] is not None or action["payload_admin_mol"]:
                switch_actions.append(action)
        arms[name] = {"observations": observations,
                      "typed_switch_actions": switch_actions,
                      "maximum_amount_residual_mol": maximum_balance_error,
                      "checkpoint_sha256": episode.checkpoint()["sha256"]}
    result = {"status": "pass", "schema": "cellsim.nfkb-synthetic-paired-comparison.v1",
              "scope": "illustrative generic stimulus and inhibitor-like payload; not fit to observed p65 data",
              "source_session_revision": revision, "configuration": config,
              "schedule": {"sequence_key": sequence,
                           "switch_times_min": [0, 120, 240, 360],
                           "stimulus_admin_mol_per_switch": per_switch,
                           "payload_start_min": start,
                           "payload_admin_mol_at_start": payload_amount,
                           "payload_uptake_rate_mol_min_by_cell": uptake_rate},
              "arms": arms}
    base = ROOT / "runs" / ("interactive_nfkb_pair_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    base.mkdir(parents=True, exist_ok=False)
    path = base / "results.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    result["artifact_path"] = str(path)
    return result


def _nfkb_predict(request: dict) -> dict:
    """Evaluate the frozen reporter candidate with categorical inputs only."""
    if set(request) != {"sequence_key", "dose_tier"}:
        raise ValueError("frozen predictor requires sequence_key and dose_tier only")
    sequence = request["sequence_key"]
    dose = request["dose_tier"]
    if type(sequence) is not str or len(sequence) != 4 or set(sequence) != {"T", "I", "L", "P"}:
        raise ValueError("sequence_key must be a T/I/L/P permutation")
    if type(dose) is not str or dose not in {"high", "mid", "low"}:
        raise ValueError("dose_tier must be high, mid, or low")
    if FROZEN is None:
        raise ValueError("frozen reporter candidate is not available")
    code = {"T": 0, "I": 1, "L": 2, "P": 3}
    tier = {"high": 1, "mid": 2, "low": 3}[dose]
    result = predict_frozen(FROZEN["candidate"], tuple(code[ch] for ch in sequence), tier,
                            frozen_candidate_sha256=FROZEN["sha256"])
    result["candidate_path"] = FROZEN["path"]
    result["status"] = "pass"
    return result


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Csim virtual-cell playground</title><style>
:root{color-scheme:dark;--bg:#0d1420;--panel:#172233;--panel2:#1e2c40;--line:#33465d;--ink:#e9f3ff;--muted:#a8bdd0;--green:#79dfbd;--blue:#80aaf9;--yellow:#edc678;--red:#f2a3a8}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 12% -5%,#264663 0%,var(--bg) 35%);font:15px/1.5 system-ui,Segoe UI,sans-serif;color:var(--ink)}header,main,footer{max-width:1440px;margin:auto;padding:0 24px}header{padding-top:34px;padding-bottom:18px}h1{font-size:clamp(2rem,4vw,3.4rem);line-height:1.08;letter-spacing:-.04em;margin:8px 0 12px}h2{font-size:1.35rem;margin:0 0 8px}h3{font-size:1rem;margin:18px 0 8px}p{margin:0 0 12px}.kicker{text-transform:uppercase;letter-spacing:.16em;color:var(--green);font-weight:800;font-size:.8rem}.intro{max-width:950px;color:var(--muted)}main{display:grid;grid-template-columns:minmax(290px,350px) minmax(0,1fr);gap:18px;padding-bottom:40px}section{background:linear-gradient(145deg,var(--panel),#132031);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:18px;box-shadow:0 14px 36px #0003}.sidebar{position:sticky;top:16px;align-self:start}.scope{padding:12px 14px;border-left:3px solid var(--green);background:#1b3837;color:#daf5e9;border-radius:4px;margin:14px 0}.muted,.note{color:var(--muted);font-size:.86rem}.badge{font-weight:750;padding:4px 9px;border-radius:100px;background:#304257}.badge.good{background:#1d4838;color:#bdf4d7}.badge.bad{background:#542e37;color:#ffd2d4}.controls{display:grid;gap:9px}label{display:block;font-size:.85rem;color:#d3e2f3}input,select,button{font:inherit}input,select{width:100%;margin-top:4px;border:1px solid #46617e;border-radius:9px;background:#0e1b2b;color:var(--ink);padding:9px}button{border:1px solid #507399;border-radius:10px;background:#284663;color:var(--ink);padding:10px 13px;cursor:pointer;font-weight:650}button:hover{background:#355a80}button:disabled{opacity:.45;cursor:not-allowed}.primary{background:#276959;border-color:#3aa27f}.primary:hover{background:#32836c}.row{display:flex;gap:9px;align-items:end;flex-wrap:wrap}.row>*{flex:1}.actions button{flex:auto}.state-grid,.charts,.evidence-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}.metric,.chart,.evidence-card{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px}.metric span,.chart label,.evidence-card span{display:block;color:var(--muted);font-size:.77rem;text-transform:uppercase;letter-spacing:.06em}.metric strong,.evidence-card strong{display:block;font-size:1.25rem;overflow-wrap:anywhere}.chart canvas{width:100%;height:100px;margin-top:8px;background:#111e2c;border-radius:7px}.status-line{min-height:30px;font-weight:650}.status-line.bad{color:var(--red)}.status-line.good{color:var(--green)}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;margin-top:10px}table{width:100%;border-collapse:collapse;min-width:680px}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid #35485e;vertical-align:top;font-variant-numeric:tabular-nums}th{font-size:.75rem;color:#d4e6f9;text-transform:uppercase;letter-spacing:.05em;background:#263b51}tr:last-child td{border-bottom:0}tr:nth-child(even){background:#fff1}code,pre{font:12px/1.5 ui-monospace,Consolas,monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0c1827;padding:12px;border-radius:8px;max-height:360px;overflow:auto}details{margin-top:10px}summary{cursor:pointer;color:#c1d9fb}a{color:#98d8ff}footer{padding-bottom:45px;color:var(--muted);font-size:.8rem}@media(max-width:850px){main{display:block}.sidebar{position:static}header,main,footer{padding-left:12px;padding-right:12px}}
</style></head><body><header><div class="kicker">Csim · local synthetic reference</div><h1>Virtual-cell playground</h1><p class="intro">Choose an episode, set a typed rate, and watch accepted cell–field state evolve. Replay the accepted history or inspect the separate symbolic and learning evidence.</p><div class="scope">Synthetic engineering examples only. Diagnostic scores are training feedback, not cell health or biological validation. The adaptive curriculum is not an RL algorithm.</div></header><main><aside class="sidebar"><section><h2>Set up an episode</h2><label>Scenario<select id="mode"></select></label><div id="config" class="controls"></div><button id="reset" class="primary">Reset scenario</button><p id="config-error" class="status-line bad" role="alert"></p></section><section><h2>Advance one step</h2><label id="action-label" for="action-rate">Typed rate (mol/s)</label><input id="action-rate" type="number" min="0" max="10" step="any"><div class="row actions"><button id="step" class="primary">Step</button><button id="replay">Verify replay</button></div><p id="action-status" class="status-line" role="status"></p><p class="note">A rejected action leaves the accepted state unchanged and remains visible in the trace.</p></section><section><h2>Export and record</h2><div class="row actions"><button id="export">Download accepted session</button><button id="record">Record through Engine + OSS</button></div><p id="record-status" class="status-line" role="status"></p><p class="note">The ledger button replays a complete uptake episode through a fixed local command. Engine and OSS IDs are execution evidence, separate from simulation results.</p></section></aside><div class="content"><section><h2>Accepted state <span id="state-badge" class="badge"></span></h2><p id="mode-description" class="muted"></p><div id="state-grid" class="state-grid"></div><h3>Live time series</h3><div id="charts" class="charts"></div></section><section><h2>Interaction trace</h2><p class="muted">Rates, field and inventory changes, memory, transfer and synthetic score are recorded per attempted step.</p><div class="table-wrap"><table><thead><tr><th>#</th><th>Status</th><th>Rate (mol/s)</th><th>Field c (mol/m³)</th><th>Inventory (mol)</th><th>Memory (1)</th><th>Transfer (mol)</th><th>Score</th></tr></thead><tbody id="trace-body"></tbody></table></div></section><section><h2>Typed symbolic program</h2><p class="muted">The current version-0 language executes only a synthetic concentration switch and gated same-species transfer. It is a separate reference scenario from the interactive episode.</p><div id="symbolic-summary" class="evidence-grid"></div><details><summary>View validated typed JSON</summary><pre id="symbolic-json"></pre></details></section><section><h2>Proposer and learner iterations</h2><p class="muted">Pre-fit development error by selected schedule, plus frozen teacher-forced one-step evaluation. Lower MAE is better; no biological or RL benefit is inferred.</p><div id="learning-summary" class="evidence-grid"></div><div class="table-wrap"><table><thead><tr><th>Arm</th><th>Round</th><th>Selected history</th><th>Pre-fit MAE (1)</th><th>Mean teacher score</th></tr></thead><tbody id="learning-body"></tbody></table></div></section><section><h2>Engine, ledger and artifact</h2><p class="muted">Execution and ledger identifiers are recorded independently of scientific component values.</p><div id="evidence-grid" class="evidence-grid"></div><p id="evidence-path" class="note"></p><button id="refresh-evidence">Refresh evidence</button></section></div></main><footer>Localhost only · no external assets · source artifacts remain in the run directory.</footer><script src="/app.js"></script></body></html>"""

# Keep the evidence qualification visible without occupying the first screenful.
PAGE = PAGE.replace("Csim · local synthetic reference", "Csim · virtual-cell R&D playground")
PAGE = PAGE.replace(
    "Synthetic engineering examples only. Diagnostic scores are training feedback, not cell health or biological validation. The adaptive curriculum is not an RL algorithm.",
    "Explore tracked cell–field dynamics, NF-κB response experiments, symbolic programs, and Ocura OSS run evidence. Model states and observed p65 traces retain distinct provenance.")
PAGE = PAGE.replace(
    "Pre-fit development error by selected schedule, plus frozen teacher-forced one-step evaluation. Lower MAE is better; no biological or RL benefit is inferred.",
    "Compare proposer-selected schedules, pre-fit development error, and frozen one-step learner evaluation. Lower MAE is better; these scores describe the computational experiment.")
PAGE = PAGE.replace("</style>",
                    ".scope{padding:4px 0;background:none;border:0;color:var(--muted);font-size:.78rem;margin:5px 0}header{padding-top:18px;padding-bottom:10px}main>.content,main>.sidebar,.content>section,#cell-scene,.csim-pixel-layout{min-width:0;max-width:100%}#observed-canvas{max-width:100%}@media(max-width:1150px){.csim-pixel-layout{grid-template-columns:minmax(0,1fr)}.csim-pixel-inspector{min-height:0}}</style>")
PAGE = PAGE.replace("style-src 'unsafe-inline'", "style-src 'self' 'unsafe-inline'")
PAGE = PAGE.replace("</style>",
                    ".csim-inspector-table{min-width:0}.csim-inspector-table{table-layout:fixed}#cell-inspector{overflow:hidden}</style>")
PAGE = PAGE.replace("</style>",
                    ".campaign-link{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:6px 0 0;padding:5px 8px;border-left:3px solid var(--yellow);background:var(--panel)}.campaign-link a{font-weight:800}.campaign-link span{color:var(--muted);font-size:.78rem}</style>")
PAGE = PAGE.replace('<button id="record">Record through Engine + OSS</button>',
                    '<button id="record">Record through Ocura OSS</button><button id="record-engine">Optional Engine + OSS</button>')
PAGE = PAGE.replace("The ledger button replays a complete uptake episode through a fixed local command. Engine and OSS IDs are execution evidence, separate from simulation results.",
                    "Record a completed uptake trace through Ocura OSS, or use the optional Engine route when configured. The integrated NF-κB run receipts appear in the evidence panel.")
PAGE = PAGE.replace("Engine, ledger and artifact", "Ocura OSS ledger and optional Engine")
PAGE = PAGE.replace(
    '<section><h2>Typed symbolic program</h2><p class="muted">The current version-0 language executes only a synthetic concentration switch and gated same-species transfer. It is a separate reference scenario from the interactive episode.</p>',
    '<section id="dsl-experiment"><h2>Typed symbolic program</h2><p class="muted">Run this fixed five-interval DSL experiment to plot an accepted cell–field trace. It encodes a synthetic concentration switch and gated same-species transfer. The other interactive episodes use their own typed action APIs.</p>')
PAGE = PAGE.replace(
    '<div id="symbolic-summary" class="evidence-grid"></div>',
    '<div id="symbolic-summary" class="evidence-grid"></div>'
    '<button id="symbolic-run" type="button">Run DSL experiment</button>'
    '<p id="symbolic-run-status" class="status-line" role="status"></p>'
    '<div id="symbolic-charts" class="charts"></div>'
    '<div class="table-wrap"><table><thead><tr><th>Time (s)</th>'
    '<th>Input concentration (mol/m³)</th><th>Cell amount (mol)</th>'
    '<th>Field amount (mol)</th><th>Accepted rule events</th></tr></thead>'
    '<tbody id="symbolic-trace"></tbody></table></div>')
PAGE = PAGE.replace("</head>", '<link rel="stylesheet" href="/pixel_renderer.css"></head>')
PAGE = PAGE.replace("</head>", '<link rel="stylesheet" href="/playground_pixel_theme.css"></head>')
PAGE = PAGE.replace('<script src="/app.js"></script>',
                    '<script src="/pixel_renderer.js"></script><script src="/app.js"></script>')
PAGE = PAGE.replace("</style>",
                    ".demo-guide{border:2px solid var(--blue);background:var(--panel);border-radius:0;padding:6px 9px;margin:5px 0 2px;box-shadow:none}"
                    ".demo-guide-top,.demo-guide-presets{display:flex;align-items:center;gap:8px;flex-wrap:wrap}"
                    ".demo-guide-top strong{color:var(--blue);text-transform:uppercase;letter-spacing:.08em}"
                    ".demo-guide-steps{font-size:11px;line-height:1.35;margin:3px 0;color:var(--ink)}"
                    ".demo-guide-presets{font-size:11px}.demo-guide-presets button{padding:3px 8px}"
                    ".demo-guide-readiness{font-size:10px;color:var(--muted);overflow-wrap:anywhere}"
                    "@media(max-width:650px){.demo-guide-steps{font-size:10px}}</style>")
PAGE = PAGE.replace("</header>",
                    '<section id="live-guide" class="demo-guide" aria-label="Live demo guide">'
                    '<div class="demo-guide-top"><strong>Live demo guide · 2-minute path</strong>'
                    '<span id="guide-readiness" class="demo-guide-readiness" role="status"></span></div>'
                    '<p class="demo-guide-steps">0:00 Choose 1, 3 or 5 identified cell instances sharing a field. '
                    '0:20 Run the separate 82-step paired comparison. '
                    '0:40 Press Step to animate the live pixel state, then click a cell to inspect it. '
                    '1:00 Browse <a href="#observed-panel">measured p65</a> and the frozen early fit. '
                    '1:20 Open the campaign review when linked. '
                    '1:40 Inspect <a href="#learning-section">learner iterations</a> and '
                    '<a href="#ledger-section">Ocura OSS evidence</a>. '
                    'Model state and observed reporter traces retain separate provenance.'
                    '<span id="coupled-guide-link"></span></p>'
                    '<div class="demo-guide-presets"><span>Reset NF-κB model:</span>'
                    '<button type="button" data-cell-preset="1">1 cell</button>'
                    '<button type="button" data-cell-preset="3">3 cells</button>'
                    '<button type="button" data-cell-preset="5">5 cells</button>'
                    '<a href="#dsl-experiment">DSL experiment ↗</a>'
                    '<a href="http://127.0.0.1:8765/" target="_blank" rel="noopener">Agent board ↗</a>'
                    '</div></section></header>', 1)
PAGE = PAGE.replace("<section><h2>Proposer and learner iterations",
                    '<section id="learning-section"><h2>Proposer and learner iterations')
PAGE = PAGE.replace("<section><h2>Ocura OSS ledger and optional Engine",
                    '<section id="ledger-section"><h2>Ocura OSS ledger and optional Engine')


APP_JS = r"""
"use strict";
let state = null;
let observedIndex = null, observedCondition = null;
let nfkbComparison = null;
let symbolicResult = null;
let predictorResult = null;
let coupledArena = null;
const $ = id => document.getElementById(id);
const fmt = value => value === null || value === undefined ? "—" :
  typeof value === "number" ? (Number.isFinite(value) ? Number(value).toPrecision(6).replace(/\.?0+$/, "") : "—") : String(value);
function node(tag, text, className) { const el = document.createElement(tag); if (text !== undefined) el.textContent = fmt(text); if (className) el.className = className; return el; }
async function api(path, method="GET", body) {
  const options = {method}; if (body !== undefined) {options.headers={"Content-Type":"application/json"}; options.body=JSON.stringify(body);}
  const response = await fetch(path, options); const data = await response.json();
  if (!response.ok && !["rejected"].includes(data.status)) throw new Error(data.error || data.reason || `HTTP ${response.status}`);
  return data;
}
function configFor(mode) { return state.modes.find(m => m.key === mode); }
function renderModes() {
  const select = $("mode"), prior = select.value; select.replaceChildren();
  for (const mode of state.modes) { const option=node("option", mode.title); option.value=mode.key; select.append(option); }
  select.value = state.modes.some(m => m.key === prior) ? prior : state.mode;
  renderConfig();
}
function renderConfig() {
  const mode=configFor($("mode").value), container=$("config"); container.replaceChildren();
  if (!mode) return;
  let details=$("config-details");if(!details){details=node("details");details.id="config-details";
    details.append(node("summary","Initial configuration · click to edit"));container.before(details);details.append(container);}
  details.open=$("mode").value!==state.mode;
  const config = $("mode").value === state.mode ? state.configuration : mode.defaults;
  for (const [key, value] of Object.entries(config)) {
    const label=node("label", mode.control_labels[key] || key);
    const input=node("input"); input.type="number"; input.step=["horizon_steps","cell_count"].includes(key) ? "1" : "any";
    input.value=String(value); input.dataset.key=key; label.append(input); container.append(label);
    if (key==="cell_count") input.addEventListener("change",renderActions);
  }
  $("action-label").textContent=mode.action_label;
  $("action-rate").value=String(mode.default_rate_mol_s);
  renderActions();
  let quick=$("quick-nfkb");if(!quick){quick=node("button","▶ Run 82-step NF-κB pair preset","primary");
    quick.id="quick-nfkb";$("reset").after(quick);
    quick.addEventListener("click",()=>{const target=$("nfkb-comparison");if(target){
      const preset={sequence_key:"TIPL",stimulus_admin_mol_per_switch:0.1,payload_start_min:120,
        payload_admin_mol_at_start:0.02,payload_uptake_rate_mol_min:0.00001};
      for(const input of target.querySelectorAll("[data-compare-key]"))input.value=String(preset[input.dataset.compareKey]);
      target.scrollIntoView({behavior:"smooth",block:"start"});$("run-nfkb-compare").click();}});}
  quick.hidden=$("mode").value!=="nfkb";quick.disabled=$("mode").value!==state.mode;
}
function renderActions() {
  let box=$("arena-actions"); if (!box) {box=node("div");box.id="arena-actions";$("action-rate").after(box);}
  box.replaceChildren(); const modeKey=$("mode").value,arena=modeKey==="arena",nfkb=modeKey==="nfkb";
  $("action-rate").hidden=arena||nfkb;$("action-label").hidden=arena||nfkb;box.hidden=!(arena||nfkb);
  $("step").disabled=state.observation.terminated||modeKey!==state.mode;
  if (!(arena||nfkb)) return;
  const mode=configFor(modeKey), countInput=$("config").querySelector('[data-key="cell_count"]');
  const count=Number(countInput?.value); if (!Number.isInteger(count)||count<1||count>5) return;
  if(nfkb) {
    box.append(node("p","Set one environment interval. T/I/L/P/FM select author schedule labels; administration and withdrawal are integrated mol, while uptake is mol/min per cell.","note"));
    const codeLabel=node("label","Stimulus label (author code only)"),select=node("select");select.id="stimulus-code";
    for(const [value,label] of [["","Keep prior / unset"],["T","T · TNF-alpha"],["I","I · IL-1beta"],["L","L · LPS"],["P","P · PAM2CSK4"],["FM","FM · author control"]]){
      const option=node("option",label);option.value=value;select.append(option);}codeLabel.append(select);box.append(codeLabel);
    for(const [key,label,value] of [["stimulus_admin_mol","Stimulus reservoir → field (mol)",0.03],
      ["stimulus_withdraw_mol","Stimulus field → waste (mol)",0],
      ["payload_admin_mol","Generic inhibitor-like payload reservoir → field (mol)",0]]){
      const row=node("label",label),input=node("input");input.type="number";input.min="0";input.max="10";input.step="any";
      input.value=String(value);input.dataset.nfkbKey=key;row.append(input);box.append(row);}
    for(let i=1;i<=count;i++){const row=node("label",`cell_${i} payload uptake controller (mol/min)`),input=node("input");
      input.type="number";input.min="0";input.max="10";input.step="any";input.value="0.001";input.dataset.payloadCell=`cell_${i}`;row.append(input);box.append(row);}
    return;
  }
  box.append(node("p","Each cell is an independent instance; the shared field step accepts one typed rate per cell.","note"));
  for(let i=1;i<=count;i++){const label=node("label",`cell_${i} fixed-rate controller (mol/s)`);
    const input=node("input");input.type="number";input.min="0";input.max="10";input.step="any";
    input.value=String(mode.default_rate_mol_s);input.dataset.cellId=`cell_${i}`;label.append(input);box.append(label);}
}
function metric(parent, label, value) { const box=node("div",undefined,"metric"); box.append(node("span",label),node("strong",value)); parent.append(box); }
function evidenceCard(parent,label,value) { const box=node("div",undefined,"evidence-card"); box.append(node("span",label),node("strong",value)); parent.append(box); }
function valuesFor(observation,mode) {
  if(mode==="nfkb") {
    const values={"Time (min)":observation.time_min,"Stimulus label":observation.stimulus_code||"unset",
      "Synthetic stimulus field (mol/m³)":observation.field.synthetic_stimulus.concentration_mol_m3,
      "Synthetic stimulus amount (mol)":observation.field.synthetic_stimulus.amount_mol,
      "Generic payload field (mol/m³)":observation.field.generic_inhibitor_payload.concentration_mol_m3,
      "Generic payload field amount (mol)":observation.field.generic_inhibitor_payload.amount_mol,
      "Stimulus reservoir (mol)":observation.reservoir_amounts_mol.synthetic_stimulus,
      "Payload reservoir (mol)":observation.reservoir_amounts_mol.generic_inhibitor_payload,
      "Remaining steps":observation.remaining_steps};
    for(const cell of observation.cells||[]){values[cell.cell_id+" nuclear proxy (1)"]=cell.nuclear_proxy;
      values[cell.cell_id+" reporter index (1)"]=cell.reporter_index;
      values[cell.cell_id+" feedback (1)"]=cell.feedback;
      values[cell.cell_id+" intracellular payload (mol)"]=cell.payload_amount_mol;}
    return values;
  }
  if (mode === "arena") {
    const values={"Time (s)":observation.time_s,"Shared field concentration (mol/m³)":observation.field_concentration_mol_m3,
      "Shared field amount (mol)":observation.field_amount_mol,"Remaining steps":observation.remaining_steps};
    for(const cell of observation.cells||[]) {
      values[cell.cell_id+" amount (mol)"]=cell.amount_mol;
      values[cell.cell_id+" memory (1)"]=cell.memory;
      values[cell.cell_id+" model / position"]=cell.model_id+" / "+JSON.stringify(cell.position_m)+" m";
    }
    return values;
  }
  if (mode === "ligand") return {
    "Time (s)":observation.time_s,"Field concentration (mol/m³)":observation.field_concentration_mol_m3,
    "Field amount (mol)":Number(observation.field_concentration_mol_m3)*0.125,
    "Sender amount (mol)":observation.sender_amount_mol,"Receiver amount (mol)":observation.receiver_amount_mol,
    "Receiver memory (1)":observation.receiver_memory,"Remaining steps":observation.remaining_steps};
  return {"Time (s)":observation.time_s,"Field concentration (mol/m³)":observation.local_concentration_mol_m3,
    "Field amount (mol)":Number(observation.local_concentration_mol_m3)*0.125,
    "Cell amount (mol)":observation.cell_amount_mol,"Response memory (1)":observation.accepted_memory,
    "Remaining steps":observation.remaining_steps};
}
function observationFrom(event) { return event.transition && event.transition.observation; }
let selectedSceneCell = null;
function renderScene() {
  let box=$("cell-scene");if(!box){box=node("div");box.id="cell-scene";box.className="metric";
    const title=node("h3","Interactive pixel cell scene"),layout=node("div",undefined,"csim-pixel-layout");
    const canvas=node("canvas");canvas.id="cell-canvas";canvas.className="csim-pixel-canvas";
    canvas.tabIndex=0;canvas.setAttribute("aria-label","Interactive cell-field scene; click a cell to inspect its state");
    const inspector=node("div");inspector.id="cell-inspector";inspector.className="csim-pixel-inspector";
    layout.append(canvas,inspector);box.append(title,layout,
      node("p","Explore one shared voxel. Click a cell to inspect before and after states; color and particles encode the model's changing values. Observed p65 traces appear in their own panel.","csim-pixel-note"));
    $("state-grid").before(box);
    canvas.addEventListener("click",event=>{const picked=window.CsimPixelRenderer.pickCell(canvas,event,state);
      if(picked){selectedSceneCell=picked;renderScene();}});
    canvas.addEventListener("keydown",event=>{if(!["ArrowLeft","ArrowRight"].includes(event.key))return;
      const ids=state.mode==="ligand"?["sender","receiver"]:state.mode==="uptake"?["cell_1"]:
        (state.observation.cells||[]).map(c=>c.cell_id);if(!ids.length)return;
      const index=Math.max(0,ids.indexOf(selectedSceneCell));selectedSceneCell=ids[(index+(event.key==="ArrowRight"?1:ids.length-1))%ids.length];
      renderScene();event.preventDefault();});}
  const ids=state.mode==="ligand"?["sender","receiver"]:state.mode==="uptake"?["cell_1"]:
    (state.observation.cells||[]).map(c=>c.cell_id);
  if(!ids.includes(selectedSceneCell))selectedSceneCell=ids[0]||null;
  const options={selectedCellId:selectedSceneCell,overlayCondition:observedCondition?.condition||null,
    switchTimesMin:observedIndex?.switch_times_min||null};
  window.CsimPixelRenderer.render($("cell-canvas"),state,options);
  window.CsimPixelRenderer.renderInspector($("cell-inspector"),state,selectedSceneCell);
}
function renderState() {
  const o=state.observation, mode=state.mode, container=$("state-grid"); container.replaceChildren();
  for (const [label,value] of Object.entries(valuesFor(o,mode))) metric(container,label,value);
  renderScene();
  $("state-badge").textContent=o.terminated ? "complete" : "ready";
  $("state-badge").className="badge "+(o.terminated?"good":"");
  $("mode-description").textContent= mode === "ligand" ?
    "One sender releases tracked material into a field; a receiver senses pre-step concentration without consuming ligand. Field amount is derived from 0.125 m³ voxel volume." :
    mode === "arena" ? "One to five independent cell instances share a 0.125 m³ voxel. Each has a declared position, model/context identity, amount and private memory. Rates are fixed controller inputs; the environment atomically rejects scarcity." :
    mode === "nfkb" ? "Explore NF-κB response across 1–5 virtual cells as stimulus and inhibitor-like payload move through tracked, finite reservoirs. Nuclear, feedback and reporter indices update each interval; stimulus codes select schedule switches. Observed p65 reporter traces are shown separately below." :
    "One cell transfers tracked tracer from a single field voxel. Response memory samples accepted pre-step concentration. Field amount is derived from 0.125 m³ voxel volume.";
  $("step").disabled=!!o.terminated||$("mode").value!==mode;
  $("export").disabled=!(o.terminated && mode==="uptake");
  $("record").disabled=!(o.terminated && mode==="uptake" && state.recording_available);
  $("record-engine").disabled=!(o.terminated && mode==="uptake" && state.recording_available && state.engine_recording_available);
  $("record").title=mode==="uptake"?"Record exact completed uptake trace through Ocura OSS":"Recording for this mode is not yet implemented";
  $("record-engine").title=state.engine_recording_available?"Optional Engine + OSS route":"Launch with --engine-cli to enable optional Engine route";
  if (!state.recording_available && !$("record-status").textContent)
    message("record-status","Ocura OSS replay wrapper is unavailable in this launch.",true);
  else if(mode!=="uptake" && !$("record-status").textContent)
    message("record-status","Record a completed uptake session here; inspect integrated NF-κB run receipts in the Ocura OSS evidence panel.");
}
function field(o,mode) { return mode==="nfkb"?o.field.synthetic_stimulus.concentration_mol_m3:["ligand","arena"].includes(mode) ? o.field_concentration_mol_m3 : o.local_concentration_mol_m3; }
function inventory(o,mode) { return mode === "nfkb"?(o.cells||[]).map(c=>c.cell_id+":"+fmt(c.payload_amount_mol)).join("; "):mode === "arena" ? (o.cells||[]).map(c=>c.cell_id+":"+fmt(c.amount_mol)).join("; ") : mode === "ligand" ? o.receiver_amount_mol : o.cell_amount_mol; }
function memory(o,mode) { return mode === "nfkb"?(o.cells||[]).map(c=>c.cell_id+":"+fmt(c.nuclear_proxy)+"/"+fmt(c.reporter_index)).join("; "):mode === "arena" ? (o.cells||[]).map(c=>c.cell_id+":"+fmt(c.memory)).join("; ") : mode === "ligand" ? o.receiver_memory : o.accepted_memory; }
function renderTrace() {
  const tbody=$("trace-body"); tbody.replaceChildren();
  const headings=tbody.closest("table").querySelectorAll("thead th");
  const labels=state.mode==="nfkb"?["#","Status","Typed interval action","Stimulus c (mol/m³)","Cell payload (mol)","Nuclear/reporter (1)","Payload transfer (mol)","Ledger / rejection"]:
    ["#","Status","Rate (mol/s)","Field c (mol/m³)","Inventory (mol)","Memory (1)","Transfer (mol)","Score / rejection"];
  labels.forEach((label,i)=>headings[i].textContent=label);
  for (const event of state.timeline) {
    const tr=node("tr"), accepted=event.kind==="accepted", after=accepted?observationFrom(event):event.before,
      before=event.before, info=accepted?(event.transition.info||{}):{};
    const rates=accepted?(event.mode==="nfkb"?event.proposal:event.rates_mol_s):
      (event.mode==="nfkb"?event.attempted_proposal:event.attempted_rates_mol_s);
    const cells=[event.index, accepted?"accepted":"rejected",typeof rates==="object"?JSON.stringify(rates):rates,
      fmt(field(before,event.mode))+" → "+fmt(field(after,event.mode)),
      fmt(inventory(before,event.mode))+" → "+fmt(inventory(after,event.mode)),
      fmt(memory(before,event.mode))+" → "+fmt(memory(after,event.mode)),
      accepted?(event.mode==="nfkb"?JSON.stringify(info.payload_transfers_mol_by_cell):event.mode==="arena"?JSON.stringify(info.transfers_mol_by_cell):info.integrated_transfer_mol):"0 (rejected)",
      accepted?(event.mode==="nfkb"?"balance "+fmt(info.maximum_amount_residual_mol):event.transition.diagnostic_score):(event.reason||"—")];
    for (const value of cells) tr.append(node("td",value)); tbody.append(tr);
  }
}
function chart(canvas,values,color) {
  const width=canvas.width=300,height=canvas.height=100,ctx=canvas.getContext("2d");
  ctx.clearRect(0,0,width,height); ctx.strokeStyle="#48617c";ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(6,82);ctx.lineTo(width-6,82);ctx.stroke();
  const valid=values.map(Number).filter(Number.isFinite); if (!valid.length) return;
  const lo=Math.min(...valid),hi=Math.max(...valid),span=hi-lo||1;
  ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.beginPath();
  values.forEach((value,index)=>{const x=10+index*(width-20)/Math.max(1,values.length-1);
    const y=76-(Number(value)-lo)/span*62;if(index===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);});ctx.stroke();
  ctx.fillStyle=color;values.forEach((value,index)=>{const x=10+index*(width-20)/Math.max(1,values.length-1);
    const y=76-(Number(value)-lo)/span*62;ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();});
}
function renderCharts() {
  const box=$("charts");box.replaceChildren(); const accepted=state.timeline.filter(e=>e.kind==="accepted");
  const observations=[accepted.length?accepted[0].before:state.observation,...accepted.map(e=>observationFrom(e))];
  const mode=state.mode,vol=0.125;
  if(mode==="nfkb") {
    const series=[["Synthetic stimulus field (mol/m³)",observations.map(o=>o.field.synthetic_stimulus.concentration_mol_m3),"#80aaf9"],
      ["Generic payload field (mol)",observations.map(o=>o.field.generic_inhibitor_payload.amount_mol),"#dda4ef"]];
    for(const cell of state.observation.cells||[]){const pick=(o,key)=>o.cells.find(c=>c.cell_id===cell.cell_id)[key];
      series.push([cell.cell_id+" nuclear proxy (1)",observations.map(o=>pick(o,"nuclear_proxy")),"#79dfbd"]);
      series.push([cell.cell_id+" reporter index (1)",observations.map(o=>pick(o,"reporter_index")),"#edc678"]);
      series.push([cell.cell_id+" payload (mol)",observations.map(o=>pick(o,"payload_amount_mol")),"#e2a5ef"]);}
    for(const [label,values,color] of series){const card=node("div",undefined,"chart"),title=node("label",label),canvas=node("canvas");
      card.append(title,canvas,node("div","Start "+fmt(values[0])+" · latest "+fmt(values.at(-1)),"note"));box.append(card);chart(canvas,values,color);}return;
  }
  if(mode==="arena") {
    const series=[["Shared field concentration (mol/m³)",observations.map(o=>field(o,mode)),"#80aaf9"],
      ["Shared field amount (mol)",observations.map(o=>o.field_amount_mol),"#6bcae1"]];
    for(const cell of state.observation.cells||[]) {
      series.push([cell.cell_id+" amount (mol)",observations.map(o=>o.cells.find(c=>c.cell_id===cell.cell_id).amount_mol),"#79dfbd"]);
      series.push([cell.cell_id+" memory (1)",observations.map(o=>o.cells.find(c=>c.cell_id===cell.cell_id).memory),"#edc678"]);
    }
    series.push(["Total cumulative transfer (mol)",accepted.reduce((a,e)=>{const total=Object.values(e.transition.info.transfers_mol_by_cell||{}).reduce((x,y)=>x+Number(y),0);a.push(a[a.length-1]+total);return a;},[0]),"#dda4ef"]);
    for(const [label,values,color] of series){const card=node("div",undefined,"chart"),title=node("label",label),canvas=node("canvas");
      card.append(title,canvas,node("div","Start "+fmt(values[0])+" · latest "+fmt(values.at(-1)),"note"));box.append(card);chart(canvas,values,color);}return;
  }
  const series=[
    ["Field concentration (mol/m³)",observations.map(o=>field(o,mode)),"#80aaf9"],
    ["Field amount (mol)",observations.map(o=>Number(field(o,mode))*vol),"#6bcae1"],
    [mode==="ligand"?"Receiver amount (mol)":"Cell amount (mol)",observations.map(o=>inventory(o,mode)),"#79dfbd"],
    ["Response memory (1)",observations.map(o=>memory(o,mode)),"#edc678"],
    ["Cumulative transfer (mol)",accepted.reduce((a,e)=>{a.push(a[a.length-1]+Number(e.transition.info.integrated_transfer_mol||0));return a;},[0]),"#dda4ef"]];
  for (const [label,values,color] of series) { const card=node("div",undefined,"chart"),title=node("label",label),canvas=node("canvas");
    card.append(title,canvas,node("div","Start "+fmt(values[0])+" · latest "+fmt(values.at(-1)),"note"));box.append(card);chart(canvas,values,color);}
}
function pairedChart(canvas,control,treated,cellId,key,switches,sequence) {
  const ctx=canvas.getContext("2d"),w=canvas.width=800,h=canvas.height=240;
  ctx.clearRect(0,0,w,h);ctx.fillStyle="#0d1b2b";ctx.fillRect(0,0,w,h);
  const take=rows=>rows.map(o=>o.cells.find(c=>c.cell_id===cellId)[key]);
  const a=take(control),b=take(treated),hi=Math.max(0.01,...a,...b),x=i=>42+i*(w-65)/82,y=v=>h-30-Number(v)/hi*(h-68);
  ctx.strokeStyle="#52677d";ctx.beginPath();ctx.moveTo(42,h-30);ctx.lineTo(w-20,h-30);ctx.stroke();
  ctx.font="12px system-ui";ctx.fillStyle="#d7e8f6";ctx.fillText("0",14,h-30);ctx.fillText(fmt(hi),6,42);ctx.fillText("492 min",w-70,h-8);
  switches.forEach((time,i)=>{const px=x(time/6);ctx.save();ctx.setLineDash([4,4]);ctx.strokeStyle="#e8bf73";
    ctx.beginPath();ctx.moveTo(px,38);ctx.lineTo(px,h-30);ctx.stroke();ctx.restore();ctx.fillStyle="#e8bf73";ctx.fillText(sequence[i],px+4,22);});
  const line=(values,color)=>{ctx.strokeStyle=color;ctx.lineWidth=3;ctx.beginPath();values.forEach((v,i)=>i?ctx.lineTo(x(i),y(v)):ctx.moveTo(x(i),y(v)));ctx.stroke();};
  line(a,"#80aaf9");line(b,"#f2a3c4");
}
function comparisonPanel() {
  let panel=$("nfkb-comparison");if(panel)return panel;
  panel=node("section");panel.id="nfkb-comparison";
  panel.append(node("h2","Paired NF-κB response experiment"),
    node("p","Compare two 82-step trajectories under the same four-switch stimulus schedule. The second arm adds an inhibitor-like payload from a finite reservoir. Inspect cell-level response curves and amount ledgers; observed p65 traces are presented in their own panel below.","muted"));
  const controls=node("div",undefined,"controls");controls.style.gridTemplateColumns="repeat(auto-fit,minmax(190px,1fr))";
  for(const [key,label,value,type] of [["sequence_key","Four-code order T/I/L/P","TIPL","text"],
    ["stimulus_admin_mol_per_switch","Stimulus amount per switch (mol)",0.1,"number"],
    ["payload_start_min","Payload start (min, 6-minute grid)",120,"number"],
    ["payload_admin_mol_at_start","Generic payload amount (mol)",0.02,"number"],
    ["payload_uptake_rate_mol_min","Per-cell payload uptake (mol/min)",0.00001,"number"]]){
    const row=node("label",label),input=node("input");input.type=type;input.value=String(value);input.dataset.compareKey=key;
    if(type==="number"){input.min="0";input.step="any";}row.append(input);controls.append(row);}
  panel.append(controls);const action=node("button","Run paired schedule","primary");action.id="run-nfkb-compare";panel.append(action);
  const status=node("p");status.id="nfkb-compare-status";status.className="status-line";panel.append(status);
  const choose=node("label","Inspect cell"),select=node("select");select.id="compare-cell";choose.append(select);panel.append(choose);
  const cards=node("div");cards.id="nfkb-compare-cards";cards.className="evidence-grid";panel.append(cards);
  for(const [id,label] of [["compare-reporter","Reporter index (1)"],["compare-nuclear","Nuclear response proxy (1)"]]){
    const chartBox=node("div",undefined,"metric");chartBox.append(node("h3",label));const canvas=node("canvas");canvas.id=id;canvas.width=800;canvas.height=240;canvas.style.width="100%";canvas.style.height="auto";chartBox.append(canvas);panel.append(chartBox);}
  panel.append(node("p","Blue: stimulus only; pink: stimulus plus payload; yellow: schedule switches at 0/120/240/360 min. Curves show dimensionless model indices; the observed reporter chart below uses its own source units.","note"));
  $("trace-body").closest("section").before(panel);
  select.addEventListener("change",renderComparison);
  action.addEventListener("click",async()=>{try{const request={};for(const input of panel.querySelectorAll("[data-compare-key]"))
      request[input.dataset.compareKey]=input.type==="text"?input.value.trim().toUpperCase():numericInput(input,input.dataset.compareKey);
    message("nfkb-compare-status","Running two bounded synthetic schedules…");action.disabled=true;
    nfkbComparison=await api("/api/nfkb/compare","POST",request);renderComparison();
    message("nfkb-compare-status","Paired run passed; typed switch actions and both trajectories saved at "+nfkbComparison.artifact_path);
  }catch(error){message("nfkb-compare-status",error.message,true);}finally{action.disabled=false;}});
  return panel;
}
function renderComparison() {
  const panel=comparisonPanel();panel.hidden=state.mode!=="nfkb";
  if(panel.hidden)return;
  const select=$("compare-cell"),old=select.value;select.replaceChildren();
  for(const cell of state.observation.cells){const option=node("option",cell.cell_id);option.value=cell.cell_id;select.append(option);}
  select.value=state.observation.cells.some(c=>c.cell_id===old)?old:state.observation.cells[0].cell_id;
  const cards=$("nfkb-compare-cards");cards.replaceChildren();if(!nfkbComparison)return;
  const a=nfkbComparison.arms.stimulus_only,b=nfkbComparison.arms.stimulus_plus_generic_payload;
  const choose=rows=>rows.at(-1).cells.find(c=>c.cell_id===select.value);
  const ca=choose(a.observations),cb=choose(b.observations);
  evidenceCard(cards,"Final reporter · stimulus only / payload",fmt(ca.reporter_index)+" / "+fmt(cb.reporter_index));
  evidenceCard(cards,"Final nuclear proxy · stimulus only / payload",fmt(ca.nuclear_proxy)+" / "+fmt(cb.nuclear_proxy));
  evidenceCard(cards,"Intracellular payload (mol)",cb.payload_amount_mol);
  evidenceCard(cards,"Maximum amount balance residual (mol)",Math.max(a.maximum_amount_residual_mol,b.maximum_amount_residual_mol));
  pairedChart($("compare-reporter"),a.observations,b.observations,select.value,"reporter_index",[0,120,240,360],nfkbComparison.schedule.sequence_key);
  pairedChart($("compare-nuclear"),a.observations,b.observations,select.value,"nuclear_proxy",[0,120,240,360],nfkbComparison.schedule.sequence_key);
}
function coupledPanel() {
  let panel=$("coupled-panel");if(panel)return panel;
  panel=node("section");panel.id="coupled-panel";
  panel.append(node("h2","Coupled 3-cell mediator arena"),
    node("p","Explore matched baseline and mediator-coupled trajectories. Three cells secrete and sense a finite shared mediator field across intervals; select a cell and time point to inspect its response and amount ledger.","muted"));
  const controls=node("div",undefined,"row"),label=node("label","Inspect modeled cell"),select=node("select");
  select.id="coupled-cell";label.append(select);controls.append(label);
  const timeLabel=node("label","Preserved sample (0–492 min)"),slider=node("input");
  slider.id="coupled-sample";slider.type="range";slider.min="0";slider.max="82";slider.step="1";slider.value="21";
  timeLabel.append(slider);controls.append(timeLabel);panel.append(controls);
  const cards=node("div");cards.id="coupled-summary";cards.className="evidence-grid";panel.append(cards);
  const scene=node("canvas");scene.id="coupled-scene";scene.width=800;scene.height=185;
  scene.style.width="100%";scene.style.height="auto";scene.setAttribute("aria-label","Preserved coupled mediator field and identified cell sprites");panel.append(scene);
  for(const [id,label] of [["coupled-field","Generic mediator field concentration (mol/m³)"],
                           ["coupled-nuclear","Nuclear response proxy (1)"],
                           ["coupled-reporter","Reporter index (1)"]]){
    const box=node("div",undefined,"metric");box.append(node("h3",label));
    const canvas=node("canvas");canvas.id=id;canvas.width=800;canvas.height=185;canvas.style.width="100%";canvas.style.height="auto";
    box.append(canvas);panel.append(box);}
  panel.append(node("p","Blue: matched baseline; cyan: mediator coupling. Curves show model state; the observed p65 chart and frozen reporter fit below retain separate provenance and units.","note"));
  $("trace-body").closest("section").before(panel);
  select.addEventListener("change",renderCoupled);slider.addEventListener("input",renderCoupled);
  return panel;
}
function pairedArtifactChart(canvas,baseline,coupled,accessor) {
  const ctx=canvas.getContext("2d"),w=canvas.width,h=canvas.height;
  ctx.clearRect(0,0,w,h);ctx.fillStyle="#0d1b2b";ctx.fillRect(0,0,w,h);
  const a=baseline.map(accessor),b=coupled.map(accessor),hi=Math.max(1e-9,...a,...b);
  const x=i=>42+i*(w-66)/Math.max(1,a.length-1),y=v=>h-27-Number(v)/hi*(h-62);
  ctx.strokeStyle="#52677d";ctx.beginPath();ctx.moveTo(42,h-27);ctx.lineTo(w-20,h-27);ctx.stroke();
  ctx.font="12px system-ui";ctx.fillStyle="#d7e8f6";ctx.fillText("0",14,h-27);ctx.fillText(fmt(hi),6,37);
  ctx.fillText(fmt(coupled.at(-1).time_min)+" min",w-77,h-6);
  const line=(values,color)=>{ctx.strokeStyle=color;ctx.lineWidth=3;ctx.beginPath();
    values.forEach((value,i)=>i?ctx.lineTo(x(i),y(value)):ctx.moveTo(x(i),y(value)));ctx.stroke();};
  line(a,"#80aaf9");line(b,"#69dfe5");
}
function drawCoupledScene(canvas,sample,maximumConcentration,selectedId) {
  const ctx=canvas.getContext("2d"),w=canvas.width,h=canvas.height;
  const fraction=Math.min(1,sample.mediator_field_concentration_mol_m3/Math.max(maximumConcentration,1e-12));
  ctx.fillStyle=`rgb(${Math.round(10+12*fraction)},${Math.round(31+86*fraction)},${Math.round(45+99*fraction)})`;
  ctx.fillRect(0,0,w,h);ctx.strokeStyle="#69dfe5";ctx.lineWidth=3;ctx.strokeRect(8,8,w-16,h-16);
  ctx.fillStyle="#e9f6fa";ctx.font="bold 13px Consolas,monospace";
  ctx.fillText(`GENERIC MEDIATOR · ${fmt(sample.mediator_field_concentration_mol_m3)} mol/m³ · ${fmt(sample.time_min)} min`,20,29);
  const cells=sample.cells,xs=cells.map(c=>c.position_m[0]),ys=cells.map(c=>c.position_m[1]);
  const xlo=Math.min(...xs),xspan=Math.max(...xs)-xlo,ylo=Math.min(...ys),yspan=Math.max(...ys)-ylo;
  for(const cell of cells){const x=190+(xspan?(cell.position_m[0]-xlo)/xspan:0.5)*410;
    const y=57+(yspan?(cell.position_m[1]-ylo)/yspan:0.5)*62;
    ctx.fillStyle=cell.cell_id===selectedId?"#ffd178":"#79dfbd";ctx.fillRect(x-15,y-15,30,30);
    ctx.strokeStyle="#07111b";ctx.lineWidth=3;ctx.strokeRect(x-15,y-15,30,30);
    ctx.fillStyle="#e9f6fa";ctx.font="12px Consolas,monospace";
    ctx.fillText(`${cell.cell_id} N ${fmt(cell.nuclear_proxy)} R ${fmt(cell.reporter_index)}`,x-70,y+49);}
  ctx.font="11px Consolas,monospace";ctx.fillStyle="#c3d9e5";
  ctx.fillText("Position from recorded model result · selected cell in gold · field tint follows mediator concentration",20,h-14);
}
function renderCoupled() {
  if(!state.coupled_arena_available)return;
  const panel=coupledPanel(),cards=$("coupled-summary");cards.replaceChildren();
  if(!coupledArena){evidenceCard(cards,"Coupled artifact","loading verified local result");return;}
  const baseline=coupledArena.cases.baseline.trace,coupled=coupledArena.cases.coupled.trace;
  const select=$("coupled-cell"),old=select.value;if(!select.options.length){
    for(const cell of coupled[0].cells){const option=node("option",cell.cell_id);option.value=cell.cell_id;select.append(option);}}
  select.value=coupled[0].cells.some(c=>c.cell_id===old)?old:coupled[0].cells[0].cell_id;
  const cellId=select.value,slider=$("coupled-sample");slider.max=String(coupled.length-1);
  const sample=coupled[Number(slider.value)],cell=sample.cells.find(c=>c.cell_id===cellId);
  evidenceCard(cards,"Preserved step",`${fmt(sample.time_min)} min · ${cellId}`);
  evidenceCard(cards,"Mediator field / waste (mol)",`${fmt(sample.mediator_field_amount_mol)} / ${fmt(sample.mediator_waste_amount_mol)}`);
  evidenceCard(cards,"Selected nuclear / reporter (1)",`${fmt(cell.nuclear_proxy)} / ${fmt(cell.reporter_index)}`);
  evidenceCard(cards,"Selected mediator inventory (mol)",cell.mediator_inventory_mol);
  evidenceCard(cards,"Cell 3 second-interval nuclear difference",coupledArena.comparison.cell_3_second_interval_nuclear_delta);
  evidenceCard(cards,"Selected reporter AUC difference (index·min)",
    coupledArena.comparison.delta_auc_reporter_index_min_by_cell?.[cellId]);
  evidenceCard(cards,"Maximum amount residual (mol)",coupledArena.maximum_amount_residual_mol);
  evidenceCard(cards,"Verified OSS atom / chokepoint",`${coupledArena.oss_atom_id} / ${coupledArena.oss_chokepoint_id}`);
  evidenceCard(cards,"Result SHA-256",coupledArena.result_sha256);
  evidenceCard(cards,"Preserved result",coupledArena.artifact_path);
  pairedArtifactChart($("coupled-field"),baseline,coupled,row=>row.mediator_field_concentration_mol_m3);
  pairedArtifactChart($("coupled-nuclear"),baseline,coupled,row=>row.cells.find(c=>c.cell_id===cellId).nuclear_proxy);
  pairedArtifactChart($("coupled-reporter"),baseline,coupled,row=>row.cells.find(c=>c.cell_id===cellId).reporter_index);
  drawCoupledScene($("coupled-scene"),sample,Math.max(...coupled.map(row=>row.mediator_field_concentration_mol_m3)),cellId);
}
function renderSymbolic() {
  const p=state.symbolic_program, e=state.evidence.symbolic||{}, box=$("symbolic-summary");box.replaceChildren();
  evidenceCard(box,"Statements",(p.statements||[]).map(s=>s.kind).join(" + "));
  evidenceCard(box,"Ruleset digest",p.ruleset_sha256);
  evidenceCard(box,"Last integrated execution",e.status||"pending");
  evidenceCard(box,"Direct / lowered trace",e.trace_bytes_equal===undefined?"pending":e.trace_bytes_equal);
  $("symbolic-json").textContent=JSON.stringify(p,null,2);
  const plots=$("symbolic-charts"),tbody=$("symbolic-trace");plots.replaceChildren();tbody.replaceChildren();
  if(!symbolicResult)return;
  evidenceCard(box,"Executed DSL intervals",symbolicResult.accepted_intervals);
  evidenceCard(box,"Amount balance residual (mol)",symbolicResult.balance_residual_mol);
  const trace=symbolicResult.trace;
  for(const [label,key,color] of [["Cell inventory (mol)","cell_amount_mol","#79dfbd"],
      ["Shared field (mol)","field_amount_mol","#80aaf9"]]){
    const card=node("div",undefined,"chart"),canvas=node("canvas");
    card.append(node("label",label),canvas);plots.append(card);chart(canvas,trace.map(row=>row[key]),color);
  }
  for(const row of trace){const tr=node("tr");
    for(const key of ["time_s","input_concentration_mol_m3","cell_amount_mol","field_amount_mol","accepted_event_count"])
      tr.append(node("td",row[key]));tbody.append(tr);}
  $("symbolic-run-status").textContent=`Executed from validated DSL JSON and lowered rules. Direct/lowered traces match: ${symbolicResult.trace_bytes_equal}. Model run: ${symbolicResult.artifact_path}.`;
}
function observedPanel() {
  let panel=$("observed-panel");if(panel)return panel;
  panel=node("section");panel.id="observed-panel";
  panel.append(node("h2","Observed p65 trajectories and frozen reporter fit"),
    node("p","Explore author-normalized nuclear/cytoplasmic p65 fluorescence from supplied sequential-stimulus data alongside a frozen reduced-state reporter fit. Exact source-row traces and residuals reveal where the fit follows or misses measured pulses. The cell–payload experiment above is a separately scoped model.","muted"));
  const row=node("div",undefined,"row"),label=node("label","Select observed condition"),select=node("select");select.id="observed-condition";
  label.append(select);row.append(label);panel.append(row);
  const scaleLabel=node("label","Vertical scale"),scale=node("select");scale.id="observed-scale";
  for(const [value,label] of [["focus","Mean + fitted baseline focus; exact samples may clip"],["full","Full range of exact samples"]]){
    const option=node("option",label);option.value=value;scale.append(option);}scaleLabel.append(scale);panel.append(scaleLabel);
  scale.addEventListener("change",renderObserved);
  const cards=node("div");cards.id="observed-summary";cards.className="evidence-grid";panel.append(cards);
  const predictBox=node("details");predictBox.id="frozen-predictor";predictBox.append(node("summary","Run frozen empirical reporter predictor"));
  predictBox.append(node("p","Run inference from the frozen reduced state-space candidate using four author stimulus codes and a categorical dose tier. Payload response is explored in the separate cell–field experiment above.","note"));
  const predictControls=node("div",undefined,"row"),orderLabel=node("label","Four-code order"),order=node("input");
  order.id="predict-order";order.type="text";order.value="TIPL";order.maxLength=4;orderLabel.append(order);
  const doseLabel=node("label","Categorical author dose tier"),dose=node("select");dose.id="predict-dose";
  for(const value of ["high","mid","low"]){const option=node("option",value);option.value=value;dose.append(option);}doseLabel.append(dose);
  const button=node("button","Predict from frozen candidate","primary");button.id="run-frozen-predictor";
  predictControls.append(orderLabel,doseLabel,button);predictBox.append(predictControls);
  const predictStatus=node("p");predictStatus.id="predict-status";predictStatus.className="note";predictBox.append(predictStatus);panel.append(predictBox);
  const canvas=node("canvas");canvas.id="observed-canvas";canvas.width=800;canvas.height=290;
  canvas.style.width="100%";canvas.style.height="auto";canvas.style.marginTop="12px";panel.append(canvas);
  const note=node("p");note.id="observed-note";note.className="note";panel.append(note);
  $("symbolic-summary").closest("section").before(panel);
  select.addEventListener("change",async()=>{try{observedCondition=await api("/api/observed?condition_id="+encodeURIComponent(select.value));renderObserved();}
    catch(error){$("observed-note").textContent=error.message;}});
  button.addEventListener("click",async()=>{try{const sequence=order.value.trim().toUpperCase();
    predictorResult=await api("/api/nfkb/predict","POST",{sequence_key:sequence,dose_tier:dose.value});
    const match=(observedIndex?.conditions||[]).find(c=>c.sequence_key===sequence&&c.dose_tier===dose.value);
    if(match)observedCondition=await api("/api/observed?condition_id="+match.condition_id);
    renderObserved();}catch(error){message("predict-status",error.message,true);}});
  return panel;
}
function drawObserved(canvas,condition,switches) {
  const ctx=canvas.getContext("2d"),w=canvas.width,h=canvas.height,times=condition.observed.time_min||[],mean=condition.observed.mean||[];
  ctx.clearRect(0,0,w,h);ctx.fillStyle="#0d1b2b";ctx.fillRect(0,0,w,h);
  const prediction=condition.model_prediction;
  const samples=(condition.sample_traces||[]).flatMap(s=>s.values||[]).filter(Number.isFinite);
  const central=[...mean,...(Array.isArray(prediction)?prediction:[])].filter(Number.isFinite);
  const band=[...(condition.observed.p10||[]),...(condition.observed.p90||[])].filter(Number.isFinite);
  const focus=$("observed-scale").value==="focus",all=focus?central:[...central,...samples,...band];
  if(!all.length)return 0;
  const rawLo=Math.min(...all),rawHi=Math.max(...all),pad=Math.max(0.02,(rawHi-rawLo)*0.08),lo=rawLo-pad,hi=rawHi+pad,span=hi-lo,tmax=Math.max(...times);
  const x=t=>48+(Number(t)/tmax)*(w-76),rawY=v=>h-38-(Number(v)-lo)/span*(h-82),y=v=>Math.max(45,Math.min(h-38,rawY(v)));
  ctx.strokeStyle="#48617c";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(48,h-38);ctx.lineTo(w-18,h-38);ctx.stroke();
  ctx.font="12px system-ui";ctx.fillStyle="#b6cfe4";ctx.fillText(fmt(lo),4,h-38);ctx.fillText(fmt(hi),4,53);
  ctx.fillText("0",48,h-16);ctx.fillText(fmt(tmax)+" min",w-66,h-16);
  (switches||[]).forEach((time,i)=>{ctx.save();ctx.setLineDash([5,5]);ctx.strokeStyle="#f0cc83";ctx.beginPath();ctx.moveTo(x(time),45);ctx.lineTo(x(time),h-38);ctx.stroke();ctx.restore();
    const ligand=(condition.ligand_sequence||[])[i]||"stimulus";ctx.fillStyle="#f0cc83";ctx.fillText(ligand,x(time)+4,28+(i%2)*14);});
  const p10=condition.observed.p10||[],p90=condition.observed.p90||[];
  if(p10.length===times.length && p90.length===times.length){ctx.fillStyle="#70e6c322";ctx.beginPath();
    p90.forEach((v,i)=>i?ctx.lineTo(x(times[i]),y(v)):ctx.moveTo(x(times[i]),y(v)));
    for(let i=p10.length-1;i>=0;i--)ctx.lineTo(x(times[i]),y(p10[i]));ctx.closePath();ctx.fill();}
  const line=(values,color,width,dashed=false)=>{ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dashed?[5,5]:[]);ctx.beginPath();let drawing=false;
    values.forEach((value,i)=>{if(!Number.isFinite(value)||!Number.isFinite(times[i])){drawing=false;return;}
      if(!drawing){ctx.moveTo(x(times[i]),y(value));drawing=true;}else ctx.lineTo(x(times[i]),y(value));});ctx.stroke();ctx.setLineDash([]);};
  for(const sample of condition.sample_traces||[])line(sample.values||[],"#68889f",1);
  line(mean,"#70e6c3",3);
  if(Array.isArray(prediction) && prediction.length===times.length)
    line(prediction,"#f5a2c8",2,true);
  const clipped=focus?samples.filter(v=>v<lo||v>hi).length:0;
  if(clipped){ctx.fillStyle="#edc678";ctx.font="bold 12px system-ui";ctx.fillText(`${clipped} exact-sample points clipped; switch to full range`,w-330,52);}
  return clipped;
}
function renderObserved() {
  observedPanel();const select=$("observed-condition"),cards=$("observed-summary");cards.replaceChildren();
  if(!observedIndex || observedIndex.status!=="available") {$("observed-note").textContent="Observed trace artifact is not available in this launch.";return;}
  if(!select.options.length){for(const c of observedIndex.conditions){const option=node("option",`#${c.condition_id} · ${c.sequence_key} · ${c.dose_tier} · ${c.split}`);
      option.value=String(c.condition_id);select.append(option);}}
  if(!observedCondition?.condition)return;
  const c=observedCondition.condition;select.value=String(c.condition_id);
  evidenceCard(cards,"Condition",`#${c.condition_id} · ${c.sequence_key} · ${c.dose_tier}`);
  evidenceCard(cards,"Declared split",c.split);
  evidenceCard(cards,"Source rows",c.row_count);
  evidenceCard(cards,"Complete traces",c.complete_trace_row_count);
  evidenceCard(cards,"Observable",observedIndex.observable?.label+" ("+observedIndex.observable?.unit+")");
  evidenceCard(cards,"Frozen reporter proxy",Array.isArray(c.model_prediction)?"pink dashed · fitted baseline":"unavailable for control");
  if(Array.isArray(c.nominal_stimulus_schedule))
    evidenceCard(cards,"Author-reported nominal schedule",c.nominal_stimulus_schedule.map(item=>`${item.time_min} min ${item.ligand} ${fmt(item.nominal_extracellular_ng_ml)} ng/mL`).join("; "));
  const residual=observedIndex.posthoc_residuals;
  if(residual && c.split==="evaluation"){
    const dose=(residual.per_dose||[]).find(item=>item.dose_tier===c.dose_tier);
    if(dose)evidenceCard(cards,"Held-out "+c.dose_tier+" MAE · model / current-only",fmt(dose.state_space_mae)+" / "+fmt(dose.current_only_mae));
    const worse=(residual.worse_than_current_only||[]).find(item=>item.condition_id===c.condition_id);
    if(worse)evidenceCard(cards,"Observed limitation","Current-only wins for this low-dose condition");
  }
  if(predictorResult){const match=predictorResult.stimulus_codes.join(",")===c.stimulus_codes.join(",")&&predictorResult.dose_tier===c.dose_tier;
    const delta=match&&Array.isArray(c.model_prediction)?Math.max(...c.model_prediction.map((v,i)=>Math.abs(v-predictorResult.predicted_reporter[i]))):null;
    $("predict-status").textContent=`Frozen inference: ${predictorResult.predicted_reporter.length} points, candidate SHA-256 ${predictorResult.frozen_candidate_sha256}; source SHA-256 ${predictorResult.source_matrix_sha256}. ${match?"Recomputed versus stored curve max |difference| "+fmt(delta):"Select the matching observed condition to compare."} Drug response: none.`;}
  const clipped=drawObserved($("observed-canvas"),c,observedIndex.switch_times_min);
  const counts=c.observed.finite_count_by_time||[],range=counts.length?Math.min(...counts)+"–"+Math.max(...counts):"unavailable";
  $("observed-note").textContent=`Green: measured condition mean; light band: descriptive source-row p10–p90; gray: ${c.sample_traces.length} exact source-row samples; pink dashed: frozen early reporter baseline; yellow: author switch times. ${clipped} sample points outside focused scale; full-range option shows all exact samples. Finite rows per time: ${range}. The fitted proxy is not the synthetic delivery episode and does not predict drug efficacy. Source SHA-256 ${observedIndex.source.sha256}; frozen candidate ${observedIndex.frozen_candidate_sha256||"none"}. Nominal doses come from the paper; actual per-row delivery and run/chamber/replicate IDs remain unresolved. Artifact: ${observedIndex.artifact_path}`;
  if(state)renderScene();
}
function renderLearning() {
  const evidence=state.evidence.self_play||{},arms=evidence.arms||{},summary=$("learning-summary"),tbody=$("learning-body");
  summary.replaceChildren();tbody.replaceChildren();
  for (const [name,arm] of Object.entries(arms)) {
    evidenceCard(summary,name+" sealed one-step MAE",arm.one_step_mae_memory_1);
    for (const a of arm.attempts||[]) {const tr=node("tr");for(const v of [name,a.round,a.schedule,a.prefit_mae_memory_1,a.mean_teacher_diagnostic_score])tr.append(node("td",v));tbody.append(tr);}
  }
  if (!Object.keys(arms).length) evidenceCard(summary,"Self-play artifact","not available yet");
}
function renderEvidence() {
  const e=state.evidence,box=$("evidence-grid");box.replaceChildren();
  evidenceCard(box,"Workload",e.workload_status||e.status);
  evidenceCard(box,"OSS atom",e.oss_atom_id||"no receipt for this run");
  evidenceCard(box,"OSS chokepoint",e.oss_chokepoint_id||"no receipt for this run");
  evidenceCard(box,"OSS verification",e.oss_verification_status||"no receipt for this run");
  evidenceCard(box,"Optional Engine run ID",e.engine_run_id||"not used in this run");
  $("evidence-path").textContent=e.workload_path||e.description||"";
}
function renderGuide() {
  const count=state.configuration.cell_count || 1;
  const observedCount=observedIndex?.status==="available" ? observedIndex.conditions.length : 0;
  $("guide-readiness").textContent=`OSS ${state.recording_available?"ready":"unavailable"} · measured overlay ${observedCount?observedCount+" conditions":"unavailable"} · campaign ${state.campaign_report_available?"linked":"unavailable"} · ${count} cell${count===1?"":"s"} · ${state.accepted_steps}/${state.configuration.horizon_steps} steps`;
  const link=$("coupled-guide-link");link.replaceChildren();
  if(state.coupled_arena_available){link.append(document.createTextNode(" · Explore the preserved "));
    const anchor=node("a","coupled 3-cell arena");anchor.href="#coupled-panel";link.append(anchor);}
}
function render() { renderState();renderTrace();renderCharts();renderComparison();renderCoupled();renderObserved();renderSymbolic();renderLearning();renderEvidence();renderGuide(); }
function message(id,text,bad=false) { const el=$(id);el.textContent=text;el.className="status-line "+(bad?"bad":"good"); }
function numericInput(input,label,integer=false) {
  if (!input || input.value.trim()==="") throw new Error(label+" cannot be blank");
  const value=Number(input.value);
  if (!Number.isFinite(value) || (integer && !Number.isInteger(value)))
    throw new Error(label+" must be a finite "+(integer?"integer":"number"));
  return value;
}
function redrawSceneAfterLayout(){requestAnimationFrame(()=>{if(state)renderScene();});}
async function load() {state=await api("/api/state");renderModes();render();redrawSceneAfterLayout();
  if(state.coupled_arena_available)try{coupledArena=await api("/api/coupled-arena");renderCoupled();}
    catch(error){const panel=coupledPanel();panel.append(node("p",error.message,"status-line bad"));}
  try{observedIndex=await api("/api/observed");if(observedIndex.status==="available")
    observedCondition=await api("/api/observed?condition_id="+observedIndex.conditions[0].condition_id);
    renderObserved();renderGuide();redrawSceneAfterLayout();}catch(error){observedPanel();$("observed-note").textContent=error.message;renderGuide();}}
async function resetNfkbPreset(count) {
  if (![1,3,5].includes(count)) throw new Error("cell preset must be 1, 3 or 5");
  const configuration={...configFor("nfkb").defaults,cell_count:count};
  state=await api("/api/reset","POST",{mode:"nfkb",configuration});
  nfkbComparison=null;$("mode").value="nfkb";renderConfig();render();
  message("config-error",`${count}-cell NF-κB scenario reset; run the paired preset or advance one typed interval.`);
  message("action-status","");message("record-status","");
}
for(const button of document.querySelectorAll("[data-cell-preset]"))button.addEventListener("click",async()=>{
  try{button.disabled=true;await resetNfkbPreset(Number(button.dataset.cellPreset));}
  catch(error){message("config-error",error.message,true);}finally{button.disabled=false;}
});
$("mode").addEventListener("change",renderConfig);
$("reset").addEventListener("click",async()=>{try{const mode=$("mode").value,config={};for(const input of $("config").querySelectorAll("input"))config[input.dataset.key]=numericInput(input,input.dataset.key,["horizon_steps","cell_count"].includes(input.dataset.key));
  state=await api("/api/reset","POST",{mode,configuration:config});nfkbComparison=null;message("config-error","Scenario reset and ready.");message("action-status","");message("record-status","");renderConfig();render();}catch(error){message("config-error",error.message,true);}});
$("step").addEventListener("click",async()=>{try{let request;
  if($("mode").value!==state.mode)throw new Error("Reset the selected scenario before stepping");
  if(state.mode==="nfkb") {const rates={};for(const input of $("arena-actions").querySelectorAll("[data-payload-cell]"))rates[input.dataset.payloadCell]=numericInput(input,input.dataset.payloadCell);
    request={stimulus_code:$("stimulus-code").value||null,payload_uptake_rates_mol_min_by_cell:rates};
    for(const input of $("arena-actions").querySelectorAll("[data-nfkb-key]"))request[input.dataset.nfkbKey]=numericInput(input,input.dataset.nfkbKey);}
  else if(state.mode==="arena") {const rates={};for(const input of $("arena-actions").querySelectorAll("input")) rates[input.dataset.cellId]=numericInput(input,input.dataset.cellId);
    request={rates_mol_s:rates};}
  else request={rate_mol_s:numericInput($("action-rate"),"rate_mol_s")};
  const result=await api("/api/step","POST",request);
  state=result.state;message("action-status",result.status==="accepted"?"Step accepted; field and response state advanced.":"Rejected: "+result.event.reason,result.status!=="accepted");render();}catch(error){message("action-status",error.message,true);}});
$("replay").addEventListener("click",async()=>{try{state=await api("/api/replay","POST",{});message("action-status",state.last_replay.equal?"Replay matched all accepted steps and the checkpoint.":"Replay differed; inspect the session.",!state.last_replay.equal);render();}catch(error){message("action-status",error.message,true);}});
$("symbolic-run").addEventListener("click",async()=>{const button=$("symbolic-run");button.disabled=true;
  message("symbolic-run-status","Running the fixed five-interval DSL experiment…");
  try{symbolicResult=await api("/api/symbolic/run","POST",{});renderSymbolic();}
  catch(error){message("symbolic-run-status",error.message,true);}finally{button.disabled=false;}});
$("export").addEventListener("click",()=>{window.location.href="/api/session.json";message("record-status","Downloaded complete accepted uptake session.");});
async function recordSession(route){message("record-status",route==="oss"?"Recording exact uptake replay through Ocura OSS…":"Running optional Engine + OSS replay…");
  $("record").disabled=true;$("record-engine").disabled=true;
  try{const result=await api(route==="oss"?"/api/record":"/api/record-engine","POST",{});
    message("record-status",result.status+" · OSS atom "+fmt(result.oss_atom_id)+" · chokepoint "+fmt(result.oss_chokepoint_id)+
      (result.engine_run_id?" · optional Engine "+fmt(result.engine_run_id):"")+" · receipt "+fmt(result.output)+"/receipt.json",result.status!=="passed");
    state=await api("/api/state");render();}catch(error){message("record-status",error.message,true);}finally{if(state)renderState();}}
$("record").addEventListener("click",()=>recordSession("oss"));
$("record-engine").addEventListener("click",()=>recordSession("engine"));
$("refresh-evidence").addEventListener("click",async()=>{try{state=await api("/api/state");render();}catch(error){message("record-status",error.message,true);}});
window.addEventListener("resize",()=>{if(state)renderScene();});
window.addEventListener("load",redrawSceneAfterLayout);
load().catch(error=>message("config-error",error.message,true));
"""


def main() -> int:
    global SESSION, ENGINE_CLI, OSS_CLI, RUN_PYTHON, OBSERVED, RESIDUAL, FROZEN, CAMPAIGN_HTML, COUPLED_ARENA, BOARD_URL, PORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766, help="loopback port, default 8766")
    parser.add_argument("--run", type=Path, help="specific integrated run directory or result/receipt JSON")
    parser.add_argument("--oss-cli", type=Path,
                        help="required Ocura OSS CLI; defaults to project .venv, then PATH")
    parser.add_argument("--engine-cli", type=Path,
                        help="fixed installed Ocura Engine CLI for optional one-click ledger replay")
    parser.add_argument("--campaign-report", type=Path,
                        help="existing standalone HTML report to serve read-only at /campaign")
    parser.add_argument("--coupled-arena-result", type=Path,
                        help="one completed coupled synthetic arena results.json with adjacent verified OSS record")
    parser.add_argument("--board-url", default=BOARD_URL,
                        help="loopback agent board root URL; default http://127.0.0.1:8765/")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024–65535")
    if args.engine_cli is not None and not args.engine_cli.resolve().is_file():
        parser.error("--engine-cli must name an existing file")
    try:
        board_url = _validate_board_url(args.board_url)
    except ValueError as exc:
        parser.error(str(exc))
    campaign_bytes = None
    if args.campaign_report is not None:
        campaign_path = args.campaign_report.resolve()
        if not campaign_path.is_file() or campaign_path.suffix.lower() not in {".html", ".htm"}:
            parser.error("--campaign-report must name one existing HTML file")
        if campaign_path.stat().st_size > 20_000_000:
            parser.error("--campaign-report must be at most 20 MB")
        try:
            campaign_bytes = campaign_path.read_bytes()
            campaign_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            parser.error(f"--campaign-report must be readable UTF-8 HTML: {exc}")
    oss_candidates = ([args.oss_cli] if args.oss_cli is not None else
                      [ROOT / ".venv/Scripts/ocura-oss.exe", ROOT / ".venv/bin/ocura-oss",
                       Path(shutil.which("ocura-oss")) if shutil.which("ocura-oss") else None])
    oss_selected = next((candidate.resolve() for candidate in oss_candidates
                         if candidate is not None and candidate.resolve().is_file()), None)
    if oss_selected is None:
        parser.error("Ocura OSS is required: initialize the local .venv, install ocura-oss on PATH, or pass --oss-cli")
    python_candidates = [ROOT / ".venv/Scripts/python.exe", ROOT / ".venv/bin/python", Path(sys.executable)]
    run_python = next(path.resolve() for path in python_candidates if path.is_file())
    PORT = args.port
    ENGINE_CLI = args.engine_cli.resolve() if args.engine_cli is not None else None
    OSS_CLI = oss_selected
    RUN_PYTHON = run_python
    CAMPAIGN_HTML = campaign_bytes
    try:
        COUPLED_ARENA = (_load_coupled_arena(args.coupled_arena_result)
                         if args.coupled_arena_result is not None else None)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    BOARD_URL = board_url
    OBSERVED = _observed_artifact()
    frozen_path = ROOT / "runs/nfkb_model_20260926_02/frozen_candidate.json"
    frozen_candidate = _read_json(frozen_path)
    FROZEN = ({"candidate": frozen_candidate,
               "sha256": hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
               "path": str(frozen_path)} if frozen_candidate is not None else None)
    residual_candidates = sorted((ROOT / "runs").glob("nfkb_residuals_*/residuals.json"),
                                 key=lambda path: path.stat().st_mtime, reverse=True)
    RESIDUAL = None
    for path in residual_candidates:
        candidate = _read_json(path)
        if candidate is not None and candidate.get("status") == "pass":
            candidate["_artifact_path"] = str(path)
            RESIDUAL = candidate
            break
    SESSION = DemoSession(args.run)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(json.dumps({"status": "ready", "url": f"http://127.0.0.1:{PORT}/",
                      "modes": list(MODES), "oss_recording_available": True,
                      "engine_recording_available": ENGINE_CLI is not None,
                      "campaign_report_available": CAMPAIGN_HTML is not None}),
          flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
