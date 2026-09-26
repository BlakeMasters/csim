#!/usr/bin/env python3
"""Prepare grouped synthetic cell-field trajectories; does not train a model.

Each output directory is create-only. Failed attempts retain their configuration,
partial rows and failure record. Parameters are engineering examples, not biology.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.checkpoint import canonical_bytes, encode_world
from cellsim_v2.scheduler import Process, WindowStepper
from cellsim_v2.state import AmountField, Cell, World, identifier, number, total_amount
from cellsim_v2.training import dataset_digest, validate_dataset
from cellsim_v2.transport import (
    BoundaryFlux, CellUptake, RectilinearGrid3D, diffusion_step,
    diffusion_timestep_limit_s, saturable_uptake_step,
)


def default_config() -> dict:
    return json.loads((ROOT / "configs/training_fixture.example.json").read_text(encoding="utf-8"))


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in sorted([*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py"), *ROOT.glob("tools/*.py")]):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _keys(value: dict, names: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError(f"{name} must contain exactly {sorted(names)}")


def _validate_config(config: dict) -> RectilinearGrid3D:
    _keys(config, {"schema_version", "dataset_id", "species", "parameter_provenance", "grid",
                  "diffusivity_m2_s", "dt_s", "steps", "process_order", "cells", "conditions"}, "config")
    if config["schema_version"] != "1" or config["process_order"] != ["uptake", "diffusion"]:
        raise ValueError("unsupported schema or process order")
    for key in ("dataset_id", "species", "parameter_provenance"):
        identifier(config[key], key)
    _keys(config["grid"], {"x_widths_m", "y_widths_m", "z_widths_m", "origin_m"}, "grid")
    grid = RectilinearGrid3D(**{key: tuple(value) for key, value in config["grid"].items()})
    number(config["diffusivity_m2_s"], "diffusivity", minimum=0)
    number(config["dt_s"], "dt", positive=True)
    if type(config["steps"]) is not int or config["steps"] <= 0:
        raise ValueError("steps must be a positive integer")
    if config["dt_s"] > diffusion_timestep_limit_s(grid, config["diffusivity_m2_s"]):
        raise ValueError("configured diffusion step exceeds positivity limit")
    if not isinstance(config["cells"], list) or not config["cells"]:
        raise ValueError("at least one fixture cell is required")
    ids = set()
    for cell in config["cells"]:
        _keys(cell, {"id", "voxel", "volume_m3", "vmax_mol_s", "km_mol_m3"}, "cell")
        identifier(cell["id"], "cell id")
        if cell["id"] in ids:
            raise ValueError("duplicate cell id")
        ids.add(cell["id"])
        grid.center_m(cell["voxel"])
        number(cell["volume_m3"], "cell volume", positive=True)
        number(cell["vmax_mol_s"], "vmax", minimum=0)
        number(cell["km_mol_m3"], "Km", positive=True)
    if not isinstance(config["conditions"], list) or not config["conditions"]:
        raise ValueError("conditions must be nonempty")
    ids, splits = set(), set()
    for condition in config["conditions"]:
        _keys(condition, {"id", "split", "initial_concentration_mol_m3",
                          "boundary_inward_mol_m2_s", "boundary_start_step"}, "condition")
        identifier(condition["id"], "condition id")
        if condition["id"] in ids:
            raise ValueError("duplicate condition id")
        ids.add(condition["id"])
        if condition["split"] not in {"train", "validation", "test"}:
            raise ValueError("unknown split")
        splits.add(condition["split"])
        number(condition["initial_concentration_mol_m3"], "initial concentration", minimum=0)
        number(condition["boundary_inward_mol_m2_s"], "boundary influx", minimum=0)
        start = condition["boundary_start_step"]
        if type(start) is not int or not 0 <= start < config["steps"]:
            raise ValueError("invalid boundary start step")
    if splits != {"train", "validation", "test"}:
        raise ValueError("all three splits must be specified before generating data")
    return grid


def prepare(output: Path, config: dict | None = None, *, config_path: Path | None = None) -> dict:
    """Export a small reproducible trajectory dataset and hash-bound manifest.

    The target is the next intracellular amount under the specified synthetic law.
    Two cells in one environment belong to the SAME experimental unit/trajectory.
    Output failure records do not promote partially generated data to a dataset.
    """
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    summary = {
        "status": "running", "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(), "device": "CPU",
        "command_template": "python tools/prepare_training_fixture.py --output PATH [--config CONFIG]",
        "process_argv": list(sys.argv),
        "source_test_tool_sha256": source_fingerprint(),
        "biological_validation": False, "model_trained": False,
        "qualification": "unqualified", "sample_count": 0, "trajectories": [],
        "costs_seconds": {"generation": 0.0, "validation": 0.0, "persistence": 0.0,
                          "training": 0.0, "inference": 0.0, "evaluation": 0.0,
                          "failed_attempt": 0.0},
    }
    _write(output / "results.json", summary)
    try:
        if config is not None and config_path is not None:
            raise ValueError("supply config or config_path, not both")
        if config_path is not None:
            summary["requested_config_path"] = str(config_path)
            raw = Path(config_path).read_bytes()
            (output / "requested_config.json").write_bytes(raw)
            config = json.loads(raw)
        config = json.loads(json.dumps(default_config() if config is None else config, allow_nan=False))
        _write(output / "simulation_config.json", config)
        grid = _validate_config(config)
        fingerprint_inputs = {"source_test_tool_sha256": summary["source_test_tool_sha256"],
                              "config": config, "python": sys.version, "platform": platform.platform()}
        summary["execution_fingerprint"] = hashlib.sha256(canonical_bytes(fingerprint_inputs)).hexdigest()
        species, h = config["species"], Fraction(str(config["dt_s"]))
        laws = tuple(CellUptake(c["id"], c["vmax_mol_s"], c["km_mol_m3"]) for c in config["cells"])
        samples, final_states = [], {}
        with (output / "samples.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for condition in config["conditions"]:
                generation_start = time.perf_counter()
                # Uniform initial concentration, unequal amounts if voxel volumes differ.
                world = World(
                    cells={c["id"]: Cell(c["id"], grid.center_m(c["voxel"]), c["volume_m3"],
                                         {species: 0.0}) for c in config["cells"]},
                    fields={species: AmountField.from_concentrations(
                        species, (condition["initial_concentration_mol_m3"],) * grid.voxel_count,
                        grid.volumes_m3)},
                )
                before_amount = total_amount(world, species)
                trajectory_id = f"trajectory:{condition['id']}"

                def transport(snapshot: World, dt: float):
                    fluxes = ()
                    if snapshot.time_s >= condition["boundary_start_step"] * h:
                        fluxes = (BoundaryFlux(0, "lower", condition["boundary_inward_mol_m2_s"]),)
                    return diffusion_step(snapshot, grid, species, config["diffusivity_m2_s"], dt, fluxes)

                stepper = WindowStepper([
                    Process("uptake", h, frozenset({"cells", "fields"}),
                            lambda state, dt: saturable_uptake_step(state, grid, species, laws, dt)),
                    Process("diffusion", h, frozenset({"fields", "ledger"}), transport),
                ], h)
                summary["costs_seconds"]["generation"] += time.perf_counter() - generation_start
                for index in range(config["steps"]):
                    generation_start = time.perf_counter()
                    pending = []
                    for cell_config in config["cells"]:
                        cell = world.cells[cell_config["id"]]
                        sample_id = f"{trajectory_id}:{index}:{cell.id}"
                        sample = {"sample_id": sample_id, "experimental_unit_id": trajectory_id,
                                  "trajectory_id": trajectory_id, "condition_id": condition["id"],
                                  "split": condition["split"], "artifact_path": "samples.jsonl"}
                        row = {**sample, "cell_id": cell.id, "time_s": float(world.time_s), "dt_s": float(h),
                               "inputs": {"extracellular_concentration_mol_m3":
                                          world.fields[species].concentrations_mol_m3[grid.locate(cell.position_m)],
                                          "cell_amount_mol": cell.amounts_mol[species],
                                          "vmax_mol_s": cell_config["vmax_mol_s"],
                                          "km_mol_m3": cell_config["km_mol_m3"]}}
                        pending.append((sample, row))
                    stepper.advance(world, (index + 1) * h)
                    for sample, row in pending:
                        row["targets"] = {"cell_amount_mol": world.cells[row["cell_id"]].amounts_mol[species]}
                    summary["costs_seconds"]["generation"] += time.perf_counter() - generation_start
                    persistence_start = time.perf_counter()
                    for sample, row in pending:
                        stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                        samples.append(sample)
                        summary["sample_count"] += 1
                    stream.flush()
                    summary["costs_seconds"]["persistence"] += time.perf_counter() - persistence_start
                after_amount = total_amount(world, species)
                expected_change = math.fsum(entry.change_mol for entry in world.ledger)
                balance_error = abs(after_amount - before_amount - expected_change)
                tolerance = 1e-18 + 1e-12 * max(abs(before_amount), abs(after_amount), abs(expected_change))
                if balance_error > tolerance:
                    raise ValueError("trajectory amount balance exceeds declared tolerance")
                summary["trajectories"].append({"id": trajectory_id, "split": condition["split"],
                    "before_mol": before_amount, "after_mol": after_amount,
                    "ledger_change_mol": expected_change, "balance_error_mol": balance_error,
                    "balance_tolerance_mol": tolerance, "status": "pass"})
                final_states[trajectory_id] = encode_world(world)
        persistence_start = time.perf_counter()
        _write(output / "final_states.json", final_states)
        artifacts = [{"path": name, "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()}
                     for name in ("samples.jsonl", "simulation_config.json", "final_states.json")]
        manifest = {
            "schema_version": "1", "dataset_id": config["dataset_id"], "data_kind": "synthetic",
            "observable": {"id": "intracellular_amount_next", "unit": "mol",
                           "observation_operator": "cells[cell_id].amounts_mol[species] after one uptake/diffusion window",
                           "modality": "physical_amount", "feature_ids": ["cell_amount_mol"],
                           "pairing": "longitudinal"},
            "artifacts": artifacts, "samples": samples,
            "split_policy": {"held_out_dimensions": ["condition_id"]},
            "source_ref": "Local synthetic reference laws; simulation_config.json",
            "reuse_terms": None,
            "metadata": {"biological_validation": False, "qualification": "unqualified",
                         "parameter_provenance": config["parameter_provenance"],
                         "source_test_tool_sha256": summary["source_test_tool_sha256"],
                         "execution_fingerprint": summary["execution_fingerprint"],
                         "prediction_horizon_s": float(h), "feature_transform": "identity",
                         "input_units": {"extracellular_concentration_mol_m3": "mol/m^3",
                                         "cell_amount_mol": "mol", "vmax_mol_s": "mol/s",
                                         "km_mol_m3": "mol/m^3", "time_s": "s", "dt_s": "s"},
                         "target_feature_order": ["cell_amount_mol"],
                         "baseline_plan": ["no_change", "training_mean_amount_increment"],
                         "limitations": ["Synthetic numerical labels only", "No transcriptomic conversion",
                                         "Cells sample a voxel; cell volume is not subtracted from extracellular volume",
                                         "One fixed uptake law; no growth, metabolism or biological cell identity"]},
        }
        summary["costs_seconds"]["persistence"] += time.perf_counter() - persistence_start
        validation_start = time.perf_counter()
        validated = validate_dataset(manifest, output)
        summary["dataset_sha256"] = dataset_digest(validated)
        summary["costs_seconds"]["validation"] += time.perf_counter() - validation_start
        persistence_start = time.perf_counter()
        _write(output / "manifest.json", validated)
        summary["costs_seconds"]["persistence"] += time.perf_counter() - persistence_start
        summary["status"] = "pass"
        summary["total_wall_seconds_before_final_report"] = time.perf_counter() - started
        summary["cost_accounting_scope"] = (
            "Measured generation, manifest validation and main artifact writes; total wall time also includes "
            "configuration loading/fingerprinting and bookkeeping inside prepare(). Imports, argument parsing, "
            "output-directory creation, interpreter startup and final report write are not measured; memory "
            "and disk bytes are not profiled. No amortized savings claim.")
        _write(output / "results.json", summary)
        return summary
    except Exception as error:
        summary["status"] = "failed"
        summary["error"] = f"{type(error).__name__}: {error}"
        summary["costs_seconds"]["failed_attempt"] = time.perf_counter() - started
        summary["failed_attempt_is_total_not_additive"] = True
        _write(output / "results.json", summary)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory; existing paths are rejected")
    parser.add_argument("--config", type=Path, help="Synthetic fixture JSON configuration")
    args = parser.parse_args()
    output = args.output or ROOT / "runs" / f"training_fixture_{uuid.uuid4().hex[:12]}"
    result = prepare(output, config_path=args.config)
    print(json.dumps({"status": result["status"], "samples": result["sample_count"],
                      "dataset_sha256": result["dataset_sha256"], "output": str(output.resolve()),
                      "biological_validation": False, "model_trained": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
