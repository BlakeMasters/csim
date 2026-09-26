"""Local data-scheduled, illustrative NF-kappa-B response and delivery demo."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cellsim_v2.nfkb_episode import NfkbEpisode, NfkbRejected  # noqa: E402


OBSERVED = ROOT / "runs" / "nfkb_observed_20260926_01" / "observed_traces.json"
SOURCE_FILES = (
    ROOT / "src" / "cellsim_v2" / "nfkb_episode.py",
    ROOT / "tests" / "test_nfkb_episode.py",
    Path(__file__).resolve(),
)


def _source_hash() -> str:
    digest = hashlib.sha256()
    for path in SOURCE_FILES:
        digest.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_observed(path: Path) -> tuple[dict, dict]:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if artifact.get("status") != "pass":
        raise ValueError("observed trace artifact has not passed")
    condition = next((row for row in artifact["conditions"]
                      if row["split"] == "evaluation" and
                      row["author_control_label"] is None), None)
    if condition is None:
        raise ValueError("no frozen evaluation condition in observed artifact")
    time = condition["observed"]["time_min"]
    if time != list(range(0, 493, 6)):
        raise ValueError("observed trace does not match declared 6-minute grid")
    if (len(condition["sequence_key"]) != 4 or
            set(condition["sequence_key"]) != set("TILP") or
            artifact["switch_times_min"] != [0, 120, 240, 360]):
        raise ValueError("unsupported observed four-stimulus schedule")
    return artifact, condition


def _scenario(*, cell_count: int, sequence: str, payload: bool,
              horizon_steps: int = 82) -> tuple[dict, bool]:
    episode = NfkbEpisode(cell_count=cell_count, horizon_steps=horizon_steps)
    initial = episode.reset()
    rows = []
    reporter_curve = [{"time_min": 0.0,
                       "reporter_index_by_cell": {cell["cell_id"]: cell["reporter_index"]
                                                  for cell in initial["cells"]}}]
    replay_equal = True
    replay = None
    for index in range(horizon_steps):
        before = episode.observe()
        interval_start = before["time_min"]
        rates = {cell["cell_id"]: (0.0001 if payload and index >= 20 else 0.0)
                 for cell in before["cells"]}
        action = episode.make_scheduled_action(
            sequence_key=sequence, payload_admin_mol_at_start=0.03 if payload else 0.0,
            payload_uptake_rates_mol_min_by_cell=rates,
        )
        if index == 20:
            replay = NfkbEpisode.from_checkpoint(json.loads(json.dumps(episode.checkpoint())))
        transition = episode.step(action)
        if replay is not None:
            replay_action = replay.make_scheduled_action(
                sequence_key=sequence, payload_admin_mol_at_start=0.03 if payload else 0.0,
                payload_uptake_rates_mol_min_by_cell=rates,
            )
            replay_transition = replay.step(replay_action)
            replay_equal &= (transition == replay_transition and
                             episode.checkpoint() == replay.checkpoint())
        after = transition["observation"]
        rows.append({
            "round": index + 1, "interval_start_min": interval_start,
            "interval_end_min": after["time_min"],
            "before": before, "action": action, "after": after,
            "ledger": transition["info"]["ledger"],
            "maximum_amount_residual_mol": transition["info"]["maximum_amount_residual_mol"],
        })
        reporter_curve.append({
            "time_min": after["time_min"],
            "reporter_index_by_cell": {cell["cell_id"]: cell["reporter_index"]
                                       for cell in after["cells"]},
        })
    return {
        "cell_count": cell_count,
        "scenario": "stimulus_plus_generic_payload" if payload else "stimulus_only",
        "accepted_steps": horizon_steps,
        "switch_times_min": [row["interval_start_min"] for row in rows
                             if row["action"]["stimulus_code"] is not None],
        "switch_codes": [row["action"]["stimulus_code"] for row in rows
                         if row["action"]["stimulus_code"] is not None],
        "maximum_amount_residual_mol": max(row["maximum_amount_residual_mol"] for row in rows),
        "round_trace": rows,
        "reporter_curve": reporter_curve,
        "final_observation": episode.observe(),
    }, replay_equal


def _delivery_sweep_case(*, cell_count: int, sequence: str,
                         payload_admin_mol: float) -> dict:
    episode = NfkbEpisode(cell_count=cell_count)
    observation = episode.reset()
    curve = [{"time_min": 0.0,
              "reporter_index_by_cell": {
                  cell["cell_id"]: cell["reporter_index"] for cell in observation["cells"]}}]
    max_residual = 0.0
    replay = None
    replay_equal = True
    attempted = 0
    accepted = 0
    error = None
    for index in range(82):
        rates = {cell["cell_id"]: 0.00002 for cell in episode.observe()["cells"]}
        action = episode.make_scheduled_action(
            sequence_key=sequence, payload_admin_mol_at_start=payload_admin_mol,
            payload_uptake_rates_mol_min_by_cell=rates,
        )
        if index == 20:
            replay = NfkbEpisode.from_checkpoint(json.loads(json.dumps(episode.checkpoint())))
        attempted += 1
        try:
            transition = episode.step(action)
        except NfkbRejected as exc:
            error = str(exc)
            break
        accepted += 1
        if replay is not None:
            twin = replay.step(replay.make_scheduled_action(
                sequence_key=sequence, payload_admin_mol_at_start=payload_admin_mol,
                payload_uptake_rates_mol_min_by_cell=rates,
            ))
            replay_equal &= (transition == twin and episode.checkpoint() == replay.checkpoint())
        max_residual = max(max_residual, transition["info"]["maximum_amount_residual_mol"])
        after = transition["observation"]
        curve.append({"time_min": after["time_min"],
                      "reporter_index_by_cell": {
                          cell["cell_id"]: cell["reporter_index"] for cell in after["cells"]}})
    final = episode.observe()
    return {
        "status": "accepted" if error is None else "rejected",
        "error": error,
        "cell_count": cell_count,
        "payload_admin_mol": payload_admin_mol,
        "payload_uptake_rate_mol_min_per_cell": 0.00002,
        "attempted_steps": attempted,
        "accepted_steps": accepted,
        "maximum_amount_residual_mol": max_residual,
        "checkpoint_replay_equal": replay_equal,
        "terminal_reporter_index_by_cell": {
            cell["cell_id"]: cell["reporter_index"] for cell in final["cells"]},
        "terminal_payload_amount_mol_by_cell": {
            cell["cell_id"]: cell["payload_amount_mol"] for cell in final["cells"]},
        "final_payload_field_amount_mol": final["field"]["generic_inhibitor_payload"]["amount_mol"],
        "reporter_curve": curve,
    }


def run(observed_artifact: Path | str = OBSERVED) -> dict:
    started = time.perf_counter()
    observed_path = Path(observed_artifact)
    observed, condition = _load_observed(observed_path)
    sequence = condition["sequence_key"]
    stimulus_only, replay_a = _scenario(cell_count=1, sequence=sequence, payload=False)
    with_payload, replay_b = _scenario(cell_count=1, sequence=sequence, payload=True)
    count_cases = {}
    replay_checks = [replay_a, replay_b]
    for count in (1, 3, 5):
        case, replay = _scenario(cell_count=count, sequence=sequence, payload=True,
                                 horizon_steps=22)
        count_cases[str(count)] = case
        replay_checks.append(replay)
    delivery_sweep = [_delivery_sweep_case(
        cell_count=count, sequence=sequence, payload_admin_mol=dose,
    ) for count in (1, 2, 3, 4, 5) for dose in (0.0, 0.01, 0.02, 0.03)]
    rejection_episode = NfkbEpisode(cell_count=5)
    before = rejection_episode.checkpoint()
    ids = [cell["cell_id"] for cell in rejection_episode.observe()["cells"]]
    try:
        rejection_episode.step(rejection_episode.make_action(
            payload_admin_mol=0.001,
            payload_uptake_rates_mol_min_by_cell={cid: 1.0 for cid in ids},
        ))
    except NfkbRejected as exc:
        rejection_error = str(exc)
    else:
        rejection_error = None
    unchanged = rejection_episode.checkpoint() == before
    result = {
        "status": "pass",
        "scope": "data-scheduled illustrative NF-kappa-B proxy with finite synthetic environment delivery",
        "biological_qualification": "unqualified",
        "device": "CPU", "python": sys.version, "platform": platform.platform(),
        "source_test_tool_sha256": _source_hash(),
        "configuration": {
            "cell_counts": [1, 3, 5], "voxel_volume_m3": 0.125,
            "time_step_min": 6.0, "full_steps": 82,
            "stimulus_administration_mol_per_switch": 0.125,
            "payload_administration_mol_at_120_min": 0.03,
            "payload_uptake_rate_mol_min_per_cell": 0.0001,
            "parameter_role": "declared synthetic values; no biological fit",
        },
        "observed_overlay": {
            "artifact": str(observed_path),
            "artifact_sha256": hashlib.sha256(observed_path.read_bytes()).hexdigest(),
            "source_sha256": observed["source"]["sha256"],
            "condition_id": condition["condition_id"],
            "split": condition["split"],
            "dose_tier": condition["dose_tier"],
            "stimulus_codes": condition["stimulus_codes"],
            "sequence_key": sequence,
            "source_row_keys_sample": [row["row_key"] for row in condition["sample_traces"]],
            "time_min": condition["observed"]["time_min"],
            "mean_normalized_nuc_cyto_p65": condition["observed"]["mean"],
            "finite_count_by_time": condition["observed"]["finite_count_by_time"],
            "comparison_role": "visual time-axis overlay only; distinct uncalibrated reporter proxy",
            "quantitative_error": None,
        },
        "scenario_traces": {
            "stimulus_only": stimulus_only["round_trace"],
            "stimulus_plus_generic_payload": with_payload["round_trace"],
        },
        "reporter_curves": {
            "stimulus_only": stimulus_only["reporter_curve"],
            "stimulus_plus_generic_payload": with_payload["reporter_curve"],
        },
        "cell_count_cases": count_cases,
        "delivery_sweep": delivery_sweep,
        "delivery_sweep_costs": {
            "attempted_scenarios": len(delivery_sweep),
            "accepted_scenarios": sum(row["status"] == "accepted" for row in delivery_sweep),
            "failed_scenarios": sum(row["status"] != "accepted" for row in delivery_sweep),
            "attempted_steps": sum(row["attempted_steps"] for row in delivery_sweep),
            "accepted_steps": sum(row["accepted_steps"] for row in delivery_sweep),
            "wall_s": time.perf_counter() - started,
        },
        "checkpoint_replay_equal": all(replay_checks),
        "overdraw_rejection": {
            "error": rejection_error,
            "accepted_state_unchanged": unchanged,
        },
        "limitations": [
            "Observed source is author-normalized Nuc/Cyto p65; normalization algorithm and physical doses are unresolved",
            "Synthetic reservoir amounts are not mapped to experimental ligand concentrations or drug exposure",
            "The nuclear/feedback/reporter proxy parameters are declared illustrative values, not fitted kinetic constants",
            "The generic inhibitor-like payload is a mechanism demonstration, not an observed treatment or efficacy claim",
            "Delivery sweep is deterministic synthetic sensitivity, not an optimized treatment or measured efficacy",
            "One fixed voxel, no spatial gradients, receptor kinetics, gene-expression assay, or biological holdout validation",
        ],
    }
    if (not all(replay_checks) or not unchanged or not rejection_error or
            any(row["status"] != "accepted" or not row["checkpoint_replay_equal"]
                for row in delivery_sweep) or
            stimulus_only["switch_times_min"] != [0.0, 120.0, 240.0, 360.0] or
            with_payload["switch_codes"] != list(sequence) or
            max(stimulus_only["maximum_amount_residual_mol"],
                with_payload["maximum_amount_residual_mol"],
                *(case["maximum_amount_residual_mol"] for case in count_cases.values())) > 1e-12):
        result["status"] = "fail"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="new output directory for results.json")
    parser.add_argument("--observed-artifact", type=Path, default=OBSERVED)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory already exists; preserve earlier evidence")
    result = run(args.observed_artifact)
    args.output.mkdir(parents=True)
    output = args.output / "results.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({
        "status": result["status"], "output": str(output.resolve()),
        "condition_id": result["observed_overlay"]["condition_id"],
        "sequence": result["observed_overlay"]["sequence_key"],
        "checkpoint_replay_equal": result["checkpoint_replay_equal"],
    }))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
