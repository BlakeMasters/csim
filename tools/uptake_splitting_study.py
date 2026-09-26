#!/usr/bin/env python3
"""Bounded synthetic 3D diffusion/uptake Lie-splitting study.

The control integrates the same fixed-grid semidiscrete equations with a
separately coded RK4 right-hand side. It is not an external solver comparison,
spatial refinement study, stiff-reaction study, or biological calibration.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cellsim_v2.scheduler import Process, WindowStepper
from cellsim_v2.state import AmountField, Cell, World, total_amount
from cellsim_v2.transport import (
    CellUptake, RectilinearGrid3D, diffusion_step,
    diffusion_timestep_limit_s, saturable_uptake_step,
)

SPECIES = "synthetic_tracer"
DX_M = 0.5
VOLUME_M3 = DX_M**3
DIFFUSIVITY_M2_S = 0.1
VMAX_MOL_S = 0.1
KM_MOL_M3 = 0.5
END_S = Fraction(1)
STEPS = (4, 8, 16, 32)
CONTROL_STEPS = (4096, 8192)
QOI_ABS_TOL_MOL = 5e-4
BALANCE_ABS_TOL_MOL = 1e-12
CONTROL_SELF_TOL_MOL = 1e-10


def _grid() -> RectilinearGrid3D:
    return RectilinearGrid3D((DX_M, DX_M), (DX_M, DX_M), (DX_M, DX_M))


def _world(grid: RectilinearGrid3D) -> World:
    field = AmountField.from_concentrations(
        SPECIES, (1.2,) + (1.0,) * (grid.voxel_count - 1), grid.volumes_m3,
    )
    return World(
        cells={"cell_0": Cell("cell_0", grid.center_m(0), 1e-3)},
        fields={SPECIES: field},
    )


def _stepper(grid: RectilinearGrid3D, window: Fraction, order: str,
             uptake: CellUptake, process_step: Fraction | None = None) -> WindowStepper:
    process_step = process_step or window
    diffusion = Process(
        "diffusion", process_step, frozenset({"fields"}),
        lambda world, dt: diffusion_step(world, grid, SPECIES, DIFFUSIVITY_M2_S, dt),
    )
    transfer = Process(
        "uptake", process_step, frozenset({"cells", "fields"}),
        lambda world, dt: saturable_uptake_step(world, grid, SPECIES, (uptake,), dt),
    )
    processes = (diffusion, transfer) if order == "diffusion_then_uptake" else (transfer, diffusion)
    return WindowStepper(list(processes), window)


def _ode_rhs(state: tuple[float, ...]) -> tuple[float, ...]:
    """Independent fixed-grid concentration ODE, x varying fastest.

    A 2x2x2 no-flux cube has exactly one neighbor per axis per voxel.
    XOR masks 1, 2, 4 select those three neighbors independently of the
    reference transport kernel's face list or Update machinery.
    """
    concentrations = state[:8]
    rate = VMAX_MOL_S * concentrations[0] / (KM_MOL_M3 + concentrations[0])
    scale = DIFFUSIVITY_M2_S / DX_M**2
    derivatives = [scale * math.fsum(
        concentrations[i ^ mask] - concentrations[i] for mask in (1, 2, 4)
    ) for i in range(8)]
    derivatives[0] -= rate / VOLUME_M3
    return (*derivatives, rate)


def _rk4_control(steps: int) -> tuple[float, ...]:
    dt = float(END_S) / steps
    state = (1.2,) + (1.0,) * 7 + (0.0,)
    for _ in range(steps):
        k1 = _ode_rhs(state)
        k2 = _ode_rhs(tuple(x + dt * v / 2 for x, v in zip(state, k1)))
        k3 = _ode_rhs(tuple(x + dt * v / 2 for x, v in zip(state, k2)))
        k4 = _ode_rhs(tuple(x + dt * v for x, v in zip(state, k3)))
        state = tuple(x + dt * (a + 2*b + 2*c + d) / 6
                      for x, a, b, c, d in zip(state, k1, k2, k3, k4))
    return state


def _observed_orders(rows: list[dict]) -> list[float | None]:
    errors = [row["absolute_qoi_error_mol"] for row in rows]
    return [math.log(a / b, 2) if a > 0 and b > 0 else None
            for a, b in zip(errors, errors[1:])]


def _source_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    paths = (
        "src/cellsim_v2/state.py",
        "src/cellsim_v2/scheduler.py",
        "src/cellsim_v2/transport.py",
        "tools/uptake_splitting_study.py",
        "tests/test_uptake_splitting_study.py",
    )
    return {relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
            for relative in paths}


def _trial(grid: RectilinearGrid3D, order: str, reference_mol: float,
           windows: int, process_step: Fraction) -> dict:
    world = _world(grid)
    before = total_amount(world, SPECIES)
    window = END_S / windows
    _stepper(grid, window, order, CellUptake("cell_0", VMAX_MOL_S, KM_MOL_M3),
             process_step).advance(world, END_S)
    qoi = world.cells["cell_0"].amounts_mol[SPECIES]
    field_amounts = world.fields[SPECIES].amounts_mol
    return {
        "windows": windows,
        "window_s": float(window),
        "process_step_s": float(process_step),
        "qoi_mol": qoi,
        "absolute_qoi_error_mol": abs(qoi - reference_mol),
        "absolute_balance_error_mol": abs(total_amount(world, SPECIES) - before),
        "minimum_amount_mol": min(*field_amounts, qoi),
        "completed_time_s": float(world.time_s),
        "accepted_windows": world.step,
    }


def _summarize(rows: list[dict]) -> dict:
    orders = _observed_orders(rows)
    eligible = [row["window_s"] for row in rows
                if row["absolute_qoi_error_mol"] <= QOI_ABS_TOL_MOL]
    return {
        "rows": rows,
        "observed_qoi_error_orders": orders,
        "coarsest_observed_window_meeting_qoi_tolerance_s": max(eligible) if eligible else None,
    }


def _refinement(grid: RectilinearGrid3D, order: str, reference_mol: float) -> dict:
    return _summarize([
        _trial(grid, order, reference_mol, windows, END_S / windows)
        for windows in STEPS
    ])


def failure_injection() -> dict:
    """Verify the tentative diffusion update is discarded after uptake overdraw."""
    grid = _grid()
    world = _world(grid)
    world.fields[SPECIES] = AmountField.from_concentrations(
        SPECIES, (1.0,) + (0.0,) * 7, grid.volumes_m3,
    )
    original = world.clone()
    probe = world.clone()
    diffusion_step(probe, grid, SPECIES, DIFFUSIVITY_M2_S, 0.25).commit(
        probe, frozenset({"fields"}),
    )
    error = ""
    try:
        _stepper(grid, Fraction(1, 4), "diffusion_then_uptake",
                 CellUptake("cell_0", 100.0, KM_MOL_M3)).advance(world, Fraction(1, 4))
    except ValueError as exc:
        error = str(exc)
    return {
        "rejected": "demand" in error,
        "error": error,
        "diffusion_would_change_field": probe.fields[SPECIES] != original.fields[SPECIES],
        "world_unchanged": world == original,
    }


def run() -> dict:
    grid = _grid()
    coarse_control = _rk4_control(CONTROL_STEPS[0])
    fine_control = _rk4_control(CONTROL_STEPS[1])
    control_qoi = fine_control[-1]
    control_balance_error = abs(VOLUME_M3 * math.fsum(fine_control[:8]) + control_qoi - 1.025)
    orderings = ("diffusion_then_uptake", "uptake_then_diffusion")
    refinements = {order: _refinement(grid, order, control_qoi) for order in orderings}
    fixed_process_step = Fraction(1, 128)
    window_only = {order: _summarize([
        _trial(grid, order, control_qoi, windows, fixed_process_step)
        for windows in STEPS
    ]) for order in orderings}
    fixed_window_count = 4
    process_only = {order: {"rows": [
        _trial(grid, order, control_qoi, fixed_window_count, Fraction(1, n))
        for n in (4, 8, 16, 32, 64, 128)
    ]} for order in orderings}
    for study in process_only.values():
        qualifying = [row["process_step_s"] for row in study["rows"]
                      if row["absolute_qoi_error_mol"] <= QOI_ABS_TOL_MOL]
        study["coarsest_observed_process_step_meeting_qoi_tolerance_s"] = (
            max(qualifying) if qualifying else None
        )
    failure = failure_injection()
    row_checks = []
    for study in refinements.values():
        rows = study["rows"]
        errors = [row["absolute_qoi_error_mol"] for row in rows]
        row_checks.append(
            all(a > b for a, b in zip(errors, errors[1:]))
            and errors[-1] < errors[0] / 4
            and errors[-1] <= QOI_ABS_TOL_MOL
            and all(row["absolute_balance_error_mol"] < BALANCE_ABS_TOL_MOL
                    and row["minimum_amount_mol"] >= 0
                    and row["accepted_windows"] == row["windows"]
                    and row["completed_time_s"] == float(END_S) for row in rows)
        )
    control_difference = abs(coarse_control[-1] - control_qoi)
    isolated_checks = all(
        study["rows"][-1]["absolute_qoi_error_mol"] < study["rows"][0]["absolute_qoi_error_mol"]
        and all(row["absolute_balance_error_mol"] < BALANCE_ABS_TOL_MOL
                and row["minimum_amount_mol"] >= 0 for row in study["rows"])
        and all(row["absolute_balance_error_mol"] < BALANCE_ABS_TOL_MOL
                and row["minimum_amount_mol"] >= 0 for row in process_only[order]["rows"])
        for order, study in window_only.items()
    )
    passed = (all(row_checks)
              and isolated_checks
              and control_difference < CONTROL_SELF_TOL_MOL
              and control_balance_error < BALANCE_ABS_TOL_MOL
              and failure["rejected"] and failure["diffusion_would_change_field"]
              and failure["world_unchanged"])
    return {
        "status": "pass" if passed else "fail",
        "biological_validation": False,
        "independent_external_solver_run": False,
        "stiff_reaction_evaluated": False,
        "execution": {
            "python": sys.version,
            "platform": platform.platform(),
            "device": "CPU",
            "source_test_tool_sha256_by_file": _source_hashes(),
        },
        "configuration": {
            "equations": [
                "dc_i/dt = (D/dx^2) sum_neighbors(c_j-c_i) - delta_i0*vmax*c_0/(Km+c_0)/V",
                "dn_cell/dt = vmax*c_0/(Km+c_0)",
            ],
            "grid_shape": list(grid.shape),
            "domain_m": [1.0, 1.0, 1.0],
            "voxel_width_m": DX_M,
            "voxel_volume_m3": VOLUME_M3,
            "boundary": "no flux on all six faces",
            "initial_field_concentration_mol_m3": [1.2] + [1.0] * 7,
            "initial_cell_amount_mol": 0.0,
            "diffusivity_m2_s": DIFFUSIVITY_M2_S,
            "vmax_mol_s": VMAX_MOL_S,
            "km_mol_m3": KM_MOL_M3,
            "end_time_s": float(END_S),
            "qoi": "cell accumulated tracer amount at T, mol",
            "integration": "ordered Lie windows; the joint sweep uses one explicit Euler step per process per window; isolated sweeps subcycle",
            "parameter_provenance": "synthetic engineering values selected for this numerical study",
        },
        "engineering_limits": {
            "qoi_absolute_error_mol": QOI_ABS_TOL_MOL,
            "closed_amount_balance_absolute_mol": BALANCE_ABS_TOL_MOL,
            "rk4_step_halving_qoi_difference_mol": CONTROL_SELF_TOL_MOL,
            "required_qoi_error_reduction_finest_vs_coarsest": 4,
        },
        "explicit_diffusion_timestep_limit_s": diffusion_timestep_limit_s(grid, DIFFUSIVITY_M2_S),
        "control": {
            "method": "separately coded RK4 integration of the same fixed-grid semidiscrete ODE",
            "steps": list(CONTROL_STEPS),
            "qoi_mol": control_qoi,
            "rk4_step_halving_qoi_difference_mol": control_difference,
            "absolute_balance_error_mol": control_balance_error,
            "minimum_concentration_mol_m3": min(fine_control[:8]),
        },
        "refinement": refinements,
        "fixed_process_step_window_refinement": {
            "process_step_s": float(fixed_process_step),
            "orderings": window_only,
        },
        "fixed_window_process_step_refinement": {
            "window_s": float(END_S / fixed_window_count),
            "orderings": process_only,
        },
        "failure_injection": failure,
        "limitations": [
            "One synthetic uniform 2x2x2 grid, one cell and one law; no spatial refinement",
            "RK4 control is separately coded but not an independent external solver",
            "Only nonstiff uptake in a closed box; no reaction network or boundary source",
            "Observed window tolerance applies only to this configuration and QoI",
            "Process-step-only QoI error can be nonmonotonic at a fixed window due to error cancellation",
            "No measured biological parameters, calibration, held-out data, or device scaling",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        help="Create this JSON file exclusively; parent directories are created")
    args = parser.parse_args()
    result = run()
    payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
        print(json.dumps({"status": result["status"], "output": str(args.output.resolve()),
                          "control_qoi_mol": result["control"]["qoi_mol"]}, indent=2))
    else:
        print(payload, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
