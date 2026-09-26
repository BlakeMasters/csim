#!/usr/bin/env python3
"""Analytical 3D diffusion studies. No external solver or biological data."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cellsim_v2.state import AmountField, World, total_amount
from cellsim_v2.transport import RectilinearGrid3D, diffusion_step

SPECIES = "synthetic_tracer"
D = 0.1
AMPLITUDE = 0.25


def _initial(n: int) -> tuple[RectilinearGrid3D, World, tuple[float, ...]]:
    grid = RectilinearGrid3D((1.0 / n,) * n, (1.0 / n,) * n, (1.0 / n,) * n)
    # Exact voxel AVERAGES of the separable cosine mode, not point samples.
    sinc = math.sin(math.pi / (2 * n)) / (math.pi / (2 * n))
    mode = tuple(AMPLITUDE * sinc**3 * math.prod(math.cos(math.pi * x) for x in grid.center_m(i))
                 for i in range(grid.voxel_count))
    field = AmountField.from_concentrations(SPECIES, tuple(1 + value for value in mode), grid.volumes_m3)
    return grid, World(fields={SPECIES: field}), mode


def _evolve(world: World, grid: RectilinearGrid3D, dt: float, steps: int) -> None:
    for _ in range(steps):
        diffusion_step(world, grid, SPECIES, D, dt).commit(world, frozenset({"fields", "ledger"}))


def _l2(a, b) -> float:
    return math.sqrt(math.fsum((x - y)**2 for x, y in zip(a, b)) / len(a))


def _orders(rows: list[dict], key: str) -> list[float | None]:
    return [math.log(left[key] / right[key], 2) if left[key] > 0 and right[key] > 0 else None
            for left, right in zip(rows, rows[1:])]


def run() -> dict:
    spatial = []
    for n in (4, 8, 16):
        grid, world, mode = _initial(n)
        initial = world.fields[SPECIES].concentrations_mol_m3
        h = 0.001  # Below the explicit positivity bound on all three meshes.
        _evolve(world, grid, h, 1)
        derivative = tuple((a - b) / h for a, b in
                           zip(world.fields[SPECIES].concentrations_mol_m3, initial))
        exact = tuple(-3 * math.pi**2 * D * value for value in mode)
        spatial.append({"n_per_axis": n, "dx_m": 1 / n, "probe_dt_s": h,
                        "derivative_l2_error_mol_m3_s": _l2(derivative, exact)})
    spatial_orders = _orders(spatial, "derivative_l2_error_mol_m3_s")

    temporal = []
    n, end = 4, 0.2
    discrete_decay = 12 * D * n**2 * math.sin(math.pi / (2 * n))**2
    for steps in (4, 8, 16, 32):
        grid, world, mode = _initial(n)
        initial_amount = total_amount(world, SPECIES)
        dt = end / steps
        _evolve(world, grid, dt, steps)
        exact = tuple(1 + value * math.exp(-discrete_decay * end) for value in mode)
        temporal.append({"steps": steps, "dt_s": dt,
                         "l2_error_mol_m3": _l2(world.fields[SPECIES].concentrations_mol_m3, exact),
                         "balance_error_mol": abs(total_amount(world, SPECIES) - initial_amount)})
    temporal_orders = _orders(temporal, "l2_error_mol_m3")

    trajectories = []
    end = 0.05
    for n in (4, 8, 16):
        grid, world, mode = _initial(n)
        initial_amount = total_amount(world, SPECIES)
        steps = math.ceil(end / (0.02 / (D * n**2)))
        dt = end / steps
        _evolve(world, grid, dt, steps)
        exact = tuple(1 + value * math.exp(-3 * math.pi**2 * D * end) for value in mode)
        trajectories.append({"n_per_axis": n, "voxel_count": grid.voxel_count,
                             "dx_m": 1 / n, "dt_s": dt, "steps": steps,
                             "l2_error_mol_m3": _l2(world.fields[SPECIES].concentrations_mol_m3, exact),
                             "balance_error_mol": abs(total_amount(world, SPECIES) - initial_amount)})
    trajectory_orders = _orders(trajectories, "l2_error_mol_m3")
    between = lambda orders, lo, hi: all(value is not None and lo < value < hi for value in orders)
    balance_limit = 1e-12
    passed = (between(spatial_orders, 1.7, 2.2) and between(temporal_orders, 0.9, 1.3)
              and between(trajectory_orders, 1.7, 2.3)
              and all(row["balance_error_mol"] < balance_limit for row in temporal + trajectories))
    return {
        "status": "pass" if passed else "fail", "biological_validation": False,
        "independent_external_solver_run": False,
        "configuration": {"equation": "dc/dt = D Laplacian(c)", "domain_m": [1, 1, 1],
                          "boundary": "no flux on all six faces", "diffusivity_m2_s": D,
                          "initial": "voxel average of 1 + 0.25 cos(pi*x) cos(pi*y) cos(pi*z)",
                          "parameter_provenance": "synthetic engineering example", "integrator": "explicit Euler"},
        "engineering_limits": {"spatial_order_open_interval": [1.7, 2.2],
                               "temporal_order_open_interval": [0.9, 1.3],
                               "joint_trajectory_order_open_interval": [1.7, 2.3],
                               "absolute_balance_mol": balance_limit},
        "spatial_operator": {"reference": "continuous derivative of exact voxel-average cosine mode",
                             "rows": spatial, "observed_orders": spatial_orders},
        "temporal": {"reference": "exact semidiscrete cosine eigenmode on fixed 4x4x4 grid",
                     "end_time_s": 0.2, "discrete_decay_per_s": discrete_decay,
                     "rows": temporal, "observed_orders": temporal_orders},
        "continuum_trajectory": {"reference": "analytic continuous PDE voxel averages; joint dx/dt refinement",
                                 "end_time_s": 0.05, "rows": trajectories,
                                 "observed_orders": trajectory_orders},
        "limitations": ["Smooth uniform-grid analytic modes only; no proof for arbitrary geometries",
                        "Unequal-volume invariants and uptake are covered separately by targeted tests",
                        "No stiff reaction/splitting convergence or independent-engine comparison"],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result["status"] == "pass" else 1)
