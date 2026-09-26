#!/usr/bin/env python3
"""Render a completed local synthetic demo as one offline, script-free HTML page."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import sys


COMPONENTS = ("symbolic", "memory", "episode", "ligand", "self_play", "splitting")
RESULT_NAME = {name: "study.json" if name == "splitting" else "results.json"
               for name in COMPONENTS}


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant {value}")


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    if path.stat().st_size > 20_000_000:
        raise ValueError(f"JSON artifact exceeds 20 MB: {path}")
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    if type(value) is not dict:
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    if path.stat().st_size > 20_000_000:
        raise ValueError(f"JSONL artifact exceeds 20 MB: {path}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line, parse_constant=_reject_constant)
            if type(value) is not dict:
                raise ValueError(f"expected JSONL object: {path}")
            rows.append(value)
    return rows


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _locate_run(requested: Path) -> tuple[Path, Path | None]:
    requested = requested.resolve()
    if requested.is_file():
        if requested.name == "receipt.json":
            outer, workload = requested.parent, requested.parent / "workload"
        elif requested.name == "results.json":
            workload = requested.parent
            outer = workload.parent if workload.name == "workload" else None
        else:
            raise ValueError("--run file must be results.json or receipt.json")
    elif requested.is_dir():
        if (requested / "workload/results.json").is_file():
            outer, workload = requested, requested / "workload"
        elif (requested / "results.json").is_file():
            workload = requested
            outer = requested.parent if requested.name == "workload" else None
        else:
            raise ValueError("--run directory has no integrated results.json")
    else:
        raise ValueError("--run path does not exist")
    if not (workload / "results.json").is_file():
        raise ValueError("integrated workload results.json is missing")
    if outer is not None and not (outer / "receipt.json").is_file():
        outer = None
    return workload, outer


def _obj(value: object) -> dict:
    return value if type(value) is dict else {}


def _list(value: object) -> list:
    return value if type(value) is list else []


def _num(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _fmt(value: object, *, digits: int = 7) -> str:
    if value is None:
        return "—"
    if type(value) is bool:
        return "yes" if value else "no"
    number = _num(value)
    if number is not None:
        return f"{number:.{digits}g}"
    return str(value)


def _e(value: object) -> str:
    return html.escape(_fmt(value), quote=True)


def _cell(value: object) -> str:
    return f"<td>{_e(value)}</td>"


def _table(headers: list[str], rows: list[list[object]], *, compact: bool = False) -> str:
    if not rows:
        return '<p class="empty">No rows recorded in this artifact.</p>'
    head = "".join(f"<th scope=\"col\">{_e(item)}</th>" for item in headers)
    body = "".join("<tr>" + "".join(_cell(item) for item in row) + "</tr>" for row in rows)
    klass = ' class="compact"' if compact else ""
    return f'<div class="table-wrap"><table{klass}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _pill(value: object) -> str:
    label = _fmt(value)
    klass = "ok" if label in ("pass", "passed", "completed", "accepted", "ok") else (
        "bad" if label in ("fail", "failed", "rejected") else "neutral")
    return f'<span class="pill {klass}">{_e(label)}</span>'


def _card(label: str, value: object, note: str = "") -> str:
    return ('<div class="card"><div class="card-label">' + _e(label) +
            '</div><div class="card-value">' + _e(value) +
            '</div><div class="card-note">' + _e(note) + '</div></div>')


def _details(title: str, value: object) -> str:
    data = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
    return (f'<details><summary>{_e(title)}</summary><pre>{html.escape(data, quote=True)}</pre></details>')


def _section(anchor: str, title: str, subtitle: str, body: str) -> str:
    return (f'<section id="{anchor}"><div class="section-heading"><h2>{_e(title)}</h2>'
            f'<p>{_e(subtitle)}</p></div>{body}</section>')


def _error_bar(value: object, maximum: float) -> str:
    number = _num(value)
    if number is None or number < 0 or maximum <= 0:
        return _e(value)
    width = max(2, min(100, round(100 * number / maximum)))
    return (f'<span class="bar-track"><span class="bar" style="width:{width}%"></span></span>'
            f'<span class="bar-value">{_e(value)}</span>')


def _overview(workload: dict, receipt: dict | None, run_dir: Path) -> str:
    components = _obj(workload.get("components"))
    accepted = sum(_obj(item).get("accepted") is True for item in components.values())
    cards = [
        _card("Workload status", workload.get("status"), "Csim component orchestration"),
        _card("Components accepted", f"{accepted}/{len(COMPONENTS)}", "Per-component process and result checks"),
        _card("Execution route", "Engine + OSS" if receipt else "Direct local", "Receipt shown separately below"),
        _card("Device", _obj(workload.get("host")).get("device", "CPU"), "Recorded host, not scale qualification"),
    ]
    note = ('<p class="scope">This page shows executed <strong>synthetic reference work</strong>. '
            'The virtual-cell learning loop uses a fixed synthetic teacher and one-step labels. '
            'It is not biological validation or an RL algorithm result.</p>')
    return '<div class="cards">' + "".join(cards) + '</div>' + note + _table(
        ["Field", "Recorded value"], [
            ["Run directory", str(run_dir)],
            ["Workload UTC", workload.get("utc")],
            ["Platform", _obj(workload.get("host")).get("platform")],
            ["Python", _obj(workload.get("host")).get("python")],
            ["Source/test/tool hash at start", workload.get("source_test_tool_sha256_start")],
            ["Source/test/tool hash at end", workload.get("source_test_tool_sha256_end")],
            ["Fingerprint stable during run", workload.get("source_fingerprint_stable")],
        ], compact=True)


def _episode_section(data: dict | None) -> str:
    if data is None:
        return _section("episode", "Cell–field episode", "No episode result was found.", "")
    config = _obj(data.get("configuration"))
    initial = _obj(data.get("initial_observation"))
    volume = _num(config.get("voxel_volume_m3"))
    rows = []
    initial_field = _num(initial.get("local_concentration_mol_m3"))
    rows.append(["0 · initial", initial.get("time_s"), "—",
                 initial.get("local_concentration_mol_m3"),
                 initial_field * volume if initial_field is not None and volume is not None else None,
                 initial.get("cell_amount_mol"), initial.get("accepted_memory"), "—", "—"])
    for index, record in enumerate(_list(data.get("trace")), start=1):
        record = _obj(record)
        action = _obj(record.get("action"))
        transition = _obj(record.get("transition"))
        observation = _obj(transition.get("observation"))
        info = _obj(transition.get("info"))
        field = _num(observation.get("local_concentration_mol_m3"))
        rows.append([str(index), observation.get("time_s"), action.get("vmax_mol_s"),
                     observation.get("local_concentration_mol_m3"),
                     field * volume if field is not None and volume is not None else None,
                     observation.get("cell_amount_mol"), observation.get("accepted_memory"),
                     info.get("integrated_transfer_mol"), transition.get("diagnostic_score")])
    body = '<div class="cards">' + "".join([
        _card("Accepted steps", len(_list(data.get("trace"))), "One cell, one voxel"),
        _card("Checkpoint replay", data.get("json_checkpoint_replay_equal"), "JSON restore and replay"),
        _card("Overdraw leaves state unchanged", _obj(data.get("overdraw_rejection")).get("world_memory_clock_unchanged"),
              "Failed transfer rejects joint state"),
        _card("Max amount balance error (mol)", data.get("maximum_closed_amount_balance_error_mol"), "Closed synthetic amount"),
    ]) + '</div>'
    body += ('<p class="caption">Field amount is derived here as recorded concentration × '
             'recorded voxel volume. Memory is dimensionless. The score is synthetic training '
             'feedback: negative absolute response-index error.</p>')
    body += _table(["Step", "Time (s)", "Action vmax (mol/s)", "Field c (mol/m³)",
                    "Field amount (mol)", "Cell amount (mol)", "Response memory (1)",
                    "Transferred (mol)", "Score"], rows)
    body += _details("Episode configuration and failure injection", {
        "configuration": config, "overdraw_rejection": data.get("overdraw_rejection")})
    return _section("episode", "Cell–field episode", "Accepted state after each typed rate action.", body)


def _ligand_section(data: dict | None) -> str:
    if data is None:
        return _section("ligand", "Ligand communication", "No ligand result was found.", "")
    initial = _obj(data.get("initial_observation"))
    rows = [["0 · initial", initial.get("time_s"), "—",
             initial.get("field_concentration_mol_m3"), initial.get("sender_amount_mol"),
             initial.get("receiver_amount_mol"), initial.get("receiver_memory"), "—"]]
    for index, record in enumerate(_list(data.get("trace")), start=1):
        record = _obj(record)
        action = _obj(record.get("action"))
        transition = _obj(record.get("transition"))
        observation = _obj(transition.get("observation"))
        info = _obj(transition.get("info"))
        rows.append([index, observation.get("time_s"), action.get("rate_mol_s",
                     action.get("secretion_rate_mol_s")),
                     observation.get("field_concentration_mol_m3"),
                     observation.get("sender_amount_mol"), observation.get("receiver_amount_mol"),
                     observation.get("receiver_memory"), info.get("integrated_transfer_mol")])
    body = '<div class="cards">' + "".join([
        _card("Accepted steps", len(_list(data.get("trace"))), "One sender and one receiver"),
        _card("Checkpoint replay", data.get("json_checkpoint_replay_equal"), "JSON continuation"),
        _card("Overdraw leaves state unchanged", _obj(data.get("overdraw_rejection")).get("world_private_state_clock_unchanged"), "Rejected secretion"),
        _card("Max amount balance error (mol)", data.get("maximum_closed_amount_balance_error_mol"), "Tracked same-species transfer"),
    ]) + '</div>'
    body += '<p class="caption">The receiver senses accepted pre-step extracellular concentration without consuming ligand. The first transfer raises field concentration; memory responds in the next interval. This is synthetic communication, without receptor binding or calibrated signaling.</p>'
    body += _table(["Step", "Time (s)", "Secretion rate (mol/s)", "Field c (mol/m³)",
                    "Sender amount (mol)", "Receiver amount (mol)",
                    "Receiver memory (1)", "Transferred (mol)"], rows)
    body += _details("Ligand configuration and failure injection", {
        "configuration": data.get("configuration"),
        "overdraw_rejection": data.get("overdraw_rejection")})
    return _section("ligand", "Ligand communication",
                    "Sender-to-field material transfer and receiver exposure memory.", body)


def _self_play_section(data: dict | None) -> str:
    if data is None:
        return _section("learning", "Virtual-cell learning iterations", "No self-play result was found.", "")
    arms = _obj(data.get("arms"))
    summary = []
    prefit_values = []
    for name, arm_value in arms.items():
        arm = _obj(arm_value)
        evaluation = _obj(arm.get("evaluation"))
        summary.append([name, arm.get("accepted_episodes"), arm.get("failed_episodes"),
                        arm.get("generated_development_steps"),
                        evaluation.get("one_step_mae_memory_1"),
                        evaluation.get("weights_unchanged")])
        for attempt in _list(arm.get("attempts")):
            value = _num(_obj(attempt).get("prefit_mae_memory_1"))
            if value is not None:
                prefit_values.append(value)
    body = '<p class="caption">Each round selects one development history, obtains four teacher steps, then refits a small numeric one-step learner. The adaptive proposer is compared with fixed-coverage and seeded-random choices under the recorded equal episode budget. Evaluation uses sealed synthetic schedules with frozen weights; no RL algorithm ran.</p>'
    body += _table(["Arm", "Accepted dev episodes", "Failed dev episodes", "Dev steps",
                    "Sealed one-step MAE (1)", "Frozen weights unchanged"], summary)
    max_prefit = max(prefit_values, default=0.0)
    for name, arm_value in arms.items():
        arm = _obj(arm_value)
        body += f'<h3>{_e(name)} · development rounds</h3>'
        body += '<div class="table-wrap"><table><thead><tr>' + "".join(
            f'<th scope="col">{_e(item)}</th>' for item in
            ("Round", "Selected schedule", "Family", "Pre-fit one-step MAE (1)",
             "Mean teacher score", "Status")) + '</tr></thead><tbody>'
        for attempt_value in _list(arm.get("attempts")):
            attempt = _obj(attempt_value)
            schedule = _obj(attempt.get("schedule"))
            body += ('<tr>' + _cell(attempt.get("round")) + _cell(schedule.get("id")) +
                     _cell(schedule.get("family")) + '<td>' +
                     _error_bar(attempt.get("prefit_mae_memory_1"), max_prefit) + '</td>' +
                     _cell(attempt.get("mean_teacher_diagnostic_score")) +
                     '<td>' + _pill(attempt.get("status")) + '</td></tr>')
        body += '</tbody></table></div>'
        for attempt_value in _list(arm.get("attempts")):
            attempt = _obj(attempt_value)
            schedule = _obj(attempt.get("schedule"))
            step_rows = []
            for row_value in _list(attempt.get("rows")):
                row = _obj(row_value)
                action = _obj(row.get("action"))
                features = _list(row.get("features"))
                step_rows.append([row.get("step"), row.get("before_time_s"),
                                  row.get("after_time_s"),
                                  features[1] if len(features) > 1 else None,
                                  features[2] if len(features) > 2 else None,
                                  action.get("vmax_mol_s"), row.get("label_next_memory"),
                                  row.get("diagnostic_score")])
            body += (f'<details><summary>{_e(name)} · round {_e(attempt.get("round"))} '
                     f'· {_e(schedule.get("id"))}: per-step observations and scores</summary>' +
                     _table(["Step", "Before (s)", "After (s)", "Memory before (1)",
                             "Field c before (mol/m³)", "Action vmax (mol/s)",
                             "Next memory (1)", "Teacher score"], step_rows, compact=True) +
                     '</details>')
    body += _details("Learning configuration and cost accounting", {
        "configuration": data.get("configuration"), "costs": data.get("costs"),
        "sealed_evaluation_schedule_sha256": data.get("sealed_evaluation_schedule_sha256"),
        "rl_algorithm_run": data.get("rl_algorithm_run")})
    return _section("learning", "Virtual-cell learning iterations",
                    "Development choices, teacher feedback, and frozen one-step evaluation.", body)


def _symbolic_section(data: dict | None, trace: list[dict]) -> str:
    if data is None:
        return _section("symbolic", "Symbolic logic", "No symbolic result was found.", "")
    rejection = _obj(data.get("unsupported_construct"))
    body = '<div class="cards">' + "".join([
        _card("Accepted intervals", data.get("accepted_intervals"), "Existing rule interpreter"),
        _card("Accepted rule events", data.get("accepted_rule_events"), "Identity binding and switch transitions"),
        _card("Direct/lowered trace equal", data.get("trace_bytes_equal"), "Same recorded decisions"),
        _card("Amount residual (mol)", data.get("total_balance_residual_mol"), "Tracked transfer and boundary ledger"),
    ]) + '</div>'
    rows = []
    for record in trace:
        decisions = _list(record.get("decisions"))
        switches = [_obj(d) for d in decisions if _obj(d).get("kind") == "concentration_switch"]
        transfers = [_obj(d) for d in decisions if _obj(d).get("kind") == "saturable_transfer"]
        rows.append([record.get("time_s"), record.get("input_concentration_mol_m3"),
                     ", ".join(f"{d.get('rule_id')}: {d.get('state')}" for d in switches),
                     ", ".join(f"{d.get('rule_id')}: {d.get('active')}" for d in transfers),
                     record.get("cell_amount_mol"), record.get("field_amount_mol"),
                     record.get("interval_balance_residual_mol")])
    body += _table(["Time (s)", "Field c (mol/m³)", "Switch", "Transfer gate",
                    "Cell amount (mol)", "Field amount (mol)", "Balance residual (mol)"], rows)
    body += '<p class="caption">The typed IR admits only the current synthetic concentration switch and gated same-species transfer. Its attempted unsupported construct was rejected before execution.</p>'
    body += _table(["Rejected construct", "Validator result", "Reason"], [[
        rejection.get("attempt_file"), rejection.get("status"), rejection.get("reason")]], compact=True)
    body += _details("Symbolic identity and comparison", {
        "symbolic_ir_sha256": data.get("symbolic_ir_sha256"),
        "lowered_ruleset_sha256": data.get("lowered_ruleset_sha256"),
        "accepted_history_digest_equal": data.get("accepted_history_digest_equal"),
        "final_world_bytes_equal": data.get("final_world_bytes_equal")})
    return _section("symbolic", "Symbolic logic",
                    "Typed data compiled to the existing two-motif rule interpreter.", body)


def _memory_section(data: dict | None) -> str:
    if data is None:
        return _section("memory", "Response memory", "No memory result was found.", "")
    early, late = _obj(data.get("early_high")), _obj(data.get("late_high"))
    rows = []
    for label, side in (("High then low", early), ("Low then high", late)):
        for index, row_value in enumerate(_list(side.get("history")), start=1):
            row = _obj(row_value)
            rows.append([label, index, row.get("start_time_s"), row.get("end_time_s"),
                         row.get("exposure_concentration_mol_m3"), row.get("memory")])
    challenge = [
        ["High then low", _obj(early.get("challenge_observation")).get("value")],
        ["Low then high", _obj(late.get("challenge_observation")).get("value")],
    ]
    body = '<p class="caption">The two histories have equal integrated exposure and the same current challenge concentration. Their response states differ because the exposure order differs. Values are synthetic and dimensionless.</p>'
    body += _table(["History", "Interval", "Start (s)", "End (s)",
                    "Concentration (mol/m³)", "Memory (1)"], rows)
    body += _table(["History", "Challenge response index (1)"], challenge, compact=True)
    body += '<div class="cards">' + "".join([
        _card("Challenge response difference (1)", data.get("challenge_difference"), "Same final input"),
        _card("JSON replay", data.get("json_round_trip_replay_equal"), "Deterministic continuation"),
    ]) + '</div>'
    return _section("memory", "Response memory", "Exact constant-input scalar relaxation control.", body)


def _splitting_section(data: dict | None) -> str:
    if data is None:
        return _section("numerics", "Uptake and splitting", "No numerical study was found.", "")
    control = _obj(data.get("control"))
    limit = _obj(data.get("engineering_limits"))
    body = '<div class="cards">' + "".join([
        _card("Fixed-grid RK4 control QoI (mol)", control.get("qoi_mol"), "Same semidiscrete equations"),
        _card("QoI absolute-error limit (mol)", limit.get("qoi_absolute_error_mol"), "Engineering threshold"),
        _card("Overdraw rejected", _obj(data.get("failure_injection")).get("rejected"), "Whole window unchanged"),
    ]) + '</div>'
    body += '<p class="caption">Cell accumulated synthetic tracer at T = 1 s is compared with a separately coded RK4 time-integration control on the same 2×2×2 fixed grid. This is not an independent spatial solver or a biological validation.</p>'
    for ordering, study_value in _obj(data.get("refinement")).items():
        study = _obj(study_value)
        body += f'<h3>{_e(ordering.replace("_", " "))}</h3>'
        rows = [[_obj(row).get("windows"), _obj(row).get("window_s"),
                 _obj(row).get("process_step_s"), _obj(row).get("qoi_mol"),
                 _obj(row).get("absolute_qoi_error_mol"),
                 _obj(row).get("absolute_balance_error_mol")]
                for row in _list(study.get("rows"))]
        body += _table(["Windows", "Window (s)", "Process step (s)", "QoI (mol)",
                        "Absolute QoI error (mol)", "Balance error (mol)"], rows)
        body += '<p class="caption">Coarsest observed window meeting this configuration’s QoI threshold: <strong>' + _e(study.get("coarsest_observed_window_meeting_qoi_tolerance_s")) + ' s</strong>.</p>'
    body += _details("Isolated window and process-step sweeps", {
        "fixed_process_step_window_refinement": data.get("fixed_process_step_window_refinement"),
        "fixed_window_process_step_refinement": data.get("fixed_window_process_step_refinement")})
    return _section("numerics", "Uptake and splitting",
                    "Declared numerical quantity of interest and refinement behavior.", body)


def _receipt_section(workload: dict, receipt: dict | None, paths: dict[str, Path]) -> str:
    components = _obj(workload.get("components"))
    rows = []
    for name in COMPONENTS:
        item = _obj(components.get(name))
        path = paths.get(name)
        rows.append([name, item.get("component_status"), item.get("accepted"),
                     item.get("exit_code"), str(path) if path is not None else None,
                     item.get("result_sha256")])
    body = _table(["Component", "Result status", "Accepted", "Exit", "Result file",
                   "Result SHA-256"], rows, compact=True)
    if receipt is None:
        body += '<p class="empty">No Engine/OSS receipt belongs to this direct run.</p>'
    else:
        body += '<p class="caption">Ocura Engine recorded command execution and requested process limits. Ocura OSS recorded and verified logs. Their identifiers are separate from Csim scientific component results.</p>'
        body += '<div class="cards">' + "".join([
            _card("Engine run ID", receipt.get("engine_run_id"), "Command execution record"),
            _card("OSS atom ID", receipt.get("oss_atom_id"), "Ledger command record"),
            _card("OSS chokepoint ID", receipt.get("oss_chokepoint_id"), "Ledger checkpoint"),
            _card("OSS verification", receipt.get("oss_verification_status"), "Log integrity result"),
        ]) + '</div>'
        body += _table(["Receipt field", "Value"], [
            ["Wrapper status", receipt.get("status")],
            ["Engine status", receipt.get("engine_status")],
            ["Engine phase status", receipt.get("engine_phase_status")],
            ["Engine phase return code", receipt.get("engine_phase_return_code")],
            ["Engine degraded capabilities", _list(receipt.get("engine_degraded_capabilities"))],
            ["OSS outcome", receipt.get("oss_outcome")],
            ["OSS verification problems", receipt.get("oss_verification_problems")],
            ["Workload status", receipt.get("workload_status")],
        ], compact=True)
        body += _details("Recorded Engine/OSS receipt", receipt)
    return _section("provenance", "Execution and ledger evidence",
                    "Component computation, command execution, and ledger verification are separate records.", body)


def _limitations_section(workload: dict, components: dict[str, dict | None]) -> str:
    rows = []
    for name, artifact in (("integrated workload", workload), *components.items()):
        for limitation in _list(_obj(artifact).get("limitations")):
            rows.append([name, limitation])
    body = _table(["Source", "Recorded limitation"], rows)
    for name, artifact in components.items():
        if artifact is not None:
            body += _details(f"Raw {name} result JSON", artifact)
    return _section("limits", "Evidence limits and raw component results",
                    "Claims are restricted to each recorded synthetic configuration.", body)


def render(run_path: Path) -> str:
    run_dir, outer = _locate_run(run_path)
    workload = _read_json(run_dir / "results.json")
    if workload is None or type(workload.get("components")) is not dict:
        raise ValueError("--run is not an integrated demo result")
    receipt = _read_json(outer / "receipt.json") if outer is not None else None
    paths = {name: run_dir / name / RESULT_NAME[name] for name in COMPONENTS}
    components = {name: _read_json(path) for name, path in paths.items()}
    symbolic_trace = _read_jsonl(run_dir / "symbolic/roundtripped/trace.jsonl")
    sections = [
        _section("overview", "Run at a glance", "Recorded status and source identity.",
                 _overview(workload, receipt, run_dir)),
        _episode_section(components["episode"]),
        _ligand_section(components["ligand"]),
        _self_play_section(components["self_play"]),
        _symbolic_section(components["symbolic"], symbolic_trace),
        _memory_section(components["memory"]),
        _splitting_section(components["splitting"]),
        _receipt_section(workload, receipt, paths),
        _limitations_section(workload, components),
    ]
    generated = datetime.now(timezone.utc).isoformat()
    css = """
    :root{color-scheme:dark;--bg:#10141d;--panel:#191f2b;--panel2:#20293a;--line:#344058;--ink:#e9f0fb;--muted:#acb9cb;--accent:#7ddcc6;--blue:#7aa6ff;--warn:#f4cc7a}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 15% 0%,#203247 0%,var(--bg) 42%);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
    header,main,footer{max-width:1420px;margin:auto;padding:0 28px}header{padding-top:46px;padding-bottom:26px}h1{font-size:clamp(2rem,4vw,3.8rem);line-height:1.05;letter-spacing:-.04em;margin:12px 0 18px}h2{font-size:1.75rem;letter-spacing:-.025em;margin:0}h3{margin:28px 0 10px;font-size:1.12rem}p{margin:0 0 16px}.kicker{text-transform:uppercase;letter-spacing:.19em;color:var(--accent);font-weight:750;font-size:.78rem}.lead{max-width:850px;color:var(--muted);font-size:1.12rem}.stamp{color:var(--muted);font-size:.81rem}nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:24px}nav a{padding:8px 11px;border:1px solid var(--line);border-radius:100px;color:var(--ink);text-decoration:none;font-size:.85rem}nav a:hover{border-color:var(--accent);color:var(--accent)}section{margin:18px 0 28px;padding:26px;background:linear-gradient(155deg,rgba(31,40,55,.98),rgba(21,27,39,.98));border:1px solid var(--line);border-radius:18px;box-shadow:0 12px 34px #070a1355}.section-heading{display:flex;justify-content:space-between;align-items:baseline;gap:24px;border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:20px}.section-heading p{color:var(--muted);max-width:530px;text-align:right;margin:0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:12px;margin:18px 0}.card{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:16px}.card-label{color:var(--muted);font-size:.77rem;text-transform:uppercase;letter-spacing:.08em}.card-value{font-size:1.3rem;font-weight:750;overflow-wrap:anywhere;margin-top:4px}.card-note{color:var(--muted);font-size:.78rem;margin-top:7px}.scope{border-left:3px solid var(--accent);padding:12px 16px;background:#17302f;color:#d7ede7}.caption{color:var(--muted);font-size:.88rem;max-width:1000px}.table-wrap{overflow-x:auto;margin:12px 0 20px;border:1px solid var(--line);border-radius:10px}table{width:100%;border-collapse:collapse;min-width:650px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #303b50;vertical-align:top}th{background:#263246;color:#d5e2f4;font-size:.78rem;text-transform:uppercase;letter-spacing:.055em;white-space:nowrap}td{font-variant-numeric:tabular-nums;overflow-wrap:anywhere}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#ffffff06}table.compact th,table.compact td{padding:8px 10px}.pill{padding:3px 8px;border-radius:100px;font-size:.78rem;font-weight:700}.pill.ok{background:#193e32;color:#a9f0ce}.pill.bad{background:#4d2930;color:#ffd0d0}.pill.neutral{background:#3a4050;color:#d5deec}.bar-track{display:inline-block;vertical-align:middle;width:100px;height:7px;background:#344158;border-radius:9px;overflow:hidden;margin-right:7px}.bar{display:block;height:100%;background:var(--blue)}.bar-value{white-space:nowrap}details{border:1px solid var(--line);border-radius:10px;padding:9px 12px;margin:10px 0;background:#17202e}summary{cursor:pointer;color:#c6d9f6;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;color:#dce8f7;background:#101722;padding:14px;border-radius:7px;max-height:560px;overflow:auto}.empty{color:var(--warn);padding:12px 0}footer{padding-top:10px;padding-bottom:55px;color:var(--muted);font-size:.8rem}@media(max-width:720px){header,main,footer{padding-left:14px;padding-right:14px}.section-heading{display:block}.section-heading p{text-align:left;margin-top:8px}section{padding:18px}}
    """
    nav = "".join(f'<a href="#{anchor}">{label}</a>' for anchor, label in (
        ("overview", "Overview"), ("episode", "Cell episode"), ("ligand", "Ligand"),
        ("learning", "Learning rounds"), ("symbolic", "Symbolic logic"),
        ("memory", "Response memory"), ("numerics", "Numerics"),
        ("provenance", "Engine + ledger"), ("limits", "Limits")))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            '<title>Local synthetic virtual-cell demo</title><style>' + css + '</style></head><body>'
            '<header><div class="kicker">Csim · local reference run</div>'
            '<h1>Virtual-cell experiment viewer</h1>'
            '<p class="lead">One inspectable synthetic run: typed logic, accepted cell–field state, '
            'response memory, proposer and learner iterations, numerical refinement, and execution records.</p>'
            '<div class="stamp">Generated ' + _e(generated) + '</div><nav aria-label="Sections">' + nav +
            '</nav></header><main>' + "".join(sections) + '</main><footer>'
            'Static local HTML · no scripts, remote assets, or network requests · '
            'scientific scope follows the recorded component limitations.</footer></body></html>')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True,
                        help="integrated run directory, workload/results.json, or outer receipt.json")
    parser.add_argument("--output", type=Path, required=True, help="new HTML file path")
    args = parser.parse_args()
    try:
        document = render(args.run)
        target = args.output.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(document)
        print(json.dumps({"status": "completed", "output": str(target),
                          "sha256": _sha(target), "bytes": target.stat().st_size}))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
