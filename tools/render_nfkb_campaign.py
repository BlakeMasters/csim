#!/usr/bin/env python3
"""Render a local, read-only NF-kappa-B campaign review from one results JSON.

The input remains authoritative. This makes no new model, score, or biological
claim. It deliberately renders both accepted and failed comparisons.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    ("peak_reporter_index", "Peak reporter index", "index"),
    ("time_to_peak_min", "Time to peak", "min"),
    ("auc_reporter_index_min", "Reporter AUC", "index·min"),
)
MAX_JSON_BYTES = 20_000_000


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("campaign JSON exceeds the local review bound")
    def reject_constant(token: str):
        raise ValueError(f"nonfinite JSON constant {token} is forbidden")
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if type(value) is not dict or value.get("status") not in {"pass", "passed", "failed", "fail"}:
        raise ValueError("campaign results require a recognized status")
    if type(value.get("pairs")) is not list or len(value["pairs"]) > 256:
        raise ValueError("campaign pairs must be a bounded list")
    if type(value.get("failures", [])) is not list:
        raise ValueError("campaign failures must be a list")
    return value


def _number(value: object, *, signed: bool = True) -> str:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        return "—"
    if not signed and value < 0:
        return "—"
    return f"{value:.6g}"


def _text(value: object) -> str:
    return escape("—" if value is None else str(value), quote=True)


def _status(value: object) -> str:
    label = "—" if value is None else str(value)
    css = "ok" if label in {"pass", "passed", "completed", "true"} else "warn"
    return f'<span class="pill {css}">{_text(label)}</span>'


def _metric_rows(pairs: list[dict]) -> str:
    rows = []
    for pair in pairs:
        if type(pair) is not dict:
            raise ValueError("each campaign pair must be an object")
        baseline = pair.get("baseline") if type(pair.get("baseline")) is dict else {}
        intervention = pair.get("intervention") if type(pair.get("intervention")) is dict else {}
        baseline_mean = baseline.get("mean_metrics") if type(baseline.get("mean_metrics")) is dict else {}
        intervention_mean = intervention.get("mean_metrics") if type(intervention.get("mean_metrics")) is dict else {}
        delta = pair.get("delta_mean_metrics") if type(pair.get("delta_mean_metrics")) is dict else {}
        protocol = pair.get("protocol") if type(pair.get("protocol")) is dict else {}
        identity = (f'{_text(pair.get("pair_id"))}<small>'
                    f'N={_text(pair.get("cell_count"))} · sequence {_text(pair.get("sequence_key"))}'
                    f' · protocol {_text(protocol.get("id"))} · replicate {_text(pair.get("replicate_id"))}'
                    f' · seed {_text(pair.get("seed"))}</small>'
                    f'<small>traces {_text(baseline.get("trace_id"))} / '
                    f'{_text(intervention.get("trace_id"))}</small>')
        for metric, label, unit in METRICS:
            rows.append(
                "<tr>"
                f'<th scope="row">{identity}</th>'
                f'<td>{_text(label)}<small>{_text(unit)}</small></td>'
                f'<td class="num">{_number(baseline_mean.get(metric))}</td>'
                f'<td class="num">{_number(intervention_mean.get(metric))}</td>'
                f'<td class="num">{_number(delta.get(metric))}</td>'
                f'<td>{_status(baseline.get("status"))} / {_status(intervention.get("status"))}'
                f'<small>matched: {_text(pair.get("matched"))}; accepted steps '
                f'{_text(baseline.get("accepted_steps"))} / {_text(intervention.get("accepted_steps"))}</small></td>'
                f'<td class="num">{_number(baseline.get("maximum_amount_residual_mol"), signed=False)} / '
                f'{_number(intervention.get("maximum_amount_residual_mol"), signed=False)}</td>'
                "</tr>"
            )
    return "\n".join(rows) or '<tr><td colspan="7">No campaign pairs were emitted.</td></tr>'


def _failure_rows(failures: list) -> str:
    if not failures:
        return '<li>None reported in this artifact.</li>'
    return "\n".join(f'<li><code>{_text(json.dumps(item, sort_keys=True, allow_nan=False))}</code></li>'
                     for item in failures[:256])


def _protocol_rows(pairs: list[dict]) -> str:
    groups: dict[str, dict] = {}
    for pair in pairs:
        protocol = pair.get("protocol") if type(pair.get("protocol")) is dict else {}
        identifier = str(protocol.get("id", "unspecified"))
        group = groups.setdefault(identifier, {"total": 0, "matched": [], "failed": 0})
        group["total"] += 1
        delta = pair.get("delta_mean_metrics")
        valid = (pair.get("matched") is True and type(delta) is dict and
                 all(type(delta.get(key)) in (int, float) and math.isfinite(float(delta[key]))
                     for key, _, _ in METRICS))
        if valid:
            group["matched"].append(delta)
        else:
            group["failed"] += 1
    rows = []
    for identifier, group in sorted(groups.items()):
        accepted = group["matched"]
        means = [(_number(math.fsum(item[key] for item in accepted) / len(accepted))
                  if accepted else "—") for key, _, _ in METRICS]
        rows.append(
            "<tr>" + f'<th scope="row">{_text(identifier)}</th>'
            + f'<td class="num">{group["total"]}</td>'
            + f'<td class="num">{len(accepted)}</td>'
            + f'<td class="num">{group["failed"]}</td>'
            + "".join(f'<td class="num">{mean}</td>' for mean in means)
            + "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="7">No protocol pairs were emitted.</td></tr>'


def render(report: dict, *, report_hash: str, oss: dict | None = None) -> str:
    """Return an escaped, standalone HTML review page."""
    pairs = report["pairs"]
    counts = sorted({item.get("cell_count") for item in pairs
                     if type(item) is dict and type(item.get("cell_count")) is int})
    failures = report.get("failures", [])
    costs = report.get("costs") if type(report.get("costs")) is dict else {}
    config = report.get("configuration") if type(report.get("configuration")) is dict else {}
    limitations = report.get("limitations") if type(report.get("limitations")) is list else []
    oss = oss if type(oss) is dict else {}
    verification = oss.get("verification") if type(oss.get("verification")) is dict else {}
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NF-κB campaign review · local Csim</title>
<style>
:root {{color-scheme:light; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; color:#15292b; background:#e7ede9}}
* {{box-sizing:border-box}} body {{margin:0;padding:20px}} main {{max-width:1520px;margin:auto}}
header,section,footer {{background:#f9fbf8;border:2px solid #243d40;box-shadow:5px 5px 0 #9ab2a6;margin:0 0 18px;padding:16px}}
h1 {{font-size:clamp(1.35rem,2vw,2.15rem);margin:0 0 6px}} h2 {{font-size:1rem;text-transform:uppercase;letter-spacing:.08em;margin:0 0 12px}}
p {{line-height:1.5;max-width:95ch}} .sub {{color:#405b58}} .grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}
.box {{border:1px solid #66827b;padding:10px;background:#edf4ed}} .box strong {{display:block;font-size:1.25rem;margin-top:5px}}
.scroll {{overflow-x:auto}} table {{border-collapse:collapse;width:100%;min-width:990px;font-size:.84rem}} th,td {{border:1px solid #9eb3aa;padding:8px;text-align:left;vertical-align:top}}
thead {{background:#d2e4d5}} tbody tr:nth-child(even) {{background:#eef5ee}} th[scope=row] {{min-width:190px}} small {{display:block;color:#52706b;margin-top:3px}}
.num {{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}} .pill {{display:inline-block;border:1px solid;padding:2px 5px;font-weight:700}}
.ok {{color:#185c36;background:#dff1df}} .warn {{color:#8b3925;background:#fff0dd}} code {{overflow-wrap:anywhere}} li {{margin:8px 0}}
.meta {{display:grid;grid-template-columns:minmax(150px,230px) 1fr;gap:7px;border-bottom:1px solid #b6c9be;padding:6px 0}}
@media(max-width:600px) {{body {{padding:10px}} header,section,footer {{padding:12px;box-shadow:3px 3px 0 #9ab2a6}} .meta {{grid-template-columns:1fr}}}}
</style></head><body><main>
<header><h1>NF-κB campaign review</h1><p class="sub">Local Csim · matched baseline and intervention schedules · numeric artifact review</p>
<p>Campaign {_status(report.get("status"))} · {len(pairs)} matched pair records · cell counts {_text(", ".join(map(str,counts)) or "none")}</p></header>
<section><h2>Campaign at a glance</h2><div class="grid">
<div class="box">Pairs<strong>{len(pairs)}</strong></div><div class="box">Failures<strong>{len(failures)}</strong></div>
<div class="box">Runs<strong>{_text(costs.get("run_count", "—"))}</strong></div>
<div class="box">Accepted steps<strong>{_text(costs.get("accepted_steps", "—"))}</strong></div>
<div class="box">Failed steps<strong>{_text(costs.get("failed_steps", "—"))}</strong></div>
</div><p><b>Protocol:</b> {_text(config.get("sequence_key"))} · {_text(config.get("horizon_steps"))} × {_text(config.get("step_min"))} min · cells {_text(", ".join(map(str, config.get("cell_counts", []))))} · switch administration {_text(config.get("stimulus_admin_mol_per_switch"))} mol · balance limit {_text(config.get("amount_balance_limit_mol"))} mol</p>
<details><summary>Full numeric configuration</summary><code>{_text(json.dumps(config, sort_keys=True, allow_nan=False))}</code></details></section>
<section><h2>By protocol · synthetic descriptive summary</h2><p class="sub">Mean intervention-minus-baseline deltas use only complete matched pairs. Failed or incomplete pairs remain counted and appear below; this is not an efficacy estimate.</p>
<div class="scroll"><table><thead><tr><th>Protocol</th><th>Pairs</th><th>Matched</th><th>Failed / incomplete</th><th>Mean Δ peak index</th><th>Mean Δ time to peak (min)</th><th>Mean Δ AUC (index·min)</th></tr></thead>
<tbody>{_protocol_rows(pairs)}</tbody></table></div></section>
<section><h2>Matched outcomes</h2><p class="sub">Peak, time, and AUC are reporter-index summaries. Delta is the intervention minus its matched baseline. Amount residuals are physical ledgers in mol, separate from reporter index.</p>
<div class="scroll"><table><thead><tr><th>Pair</th><th>Observable</th><th>Baseline</th><th>Intervention</th><th>Delta</th><th>Run status B / I</th><th>Max amount residual B / I (mol)</th></tr></thead>
<tbody>{_metric_rows(pairs)}</tbody></table></div></section>
<section><h2>Failures and limits</h2><ul>{_failure_rows(failures)}</ul><ul>{''.join(f'<li>{_text(item)}</li>' for item in limitations)}</ul></section>
<section><h2>Provenance and execution record</h2>
<div class="meta"><b>Campaign JSON SHA-256</b><code>{_text(report_hash)}</code></div>
<div class="meta"><b>Manifest SHA-256</b><code>{_text(report.get("manifest_sha256"))}</code></div>
<div class="meta"><b>Source/test/tool SHA-256</b><code>{_text(report.get("source_test_tool_sha256"))}</code></div>
<div class="meta"><b>Ocura OSS atom / chokepoint</b><code>{_text(oss.get("oss_atom_id", oss.get("atom_id")))} / {_text(oss.get("oss_chokepoint_id", oss.get("chokepoint_id")))}</code></div>
<div class="meta"><b>OSS verification</b><code>{_text(verification.get("status", oss.get("oss_verification_status", oss.get("verification_status"))))}; {_text(verification.get("logs_checked"))} logs checked; {_text(len(verification.get("problems", [])) if type(verification.get("problems")) is list else None)} problems</code></div>
</section><footer><b>Evidence boundary.</b> The supplied NF-κB reporter trajectories are observed data, but these campaign baseline/intervention traces and payload-response results are synthetic. The campaign does not validate a molecular mechanism, a biological drug effect, or patient outcomes. Review the source results, trace JSON, manifest and failures before reuse.</footer>
</main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="campaign results.json")
    parser.add_argument("--output", type=Path, required=True, help="new directory for index.html and receipt")
    parser.add_argument("--oss-record", type=Path, help="optional OSS receipt or record JSON")
    args = parser.parse_args()
    report = _load(args.input)
    oss_path = args.oss_record or args.input.parent / "oss_record.json"
    oss = _load_oss(oss_path) if oss_path.is_file() else None
    if oss is not None:
        for key, expected in (("results_sha256", _sha(args.input)),
                              ("manifest_sha256", report.get("manifest_sha256")),
                              ("source_test_tool_sha256", report.get("source_test_tool_sha256"))):
            if oss.get(key) is not None and oss[key] != expected:
                raise ValueError(f"OSS record {key} does not match campaign results")
    verification = (oss.get("verification") if oss and type(oss.get("verification")) is dict
                    else {})
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    page = render(report, report_hash=_sha(args.input), oss=oss)
    with (output / "index.html").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(page)
    receipt = {
        "status": "pass", "schema": "cellsim.nfkb-campaign-review.v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": sys.version,
        "input": str(args.input.resolve()), "input_sha256": _sha(args.input),
        "input_campaign_status": report["status"], "pairs": len(report["pairs"]),
        "failures": len(report.get("failures", [])),
        "oss_record": str(oss_path.resolve()) if oss else None,
        "oss_record_sha256": _sha(oss_path) if oss else None,
        "oss_atom_id": (oss.get("atom_id", oss.get("oss_atom_id")) if oss else None),
        "oss_chokepoint_id": (oss.get("chokepoint_id", oss.get("oss_chokepoint_id"))
                               if oss else None),
        "oss_verification_status": verification.get("status"),
        "renderer_sha256": _sha(Path(__file__)),
        "test_sha256": _sha(ROOT / "tests/test_render_nfkb_campaign.py"),
        "html_sha256": _sha(output / "index.html"),
        "limitations": "Static numeric review only; no new model fit or biological qualification.",
    }
    with (output / "receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": "pass", "output": str(output), "pairs": receipt["pairs"],
                      "html": str(output / "index.html")}, allow_nan=False))
    return 0


def _load_oss(path: Path) -> dict:
    if path.stat().st_size > 1_000_000:
        raise ValueError("OSS record exceeds local review bound")
    record = json.loads(path.read_text(encoding="utf-8"))
    if type(record) is not dict:
        raise ValueError("OSS record must be an object")
    return record


if __name__ == "__main__":
    raise SystemExit(main())
