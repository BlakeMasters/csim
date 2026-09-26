"""Seeded one-to-five-cell NF-kappa-B proxy variability on an observed schedule."""
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
from cellsim_v2.seeded_nfkb_episode import SeededNfkbEpisode, SeededNfkbRejected  # noqa: E402


OBSERVED = ROOT / "runs" / "nfkb_observed_20260926_01" / "observed_traces.json"
SEEDS = (7, 17, 29, 43)
COUNTS = (1, 3, 5)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component_hash() -> str:
    digest = hashlib.sha256()
    for relative in (
            "src/cellsim_v2/nfkb_episode.py",
            "src/cellsim_v2/seeded_nfkb_episode.py",
            "tests/test_seeded_nfkb_episode.py",
            "tools/run_seeded_nfkb_demo.py"):
        path = ROOT / relative
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _run_case(cell_count: int, sequence: str, seed: int | None) -> dict:
    seeded = seed is not None
    episode = (SeededNfkbEpisode(seed=seed, cell_count=cell_count)
               if seeded else NfkbEpisode(cell_count=cell_count))
    observation = episode.reset()
    curve = [{"time_min": 0.0,
              "reporter_index_by_cell": {
                  cell["cell_id"]: cell["reporter_index"] for cell in observation["cells"]}}]
    replay = None
    replay_equal = True
    max_residual = 0.0
    for index in range(82):
        rates = {cell["cell_id"]: 0.00002 for cell in episode.observe()["cells"]}
        action = episode.make_scheduled_action(
            sequence_key=sequence, payload_admin_mol_at_start=0.02,
            payload_uptake_rates_mol_min_by_cell=rates,
        )
        if seeded and index == 20:
            replay = SeededNfkbEpisode.from_checkpoint(
                json.loads(json.dumps(episode.checkpoint())))
        transition = episode.step(action)
        if replay is not None:
            twin = replay.step(replay.make_scheduled_action(
                sequence_key=sequence, payload_admin_mol_at_start=0.02,
                payload_uptake_rates_mol_min_by_cell=rates,
            ))
            replay_equal &= (transition == twin and episode.checkpoint() == replay.checkpoint())
        max_residual = max(max_residual, transition["info"]["maximum_amount_residual_mol"])
        observation = transition["observation"]
        curve.append({"time_min": observation["time_min"],
                      "reporter_index_by_cell": {
                          cell["cell_id"]: cell["reporter_index"]
                          for cell in observation["cells"]}})
    terminal = episode.observe()
    return {
        "kind": "seeded" if seeded else "deterministic_baseline",
        "seed": seed, "cell_count": cell_count,
        "accepted_steps": 82,
        "maximum_amount_residual_mol": max_residual,
        "checkpoint_replay_equal": replay_equal,
        "terminal_mean_reporter_index": math.fsum(
            cell["reporter_index"] for cell in terminal["cells"]) / cell_count,
        "terminal_field": terminal["field"],
        "terminal_payload_amount_mol_by_cell": {
            cell["cell_id"]: cell["payload_amount_mol"] for cell in terminal["cells"]},
        "curve": curve,
        "cell_parameters_by_id": (episode.checkpoint()["payload"]["cell_parameters_by_id"]
                                  if seeded else None),
    }


def run(observed_artifact: Path | str = OBSERVED) -> dict:
    started = time.perf_counter()
    source_path = Path(observed_artifact)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source.get("status") != "pass":
        raise ValueError("observed NF-kB schedule artifact has not passed")
    condition = next((item for item in source["conditions"]
                      if item["split"] == "evaluation" and
                      item["author_control_label"] is None), None)
    if condition is None or condition["sequence_key"] is None:
        raise ValueError("verified evaluation stimulus sequence missing")
    sequence = condition["sequence_key"]
    cases = {}
    for count in COUNTS:
        baseline = _run_case(count, sequence, None)
        replicates = [_run_case(count, sequence, seed) for seed in SEEDS]
        terminals = [row["terminal_mean_reporter_index"] for row in replicates]
        cases[str(count)] = {
            "baseline": baseline,
            "replicates": replicates,
            "terminal_reporter_min": min(terminals),
            "terminal_reporter_max": max(terminals),
            "terminal_reporter_span": max(terminals) - min(terminals),
            "terminal_reporter_mean": math.fsum(terminals) / len(terminals),
        }
    rejection_episode = SeededNfkbEpisode(seed=7, cell_count=5)
    before = rejection_episode.checkpoint()
    ids = [cell["cell_id"] for cell in rejection_episode.observe()["cells"]]
    try:
        rejection_episode.step(rejection_episode.make_action(
            payload_admin_mol=0.001,
            payload_uptake_rates_mol_min_by_cell={cid: 1.0 for cid in ids},
        ))
    except SeededNfkbRejected as exc:
        rejection_error = str(exc)
    else:
        rejection_error = None
    unchanged = rejection_episode.checkpoint() == before
    all_replays = all(row["checkpoint_replay_equal"]
                      for case in cases.values() for row in case["replicates"])
    maximum_residual = max(row["maximum_amount_residual_mol"]
                           for case in cases.values()
                           for row in [case["baseline"], *case["replicates"]])
    result = {
        "status": "pass",
        "scope": "seeded illustrative per-cell NF-kappa-B proxy variability; finite paired amounts unchanged",
        "biological_qualification": "unqualified",
        "python": sys.version, "platform": platform.platform(), "device": "CPU",
        "source_test_tool_sha256": _component_hash(),
        "observed_schedule": {
            "artifact_path": str(source_path), "artifact_sha256": _digest(source_path),
            "source_matrix_sha256": source["source"]["sha256"],
            "condition_id": condition["condition_id"],
            "split": condition["split"],
            "sequence_key": sequence,
            "time_min": condition["observed"]["time_min"],
            "mean_normalized_nuc_cyto_p65": condition["observed"]["mean"],
            "comparison_role": "separate observed curve, no calibration of stochastic proxy",
        },
        "seeds": list(SEEDS),
        "cell_count_cases": cases,
        "all_replays_equal": all_replays,
        "overdraw_rejection_error": rejection_error,
        "overdraw_rejection_unchanged": unchanged,
        "maximum_amount_residual_mol": maximum_residual,
        "costs": {
            "seeded_replicates": len(SEEDS) * len(COUNTS),
            "deterministic_baselines": len(COUNTS),
            "attempted_steps": 82 * (len(SEEDS) + 1) * len(COUNTS),
            "accepted_steps": 82 * (len(SEEDS) + 1) * len(COUNTS),
            "failed_steps": 0,
            "wall_s": time.perf_counter() - started,
        },
        "limitations": [
            "Seeded parameter spread and step noise are declared synthetic, not estimated from observed cell variance",
            "Counter-addressed draws reproduce exactly under a given seed on the tested Python/host build",
            "The observed normalized Nuc/Cyto p65 curve is separate from the uncalibrated reporter proxy",
            "The same one-voxel amount transfer kernel is used; no stochastic material reaction or drug efficacy is modeled",
        ],
    }
    if (not all_replays or not unchanged or not rejection_error or
            maximum_residual > 1e-12 or
            any(case["terminal_reporter_span"] <= 0 for case in cases.values())):
        result["status"] = "fail"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observed-artifact", type=Path, default=OBSERVED)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory already exists; preserve earlier evidence")
    result = run(args.observed_artifact)
    args.output.mkdir(parents=True)
    target = args.output / "results.json"
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(target.resolve()),
                      "seeded_replicates": result["costs"]["seeded_replicates"],
                      "all_replays_equal": result["all_replays_equal"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
