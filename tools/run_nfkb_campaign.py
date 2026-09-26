"""Run a bounded, manifest-fixed synthetic NF-kB response campaign locally."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cellsim_v2.nfkb_episode import NfkbEpisode  # noqa: E402
from cellsim_v2.seeded_nfkb_episode import SeededNfkbEpisode  # noqa: E402

FORMAT = "cellsim-nfkb-campaign/1"
STEPS = 82
STEP_MIN = 6
_MANIFEST_KEYS = {
    "format", "campaign_id", "sequence_key", "cell_counts",
    "stimulus_admin_mol_per_switch", "initial_stimulus_reservoir_mol",
    "initial_payload_reservoir_mol", "amount_balance_limit_mol",
    "protocols", "replicates",
}
_PROTOCOL_KEYS = {
    "id", "payload_start_min", "payload_amount_mol",
    "uptake_rate_mol_min_per_cell",
}
_REPLICATE_KEYS = {"id", "kind", "seed"}


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{label} must be {'positive' if positive else 'nonnegative'}")
    return float(value)


def _identifier(value: object, label: str) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 64 or
            any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for char in value)):
        raise ValueError(f"{label} must be a 1-64 character ASCII identifier")
    return value


def validate_manifest(value: object) -> dict:
    """Reject ambiguous, unbounded or non-categorical campaign declarations."""
    if type(value) is not dict or set(value) != _MANIFEST_KEYS:
        raise ValueError("campaign manifest requires exactly the declared fields")
    if value["format"] != FORMAT:
        raise ValueError("unsupported campaign manifest format")
    _identifier(value["campaign_id"], "campaign ID")
    sequence = value["sequence_key"]
    if (type(sequence) is not str or len(sequence) != 4 or
            set(sequence) != {"T", "I", "L", "P"}):
        raise ValueError("sequence must be a T/I/L/P permutation")
    counts = value["cell_counts"]
    if (type(counts) is not list or not 1 <= len(counts) <= 5 or
            any(type(count) is not int or not 1 <= count <= 5 for count in counts) or
            len(set(counts)) != len(counts)):
        raise ValueError("cell counts must be unique integers from one to five")
    _number(value["stimulus_admin_mol_per_switch"], "stimulus switch amount")
    _number(value["initial_stimulus_reservoir_mol"], "stimulus reservoir")
    _number(value["initial_payload_reservoir_mol"], "payload reservoir")
    _number(value["amount_balance_limit_mol"], "amount balance limit", positive=True)
    protocols = value["protocols"]
    if type(protocols) is not list or not 1 <= len(protocols) <= 8:
        raise ValueError("campaign requires one to eight payload protocols")
    protocol_ids = []
    for protocol in protocols:
        if type(protocol) is not dict or set(protocol) != _PROTOCOL_KEYS:
            raise ValueError("payload protocol requires exactly the declared fields")
        protocol_ids.append(_identifier(protocol["id"], "payload protocol ID"))
        start = _number(protocol["payload_start_min"], "payload start minute")
        if start > 486 or start % STEP_MIN != 0:
            raise ValueError("payload start minute must align with a 0-486 six-minute step")
        _number(protocol["payload_amount_mol"], "payload amount")
        _number(protocol["uptake_rate_mol_min_per_cell"], "payload uptake rate")
    if len(set(protocol_ids)) != len(protocol_ids):
        raise ValueError("payload protocol IDs must be unique")
    replicates = value["replicates"]
    if type(replicates) is not list or not 1 <= len(replicates) <= 8:
        raise ValueError("campaign requires one to eight explicit replicates")
    replicate_ids = []
    seeds = []
    for replicate in replicates:
        if type(replicate) is not dict or set(replicate) != _REPLICATE_KEYS:
            raise ValueError("replicate requires exactly ID, kind and seed")
        replicate_ids.append(_identifier(replicate["id"], "replicate ID"))
        if replicate["kind"] == "deterministic":
            if replicate["seed"] is not None:
                raise ValueError("deterministic replicate seed must be null")
        elif replicate["kind"] == "seeded":
            seed = replicate["seed"]
            if type(seed) is not int or not 0 <= seed < 2**64:
                raise ValueError("seed must be an unsigned 64-bit integer")
            seeds.append(seed)
        else:
            raise ValueError("replicate kind must be deterministic or seeded")
    if len(set(replicate_ids)) != len(replicate_ids) or len(set(seeds)) != len(seeds):
        raise ValueError("replicate IDs and seeded values must be unique")
    if len(counts) * len(protocols) * len(replicates) > 40:
        raise ValueError("campaign exceeds forty matched pairs")
    return value


def _source_hash() -> str:
    digest = hashlib.sha256()
    for relative in (
        "src/cellsim_v2/nfkb_episode.py", "src/cellsim_v2/seeded_nfkb_episode.py",
        "tests/test_nfkb_campaign.py", "tools/run_nfkb_campaign.py",
    ):
        path = ROOT / relative
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _write(path: Path, payload: object) -> int:
    encoded = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(encoded)
    return len(encoded)


def _sample(observation: dict) -> dict:
    return {
        "time_min": observation["time_min"],
        "stimulus_code": observation["stimulus_code"],
        "field": observation["field"],
        "reservoir_amounts_mol": observation["reservoir_amounts_mol"],
        "waste_stimulus_amount_mol": observation["waste_stimulus_amount_mol"],
        "cells": [{key: cell[key] for key in (
            "cell_id", "model_id", "payload_amount_mol", "nuclear_proxy",
            "feedback", "reporter_index")}
                  for cell in observation["cells"]],
    }


def _curve_metrics(samples: list[dict], cell_id: str | None) -> dict:
    times = [row["time_min"] for row in samples]
    if cell_id is None:
        values = [math.fsum(cell["reporter_index"] for cell in row["cells"])
                  / len(row["cells"]) for row in samples]
    else:
        values = [next(cell["reporter_index"] for cell in row["cells"]
                       if cell["cell_id"] == cell_id) for row in samples]
    maximum = max(values)
    first_peak = values.index(maximum)
    auc = math.fsum((values[index] + values[index + 1])
                    * (times[index + 1] - times[index]) / 2
                    for index in range(len(values) - 1))
    return {"peak_reporter_index": maximum,
            "time_to_peak_min": times[first_peak],
            "auc_reporter_index_min": auc}


def _run_arm(manifest: dict, manifest_sha: str, cell_count: int,
             protocol: dict, replicate: dict, arm: str,
             output: Path) -> tuple[dict, int]:
    identity = {
        "manifest_sha256": manifest_sha, "cell_count": cell_count,
        "protocol_id": protocol["id"], "replicate_id": replicate["id"],
        "arm": arm,
    }
    trace_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    relative = Path("traces") / f"{trace_id}.json"
    seed = replicate["seed"]
    started = time.perf_counter()
    trace = {**identity, "trace_id": trace_id, "seed": seed,
             "replicate_kind": replicate["kind"], "samples": [],
             "transitions": [], "failure": None}
    attempted = 0
    accepted = 0
    maximum_residual = 0.0
    episode = None
    try:
        args = dict(
            cell_count=cell_count, horizon_steps=STEPS, step_min=STEP_MIN,
            initial_stimulus_reservoir_mol=manifest["initial_stimulus_reservoir_mol"],
            initial_payload_reservoir_mol=manifest["initial_payload_reservoir_mol"],
        )
        episode = (NfkbEpisode(**args) if seed is None
                   else SeededNfkbEpisode(seed=seed, **args))
        trace["samples"].append(_sample(episode.reset()))
        for step_index in range(STEPS):
            ids = [cell["cell_id"] for cell in episode.observe()["cells"]]
            intervention = arm == "intervention"
            rates = {cid: (protocol["uptake_rate_mol_min_per_cell"]
                           if intervention else 0.0) for cid in ids}
            action = episode.make_scheduled_action(
                sequence_key=manifest["sequence_key"],
                stimulus_admin_mol_per_switch=manifest["stimulus_admin_mol_per_switch"],
                payload_start_min=protocol["payload_start_min"],
                payload_admin_mol_at_start=(protocol["payload_amount_mol"]
                                           if intervention else 0.0),
                payload_uptake_rates_mol_min_by_cell=rates,
            )
            attempted += 1
            try:
                transition = episode.step(action)
            except Exception as exc:
                trace["failure"] = {
                    "step_index": step_index, "time_min": step_index * STEP_MIN,
                    "error_type": type(exc).__name__, "error": str(exc),
                    "action": action,
                    "accepted_checkpoint_sha256": episode.checkpoint()["sha256"],
                }
                break
            accepted += 1
            residual = transition["info"]["maximum_amount_residual_mol"]
            maximum_residual = max(maximum_residual, abs(residual))
            trace["transitions"].append({
                "step_index": step_index, "action": action,
                "ledger": transition["info"]["ledger"],
                "maximum_amount_residual_mol": residual,
            })
            trace["samples"].append(_sample(transition["observation"]))
            if maximum_residual > manifest["amount_balance_limit_mol"]:
                trace["failure"] = {
                    "step_index": step_index, "time_min": (step_index + 1) * STEP_MIN,
                    "error_type": "AmountBalanceLimitExceeded",
                    "error": "accepted step exceeded manifest balance limit",
                    "accepted_checkpoint_sha256": episode.checkpoint()["sha256"],
                }
                break
    except Exception as exc:
        trace["failure"] = {
            "step_index": accepted, "time_min": accepted * STEP_MIN,
            "error_type": type(exc).__name__, "error": str(exc),
            "accepted_checkpoint_sha256": (episode.checkpoint()["sha256"]
                                           if episode is not None else None),
        }
    passed = trace["failure"] is None and accepted == STEPS
    trace["status"] = "pass" if passed else "fail"
    trace["accepted_steps"] = accepted
    trace["attempted_steps"] = attempted
    trace["maximum_amount_residual_mol"] = maximum_residual
    trace["wall_s"] = time.perf_counter() - started
    trace_bytes = _write(output / relative, trace)
    metrics_by_cell = None
    mean_metrics = None
    if passed:
        ids = [cell["cell_id"] for cell in trace["samples"][0]["cells"]]
        metrics_by_cell = {cid: _curve_metrics(trace["samples"], cid) for cid in ids}
        mean_metrics = _curve_metrics(trace["samples"], None)
    summary = {
        "status": trace["status"], "arm": arm, "trace_id": trace_id,
        "trace_path": relative.as_posix(), "trace_sha256": hashlib.sha256(
            (output / relative).read_bytes()).hexdigest(),
        "seed": seed, "replicate_kind": replicate["kind"],
        "attempted_steps": attempted, "accepted_steps": accepted,
        "maximum_amount_residual_mol": maximum_residual,
        "metrics_by_cell": metrics_by_cell, "mean_metrics": mean_metrics,
        "failure": trace["failure"], "wall_s": trace["wall_s"],
        "trace_bytes": trace_bytes,
    }
    return summary, trace_bytes


def run_campaign(manifest_path: Path | str, output: Path | str) -> dict:
    """Execute every declared pair, retaining accepted and failed traces."""
    started = time.perf_counter()
    source = Path(manifest_path).resolve()
    raw = source.read_bytes()
    manifest = validate_manifest(json.loads(raw))
    manifest_sha = hashlib.sha256(raw).hexdigest()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "traces").mkdir()
    with (output / "manifest.json").open("xb") as stream:
        stream.write(raw)
    pairs = []
    failures = []
    trace_bytes = 0
    for count in manifest["cell_counts"]:
        for protocol in manifest["protocols"]:
            for replicate in manifest["replicates"]:
                pair_identity = {"manifest_sha256": manifest_sha,
                                 "cell_count": count, "protocol_id": protocol["id"],
                                 "replicate_id": replicate["id"]}
                pair_id = hashlib.sha256(json.dumps(
                    pair_identity, sort_keys=True).encode()).hexdigest()[:24]
                baseline, size = _run_arm(manifest, manifest_sha, count,
                                          protocol, replicate, "baseline", output)
                trace_bytes += size
                intervention, size = _run_arm(manifest, manifest_sha, count,
                                              protocol, replicate, "intervention", output)
                trace_bytes += size
                matched = baseline["status"] == intervention["status"] == "pass"
                delta = ({key: intervention["mean_metrics"][key]
                          - baseline["mean_metrics"][key]
                          for key in baseline["mean_metrics"]} if matched else None)
                pair = {
                    **pair_identity, "pair_id": pair_id,
                    "sequence_key": manifest["sequence_key"],
                    "seed": replicate["seed"], "replicate_kind": replicate["kind"],
                    "protocol": protocol, "baseline": baseline,
                    "intervention": intervention, "matched": matched,
                    "delta_mean_metrics": delta,
                }
                pairs.append(pair)
                for run in (baseline, intervention):
                    if run["status"] != "pass":
                        failures.append({"pair_id": pair_id,
                                         "trace_id": run["trace_id"],
                                         "arm": run["arm"],
                                         "failure": run["failure"]})
    runs = [pair[arm] for pair in pairs for arm in ("baseline", "intervention")]
    costs = {
        "pair_count": len(pairs), "run_count": len(runs),
        "deterministic_runs": sum(run["replicate_kind"] == "deterministic"
                                  for run in runs),
        "seeded_runs": sum(run["replicate_kind"] == "seeded" for run in runs),
        "failed_run_count": len(failures),
        "attempted_steps": sum(run["attempted_steps"] for run in runs),
        "accepted_steps": sum(run["accepted_steps"] for run in runs),
        "failed_steps": sum(run["attempted_steps"] - run["accepted_steps"]
                            for run in runs),
        "metric_evaluations": sum(run["mean_metrics"] is not None for run in runs),
        "trace_persistence_bytes": trace_bytes,
        "wall_s": time.perf_counter() - started,
    }
    result = {
        "status": "pass" if not failures else "fail",
        "scope": "manifest-fixed synthetic NF-kappa-B reporter/payload comparison",
        "manifest_path": str(source), "manifest_sha256": manifest_sha,
        "manifest_copy_path": "manifest.json",
        "campaign_id": manifest["campaign_id"],
        "source_test_tool_sha256": _source_hash(),
        "host": {"platform": platform.platform(), "python": sys.version,
                 "device": "CPU"},
        "configuration": {"horizon_steps": STEPS, "step_min": STEP_MIN,
                          "time_grid_min": list(range(0, 493, STEP_MIN)),
                          "cell_counts": manifest["cell_counts"],
                          "sequence_key": manifest["sequence_key"],
                          "stimulus_admin_mol_per_switch": manifest["stimulus_admin_mol_per_switch"],
                          "amount_balance_limit_mol": manifest["amount_balance_limit_mol"]},
        "pairs": pairs, "failures": failures, "costs": costs,
        "limitations": [
            "The response law and amount-bearing payload protocol are illustrative, not fitted drug efficacy.",
            "The four stimulus letters are categorical author codes; no physical dose is converted to synthetic mol.",
            "Seeded variability is reproducible synthetic spread, not observed cell variance calibration.",
            "Reporter metrics are on a dimensionless synthetic index and are not measured Nuc/Cyto p65 metrics.",
            "All runs use one fixed voxel on this local CPU; no spatial gradient or external solver is tested.",
        ],
    }
    _write(output / "results.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_campaign(args.manifest, args.output)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": result["status"],
                      "output": str((args.output / "results.json").resolve()),
                      "pairs": result["costs"]["pair_count"],
                      "runs": result["costs"]["run_count"],
                      "failed_runs": result["costs"]["failed_run_count"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
